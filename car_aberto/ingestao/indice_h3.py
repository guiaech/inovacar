"""Indice H3 dos imoveis.

Cobertura de cada poligono em res 7 com containment OVERLAPPING (toda celula que toca o
poligono entra, sem falso negativo na borda), compactada com compact_cells. Tabela separada
(id_registro, cod_imovel, h3). Como a tabela e compactada, a consulta por ponto procura a
celula res 7 do ponto e todos os seus ancestrais ate res 0, depois aplica ST_Intersects exato.

As coordenadas SIRGAS 2000 (EPSG:4674) sao usadas direto como lat/lng do H3. A diferenca
para WGS 84 e submetrica e o filtro final e sempre geometrico exato.
"""

from __future__ import annotations

import argparse
import logging
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import shapely

from car_aberto import config

log = logging.getLogger(__name__)


def cobertura_compacta(geom, res: int = config.H3_RES_COBERTURA) -> list[int]:
    if geom is None or geom.is_empty:
        return []
    forma = h3.geo_to_h3shape(geom)
    celulas = h3.h3shape_to_cells_experimental(forma, res, contain="overlap")
    return [h3.str_to_int(c) for c in h3.compact_cells(celulas)]


def _lote(wkbs: list[bytes]) -> list[list[int]]:
    return [cobertura_compacta(g) for g in shapely.from_wkb(wkbs)]


def celulas_do_ponto(lon: float, lat: float, res: int = config.H3_RES_COBERTURA) -> list[int]:
    """Celula do ponto em `res` e todos os ancestrais ate res 0."""
    c = h3.latlng_to_cell(lat, lon, res)
    return [h3.str_to_int(c)] + [h3.str_to_int(h3.cell_to_parent(c, r)) for r in range(res)]


def centroide_r9(gdf: gpd.GeoDataFrame) -> pd.Series:
    c = shapely.centroid(gdf.geometry.values)
    xs, ys = shapely.get_x(c), shapely.get_y(c)
    out = [
        None if np.isnan(x) else h3.latlng_to_cell(y, x, config.H3_RES_CENTROIDE)
        for x, y in zip(xs, ys, strict=True)
    ]
    return pd.Series(out, index=gdf.index, dtype="string")


def montar_indice(gdf: gpd.GeoDataFrame, processos: int = 1, lote: int = 2_000) -> pd.DataFrame:
    wkbs = list(shapely.to_wkb(gdf.geometry.values))
    pedacos = [wkbs[i : i + lote] for i in range(0, len(wkbs), lote)]
    if processos > 1:
        with ProcessPoolExecutor(processos) as ex:
            resultados = [c for r in ex.map(_lote, pedacos) for c in r]
    else:
        resultados = [c for p in pedacos for c in _lote(p)]
    n = np.array([len(r) for r in resultados])
    df = pd.DataFrame(
        {
            "id_registro": np.repeat(gdf["id_registro"].to_numpy(), n),
            "cod_imovel": np.repeat(gdf["cod_imovel"].to_numpy(), n),
            "h3": np.fromiter((c for r in resultados for c in r), dtype=np.uint64, count=n.sum()),
        }
    )
    imax = int(n.argmax()) if len(n) else 0
    log.info(
        "H3 res %d: %d linhas, max %d celulas por imovel (%s), mediana %.0f, sem celula %d",
        config.H3_RES_COBERTURA,
        len(df),
        int(n.max()) if len(n) else 0,
        gdf["cod_imovel"].iloc[imax] if len(n) else "-",
        float(np.median(n)) if len(n) else 0,
        int((n == 0).sum()),
    )
    return df.sort_values("h3", kind="stable").reset_index(drop=True)


def gravar_indice(df: pd.DataFrame, destino: Path) -> Path:
    destino.mkdir(parents=True, exist_ok=True)
    arq = destino / "part-0.parquet"
    pq.write_table(
        pa.Table.from_pandas(df, preserve_index=False),
        arq,
        compression=config.COMPRESSAO,
        row_group_size=config.ROW_GROUP_H3,
    )
    return arq


def dir_indice(uf: str, snapshot: str, base: Path | None = None) -> Path:
    return (base or config.DIR_H3) / f"uf={uf.lower()}" / f"snapshot={snapshot}"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--uf", required=True)
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--processos", type=int, default=4)
    a = ap.parse_args()
    from car_aberto.ingestao.para_geoparquet import dir_saida

    src = dir_saida(a.uf, a.snapshot) / "part-0.parquet"
    gdf = gpd.read_parquet(src, columns=["id_registro", "cod_imovel", "geometry"])
    df = montar_indice(gdf, processos=a.processos)
    print(gravar_indice(df, dir_indice(a.uf, a.snapshot)))


if __name__ == "__main__":
    main()
