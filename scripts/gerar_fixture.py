"""Gera tests/fixtures/raw/go/2026-11-01/area_imovel/ com 200 imoveis reais de GO.

Inclui: o maior imovel, todas as geometrias invalidas, um AST, um PCT, um par de cod_imovel
repetido, um codigo de outra UF e um sem dat_atuali. O resto e um bloco espacialmente vizinho
(para haver sobreposicao e pontos de borda) mais amostra aleatoria com semente fixa.
O shapefile e gravado sem .cpg, como o Sicar publica.
"""

from __future__ import annotations

import argparse
import warnings

import geopandas as gpd
import numpy as np

from car_aberto import config

DESTINO = config.RAIZ / "tests" / "fixtures" / "raw" / "go" / "2026-11-01" / "area_imovel"


def selecionar(g: gpd.GeoDataFrame, n: int = 200, semente: int = 42) -> gpd.GeoDataFrame:
    cols = {c.lower(): c for c in g.columns}
    cod, tipo, area = cols["cod_imovel"], cols["ind_tipo"], cols["num_area"]
    escolha: list[int] = []

    def add(idx) -> None:
        for i in np.atleast_1d(idx):
            if int(i) not in escolha:
                escolha.append(int(i))

    add(g[area].astype(float).idxmax())
    add(np.flatnonzero(~g.geometry.is_valid.to_numpy()))
    add(np.flatnonzero((g[tipo] == "AST").to_numpy())[:1])
    add(np.flatnonzero((g[tipo] == "PCT").to_numpy())[:1])
    rep = g[g[cod].duplicated(keep=False)]
    add(rep[rep[cod] == rep[cod].iloc[0]].index)
    add(np.flatnonzero(~g[cod].str.startswith("GO-").to_numpy())[:1])
    add(np.flatnonzero(g[cols["dat_atuali"]].fillna("").str.strip().eq("").to_numpy())[:1])
    # bloco vizinho: imoveis mais proximos de um imovel de Abadia de Goias
    warnings.filterwarnings("ignore", message="Geometry is in a geographic CRS")
    alvo = g[g[cols["municipio"]] == "Abadia de Goias"].geometry.iloc[0].centroid
    dist = g.geometry.centroid.distance(alvo).to_numpy()
    add(np.argsort(dist)[:120])
    rng = np.random.default_rng(semente)
    resto = np.setdiff1d(np.arange(len(g)), escolha)
    add(rng.choice(resto, n - len(escolha), replace=False))
    return g.iloc[escolha[:n]]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--snapshot", default="2026-11-01")
    a = ap.parse_args()
    src = config.DIR_RAW / "go" / a.snapshot / "area_imovel"
    g = gpd.read_file(next(src.glob("*.shp")), encoding="latin1", engine="pyogrio")
    amostra = selecionar(g)
    DESTINO.mkdir(parents=True, exist_ok=True)
    for p in DESTINO.glob("*"):
        p.unlink()
    amostra.to_file(DESTINO / "AREA_IMOVEL_1.shp", encoding="latin1", engine="pyogrio")
    DESTINO.joinpath("AREA_IMOVEL_1.cpg").unlink(missing_ok=True)
    print(len(amostra), "imoveis em", DESTINO)


if __name__ == "__main__":
    main()
