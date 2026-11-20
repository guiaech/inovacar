# Peculiaridades do dado publicado pelo Sicar

Registro por UF do que o shapefile da consulta pública traz de diferente do esperado.
O código trata cada caso de forma genérica; aqui fica o que foi observado.

## GO | disponibilização 2026-11-01

- Arquivos: `AREA_IMOVEL_1.{shp,shx,dbf,prj,fix}` dentro de `AREA_IMOVEL.zip` (168.566.814 bytes). O `.fix` é índice espacial do
  software de origem e não é usado.
- **Texto em ASCII sem acentos.** Nenhum byte acima de 127 em todo o `.dbf` (ex.: "Goias", "Aguardando analise",
  "Lei n 12.651/2012", "Sitio d'Abadia"). Não há `.cpg`; a leitura usa latin1, que é compatível. Consultas por nome
  normalizam acento e caixa do lado de quem pergunta.
- `.prj` é SIRGAS 2000 (EPSG:4674), eixos lon/lat.
- Todos os campos de texto são `C(254)` com espaços à direita; números são `N(33,31)`; datas são texto `dd/mm/aaaa`.
- 246.211 linhas, 502 `cod_imovel` repetidos (1.351 linhas), 4 códigos de outra UF, 1 geometria inválida.
- Detalhes e contagens: [dicionario.md](dicionario.md).
