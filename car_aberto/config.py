"""Parametros fixos do pipeline. Mudar aqui muda a base inteira."""

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_DADOS = RAIZ / "data"
DIR_RAW = DIR_DADOS / "raw"
DIR_PARQUET = DIR_DADOS / "parquet"
DIR_H3 = DIR_DADOS / "h3"
DIR_RELATORIOS = DIR_DADOS / "relatorios"

# CRS de armazenamento: SIRGAS 2000 geografico, igual ao Sicar. Nunca converter para 4326.
CRS_BASE = "EPSG:4674"

# Albers de area igual, padrao IBGE para o Brasil. Usado so para calcular area.
CRS_AREA = (
    "+proj=aea +lat_0=-12 +lon_0=-54 +lat_1=-2 +lat_2=-22 "
    "+x_0=5000000 +y_0=10000000 +ellps=GRS80 +units=m +no_defs"
)

# Encoding padrao quando o shapefile nao traz .cpg.
ENCODING_PADRAO = "latin1"

# Esquema da camada AREA_IMOVEL (minusculas). Falta de qualquer coluna e erro.
COLUNAS_AREA_IMOVEL = [
    "cod_tema",
    "nom_tema",
    "cod_imovel",
    "mod_fiscal",
    "num_area",
    "ind_status",
    "ind_tipo",
    "des_condic",
    "municipio",
    "cod_estado",
    "dat_criaca",
    "dat_atuali",
]
COLUNAS_DATA = ["dat_criaca", "dat_atuali"]
FORMATO_DATA = "%d/%m/%Y"

# Codigo IBGE da UF (dois primeiros digitos do municipio).
COD_IBGE_UF = {"go": "52", "pa": "15", "rs": "43", "ba": "29"}

# H3
H3_RES_COBERTURA = 7
H3_RES_CENTROIDE = 9

# GeoParquet
ROW_GROUP = 50_000
COMPRESSAO = "zstd"
# Nivel 19: em GO reduz o arquivo de 184 MB (nivel 3) para 146 MB. Escrita mais lenta,
# feita uma vez por snapshot; a leitura nao muda.
COMPRESSAO_NIVEL = 19
