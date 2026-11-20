import numpy as np
import pytest
import shapely
from shapely.geometry import Point


def _forca_bruta(gdf, geom):
    return set(gdf.loc[gdf.intersects(geom), "id_registro"])


def test_por_codigo_devolve_todas_as_versoes(consulta, base):
    gdf = base["gdf"]
    cod = gdf.loc[gdf["cod_imovel"].duplicated(), "cod_imovel"].iloc[0]
    r = consulta.consultar_por_codigo(cod)
    assert len(r) == (gdf["cod_imovel"] == cod).sum() >= 2
    assert r.crs.to_epsg() == 4674


def test_por_codigo_inexistente(consulta):
    assert consulta.consultar_por_codigo("GO-0000000-X").empty


def test_ponto_perto_da_borda(consulta, base):
    """Ponto a ~0,1 m da borda, por dentro e por fora, igual a forca bruta."""
    gdf = base["gdf"]
    testados = 0
    for _, linha in gdf.sample(30, random_state=1).iterrows():
        g = linha.geometry
        b = g.geoms[0].exterior.interpolate(0.37, normalized=True)
        c = g.geoms[0].representative_point()
        v = np.array([c.x - b.x, c.y - b.y])
        v = v / np.linalg.norm(v) * 1e-6
        dentro, fora = Point(b.x + v[0], b.y + v[1]), Point(b.x - v[0], b.y - v[1])
        if not (g.contains(dentro) and not g.contains(fora)):
            continue
        r_in = set(consulta.consultar_por_ponto(dentro.x, dentro.y)["id_registro"])
        r_out = set(consulta.consultar_por_ponto(fora.x, fora.y)["id_registro"])
        assert linha["id_registro"] in r_in
        assert linha["id_registro"] not in r_out
        assert r_in == _forca_bruta(gdf, dentro)
        assert r_out == _forca_bruta(gdf, fora)
        testados += 1
    assert testados >= 10


def test_pontos_aleatorios_iguais_a_forca_bruta(consulta, base):
    gdf = base["gdf"]
    rng = np.random.default_rng(0)
    for g in gdf.sample(20, random_state=2).geometry:
        xmin, ymin, xmax, ymax = g.bounds
        p = Point(rng.uniform(xmin, xmax), rng.uniform(ymin, ymax))
        assert set(consulta.consultar_por_ponto(p.x, p.y)["id_registro"]) == _forca_bruta(gdf, p)


def test_bbox_igual_a_forca_bruta(consulta, base):
    gdf = base["gdf"]
    xmin, ymin, xmax, ymax = gdf.geometry.iloc[10].buffer(0.05).bounds
    r = consulta.consultar_por_bbox(xmin, ymin, xmax, ymax, limit=1000)
    assert set(r["id_registro"]) == _forca_bruta(gdf, shapely.box(xmin, ymin, xmax, ymax))


def test_bbox_paginacao(consulta, base):
    xmin, ymin, xmax, ymax = base["gdf"].total_bounds
    p1 = consulta.consultar_por_bbox(xmin, ymin, xmax, ymax, limit=50, com_geometria=False)
    p2 = consulta.consultar_por_bbox(
        xmin, ymin, xmax, ymax, limit=50, offset=50, com_geometria=False
    )
    assert len(p1) == len(p2) == 50
    assert not set(p1["id_registro"]) & set(p2["id_registro"])


def test_limites(consulta):
    with pytest.raises(ValueError):
        consulta.consultar_por_filtros(limit=0)
    with pytest.raises(ValueError):
        consulta.consultar_por_filtros(limit=10_001)
    with pytest.raises(ValueError):
        consulta.consultar_por_bbox(1, 1, 0, 0)


def test_filtros_cancelados(consulta, base):
    gdf = base["gdf"]
    todos = consulta.consultar_por_filtros(limit=1000, com_geometria=False)
    assert len(todos) == len(gdf)
    sem_ca = consulta.consultar_por_filtros(
        excluir_cancelados=True, limit=1000, com_geometria=False
    )
    assert "CA" not in set(sem_ca["ind_status"])
    assert len(sem_ca) == (gdf["ind_status"] != "CA").sum()


def test_filtros_combinados(consulta, base):
    gdf = base["gdf"]
    r = consulta.consultar_por_filtros(
        municipio="Abadia de Goiás",
        ind_tipo="IRU",
        area_min=10,
        area_max=500,
        mod_fiscal_max=20,
        limit=1000,
    )
    esperado = gdf[
        (gdf.municipio == "Abadia de Goias")
        & (gdf.ind_tipo == "IRU")
        & gdf.num_area.between(10, 500)
        & (gdf.mod_fiscal <= 20)
    ]
    assert len(r) == len(esperado) > 0
    # geometria da segunda etapa corresponde ao id_registro certo
    ref = gdf.set_index("id_registro").geometry
    assert all(g.equals(ref[i]) for i, g in zip(r["id_registro"], r.geometry, strict=True))


def test_filtro_des_condic_e_status(consulta, base):
    gdf = base["gdf"]
    valor = gdf["des_condic"].iloc[0]
    r = consulta.consultar_por_filtros(des_condic=valor, ind_status=["AT", "PE"], limit=1000)
    assert len(r) == (gdf.des_condic.eq(valor) & gdf.ind_status.isin(["AT", "PE"])).sum()


def test_filtro_ast(consulta):
    r = consulta.consultar_por_filtros(ind_tipo="ast", limit=10)
    assert len(r) >= 1 and set(r["ind_tipo"]) == {"AST"}
