# Dicionário de dados | camada imoveis (AREA_IMOVEL)

Versão 0.1 | referência: GO, disponibilização de 2026-11-01 (246.211 linhas).
Fonte oficial: [Dicionario_de_Dados_SICAR.pdf](fonte/Dicionario_de_Dados_SICAR.pdf), baixado da consulta pública do Sicar.
Esquema formal: [schemas/imovel.json](../schemas/imovel.json) (JSON Schema 2020-12).

Formato publicado: GeoParquet 1.1, geometria MultiPolygon em EPSG:4674 (SIRGAS 2000), particionado por `uf` e `snapshot`.
Todo campo derivado é marcado como tal. Nenhum campo pessoal existe na camada pública (ver [lgpd.md](lgpd.md), a escrever).

## Campos de origem (Sicar)

| Campo | Tipo publicado | Tipo no shapefile | Significado (oficial) | Valores reais em GO 2026-11-01 |
|---|---|---|---|---|
| cod_tema | string | C(254) | Código do tema de uso do solo | só `AREA_IMOVEL` |
| nom_tema | string | C(254) | Nome do tema | só `Area do Imovel` |
| cod_imovel | string | C(254) | Número de inscrição do imóvel no Sicar | formato `UF-NNNNNNN-HEX32`, 43 caracteres; **não é único** (ver divergências) |
| mod_fiscal | float64 | N(33,31) | Tamanho do imóvel em módulos fiscais | 0 a 12.339,33 |
| num_area | float64 (ha) | N(33,31) | Área bruta informada na inscrição | 0 a 491.335,26 ha; 4 linhas com 0 |
| ind_status | string | C(254) | Situação do cadastro: AT ativo, PE pendente, SU suspenso, CA cancelado | AT 218.109, PE 23.931, CA 4.170, SU 1 |
| ind_tipo | string | C(254) | IRU imóvel rural, AST assentamento de reforma agrária, PCT povos e comunidades tradicionais | IRU 244.658, AST 1.534, PCT 19 |
| des_condic | string | C(254) | Condição da análise do cadastro | 12 valores, tabela abaixo |
| municipio | string | C(254) | Município onde o imóvel está localizado | 246 nomes, ASCII sem acento |
| cod_estado | string | C(254) | UF | só `GO` |
| dat_criaca | date | C(254) `dd/mm/aaaa` | Data da inscrição | 2014-05-07 a 2026-10-31; 4 nulos |
| dat_atuali | date | C(254) `dd/mm/aaaa` | Data da última modificação da inscrição | 2014-05-07 a 2026-11-01; 532 nulos (524 em CA) |
| geometry | MultiPolygon | Polygon/MultiPolygon | Perímetro do imóvel | 1 geometria inválida corrigida com make_valid |

### Valores de des_condic

| des_condic | linhas |
|---|---:|
| Aguardando analise | 220.795 |
| Analisado, aguardando atendimento a notificacao | 19.762 |
| Cancelado por decisao administrativa | 2.266 |
| Cancelado por duplicidade | 1.368 |
| Aguardando analise, apos revisao ou atendimento da notificacao | 1.158 |
| Cancelado por solicitacao do proprietario/possuidor | 522 |
| Analisado, em conformidade com a Lei n 12.651/2012 | 188 |
| Analisado, aguardando regularizacao ambiental (Lei n 12.651/2012) | 102 |
| Cancelado por alteracao na base de municipios | 19 |
| Analisado, em conformidade com a Lei n 12.651/2012, com ativos ambientais | 18 |
| Em analise | 10 |
| Cancelado por decisao judicial | 3 |

## Campos derivados (CAR Aberto)

| Campo | Tipo | Como é calculado |
|---|---|---|
| id_registro | string | Chave da linha. 16 hex do SHA-1 de `cod_imovel`, `ind_status`, `des_condic`, `num_area` e WKB da geometria; sufixo `-n` para linhas idênticas. A mesma linha em snapshots diferentes gera o mesmo id. |
| cod_municipio_ibge | string (7 dígitos) | Segundo bloco de `cod_imovel`. É o município **da inscrição**, não necessariamente o de `municipio` (ver divergências). |
| area_ha | float64 | Área da geometria em Albers de área igual (padrão IBGE: `+proj=aea +lat_0=-12 +lon_0=-54 +lat_1=-2 +lat_2=-22 +x_0=5000000 +y_0=10000000 +ellps=GRS80`), em hectares. |
| h3_centroide_r9 | string | Célula H3 res 9 do centróide da geometria. Só atributo, não serve para busca espacial. |
| bbox | struct(xmin, ymin, xmax, ymax) | Covering do GeoParquet 1.1, usado para pular row groups. |
| uf, snapshot | partição | `uf` minúscula; `snapshot` é a data de disponibilização no Sicar (aaaa-mm-dd), não a data do download. |

Tabela auxiliar `imovel_h3` (`id_registro`, `cod_imovel`, `h3`): cobertura de cada polígono em H3 res 7 com containment
OVERLAPPING, compactada. Em GO: 558.723 linhas, mediana de 2 células por imóvel, máximo de 192.

## Divergências entre o dicionário oficial e o dado real

1. **cod_imovel não é único.** O oficial diz "número de inscrição único". Em GO há 502 códigos com mais de uma linha
   (1.351 linhas, grupos de 2 a 14). O caso típico é a mesma geometria com uma linha AT e outra CA
   "Cancelado por duplicidade". Só 3 grupos são cópias idênticas. Por isso a chave da base é `id_registro`, e a consulta
   por código devolve todas as linhas.
2. **Datas são texto.** O oficial tipifica `dat_criaca` e `dat_atuali` como texto; o conteúdo é `dd/mm/aaaa`. Publicamos como
   `date`. Não há data inválida; há 4 nulos em `dat_criaca` e 532 em `dat_atuali`.
3. **Valores de des_condic não estão no oficial.** Ele só descreve o campo. A lista real tem 12 valores (tabela acima).
4. **cod_tema e nom_tema** são descritos como tema de uso do solo, com vários exemplos; na camada AREA_IMOVEL têm valor único.
5. **Sem acentos e sem .cpg.** O oficial grafa nomes com acento; o dado vem em ASCII puro ("Goias", "analise", "Lei n 12.651").
   O shapefile não traz `.cpg`; lemos como latin1. Busca por município ignora acento e caixa.
6. **Código do município não existe como campo.** Derivamos `cod_municipio_ibge` de `cod_imovel`. Em 709 linhas (0,29%)
   o nome em `municipio` é de um vizinho do município do código, e 4 imóveis da base de GO têm código de outra UF
   (DF-5300108, TO-1702000, MG-3126208), todos com `municipio` de GO. Agregados por município devem usar `municipio`
   associado a uma tabela oficial de códigos do IBGE, não o código derivado.
7. **Combinações incoerentes de situação.** 8 linhas AT e 1 PE têm `des_condic` "Cancelado por duplicidade"
   ou outro cancelamento. Mantidas como estão.
8. **num_area igual a 0** em 4 linhas com geometria de área desprezível. Mantidas; excluídas só do cálculo de divergência de área.

Qualidade de área: a área calculada em Albers difere de `num_area` com mediana de 0,046% e p95 de 0,14%;
0,013% das linhas passam de 1%.

## Uso

Cancelados (CA) ficam na base. Filtros devolvem todas as situações por padrão; `excluir_cancelados=True` remove CA.
Indicadores derivados são informativos e não substituem a análise do órgão estadual.
