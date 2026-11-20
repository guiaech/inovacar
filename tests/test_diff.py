import datetime as dt

import geopandas as gpd
import pyarrow.parquet as pq
import pytest
from shapely.affinity import translate
from shapely.geometry import MultiPolygon, box

from car_aberto import config
from car_aberto.historico.diff import comparar, dir_eventos, gravar_eventos, iou
from car_aberto.ingestao.carregar_uf import gerar_id_registro

ANT, ATU = "2026-05-03", "2026-11-01"
QUADRADO = box(-49.0, -16.0, -48.99, -15.99)


def reg(cod, status="AT", condic="Aguardando analise", area=10.0, geom=QUADRADO, dat="2026-01-01"):
    return {
        "cod_imovel": f"GO-5200050-{cod:0>32}",
        "num_area": area,
        "ind_status": status,
        "ind_tipo": "IRU",
        "des_condic": condic,
        "municipio": "Abadia de Goias",
        "cod_municipio_ibge": "5200050",
        "dat_atuali": dt.date.fromisoformat(dat) if dat else None,
        "geometry": MultiPolygon([geom]),
    }


def gdf(*linhas):
    g = gpd.GeoDataFrame(list(linhas), geometry="geometry", crs=config.CRS_BASE)
    g["id_registro"] = gerar_id_registro(g)
    return g


def eventos(ant, atu):
    return comparar(gdf(*ant), gdf(*atu), ANT, ATU)


def tipos(df):
    return sorted(df["tipo_evento"])


def test_inalterado_nao_gera_evento():
    assert eventos([reg("A")], [reg("A")]).empty


def test_novo_e_removido_imovel():
    df = eventos([reg("A")], [reg("B")])
    assert tipos(df) == ["novo", "removido"]
    assert set(df["escopo"]) == {"imovel"}


def test_novo_registro_em_codigo_existente():
    df = eventos([reg("A")], [reg("A"), reg("A", "CA", "Cancelado por duplicidade")])
    assert tipos(df) == ["novo"]
    assert df.iloc[0]["escopo"] == "registro" and df.iloc[0]["valor_atual"] == "CA"


def test_mudanca_dat_atuali_com_data_provavel():
    df = eventos([reg("A")], [reg("A", dat="2026-08-15")])
    assert tipos(df) == ["mudanca_dat_atuali"]
    assert df.iloc[0]["data_provavel"] == dt.date(2026, 8, 15)
    assert df.iloc[0]["fonte_data"] == "dat_atuali"


def test_data_fora_do_intervalo_fica_nula():
    df = eventos([reg("A", "PE")], [reg("A", "AT", dat="2026-01-01")])
    assert tipos(df) == ["mudanca_ind_status"]
    assert df.iloc[0]["data_provavel"] is None


def test_mudanca_status_e_condicao():
    df = eventos(
        [reg("A")], [reg("A", "CA", "Cancelado por decisao administrativa", dat="2026-06-01")]
    )
    assert tipos(df) == ["mudanca_dat_atuali", "mudanca_des_condic", "mudanca_ind_status"]
    st = df[df.tipo_evento == "mudanca_ind_status"].iloc[0]
    assert (st.valor_anterior, st.valor_atual) == ("AT", "CA")


@pytest.mark.parametrize("nova_area,espera", [(10.5, True), (10.05, False)])
def test_mudanca_area_limiar_1pct(nova_area, espera):
    df = eventos([reg("A")], [reg("A", area=nova_area)])
    assert ("mudanca_area" in set(df["tipo_evento"])) is espera


@pytest.mark.parametrize("dx,espera", [(0.005, True), (0.00005, False)])
def test_mudanca_geometria_limiar_iou(dx, espera):
    df = eventos([reg("A")], [reg("A", geom=translate(QUADRADO, xoff=dx))])
    assert ("mudanca_geometria" in set(df["tipo_evento"])) is espera


def test_iou():
    a = MultiPolygon([QUADRADO])
    b = MultiPolygon([translate(QUADRADO, xoff=0.005)])
    v = iou(gpd.GeoSeries([a, a]).values, gpd.GeoSeries([a, b]).values)
    assert v[0] == 1.0 and v[1] == pytest.approx(1 / 3, abs=0.01)


def test_desempate_prefere_registro_nao_cancelado():
    novo_geom = translate(QUADRADO, xoff=0.002)
    df = eventos(
        [reg("A", "PE", "Analisado, aguardando atendimento a notificacao")],
        [
            reg("A", "CA", "Cancelado por duplicidade", area=8, geom=novo_geom),
            reg("A", "AT", "Aguardando analise", area=8, geom=novo_geom),
        ],
    )
    st = df[df.tipo_evento == "mudanca_ind_status"].iloc[0]
    assert st.valor_atual == "AT"
    assert df[df.tipo_evento == "novo"].iloc[0]["valor_atual"] == "CA"


def test_gravar_eventos(tmp_path):
    df = eventos([reg("A")], [reg("A", "CA", dat="2026-06-01"), reg("B")])
    arq = gravar_eventos(df, dir_eventos("go", ANT, ATU, tmp_path))
    t = pq.read_table(arq)
    assert t.num_rows == len(df)
    assert str(t.schema.field("data_provavel").type) == "date32[day]"
    assert "intervalo=2026-05-03_2026-11-01" in str(arq)


def test_dat_atuali_nula_nos_dois_lados_nao_e_mudanca():
    assert eventos([reg("A", dat=None)], [reg("A", dat=None)]).empty


def test_dat_atuali_nula_em_registro_pareado_nao_e_mudanca():
    df = eventos([reg("A", "AT", dat=None)], [reg("A", "CA", dat=None)])
    assert tipos(df) == ["mudanca_ind_status"]


def test_dat_atuali_de_nula_para_preenchida_e_mudanca():
    df = eventos([reg("A", dat=None)], [reg("A", dat="2026-07-01")])
    assert tipos(df) == ["mudanca_dat_atuali"]
