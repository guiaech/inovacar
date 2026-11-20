import hashlib

from car_aberto.ingestao.manifest import gerar_manifest


def test_manifest(tmp_path):
    d = tmp_path / "go" / "2026-11-01" / "area_imovel"
    d.mkdir(parents=True)
    (d / "A.dbf").write_bytes(b"abc")
    m = gerar_manifest(d.parent, "2026-11-20")
    assert m["uf"] == "go" and m["data_disponibilizacao"] == "2026-11-01"
    assert m["arquivos"][0]["sha256"] == hashlib.sha256(b"abc").hexdigest()
    assert m["arquivos"][0]["bytes"] == 3
