"""Consultas sobre o GeoParquet com DuckDB + spatial, sem carregar a UF inteira.

Toda consulta usa o particionamento uf/snapshot e a coluna bbox para pular row groups.
A consulta por ponto passa antes pelo indice H3 compactado e termina em ST_Intersects exato.
Por padrao todas as situacoes sao devolvidas, inclusive CA; excluir_cancelados=True remove CA.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import geopandas as gpd
import pandas as pd
import shapely

from car_aberto import config
from car_aberto.ingestao.indice_h3 import celulas_do_ponto

LIMITE_MAXIMO = 10_000
COLUNAS_SAIDA = (
    "id_registro, cod_imovel, cod_tema, nom_tema, mod_fiscal, num_area, ind_status, ind_tipo, "
    "des_condic, municipio, cod_estado, dat_criaca, dat_atuali, cod_municipio_ibge, area_ha, "
    "h3_centroide_r9, uf, snapshot"
)


def sem_acento(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    ).strip()


@dataclass
class Fonte:
    """Onde estao as tabelas. `base_*` pode ser pasta local ou URL (s3://, https://, gs://)."""

    base_imoveis: str = field(default_factory=lambda: config.DIR_PARQUET.as_posix())
    base_h3: str = field(default_factory=lambda: config.DIR_H3.as_posix())

    def imoveis(self) -> str:
        return (
            f"read_parquet('{self.base_imoveis}/uf=*/snapshot=*/*.parquet', "
            "hive_partitioning=true, hive_types={'snapshot': VARCHAR})"
        )

    def h3(self) -> str:
        return (
            f"read_parquet('{self.base_h3}/uf=*/snapshot=*/*.parquet', "
            "hive_partitioning=true, hive_types={'snapshot': VARCHAR})"
        )


def conectar(con: duckdb.DuckDBPyConnection | None = None) -> duckdb.DuckDBPyConnection:
    con = con or duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    return con


def snapshots_locais(uf: str, base: Path | None = None) -> list[str]:
    d = (base or config.DIR_PARQUET) / f"uf={uf.lower()}"
    return sorted(p.name.split("=", 1)[1] for p in d.glob("snapshot=*") if p.is_dir())


class ConsultaCAR:
    def __init__(
        self,
        uf: str,
        snapshot: str | None = None,
        fonte: Fonte | None = None,
        con: duckdb.DuckDBPyConnection | None = None,
    ):
        self.uf = uf.lower()
        self.fonte = fonte or Fonte()
        if snapshot is None:
            disponiveis = snapshots_locais(self.uf, Path(self.fonte.base_imoveis))
            if not disponiveis:
                raise FileNotFoundError(f"nenhum snapshot de {self.uf} em {self.fonte}")
            snapshot = disponiveis[-1]
        self.snapshot = snapshot
        self.con = conectar(con)

    # utilitarios -----------------------------------------------------------------
    def _particao(self, alias: str = "") -> str:
        p = f"{alias}." if alias else ""
        return f"{p}uf = '{self.uf}' AND {p}snapshot = '{self.snapshot}'"

    def _executar(self, sql: str, params: list) -> gpd.GeoDataFrame:
        df = self.con.execute(sql, params).df()
        geom = shapely.from_wkb(df.pop("geom_wkb").map(bytes)) if len(df) else []
        return gpd.GeoDataFrame(df, geometry=gpd.GeoSeries(geom, crs=config.CRS_BASE))

    def _select(self, alias: str = "i", com_geometria: bool = True) -> str:
        cols = ", ".join(f"{alias}.{c.strip()}" for c in COLUNAS_SAIDA.split(","))
        g = f", ST_AsWKB({alias}.geometry) AS geom_wkb" if com_geometria else ""
        return f"SELECT {cols}{g}"

    @staticmethod
    def _paginacao(limit: int, offset: int) -> str:
        if not 0 < limit <= LIMITE_MAXIMO:
            raise ValueError(f"limit deve estar entre 1 e {LIMITE_MAXIMO}")
        if offset < 0:
            raise ValueError("offset negativo")
        return f"ORDER BY i.cod_imovel, i.id_registro LIMIT {int(limit)} OFFSET {int(offset)}"

    # consultas -------------------------------------------------------------------
    def consultar_por_codigo(self, cod_imovel: str) -> gpd.GeoDataFrame:
        """Todas as linhas com o codigo. cod_imovel se repete na base publica (ver dicionario)."""
        sql = (
            f"{self._select()} FROM {self.fonte.imoveis()} i "
            f"WHERE {self._particao('i')} AND i.cod_imovel = ? ORDER BY i.id_registro"
        )
        return self._executar(sql, [cod_imovel.strip()])

    def consultar_por_ponto(self, lon: float, lat: float) -> gpd.GeoDataFrame:
        """Imoveis que contem o ponto (borda inclusa). H3 primeiro, depois ST_Intersects."""
        celulas = celulas_do_ponto(lon, lat)
        marcadores = ", ".join("?" for _ in celulas)
        sql = f"""
            WITH candidatos AS (
                SELECT DISTINCT id_registro FROM {self.fonte.h3()} h
                WHERE {self._particao("h")} AND h.h3 IN ({marcadores})
            )
            {self._select()} FROM {self.fonte.imoveis()} i
            WHERE {self._particao("i")}
              AND i.id_registro IN (SELECT id_registro FROM candidatos)
              AND i.bbox.xmin <= ? AND i.bbox.xmax >= ? AND i.bbox.ymin <= ? AND i.bbox.ymax >= ?
              AND ST_Intersects(i.geometry, ST_Point(?, ?))
            ORDER BY i.cod_imovel, i.id_registro
        """
        return self._executar(sql, [*celulas, lon, lon, lat, lat, lon, lat])

    def consultar_por_bbox(
        self,
        xmin: float,
        ymin: float,
        xmax: float,
        ymax: float,
        limit: int = 1000,
        offset: int = 0,
        com_geometria: bool = True,
    ) -> gpd.GeoDataFrame:
        if xmin > xmax or ymin > ymax:
            raise ValueError("bbox invertido")
        sql = f"""
            {self._select(com_geometria=com_geometria)} FROM {self.fonte.imoveis()} i
            WHERE {self._particao("i")}
              AND i.bbox.xmax >= ? AND i.bbox.xmin <= ? AND i.bbox.ymax >= ? AND i.bbox.ymin <= ?
              AND ST_Intersects(i.geometry, ST_MakeEnvelope(?, ?, ?, ?))
            {self._paginacao(limit, offset)}
        """
        params = [xmin, xmax, ymin, ymax, xmin, ymin, xmax, ymax]
        return self._executar_talvez_sem_geom(sql, params, com_geometria)

    def consultar_por_filtros(
        self,
        municipio: str | None = None,
        cod_municipio_ibge: str | None = None,
        ind_status: str | Iterable[str] | None = None,
        ind_tipo: str | Iterable[str] | None = None,
        des_condic: str | Iterable[str] | None = None,
        area_min: float | None = None,
        area_max: float | None = None,
        mod_fiscal_min: float | None = None,
        mod_fiscal_max: float | None = None,
        excluir_cancelados: bool = False,
        limit: int = 1000,
        offset: int = 0,
        com_geometria: bool = True,
    ) -> gpd.GeoDataFrame:
        """Filtros por propriedade. Faixa de area usa num_area (area declarada, em ha)."""
        conds, params = [self._particao("i")], []

        def em(coluna: str, valores) -> None:
            vals = [valores] if isinstance(valores, str) else list(valores)
            conds.append(f"i.{coluna} IN ({', '.join('?' for _ in vals)})")
            params.extend(v.strip() for v in vals)

        if municipio:
            conds.append("lower(i.municipio) = lower(?)")
            params.append(sem_acento(municipio))
        if cod_municipio_ibge:
            conds.append("i.cod_municipio_ibge = ?")
            params.append(cod_municipio_ibge)
        if ind_status:
            em("ind_status", [ind_status.upper()] if isinstance(ind_status, str) else ind_status)
        if ind_tipo:
            em("ind_tipo", [ind_tipo.upper()] if isinstance(ind_tipo, str) else ind_tipo)
        if des_condic:
            em("des_condic", des_condic)
        for col, op, val in (
            ("num_area", ">=", area_min),
            ("num_area", "<=", area_max),
            ("mod_fiscal", ">=", mod_fiscal_min),
            ("mod_fiscal", "<=", mod_fiscal_max),
        ):
            if val is not None:
                conds.append(f"i.{col} {op} ?")
                params.append(float(val))
        if excluir_cancelados:
            conds.append("i.ind_status <> 'CA'")
        sql = (
            f"{self._select(com_geometria=com_geometria)} FROM {self.fonte.imoveis()} i "
            f"WHERE {' AND '.join(conds)} {self._paginacao(limit, offset)}"
        )
        return self._executar_talvez_sem_geom(sql, params, com_geometria)

    def _executar_talvez_sem_geom(self, sql: str, params: list, com_geometria: bool):
        if com_geometria:
            return self._executar(sql, params)
        return pd.DataFrame(self.con.execute(sql, params).df())
