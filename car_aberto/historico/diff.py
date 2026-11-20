"""Compara dois snapshots de uma UF e gera a tabela de eventos do ciclo do cadastro.

O snapshot diz O QUE mudou; dat_atuali do registro novo diz QUANDO, se cair no intervalo.

Pareamento de registros:
1. mesmo id_registro nos dois snapshots: registro inalterado (so dat_atuali pode ter mudado,
   porque ela nao entra no id);
2. sobras pareadas por cod_imovel. Num codigo com mais de um registro de cada lado, o par e
   escolhido pela maior semelhanca (mesma situacao, mesmo des_condic, maior IoU); no empate,
   o registro nao cancelado.
Sobras sem par viram novo/removido. escopo='imovel' quando o cod_imovel inteiro aparece ou
some; escopo='registro' quando o codigo continua existindo mas uma linha dele aparece ou some.

Tipos de evento: novo, removido, mudanca_ind_status, mudanca_des_condic, mudanca_area
(num_area variou mais de 1%), mudanca_geometria (IoU abaixo de 0,98), mudanca_dat_atuali.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import shapely

from car_aberto import config

log = logging.getLogger(__name__)

LIMIAR_AREA = 0.01
LIMIAR_IOU = 0.98
COLUNAS = [
    "id_registro",
    "cod_imovel",
    "num_area",
    "ind_status",
    "ind_tipo",
    "des_condic",
    "municipio",
    "cod_municipio_ibge",
    "dat_atuali",
    "geometry",
]
ESQUEMA = pa.schema(
    [
        ("tipo_evento", pa.string()),
        ("escopo", pa.string()),
        ("cod_imovel", pa.string()),
        ("id_registro_anterior", pa.string()),
        ("id_registro_atual", pa.string()),
        ("valor_anterior", pa.string()),
        ("valor_atual", pa.string()),
        ("snapshot_anterior", pa.string()),
        ("snapshot_atual", pa.string()),
        ("data_provavel", pa.date32()),
        ("fonte_data", pa.string()),
        ("municipio", pa.string()),
        ("cod_municipio_ibge", pa.string()),
        ("ind_tipo", pa.string()),
        ("ind_status_atual", pa.string()),
    ]
)


def iou(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """IoU vetorizado em Albers. Geometrias identicas dao 1 sem calculo."""
    out = np.ones(len(a))
    dif = ~shapely.equals_exact(a, b, tolerance=0)
    if dif.any():
        from pyproj import Transformer

        t = Transformer.from_crs(config.CRS_BASE, config.CRS_AREA, always_xy=True)
        pa_, pb = (
            shapely.transform(g[dif], lambda c: np.column_stack(t.transform(c[:, 0], c[:, 1])))
            for g in (a, b)
        )
        inter = shapely.area(shapely.intersection(pa_, pb))
        uniao = shapely.area(pa_) + shapely.area(pb) - inter
        out[dif] = np.where(uniao > 0, inter / np.where(uniao > 0, uniao, 1), 0)
    return out


def _parear_sobras(a: pd.DataFrame, b: pd.DataFrame) -> list[tuple[int, int]]:
    """Pares (indice em a, indice em b) por cod_imovel; escolha gulosa por semelhanca."""
    pares: list[tuple[int, int]] = []
    comuns = set(a["cod_imovel"]) & set(b["cod_imovel"])
    ga = a[a["cod_imovel"].isin(comuns)].groupby("cod_imovel").groups
    gb = b[b["cod_imovel"].isin(comuns)].groupby("cod_imovel").groups
    for cod in comuns:
        ia, ib = list(ga[cod]), list(gb[cod])
        if len(ia) == 1 and len(ib) == 1:
            pares.append((ia[0], ib[0]))
            continue
        ra, rb = a.loc[ia], b.loc[ib]
        cand = []
        for i, x in ra.iterrows():
            for j, y in rb.iterrows():
                geo = iou(np.array([x.geometry]), np.array([y.geometry]))[0]
                # desempate: prefere o registro nao cancelado (a copia CA e a duplicata)
                s = (
                    2 * (x.ind_status == y.ind_status)
                    + (x.des_condic == y.des_condic)
                    + geo
                    + 0.1 * (y.ind_status != "CA")
                )
                cand.append((s, i, j))
        usados_a, usados_b = set(), set()
        for _, i, j in sorted(cand, key=lambda c: -c[0]):
            if i not in usados_a and j not in usados_b:
                pares.append((i, j))
                usados_a.add(i)
                usados_b.add(j)
    return pares


def _data_mudou(a, b) -> bool:
    """Compara datas tratando nulo (None, NaT, NaN) como igual a nulo."""
    na, nb = a is None or pd.isna(a), b is None or pd.isna(b)
    if na or nb:
        return na != nb
    return pd.Timestamp(a).date() != pd.Timestamp(b).date()


def _data_provavel(dat_atuali, inicio: dt.date, fim: dt.date):
    if dat_atuali is None or pd.isna(dat_atuali):
        return None
    d = pd.Timestamp(dat_atuali).date()
    return d if inicio < d <= fim else None


def comparar(
    ant: gpd.GeoDataFrame, atu: gpd.GeoDataFrame, snap_ant: str, snap_atu: str
) -> pd.DataFrame:
    ant = ant[COLUNAS].reset_index(drop=True)
    atu = atu[COLUNAS].reset_index(drop=True)
    inicio, fim = dt.date.fromisoformat(snap_ant), dt.date.fromisoformat(snap_atu)
    eventos: list[dict] = []

    def ev(tipo, escopo, x, y, va=None, vb=None):
        ref = y if y is not None else x
        data = _data_provavel(y["dat_atuali"], inicio, fim) if y is not None else None
        eventos.append(
            {
                "tipo_evento": tipo,
                "escopo": escopo,
                "cod_imovel": ref["cod_imovel"],
                "id_registro_anterior": None if x is None else x["id_registro"],
                "id_registro_atual": None if y is None else y["id_registro"],
                "valor_anterior": None if va is None else str(va),
                "valor_atual": None if vb is None else str(vb),
                "snapshot_anterior": snap_ant,
                "snapshot_atual": snap_atu,
                "data_provavel": data,
                "fonte_data": "dat_atuali" if data else None,
                "municipio": ref["municipio"],
                "cod_municipio_ibge": ref["cod_municipio_ibge"],
                "ind_tipo": ref["ind_tipo"],
                "ind_status_atual": None if y is None else y["ind_status"],
            }
        )

    # 1. mesmo id_registro
    m = ant.reset_index().merge(atu.reset_index(), on="id_registro", suffixes=("_a", "_b"))
    iguais_a, iguais_b = set(m["index_a"]), set(m["index_b"])
    mudou = [_data_mudou(a, b) for a, b in zip(m["dat_atuali_a"], m["dat_atuali_b"], strict=True)]
    mud = m[np.array(mudou, dtype=bool)]
    for ia, ib in zip(mud["index_a"], mud["index_b"], strict=True):
        x, y = ant.loc[ia], atu.loc[ib]
        ev("mudanca_dat_atuali", "registro", x, y, x["dat_atuali"], y["dat_atuali"])

    # 2. sobras pareadas por cod_imovel
    sa = ant.drop(index=list(iguais_a))
    sb = atu.drop(index=list(iguais_b))
    pares = _parear_sobras(sa, sb)
    if pares:
        ia, ib = map(list, zip(*pares, strict=True))
        geo = iou(ant.loc[ia, "geometry"].to_numpy(), atu.loc[ib, "geometry"].to_numpy())
        for k, (i, j) in enumerate(pares):
            x, y = ant.loc[i], atu.loc[j]
            if x["ind_status"] != y["ind_status"]:
                ev("mudanca_ind_status", "registro", x, y, x["ind_status"], y["ind_status"])
            if x["des_condic"] != y["des_condic"]:
                ev("mudanca_des_condic", "registro", x, y, x["des_condic"], y["des_condic"])
            na, nb = x["num_area"], y["num_area"]
            base = max(abs(na), 1e-9)
            if abs(nb - na) / base > LIMIAR_AREA:
                ev("mudanca_area", "registro", x, y, round(na, 4), round(nb, 4))
            if geo[k] < LIMIAR_IOU:
                ev("mudanca_geometria", "registro", x, y, None, round(float(geo[k]), 4))
            if _data_mudou(x["dat_atuali"], y["dat_atuali"]):
                ev("mudanca_dat_atuali", "registro", x, y, x["dat_atuali"], y["dat_atuali"])

    # 3. sem par
    pa_set = {i for i, _ in pares}
    pb_set = {j for _, j in pares}
    cods_ant, cods_atu = set(ant["cod_imovel"]), set(atu["cod_imovel"])
    for i in sa.index.difference(list(pa_set)):
        x = ant.loc[i]
        escopo = "registro" if x["cod_imovel"] in cods_atu else "imovel"
        ev("removido", escopo, x, None, x["ind_status"], None)
    for j in sb.index.difference(list(pb_set)):
        y = atu.loc[j]
        escopo = "registro" if y["cod_imovel"] in cods_ant else "imovel"
        ev("novo", escopo, None, y, None, y["ind_status"])

    df = pd.DataFrame(eventos, columns=ESQUEMA.names)
    log.info(
        "%s -> %s: %d eventos %s",
        snap_ant,
        snap_atu,
        len(df),
        df["tipo_evento"].value_counts().to_dict(),
    )
    return df.sort_values(["cod_imovel", "tipo_evento"], kind="stable").reset_index(drop=True)


def dir_eventos(uf: str, snap_ant: str, snap_atu: str, base: Path | None = None) -> Path:
    raiz = base or (config.DIR_PARQUET / "eventos")
    return raiz / f"uf={uf.lower()}" / f"intervalo={snap_ant}_{snap_atu}"


def gravar_eventos(df: pd.DataFrame, destino: Path) -> Path:
    destino.mkdir(parents=True, exist_ok=True)
    arq = destino / "part-0.parquet"
    tabela = pa.Table.from_pandas(df, schema=ESQUEMA, preserve_index=False)
    pq.write_table(tabela, arq, compression=config.COMPRESSAO)
    return arq


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--uf", required=True)
    ap.add_argument("--anterior", required=True)
    ap.add_argument("--atual", required=True)
    a = ap.parse_args()
    from car_aberto.ingestao.para_geoparquet import dir_saida

    ler = lambda s: gpd.read_parquet(dir_saida(a.uf, s) / "part-0.parquet", columns=COLUNAS)  # noqa: E731
    df = comparar(ler(a.anterior), ler(a.atual), a.anterior, a.atual)
    print(gravar_eventos(df, dir_eventos(a.uf, a.anterior, a.atual)))


if __name__ == "__main__":
    main()
