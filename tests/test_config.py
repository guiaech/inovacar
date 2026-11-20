from car_aberto import config


def test_crs_base_e_sirgas():
    assert config.CRS_BASE == "EPSG:4674"


def test_albers_ibge():
    assert "+proj=aea" in config.CRS_AREA and "+lon_0=-54" in config.CRS_AREA
