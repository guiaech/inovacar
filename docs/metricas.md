# Métricas

Todas as medições são reproduzíveis com os scripts citados. Máquina: notebook Windows 11, SSD local, DuckDB 1.5.6.

## 1. A base muda: primeira evidência

| Snapshot de GO (AREA_IMOVEL) | Linhas | Origem |
|---|---:|---|
| 2026-05-03 (data interna dos arquivos; disponibilização desconhecida) | 239.600 | base usada no projeto CPSI, baixada em 2026-05-31, com manifest e SHA-256 |
| 2026-11-01 | 246.211 | snapshot de referência, baixado em 2026-11-20, com manifest e SHA-256 |

Entre as duas versões a camada pública de GO ganhou **6.611 linhas (+2,8%)**, contando linhas e não imóveis
(a base tem códigos repetidos e cancelados). A consulta pública oferece para download só a versão atual de cada UF;
quem não guardou a versão anterior perde essa trajetória. É isso que o histórico do CAR Aberto preserva.
O diff por registro está em [historico.md](historico.md): 35.312 eventos em 21.304 imóveis no intervalo.
Ingestão de maio: [evidencias/ingestao_go_2026-05-03.json](evidencias/ingestao_go_2026-05-03.json)
(1 geometria corrigida, divergência mediana de área 0,051%).

## 2. Ingestão de GO, 2026-11-01

`uv run python -m car_aberto.ingestao.para_geoparquet --uf go --snapshot 2026-11-01`

| Item | Valor |
|---|---|
| Linhas lidas | 246.211 |
| Geometrias inválidas corrigidas (make_valid) | 1 |
| Geometrias perdidas na correção | 0 |
| Área calculada (Albers IBGE) x `num_area`: divergência mediana | **0,046%** (meta: abaixo de 1%) |
| Divergência p95 | 0,14% |
| Linhas com divergência acima de 1% | 0,013% |
| Tempo de leitura + limpeza | ~15 s |
| Validação externa (`gpio check all`) | 30 checagens da especificação aprovadas, ordem espacial confirmada, bbox covering, ZSTD |


## 3. Tamanho

| Artefato | Bytes | MB |
|---|---:|---:|
| Zip original do Sicar (`AREA_IMOVEL.zip`) | 168.566.814 | 168,6 |
| Shapefile descompactado | 860.438.492 | 860,4 |
| GeoParquet 1.1 (Hilbert, bbox, zstd 19, row group 5 mil) | 147.161.006 | 147,2 |
| Índice H3 res 7 compactado (558.723 linhas, row group 10 mil) | 9.108.521 | 9,1 |
| Índice por código (246.211 linhas, row group 2 mil) | 15.385.776 | 15,4 |
| **Total publicado por snapshot** | 171.655.303 | **171,7** |

A geometria responde por cerca de 88% do GeoParquet. O nível de zstd foi escolhido por medição:
nível 3 gera 184 MB, nível 19 gera 146 MB; a escrita fica mais lenta (uma vez por snapshot) e a leitura não muda.
O conjunto publicado (dados + dois índices) tem praticamente o tamanho do zip, mas pode ser lido em partes.

## 4. Benchmark local: 20 consultas típicas

`uv run python scripts/bench_basico.py --uf go --snapshot 2026-11-01`

Linha de base sem o CAR Aberto: para responder qualquer pergunta pontual é preciso baixar o zip da UF (**168,6 MB**),
descompactar (860 MB) e abrir o shapefile inteiro (**4,9 a 9,8 s** só para ler, nesta máquina, conforme a carga).

Bytes lidos são contados byte a byte por um sistema de arquivos instrumentado registrado no DuckDB
([car_aberto/consulta/medicao.py](../car_aberto/consulta/medicao.py)), com conexão nova por consulta (sem cache do DuckDB).
"Frio" é conexão nova; "cache" é a segunda execução na mesma conexão. Localmente o cache de disco do sistema operacional está
quente nos dois casos; a medição a frio de verdade é a remota (pendente).

**Bytes são determinísticos; latência local não.** Neste notebook a mesma consulta varia até cerca de 50% entre rodadas
(ex.: filtro Rio Verde entre 75 e 109 ms na mesma tarde; leitura do shapefile entre 4,9 e 9,8 s). Use os bytes para comparar
versões e trate as latências como ordem de grandeza.

| Resumo (2026-11-20, sessão 2) | Valor |
|---|---:|
| Bytes lidos localmente, mediana | **4,0 MB** (sessão 1: 6,4 MB; zip: 168,6 MB, sem contar o tempo de download) |
| Bytes lidos, máximo | 147,2 MB (filtro de alcance estadual) |
| Latência a frio p50 / p95 | 42 ms / 320 ms |
| Latência com cache p50 / p95 | 53 ms / 330 ms |

| # | Tipo | Consulta | Linhas | MB lidos sessão 1 | MB lidos sessão 2 | ms frio |
|---:|---|---|---:|---:|---:|---:|
| 1 | código | cod_imovel com 12 linhas | 12 | 8,11 | 5,52 | 53,5 |
| 2 | código | cod_imovel | 1 | 6,34 | 2,93 | 42,6 |
| 3 | código | cod_imovel | 1 | 8,09 | 3,95 | 50,7 |
| 4 | código | cod_imovel | 1 | 4,79 | 2,71 | 39,0 |
| 5 | código | cod_imovel | 1 | 4,42 | 3,12 | 38,5 |
| 6 | ponto | lon -49,7564 lat -14,9682 | 1 | 6,38 | 3,81 | 35,6 |
| 7 | ponto | lon -50,8104 lat -17,1475 | 2 | 6,22 | 3,63 | 44,3 |
| 8 | ponto | lon -51,8156 lat -16,4875 | 1 | 6,01 | 3,43 | 40,9 |
| 9 | ponto | lon -49,3162 lat -18,5195 | 1 | 6,34 | 3,76 | 39,4 |
| 10 | ponto | lon -49,0478 lat -13,8627 | 1 | 6,27 | 3,68 | 42,0 |
| 11 | bbox | janela 0,01 grau | 17 | 2,88 | 2,88 | 33,7 |
| 12 | bbox | janela 0,01 grau | 16 | 4,10 | 4,10 | 30,2 |
| 13 | bbox | janela 0,1 grau | 193 | 4,51 | 4,51 | 33,0 |
| 14 | bbox | janela 0,1 grau | 198 | 6,85 | 6,85 | 33,8 |
| 15 | filtros | municipio=Rio Verde | 1000 | 37,55 | 37,55 | 109,0 |
| 16 | filtros | cod_municipio_ibge=5208707, sem CA | 853 | 21,65 | 21,65 | 113,7 |
| 17 | filtros | PE em Jatai | 354 | 31,42 | 31,42 | 100,6 |
| 18 | filtros | ind_tipo=AST | 1000 | 144,94 | 144,94 | 317,4 |
| 19 | filtros | notificação pendente em Mineiros | 71 | 29,08 | 29,08 | 81,8 |
| 20 | filtros | 1.000 a 5.000 ha, 15+ MF, sem CA | 1000 | 147,16 | 147,16 | 363,4 |

Com dois snapshots no lago, o primeiro desenho (glob `uf=*/snapshot=*`) fazia o DuckDB ler o rodapé de cada arquivo antes
de descartá-lo pela partição: +0,26 MB por snapshot em GO, que cresceria com o histórico mensal. A consulta agora aponta direto
para `uf={uf}/snapshot={data}/`, e bbox e filtros voltaram exatamente aos bytes da sessão 1.

Resultado bruto: [evidencias/bench_local_go_2026-11-01.json](evidencias/bench_local_go_2026-11-01.json);
relatório de ingestão com a saída do `gpio check`: [evidencias/ingestao_go_2026-11-01.json](evidencias/ingestao_go_2026-11-01.json).

### Decisões tomadas a partir da medição

- **Row group de 5 mil linhas no GeoParquet, não 50 mil.** Com 50 mil cada row group tem ~28 MB de geometria e a consulta pontual
  lia ~31 MB; com 5 mil lê ~6 MB. O arquivo cresce menos de 1% (146,0 → 147,2 MB). Mediana de MB lidos por tipo:

  | Row group | Arquivo | código | ponto | bbox | filtros |
  |---:|---:|---:|---:|---:|---:|
  | 50.000 | 146,0 MB | 30,6 | 31,8 | 44,8 | 138,2 |
  | 10.000 | 146,9 MB | 9,0 | 9,1 | 8,5 | 140,1 |
  | 5.000 | 147,2 MB | 6,3 | 6,3 | 4,3 | 140,0 |
  | 2.000 | 147,7 MB | 4,0 | 4,6 | 2,5 | 141,0 |

- **Filtros em duas etapas.** Primeiro atributos e bbox sem geometria; depois a geometria só dos `id_registro` selecionados,
  com o envelope do resultado podando row groups. Filtros por município caíram de ~138 MB para 22 a 38 MB.

- **Índice H3 com row group de 10 mil linhas, não 500 mil.** Mediana de 30 consultas por ponto:

  | Row group do índice H3 | Arquivo | MB lidos do índice | MB lidos no total |
  |---:|---:|---:|---:|
  | 500.000 | 8,6 MB | 3,00 | 6,34 |
  | 50.000 | 9,1 MB | 0,69 | 4,12 |
  | 20.000 | 9,1 MB | 0,45 | 3,86 |
  | 10.000 | 9,1 MB | 0,42 | 3,83 |
  | 5.000 | 9,2 MB | 0,41 | 3,82 |
  | 2.000 | 9,5 MB | 0,44 | 3,85 |

  Platô a partir de 10 a 20 mil. Medido ainda com glob sobre os dois snapshots; os ~3,4 MB restantes são o bloco de geometria de um row group do GeoParquet.

- **Tabela auxiliar ordenada por cod_imovel.** O GeoParquet é ordenado por Hilbert, então o código fica espalhado e a busca lia a
  coluna `cod_imovel` inteira. A tabela (`cod_imovel`, `id_registro`, bbox) isola o código em um row group; o bbox devolvido poda
  o GeoParquet. Mediana de 30 consultas por código:

  | Row group da tabela por código | Arquivo | MB lidos da tabela | MB lidos no total |
  |---:|---:|---:|---:|
  | 50.000 | 15,9 MB | 3,25 | 6,80 |
  | 20.000 | 16,1 MB | 1,33 | 4,89 |
  | 5.000 | 15,7 MB | 0,36 | 3,92 |
  | 2.000 | 15,4 MB | 0,22 | 3,78 |
  | 1.000 | 15,4 MB | 0,25 | 3,81 |

### Limites conhecidos

- O piso da consulta pontual é o bloco de geometria de um row group (~3 MB com 5 mil linhas). Para descer mais, row groups de
  2 mil linhas (medido: ~4 MB no total contra ~6 MB) ou leitura por página com page index; a decidir pela medição remota.
- Filtros de alcance estadual com geometria (AST, faixa de área) ainda leem o arquivo inteiro, porque as linhas estão espalhadas
  pela UF. Sem geometria (`com_geometria=False`, ou export CSV sem geometria) leem só as colunas de atributo.
- Medição remota (httpfs contra bucket, bytes por Range Request, a frio de verdade) pendente: exige o bucket da etapa de deploy.
