import datetime as dt

import pandas as pd
import pytest
from shapely.geometry import GeometryCollection, LineString, MultiPolygon, Polygon

from car_aberto import config
from car_aberto.ingestao.carregar_uf import (
    EsquemaInvalido,
    conferir_esquema,
    para_data,
    para_multipolygon,
)


def test_le_200_imoveis_em_4674(carregado):
    gdf, rel = carregado
    assert rel["imoveis_lidos"] == len(gdf) == 200
    assert gdf.crs.to_epsg() == 4674
    assert rel["encoding"] == "latin1" and rel["cpg_presente"] is False


def test_colunas_minusculas_e_derivadas(carregado):
    gdf, _ = carregado
    for c in config.COLUNAS_AREA_IMOVEL:
        assert c in gdf.columns
    assert {"id_registro", "cod_municipio_ibge", "area_ha"} <= set(gdf.columns)
    assert gdf["id_registro"].is_unique


def test_esquema_falha_sem_coluna():
    with pytest.raises(EsquemaInvalido, match="num_area"):
        conferir_esquema([c for c in config.COLUNAS_AREA_IMOVEL if c != "num_area"])


def test_datas():
    s, falhas = para_data(pd.Series(["01/02/2026", "", None, "31/02/2026"]))
    assert s.iloc[0] == dt.date(2026, 2, 1)
    assert s.iloc[1] is None and s.iloc[2] is None and s.iloc[3] is None
    assert falhas == 1


def test_datas_reais_e_nulas(carregado):
    gdf, rel = carregado
    assert all(isinstance(d, dt.date) for d in gdf["dat_criaca"].dropna())
    assert rel["datas_nulas"]["dat_atuali"] >= 1
    assert rel["datas_invalidas"] == {"dat_criaca": 0, "dat_atuali": 0}


def test_geometria_valida_multipolygon(carregado):
    gdf, rel = carregado
    assert rel["geometria"]["geometrias_invalidas_corrigidas"] >= 1
    assert rel["geometria"]["ainda_invalidas"] == 0
    assert (gdf.geom_type == "MultiPolygon").all()
    assert gdf.is_valid.all()


def test_para_multipolygon():
    q = Polygon([(0, 0), (1, 0), (1, 1)])
    assert isinstance(para_multipolygon(q), MultiPolygon)
    gc = GeometryCollection([q, LineString([(0, 0), (2, 2)])])
    assert len(para_multipolygon(gc).geoms) == 1
    assert para_multipolygon(LineString([(0, 0), (1, 1)])) is None


def test_area_albers_bate_com_declarada(carregado):
    _, rel = carregado
    assert rel["area"]["divergencia_mediana_pct"] < 1.0


def test_codigo_municipio_derivado(carregado):
    gdf, rel = carregado
    assert gdf["cod_municipio_ibge"].str.fullmatch(r"\d{7}").all()
    # a fixture inclui um imovel com codigo de outra UF, como na base real
    assert len(rel["cod_municipio_ibge_fora_da_uf"]) == 1


def test_cod_imovel_repetido_preservado(carregado):
    gdf, rel = carregado
    assert rel["cod_imovel_repetidos"]["codigos"] >= 1
    assert gdf["cod_imovel"].duplicated().any()


def test_tipos_presentes(carregado):
    gdf, _ = carregado
    assert {"IRU", "AST", "PCT"} <= set(gdf["ind_tipo"])
