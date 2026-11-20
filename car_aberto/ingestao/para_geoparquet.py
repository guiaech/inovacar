"""Grava o snapshot como GeoParquet 1.1 otimizado para leitura parcial por HTTP.

Linhas ordenadas por curva de Hilbert, coluna bbox (covering), row groups de
config.ROW_GROUP linhas (5 mil, escolhido por medicao) e compressao zstd. Saida em data/parquet/uf={uf}/snapshot={aaaa-mm-dd}/.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pyarrow.parquet as pq

from car_aberto import config
from car_aberto.ingestao.carregar_uf import carregar_uf, salvar_relatorio
from car_aberto.ingestao.indice_h3 import centroide_r9

log = logging.getLogger(__name__)


def dir_saida(uf: str, snapshot: str, base: Path | None = None) -> Path:
    return (base or config.DIR_PARQUET) / f"uf={uf.lower()}" / f"snapshot={snapshot}"


def ordenar_hilbert(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    dist = gdf.geometry.hilbert_distance(total_bounds=gdf.total_bounds, level=16)
    return gdf.iloc[np.argsort(dist.to_numpy(), kind="stable")].reset_index(drop=True)


def gravar(gdf: gpd.GeoDataFrame, destino: Path) -> Path:
    destino.mkdir(parents=True, exist_ok=True)
    arq = destino / "part-0.parquet"
    gdf.to_parquet(
        arq,
        schema_version="1.1.0",
        write_covering_bbox=True,
        geometry_encoding="WKB",
        compression=config.COMPRESSAO,
        compression_level=config.COMPRESSAO_NIVEL,
        row_group_size=config.ROW_GROUP,
        index=False,
    )
    return arq


def validar(arq: Path, n_esperado: int | None = None) -> dict:
    """Confere metadados GeoParquet 1.1, bbox covering, CRS, zstd e tamanho dos row groups."""
    pf = pq.ParquetFile(arq)
    geo = json.loads(pf.schema_arrow.metadata[b"geo"])
    col = geo["columns"][geo["primary_column"]]
    md = pf.metadata
    codecs = {
        md.row_group(i).column(j).compression
        for i in range(md.num_row_groups)
        for j in range(md.num_columns)
    }
    tamanhos = [md.row_group(i).num_rows for i in range(md.num_row_groups)]
    crs_id = (col.get("crs") or {}).get("id", {})
    erros = []
    if geo.get("version") != "1.1.0":
        erros.append(f"versao {geo.get('version')}")
    if "bbox" not in col.get("covering", {}):
        erros.append("sem covering bbox")
    if (crs_id.get("authority"), crs_id.get("code")) != ("EPSG", 4674):
        erros.append(f"crs {crs_id}")
    if codecs != {"ZSTD"}:
        erros.append(f"compressao {codecs}")
    if max(tamanhos) > config.ROW_GROUP:
        erros.append(f"row group maior que {config.ROW_GROUP}")
    if n_esperado is not None and md.num_rows != n_esperado:
        erros.append(f"linhas {md.num_rows} != {n_esperado}")
    if not set(col.get("geometry_types", [])) <= {"MultiPolygon"}:
        erros.append(f"tipos {col.get('geometry_types')}")
    if erros:
        raise ValueError(f"GeoParquet invalido: {erros}")
    return {
        "arquivo": str(arq),
        "bytes": arq.stat().st_size,
        "linhas": md.num_rows,
        "row_groups": md.num_row_groups,
        "geoparquet": geo["version"],
        "geometry_types": col.get("geometry_types"),
    }


def validar_gpio(arq: Path) -> str:
    """Validacao externa com geoparquet-io (gpio check all). Devolve a saida do comando."""
    exe = Path(sys.executable).with_name("gpio")
    cmd = [str(exe), "check", "all", str(arq)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout + r.stderr).strip()


def converter(uf: str, snapshot: str, dir_raw: Path | None = None, base: Path | None = None):
    gdf, rel = carregar_uf(uf, snapshot, dir_raw=dir_raw)
    gdf["h3_centroide_r9"] = centroide_r9(gdf)
    gdf = ordenar_hilbert(gdf)
    arq = gravar(gdf, dir_saida(uf, snapshot, base))
    rel["parquet"] = validar(arq, n_esperado=len(gdf))
    log.info("GeoParquet ok: %s", rel["parquet"])
    return arq, rel


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--uf", required=True)
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--sem-gpio", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    arq, rel = converter(a.uf, a.snapshot)
    if not a.sem_gpio:
        rel["gpio_check"] = validar_gpio(arq)
        print(rel["gpio_check"])
    print(salvar_relatorio(rel, f"ingestao_{a.uf.lower()}_{a.snapshot}.json"))


if __name__ == "__main__":
    main()
