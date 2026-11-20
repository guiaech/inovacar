# CAR Aberto

Pipeline e padrão aberto para publicar a base do Cadastro Ambiental Rural (CAR) em formato cloud-native.

Hoje, consultar um único imóvel de Goiás exige baixar o zip da UF inteira (168,6 MB) e abrir 860 MB de shapefile.
No CAR Aberto, a mesma consulta lê em mediana 6,4 MB de um GeoParquet otimizado, em cerca de 30 ms
(medição local, [docs/metricas.md](docs/metricas.md)), sem tocar no Sicar.

Pronto: ingestão validada, GeoParquet 1.1 (Hilbert, bbox, zstd), índice H3, consultas por código, ponto, bbox e filtros.
Em desenvolvimento: histórico de mudanças entre disponibilizações, API OGC API Features e implantação pública.

Projeto inscrito no InovaCAR, Ciclo 1, Desafio 3 (Edital 299/2026).

## Uso rápido

```bash
uv sync --group dev
uv run python -m car_aberto.ingestao.para_geoparquet --uf go --snapshot 2026-11-01
uv run python -m car_aberto.ingestao.indice_h3 --uf go --snapshot 2026-11-01
uv run pytest
```

O dado bruto vem da consulta pública do Sicar (download manual por UF) e fica em
`data/raw/{uf}/{aaaa-mm-dd}/`, onde a data é a data de disponibilização.

- Dicionário de dados: [docs/dicionario.md](docs/dicionario.md)
- Métricas: [docs/metricas.md](docs/metricas.md)

Indicadores derivados são informativos e não substituem a análise do órgão estadual.

Licença Apache-2.0.
