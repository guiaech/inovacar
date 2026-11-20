"""Le a camada AREA_IMOVEL de um snapshot bruto do Sicar e devolve um GeoDataFrame limpo.

Passos: encoding pelo .cpg (latin1 se ausente), esquema conferido, colunas em minusculas,
datas dd/mm/aaaa para date, cod_municipio_ibge derivado de cod_imovel, make_valid com contagem,
geometria em MultiPolygon e EPSG:4674, area em ha no Albers IBGE e divergencia contra num_area.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from pyproj import CRS
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon

from car_aberto import config

log = logging.getLogger(__name__)


class EsquemaInvalido(ValueError):
    """O shapefile nao tem as colunas esperadas."""


def localizar_shp(dir_camada: Path) -> Path:
    shps = sorted(dir_camada.glob("*.shp"))
    if len(shps) != 1:
        raise FileNotFoundError(f"esperado 1 .shp em {dir_camada}, achei {len(shps)}")
    return shps[0]


def detectar_encoding(shp: Path) -> str:
    cpg = shp.with_suffix(".cpg")
    if cpg.exists():
        valor = cpg.read_text(encoding="ascii", errors="ignore").strip()
        if valor:
            return valor
    return config.ENCODING_PADRAO


def conferir_esquema(colunas: list[str], esperadas: list[str] | None = None) -> None:
    esperadas = esperadas or config.COLUNAS_AREA_IMOVEL
    faltando = [c for c in esperadas if c not in colunas]
    if faltando:
        raise EsquemaInvalido(f"colunas ausentes: {faltando}")


def para_data(serie: pd.Series) -> tuple[pd.Series, int]:
    """Converte dd/mm/aaaa para date. Vazio vira nulo. Devolve tambem as falhas de conversao."""
    texto = serie.astype("string").str.strip().replace("", pd.NA)
    convertida = pd.to_datetime(texto, format=config.FORMATO_DATA, errors="coerce")
    falhas = int((texto.notna() & convertida.isna()).sum())
    return convertida.dt.date.astype(object).where(convertida.notna(), None), falhas


def _poligonos(geom) -> list[Polygon]:
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, (MultiPolygon, GeometryCollection)):
        return [p for parte in geom.geoms for p in _poligonos(parte)]
    return []


def para_multipolygon(geom):
    """Normaliza qualquer geometria para MultiPolygon. Partes nao poligonais sao descartadas."""
    if isinstance(geom, MultiPolygon):
        return geom
    polis = _poligonos(geom)
    return MultiPolygon(polis) if polis else None


def corrigir_geometrias(geoms: gpd.GeoSeries) -> tuple[gpd.GeoSeries, dict]:
    arr = shapely.force_2d(geoms.values)
    nulas = shapely.is_missing(arr) | shapely.is_empty(arr)
    invalidas = ~nulas & ~shapely.is_valid(arr)
    corrigidas = arr.copy()
    if invalidas.any():
        corrigidas[invalidas] = shapely.make_valid(
            arr[invalidas], method="structure", keep_collapsed=False
        )
    multi = np.array([para_multipolygon(g) for g in corrigidas], dtype=object)
    perdidas = int((~nulas & pd.isna(multi)).sum())
    stats = {
        "geometrias_nulas_ou_vazias": int(nulas.sum()),
        "geometrias_invalidas_corrigidas": int(invalidas.sum()),
        "geometrias_perdidas_apos_correcao": perdidas,
        "ainda_invalidas": int((~pd.isna(multi) & ~shapely.is_valid(multi)).sum()),
    }
    return gpd.GeoSeries(multi, index=geoms.index, crs=geoms.crs), stats


def divergencia_area(area_ha: pd.Series, num_area: pd.Series) -> dict:
    ok = (num_area > 0) & area_ha.notna()
    rel = ((area_ha[ok] - num_area[ok]).abs() / num_area[ok]).astype(float)
    return {
        "imoveis_comparados": int(ok.sum()),
        "divergencia_mediana_pct": round(float(rel.median() * 100), 4),
        "divergencia_p95_pct": round(float(rel.quantile(0.95) * 100), 4),
        "pct_imoveis_acima_1pct": round(float((rel > 0.01).mean() * 100), 3),
        "pct_imoveis_acima_5pct": round(float((rel > 0.05).mean() * 100), 3),
    }


def gerar_id_registro(gdf: gpd.GeoDataFrame) -> pd.Series:
    """Chave da linha. cod_imovel se repete na base publica (versao ativa e versao cancelada
    por duplicidade), entao a chave e um hash de cod_imovel, situacao, area declarada e geometria.
    Linhas identicas recebem sufixo ordinal. Mesma linha em snapshots diferentes gera o mesmo id."""
    wkb = shapely.to_wkb(gdf.geometry.values, hex=False)
    base = (
        gdf["cod_imovel"].fillna("")
        + "|"
        + gdf["ind_status"].fillna("")
        + "|"
        + gdf["des_condic"].fillna("")
        + "|"
        + gdf["num_area"].round(4).astype(str)
    )
    ids = [
        hashlib.sha1(b.encode() + b"|" + (w or b"")).hexdigest()[:16]
        for b, w in zip(base, wkb, strict=True)
    ]
    s = pd.Series(ids, index=gdf.index, dtype="string")
    ordem = s.groupby(s).cumcount()
    return s.where(ordem == 0, s + "-" + ordem.astype(str))


def carregar_camada(dir_camada: Path, uf: str) -> tuple[gpd.GeoDataFrame, dict]:
    shp = localizar_shp(dir_camada)
    encoding = detectar_encoding(shp)
    gdf = gpd.read_file(shp, encoding=encoding, engine="pyogrio")
    gdf.columns = [c if c == "geometry" else c.lower() for c in gdf.columns]
    conferir_esquema(list(gdf.columns))
    rel: dict = {
        "arquivo": shp.name,
        "encoding": encoding,
        "cpg_presente": shp.with_suffix(".cpg").exists(),
        "imoveis_lidos": len(gdf),
    }

    crs_lido = gdf.crs
    if crs_lido is None:
        log.warning("sem .prj, assumindo %s", config.CRS_BASE)
        gdf = gdf.set_crs(config.CRS_BASE)
    elif not CRS(crs_lido).equals(CRS(config.CRS_BASE)):
        raise ValueError(f"CRS inesperado {crs_lido}; o Sicar publica em {config.CRS_BASE}")
    else:
        gdf = gdf.set_crs(config.CRS_BASE, allow_override=True)

    for c in gdf.columns:
        if c != "geometry" and gdf[c].dtype == object:
            gdf[c] = gdf[c].astype("string").str.strip()
    for c in ("mod_fiscal", "num_area"):
        gdf[c] = pd.to_numeric(gdf[c], errors="coerce").astype("float64")
    rel["datas_invalidas"] = {}
    for c in config.COLUNAS_DATA:
        gdf[c], falhas = para_data(gdf[c])
        rel["datas_invalidas"][c] = falhas
        rel.setdefault("datas_nulas", {})[c] = int(gdf[c].isna().sum())

    partes = gdf["cod_imovel"].str.split("-", expand=True)
    gdf["cod_municipio_ibge"] = partes[1].astype("string")
    prefixo = config.COD_IBGE_UF.get(uf.lower())
    cod_ok = gdf["cod_municipio_ibge"].str.fullmatch(r"\d{7}").fillna(False)
    if prefixo:
        cod_ok &= gdf["cod_municipio_ibge"].str.startswith(prefixo).fillna(False)
    rel["cod_municipio_ibge_fora_da_uf"] = gdf.loc[~cod_ok, "cod_imovel"].tolist()
    repetidos = gdf["cod_imovel"].duplicated(keep=False)
    rel["cod_imovel_repetidos"] = {
        "codigos": int(gdf.loc[repetidos, "cod_imovel"].nunique()),
        "linhas": int(repetidos.sum()),
    }

    gdf["geometry"], rel["geometria"] = corrigir_geometrias(gdf.geometry)
    gdf = gdf.set_geometry("geometry", crs=config.CRS_BASE)

    gdf["area_ha"] = gdf.geometry.to_crs(config.CRS_AREA).area / 10_000
    rel["area"] = divergencia_area(gdf["area_ha"], gdf["num_area"])
    for c in ("ind_status", "ind_tipo", "des_condic"):
        rel.setdefault("valores", {})[c] = gdf[c].value_counts(dropna=False).to_dict()

    gdf["id_registro"] = gerar_id_registro(gdf)

    ordem = [
        "id_registro",
        *config.COLUNAS_AREA_IMOVEL,
        "cod_municipio_ibge",
        "area_ha",
        "geometry",
    ]
    return gdf[ordem], rel


def carregar_uf(
    uf: str, snapshot: str, dir_raw: Path | None = None
) -> tuple[gpd.GeoDataFrame, dict]:
    dir_camada = (dir_raw or config.DIR_RAW) / uf.lower() / snapshot / "area_imovel"
    gdf, rel = carregar_camada(dir_camada, uf)
    rel = {"uf": uf.lower(), "snapshot": snapshot, **rel}
    log.info(
        "%s %s: %d imoveis, %d geometrias corrigidas, divergencia mediana de area %.3f%%",
        uf,
        snapshot,
        rel["imoveis_lidos"],
        rel["geometria"]["geometrias_invalidas_corrigidas"],
        rel["area"]["divergencia_mediana_pct"],
    )
    return gdf, rel


def salvar_relatorio(rel: dict, nome: str) -> Path:
    config.DIR_RELATORIOS.mkdir(parents=True, exist_ok=True)
    p = config.DIR_RELATORIOS / nome
    p.write_text(json.dumps(rel, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return p


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--uf", required=True)
    ap.add_argument("--snapshot", required=True)
    a = ap.parse_args()
    _, rel = carregar_uf(a.uf, a.snapshot)
    print(salvar_relatorio(rel, f"ingestao_{a.uf.lower()}_{a.snapshot}.json"))


if __name__ == "__main__":
    main()
