import h3

from car_aberto import config
from car_aberto.ingestao.indice_h3 import celulas_do_ponto, cobertura_compacta, montar_indice


def test_ancestrais_ate_res0():
    cel = celulas_do_ponto(-49.3, -16.7)
    assert len(cel) == config.H3_RES_COBERTURA + 1
    assert sorted(h3.get_resolution(h3.int_to_str(c)) for c in cel) == list(range(8))


def test_todo_imovel_tem_celula(base):
    df = montar_indice(base["gdf"])
    assert set(df["id_registro"]) == set(base["gdf"]["id_registro"])


def test_sem_falso_negativo_na_borda(base):
    """Pontos sobre o contorno de cada imovel caem numa celula da cobertura (ou ancestral)."""
    for geom in base["gdf"].geometry:
        cobertura = set(cobertura_compacta(geom))
        anel = geom.geoms[0].exterior
        for frac in (0.0, 0.25, 0.5, 0.75):
            p = anel.interpolate(frac, normalized=True)
            assert cobertura & set(celulas_do_ponto(p.x, p.y))


def test_compactacao_reduz_maior_imovel(base):
    gdf = base["gdf"]
    maior = gdf.loc[gdf["area_ha"].idxmax(), "geometry"]
    forma = h3.geo_to_h3shape(maior)
    cheio = h3.h3shape_to_cells_experimental(forma, config.H3_RES_COBERTURA, contain="overlap")
    assert len(cobertura_compacta(maior)) < len(cheio)
