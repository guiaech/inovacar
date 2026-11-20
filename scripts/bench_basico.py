"""Benchmark local: baixar o shapefile da UF x consultar o GeoParquet.

Para cada uma de 20 consultas tipicas mede:
- bytes lidos do disco (sistema de arquivos fsspec que conta cada read feito pelo DuckDB);
- latencia a frio (conexao DuckDB nova por consulta) e com cache (mesma conexao, 2a execucao).
Linha de base: tamanho do zip original do Sicar e tempo de abrir o shapefile inteiro.

Local, "a frio" significa sem cache do DuckDB; o cache de disco do sistema operacional
continua quente. A versao remota (httpfs contra bucket, com Range Requests) fica na sessao 2.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time

import duckdb
import geopandas as gpd
import numpy as np
from fsspec.implementations.local import LocalFileSystem

from car_aberto import config
from car_aberto.consulta.duck import ConsultaCAR, Fonte


class _Contador:
    def __init__(self, f, fs):
        self._f, self._fs = f, fs

    def read(self, n=-1):
        dados = self._f.read(n)
        self._fs.bytes_lidos += len(dados)
        return dados

    def readinto(self, b):
        n = self._f.readinto(b)
        self._fs.bytes_lidos += n or 0
        return n

    def __getattr__(self, nome):
        return getattr(self._f, nome)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self._f.close()


class FSContador(LocalFileSystem):
    """LocalFileSystem com protocolo proprio que soma os bytes efetivamente lidos."""

    protocol = ("conta",)
    root_marker = ""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.bytes_lidos = 0

    @classmethod
    def _strip_protocol(cls, path):
        path = path[len("conta://") :] if str(path).startswith("conta://") else path
        return super()._strip_protocol(path)

    def _open(self, path, mode="rb", **kw):
        return _Contador(super()._open(path, mode, **kw), self)

    def unstrip_protocol(self, name):
        return "conta://" + name


def consultas_tipicas(gdf, rng) -> list[tuple[str, str, dict]]:
    """20 consultas: 5 por codigo, 5 por ponto, 4 por bbox, 6 por filtros."""
    q: list[tuple[str, str, dict]] = []
    repetido = gdf.loc[gdf["cod_imovel"].duplicated(), "cod_imovel"].iloc[0]
    codigos = [repetido, *gdf["cod_imovel"].sample(4, random_state=7)]
    for c in codigos:
        q.append(("codigo", f"cod_imovel={c[:20]}...", {"cod_imovel": c}))
    for g in gdf.geometry.sample(5, random_state=11):
        p = g.representative_point()
        q.append(("ponto", f"lon={p.x:.4f} lat={p.y:.4f}", {"lon": p.x, "lat": p.y}))
    for lado in (0.01, 0.01, 0.1, 0.1):
        c = gdf.geometry.iloc[int(rng.integers(len(gdf)))].representative_point()
        bb = (c.x - lado / 2, c.y - lado / 2, c.x + lado / 2, c.y + lado / 2)
        q.append(("bbox", f"janela {lado} grau", {"bbox": bb}))
    filtros = [
        {"municipio": "Rio Verde"},
        {"cod_municipio_ibge": "5208707", "excluir_cancelados": True},
        {"ind_status": "PE", "municipio": "Jatai"},
        {"ind_tipo": "AST"},
        {"des_condic": "Analisado, aguardando atendimento a notificacao", "municipio": "Mineiros"},
        {"area_min": 1000, "area_max": 5000, "mod_fiscal_min": 15, "excluir_cancelados": True},
    ]
    for f in filtros:
        q.append(("filtros", ", ".join(f"{k}={v}" for k, v in f.items()), f))
    return q


def executar(c: ConsultaCAR, tipo: str, args: dict):
    if tipo == "codigo":
        return c.consultar_por_codigo(args["cod_imovel"])
    if tipo == "ponto":
        return c.consultar_por_ponto(args["lon"], args["lat"])
    if tipo == "bbox":
        return c.consultar_por_bbox(*args["bbox"], limit=1000)
    return c.consultar_por_filtros(**args, limit=1000)


def p(vals, q):
    return float(np.percentile(vals, q))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--uf", default="go")
    ap.add_argument("--snapshot", default="2026-11-01")
    a = ap.parse_args()

    raw = config.DIR_RAW / a.uf / a.snapshot / "area_imovel"
    zip_bytes = sum(z.stat().st_size for z in raw.glob("*.zip"))
    shp_bytes = sum(f.stat().st_size for f in raw.iterdir() if f.suffix != ".zip")
    pq_arq = config.DIR_PARQUET / f"uf={a.uf}" / f"snapshot={a.snapshot}" / "part-0.parquet"
    h3_arq = config.DIR_H3 / f"uf={a.uf}" / f"snapshot={a.snapshot}" / "part-0.parquet"

    t0 = time.perf_counter()
    gpd.read_file(next(raw.glob("*.shp")), encoding="latin1", engine="pyogrio")
    t_shp = time.perf_counter() - t0

    gdf = gpd.read_parquet(pq_arq, columns=["cod_imovel", "geometry"])
    consultas = consultas_tipicas(gdf, np.random.default_rng(3))

    fs = FSContador()
    fonte_conta = Fonte(
        base_imoveis="conta://" + config.DIR_PARQUET.as_posix(),
        base_h3="conta://" + config.DIR_H3.as_posix(),
    )
    c_quente = ConsultaCAR(a.uf, a.snapshot)

    linhas = []
    for tipo, desc, args in consultas:
        # conexao nova por consulta: o DuckDB guarda cache de arquivo dentro da conexao
        con_conta = duckdb.connect()
        con_conta.register_filesystem(fs)
        c_conta = ConsultaCAR(a.uf, a.snapshot, fonte=fonte_conta, con=con_conta)
        fs.bytes_lidos = 0
        n = len(executar(c_conta, tipo, args))
        lidos = fs.bytes_lidos
        con_conta.close()

        frio = ConsultaCAR(a.uf, a.snapshot)
        t0 = time.perf_counter()
        executar(frio, tipo, args)
        t_frio = time.perf_counter() - t0
        frio.con.close()

        executar(c_quente, tipo, args)
        t0 = time.perf_counter()
        executar(c_quente, tipo, args)
        t_quente = time.perf_counter() - t0
        linhas.append(
            {
                "tipo": tipo,
                "consulta": desc,
                "linhas": n,
                "bytes_lidos": lidos,
                "ms_frio": round(t_frio * 1000, 1),
                "ms_cache": round(t_quente * 1000, 1),
            }
        )
        print(f"{tipo:8s} {n:6d} linhas {lidos / 1e6:8.2f} MB {t_frio * 1000:7.1f} ms {desc}")

    b = [x["bytes_lidos"] for x in linhas]
    f = [x["ms_frio"] for x in linhas]
    q = [x["ms_cache"] for x in linhas]
    resumo = {
        "uf": a.uf,
        "snapshot": a.snapshot,
        "zip_sicar_bytes": zip_bytes,
        "shapefile_descompactado_bytes": shp_bytes,
        "geoparquet_bytes": pq_arq.stat().st_size,
        "indice_h3_bytes": h3_arq.stat().st_size,
        "abrir_shapefile_inteiro_s": round(t_shp, 1),
        "bytes_lidos_mediana": int(statistics.median(b)),
        "bytes_lidos_max": max(b),
        "ms_frio_p50": round(p(f, 50), 1),
        "ms_frio_p95": round(p(f, 95), 1),
        "ms_cache_p50": round(p(q, 50), 1),
        "ms_cache_p95": round(p(q, 95), 1),
        "ms_frio_media": round(statistics.mean(f), 1),
        "consultas": linhas,
    }
    config.DIR_RELATORIOS.mkdir(parents=True, exist_ok=True)
    saida = config.DIR_RELATORIOS / f"bench_local_{a.uf}_{a.snapshot}.json"
    saida.write_text(json.dumps(resumo, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in resumo.items() if k != "consultas"}, indent=2))
    print(saida)


if __name__ == "__main__":
    main()
