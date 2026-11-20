import pyarrow.parquet as pq

from car_aberto import config
from car_aberto.consulta.medicao import FSContador


def test_ordenado_por_codigo_e_completo(base):
    t = pq.read_table(base["arq_codigo"]).to_pandas()
    assert t["cod_imovel"].is_monotonic_increasing
    assert set(t["id_registro"]) == set(base["gdf"]["id_registro"])
    md = pq.ParquetFile(base["arq_codigo"]).metadata
    assert max(md.row_group(i).num_rows for i in range(md.num_row_groups)) <= (
        config.ROW_GROUP_CODIGO
    )


def test_bbox_bate_com_geometria(base):
    t = pq.read_table(base["arq_codigo"]).to_pandas().set_index("id_registro")
    b = base["gdf"].set_index("id_registro").geometry.bounds
    assert (t.loc[b.index, "xmin"].to_numpy() == b["minx"].to_numpy()).all()
    assert (t.loc[b.index, "ymax"].to_numpy() == b["maxy"].to_numpy()).all()


def test_todos_os_codigos_encontrados(consulta, base):
    gdf = base["gdf"]
    for cod, n in gdf["cod_imovel"].value_counts().head(30).items():
        r = consulta.consultar_por_codigo(cod)
        assert len(r) == n
        ref = gdf.set_index("id_registro").geometry
        assert all(g.equals(ref[i]) for i, g in zip(r["id_registro"], r.geometry, strict=True))


def test_contador_de_bytes(tmp_path):
    p = tmp_path / "a.bin"
    p.write_bytes(b"x" * 1000)
    fs = FSContador()
    with fs.open("conta://" + p.as_posix(), "rb") as f:
        f.read(300)
    assert fs.bytes_lidos == 300
    assert sum(fs.por_arquivo.values()) == 300
