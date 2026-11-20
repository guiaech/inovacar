import json

import h3
import numpy as np
import pyarrow.parquet as pq

from car_aberto import config


def test_geoparquet_11_valido(base):
    rel = base["rel"]["parquet"]
    assert rel["geoparquet"] == "1.1.0" and rel["linhas"] == 200


def test_metadados(base):
    pf = pq.ParquetFile(base["arq"])
    geo = json.loads(pf.schema_arrow.metadata[b"geo"])
    col = geo["columns"]["geometry"]
    assert col["covering"]["bbox"]["xmin"] == ["bbox", "xmin"]
    assert col["crs"]["id"] == {"authority": "EPSG", "code": 4674}
    md = pf.metadata
    assert md.row_group(0).column(0).compression == "ZSTD"
    assert max(md.row_group(i).num_rows for i in range(md.num_row_groups)) <= config.ROW_GROUP


def test_ordem_hilbert(base):
    gdf = base["gdf"]
    d = gdf.geometry.hilbert_distance(total_bounds=gdf.total_bounds, level=16).to_numpy()
    assert np.all(np.diff(d) >= 0)


def test_centroide_r9(base):
    assert base["gdf"]["h3_centroide_r9"].map(h3.get_resolution).eq(9).all()
