from pathlib import Path

import geopandas as gpd
import pytest

from car_aberto.consulta.duck import ConsultaCAR, Fonte
from car_aberto.ingestao.carregar_uf import carregar_uf
from car_aberto.ingestao.indice_h3 import dir_indice, gravar_indice, montar_indice
from car_aberto.ingestao.para_geoparquet import converter

RAW = Path(__file__).parent / "fixtures" / "raw"
UF, SNAP = "go", "2026-11-01"


@pytest.fixture(scope="session")
def carregado():
    return carregar_uf(UF, SNAP, dir_raw=RAW)


@pytest.fixture(scope="session")
def base(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("lake")
    arq, rel = converter(UF, SNAP, dir_raw=RAW, base=raiz / "parquet")
    gdf = gpd.read_parquet(arq)
    gravar_indice(montar_indice(gdf), dir_indice(UF, SNAP, raiz / "h3"))
    return {"raiz": raiz, "arq": arq, "rel": rel, "gdf": gdf}


@pytest.fixture(scope="session")
def consulta(base):
    fonte = Fonte(
        base_imoveis=(base["raiz"] / "parquet").as_posix(),
        base_h3=(base["raiz"] / "h3").as_posix(),
    )
    return ConsultaCAR(UF, fonte=fonte)
