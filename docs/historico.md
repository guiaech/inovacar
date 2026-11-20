# Histórico do cadastro | GO, 2026-05-03 a 2026-11-01

Primeiro diff real entre duas versões da camada pública AREA_IMOVEL de Goiás.
Código: [car_aberto/historico/diff.py](../car_aberto/historico/diff.py). Números: `scripts/resumo_historico.py`,
resultado bruto em [evidencias/historico_go_2026-05-03_2026-11-01.json](evidencias/historico_go_2026-05-03_2026-11-01.json).

| Snapshot | Linhas | Procedência |
|---|---:|---|
| 2026-05-03 | 239.600 | data de disponibilização desconhecida; 2026-05-03 é a data interna dos arquivos; baixado em 2026-05-31 |
| 2026-11-01 | 246.211 | data de disponibilização no Sicar; baixado em 2026-11-20 |

Ambos com manifest e SHA-256 em `data/raw/go/{data}/manifest.json`.

## Método

1. Registros com o mesmo `id_registro` nos dois snapshots estão inalterados em situação, condição, área declarada e geometria
   (só `dat_atuali` pode mudar, porque não entra no id).
2. Os demais são pareados por `cod_imovel`. Num código com vários registros, o par é o mais parecido (mesma situação, mesma condição,
   maior IoU); no empate, o registro não cancelado, porque a cópia CA "Cancelado por duplicidade" é a duplicata.
3. Sem par: `novo` ou `removido`, com `escopo = imovel` quando o código inteiro aparece ou some, e `escopo = registro` quando o
   código continua existindo e só uma linha dele aparece ou some.
4. Cada evento leva o intervalo (`snapshot_anterior`, `snapshot_atual`) e, quando `dat_atuali` do registro atual cai dentro dele,
   `data_provavel` (com `fonte_data = dat_atuali`).

Limiares: área declarada (`num_area`) variando mais de 1%; geometria com IoU abaixo de 0,98, calculado em Albers IBGE.

## Números

**35.312 eventos em 21.304 imóveis (cerca de 9% da base) em seis meses.**

| Evento | Escopo | Eventos | Com data provável |
|---|---|---:|---:|
| mudança de dat_atuali | registro | 13.660 | 13.122 |
| novo | imóvel | 6.549 (6.526 códigos) | 6.543 |
| mudança de geometria (IoU abaixo de 0,98) | registro | 5.764 | 5.761 |
| mudança de área (acima de 1%) | registro | 5.003 | 5.000 |
| mudança de ind_status | registro | 2.910 | 1.624 |
| mudança de des_condic | registro | 1.364 | 1.174 |
| novo | registro (código já existia) | 62 | 62 |
| removido | qualquer | **0** | |

Transições de ind_status:

| De | Para | Eventos |
|---|---|---:|
| PE | AT | 2.193 |
| AT | PE | 394 |
| AT | CA | 299 |
| PE | CA | 23 |
| PE | SU | 1 |

### As 10 transições de des_condic mais comuns

| De | Para | Eventos |
|---|---|---:|
| Analisado, aguardando atendimento a notificacao | Aguardando analise | 704 |
| Aguardando analise | Cancelado por solicitacao do proprietario/possuidor | 267 |
| Aguardando analise, apos revisao ou atendimento da notificacao | Aguardando analise | 113 |
| Aguardando analise | Aguardando analise, apos revisao ou atendimento da notificacao | 75 |
| Aguardando analise | Analisado, aguardando atendimento a notificacao | 60 |
| Aguardando analise | Cancelado por decisao administrativa | 43 |
| Analisado, aguardando atendimento a notificacao | Aguardando analise, apos revisao ou atendimento da notificacao | 33 |
| Analisado, aguardando regularizacao ambiental (Lei n 12.651/2012) | Aguardando analise | 12 |
| Aguardando analise | Analisado, em conformidade com a Lei n 12.651/2012 | 12 |
| Analisado, aguardando atendimento a notificacao | Cancelado por solicitacao do proprietario/possuidor | 8 |

### Municípios com mais eventos

Contagem sem `mudanca_dat_atuali`; a coluna de imóveis conta qualquer evento.

| Município | Eventos | Imóveis com evento |
|---|---:|---:|
| Rio Verde | 614 | 634 |
| Jatai | 461 | 456 |
| Niquelandia | 434 | 446 |
| Cavalcante | 423 | 428 |
| Monte Alegre de Goias | 359 | 362 |
| Caiaponia | 351 | 352 |
| Catalao | 333 | 280 |
| Morrinhos | 332 | 293 |
| Itumbiara | 323 | 253 |
| Goias | 309 | 264 |

Em Cavalcante e Monte Alegre de Goiás, 603 dos eventos são imóveis novos.

### Distribuição no tempo (data provável)

| Mês | Eventos |
|---|---:|
| 2026-05 | 4.362 |
| 2026-06 | 4.774 |
| 2026-07 | 5.324 |
| 2026-08 | 5.676 |
| 2026-09 | 6.908 |
| 2026-10 | 6.233 |
| 2026-11 | 9 |

## Três trajetórias reais

Indicadores informativos, derivados só da base pública. Não substituem a análise do órgão estadual.

**1. Notificação atendida com retificação.** `GO-5212303-A59DEEE8F5564913B1AC6335AF378B77`, Leopoldo de Bulhões, inscrito em 2015.
Em maio: PE, "Analisado, aguardando atendimento a notificacao", 8,24 ha, sem atualização desde 2015.
Em novembro (dat_atuali 29/09/2026): AT, "Aguardando analise", 5,46 ha, perímetro redesenhado (IoU 0,54), e uma cópia CA
"Cancelado por duplicidade" com a mesma geometria. É o caminho mais comum da base: 704 cadastros saíram de notificação para nova análise.

**2. Perímetro substituído.** `GO-5200100-A67B5C41AEA249C19E35325D02E42A92`, Abadiânia, inscrito em 2023.
Continua AT, "Aguardando analise", mas a área declarada caiu de 18,73 ha para 2,42 ha e o novo polígono não se sobrepõe ao antigo
(IoU 0; centróide deslocado cerca de 1,3 km), com dat_atuali 10/07/2026. Só a comparação de versões revela isso: a situação e a
condição não mudaram. Há 1.494 mudanças de geometria com IoU abaixo de 0,5.

**3. Redução de área seguida de cancelamento.** `GO-5205406-5B9AB1D01AE14E3F999EB52836CD4C10`, Ceres, inscrito em 2023.
Em maio: AT, 25,94 ha. Em novembro (dat_atuali 28/05/2026): CA, "Cancelado por decisao administrativa", 20,70 ha, IoU 0,80.

## O que o diff ensina sobre a base

- **Nada é apagado.** Nenhum `cod_imovel` de maio sumiu em novembro; cancelamentos ficam na base como CA. A base só cresce, e o
  histórico precisa guardar as versões para mostrar o que mudou dentro dela.
- **dat_atuali não data todas as mudanças.** Só 56% das mudanças de ind_status (1.624 de 2.910) têm dat_atuali dentro do
  intervalo; mudanças de situação feitas pelo órgão nem sempre atualizam esse campo. Para essas, a melhor data disponível é o
  intervalo entre snapshots, e por isso a cadência de captura (mensal) define a precisão da linha do tempo.
- **63 registros novos têm dat_criaca anterior a 03/05/2026** (o mais antigo de 2014). Entraram na camada pública depois de inscritos; um deles
  é o código TO-1702000 presente na base de GO.
- O snapshot de maio não tem data de disponibilização confirmada. Os próximos (01/12, 01/01) terão, e permitirão diffs mensais.
