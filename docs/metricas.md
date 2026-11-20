# Métricas

Todas as medições são reproduzíveis com os scripts citados. Máquina: notebook Windows 11, SSD local, DuckDB 1.5.6.

## 1. A base muda: primeira evidência

| Snapshot de GO (AREA_IMOVEL) | Linhas | Origem |
|---|---:|---|
| 2026-05-03 | 239.600 | base usada no projeto CPSI, data anterior |
| 2026-11-01 | 246.211 | snapshot de referência desta etapa |

Em seis meses a camada pública de GO ganhou **6.611 linhas líquidas (+2,8%)**. Como o Sicar republica a base inteira e não guarda
versões anteriores para download, quem só baixa a versão atual perde essa trajetória. É isso que o histórico do CAR Aberto preserva.
(Diferença líquida: entradas, saídas e mudanças de situação só aparecem no diff por imóvel, previsto para a próxima etapa.)

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
| Índice H3 res 7 compactado (558.723 linhas) | 8.641.928 | 8,6 |

A geometria responde por cerca de 88% do GeoParquet. O nível de zstd foi escolhido por medição:
nível 3 gera 184 MB, nível 19 gera 146 MB; a escrita fica mais lenta (uma vez por snapshot) e a leitura não muda.

## 4. Benchmark local: 20 consultas típicas

`uv run python scripts/bench_basico.py --uf go --snapshot 2026-11-01`

Linha de base sem o CAR Aberto: para responder qualquer pergunta pontual é preciso baixar o zip da UF (**168,6 MB**),
descompactar (860 MB) e abrir o shapefile inteiro (**5,0 s** só para ler, nesta máquina).

Bytes lidos são contados byte a byte por um sistema de arquivos instrumentado registrado no DuckDB, com conexão nova por consulta
(sem cache do DuckDB). "Frio" é conexão nova; "cache" é a segunda execução na mesma conexão. Localmente o cache de disco do
sistema operacional está quente nos dois casos; a medição a frio de verdade é a remota (sessão 2).

| Resumo | Valor |
|---|---:|
| Bytes lidos, mediana | **6,4 MB** (26x menos que o zip) |
| Bytes lidos, máximo | 147,2 MB (filtro de alcance estadual) |
| Latência a frio p50 / p95 | **31 ms** / 165 ms |
| Latência com cache p50 / p95 | 30 ms / 180 ms |
| Latência média a frio | 48 ms |

| # | Tipo | Consulta | Linhas | MB lidos | ms frio |
|---:|---|---|---:|---:|---:|
| 1 | código | cod_imovel com 12 linhas | 12 | 8,11 | 29,5 |
| 2 | código | cod_imovel | 1 | 6,34 | 18,4 |
| 3 | código | cod_imovel | 1 | 8,09 | 25,3 |
| 4 | código | cod_imovel | 1 | 4,79 | 15,4 |
| 5 | código | cod_imovel | 1 | 4,42 | 15,8 |
| 6 | ponto | lon -49,7564 lat -14,9682 | 1 | 6,38 | 29,3 |
| 7 | ponto | lon -50,8104 lat -17,1475 | 2 | 6,22 | 32,1 |
| 8 | ponto | lon -51,8156 lat -16,4875 | 1 | 6,01 | 37,1 |
| 9 | ponto | lon -49,3162 lat -18,5195 | 1 | 6,34 | 41,2 |
| 10 | ponto | lon -49,0478 lat -13,8627 | 1 | 6,27 | 33,6 |
| 11 | bbox | janela 0,01 grau | 17 | 2,88 | 25,9 |
| 12 | bbox | janela 0,01 grau | 16 | 4,10 | 20,5 |
| 13 | bbox | janela 0,1 grau | 193 | 4,51 | 23,9 |
| 14 | bbox | janela 0,1 grau | 198 | 6,85 | 25,0 |
| 15 | filtros | municipio=Rio Verde | 1000 | 37,55 | 64,1 |
| 16 | filtros | cod_municipio_ibge=5208707, sem CA | 853 | 21,65 | 41,7 |
| 17 | filtros | PE em Jatai | 354 | 31,42 | 57,5 |
| 18 | filtros | ind_tipo=AST | 1000 | 144,94 | 162,7 |
| 19 | filtros | notificação pendente em Mineiros | 71 | 29,08 | 55,4 |
| 20 | filtros | 1.000 a 5.000 ha, 15+ MF, sem CA | 1000 | 147,16 | 198,8 |

Resultado bruto: `data/relatorios/bench_local_go_2026-11-01.json`.

### Decisões tomadas a partir da medição

- **Row group de 5 mil linhas, não 50 mil.** Com 50 mil cada row group tem ~28 MB de geometria e a consulta pontual lia ~31 MB;
  com 5 mil lê ~6 MB. O arquivo cresce menos de 1% (146,0 → 147,2 MB). Medição completa (mediana de MB lidos por tipo):

  | Row group | Arquivo | código | ponto | bbox | filtros |
  |---:|---:|---:|---:|---:|---:|
  | 50.000 | 146,0 MB | 30,6 | 31,8 | 44,8 | 138,2 |
  | 10.000 | 146,9 MB | 9,0 | 9,1 | 8,5 | 140,1 |
  | 5.000 | 147,2 MB | 6,3 | 6,3 | 4,3 | 140,0 |
  | 2.000 | 147,7 MB | 4,0 | 4,6 | 2,5 | 141,0 |

- **Filtros em duas etapas.** Primeiro atributos e bbox sem geometria; depois a geometria só dos `id_registro` selecionados,
  com o envelope do resultado podando row groups. Filtros por município caíram de ~138 MB para 22 a 38 MB.

### Limites conhecidos (próximas sessões)

- Filtros de alcance estadual com geometria (AST, faixa de área) ainda leem o arquivo inteiro, porque as linhas estão espalhadas
  pela UF. Sem geometria (`com_geometria=False`, ou export CSV sem geometria) leem só as colunas de atributo.
- Consulta por código lê a coluna `cod_imovel` inteira (~4,5 MB) por falta de poda por estatística. Candidatos: bloom filter ou
  tabela auxiliar ordenada por código.
- Medição remota (httpfs contra bucket, bytes por Range Request, a frio de verdade) fica para a sessão 2.
