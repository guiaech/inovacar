"""Tabela auxiliar ordenada por cod_imovel: (cod_imovel, id_registro, bbox).

Como o GeoParquet e ordenado por Hilbert, o cod_imovel fica espalhado e a busca por codigo
teria de ler a coluna inteira. Nesta tabela, ordenada por codigo, as estatisticas min/max de
cada row group isolam o codigo em um unico row group pequeno; o bbox devolvido poda os row
groups do GeoParquet na segunda etapa.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from car_aberto import config

log = logging.getLogger(__name__)


def montar_indice_codigo(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    b = gdf.geometry.bounds
    df = pd.DataFrame(
        {
            "cod_imovel": gdf["cod_imovel"].astype(str).to_numpy(),
            "id_registro": gdf["id_registro"].astype(str).to_numpy(),
            "xmin": b["minx"].to_numpy(),
            "ymin": b["miny"].to_numpy(),
            "xmax": b["maxx"].to_numpy(),
            "ymax": b["maxy"].to_numpy(),
        }
    )
    return df.sort_values(["cod_imovel", "id_registro"], kind="stable").reset_index(drop=True)


def gravar_indice_codigo(df: pd.DataFrame, destino: Path) -> Path:
    destino.mkdir(parents=True, exist_ok=True)
    arq = destino / "part-0.parquet"
    pq.write_table(
        pa.Table.from_pandas(df, preserve_index=False),
        arq,
        compression=config.COMPRESSAO,
        row_group_size=config.ROW_GROUP_CODIGO,
    )
    return arq


def dir_indice_codigo(uf: str, snapshot: str, base: Path | None = None) -> Path:
    return (base or config.DIR_CODIGO) / f"uf={uf.lower()}" / f"snapshot={snapshot}"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--uf", required=True)
    ap.add_argument("--snapshot", required=True)
    a = ap.parse_args()
    from car_aberto.ingestao.para_geoparquet import dir_saida

    src = dir_saida(a.uf, a.snapshot) / "part-0.parquet"
    gdf = gpd.read_parquet(src, columns=["id_registro", "cod_imovel", "geometry"])
    print(gravar_indice_codigo(montar_indice_codigo(gdf), dir_indice_codigo(a.uf, a.snapshot)))


if __name__ == "__main__":
    main()
