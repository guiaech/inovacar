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
   (só `dat_atuali` pode mudar, porque não entra no id). Data nula nos dois lados não conta como mudança.
2. Os demais são pareados por `cod_imovel`. Num código com vários registros, o par é o mais parecido (mesma situação, mesma condição,
   maior IoU); no empate, o registro não cancelado, porque a cópia CA "Cancelado por duplicidade" é a duplicata.
3. Sem par: `novo` ou `removido`, com `escopo = imovel` quando o código inteiro aparece ou some, e `escopo = registro` quando o
   código continua existindo e só uma linha dele aparece ou some.
4. Cada evento leva o intervalo (`snapshot_anterior`, `snapshot_atual`) e, quando `dat_atuali` do registro atual cai dentro dele
   (início exclusivo, fim inclusivo), `data_provavel` com `fonte_data = dat_atuali`. Sem isso, a única datação é o intervalo.

Limiares: área declarada (`num_area`) variando mais de 1%; geometria com IoU abaixo de 0,98, calculado em Albers IBGE.

Unidade de contagem: um **evento** é uma faceta da mudança. Uma retificação pode gerar até cinco eventos no mesmo registro
(geometria, área, `dat_atuali`, situação, condição). Para leitura de gestão, use a contagem de registros abaixo.

## Números

| Contagem | Valor |
|---|---:|
| Registros novos | **6.611** (6.549 em códigos novos, 62 em códigos que já existiam) |
| Registros removidos | **0** |
| Registros existentes que mudaram algo | **14.490** |
| dos quais com área ou perímetro alterado | 5.941 |
| dos quais com mudança de situação (ind_status) | 2.910 |
| Imóveis (cod_imovel) com qualquer evento | 20.785 (8,4% da base de novembro) |
| Eventos (facetas) | 34.780 |

| Evento | Escopo | Eventos | Com data provável |
|---|---|---:|---:|
| mudança de dat_atuali | registro | 13.128 | 13.122 |
| novo | imóvel | 6.549 | 6.543 |
| mudança de geometria (IoU abaixo de 0,98) | registro | 5.764 | 5.761 |
| mudança de área (acima de 1%) | registro | 5.003 | 5.000 |
| mudança de ind_status | registro | 2.910 | 1.624 |
| mudança de des_condic | registro | 1.364 | 1.174 |
| novo | registro (código já existia) | 62 | 62 |

4.826 das 5.764 mudanças de geometria vêm junto com mudança de área; 1.494 têm IoU abaixo de 0,5.

### Transições de ind_status e quanto delas tem data

| De | Para | Registros | Com dat_atuali no intervalo |
|---|---|---:|---:|
| PE | AT | 2.193 | 1.312 (60%) |
| AT | PE | 394 | 79 (20%) |
| AT | CA | 299 | 210 (70%) |
| PE | CA | 23 | 23 (100%) |
| PE | SU | 1 | 0 |

### As 10 transições de des_condic mais comuns

| De | Para | Registros |
|---|---|---:|
| Analisado, aguardando atendimento a notificacao | Aguardando analise | 704 |
| Aguardando analise | Cancelado por solicitacao do proprietario/possuidor | 267 |
| Aguardando analise, apos revisao ou atendimento da notificacao | Aguardando analise | 113 |
| Aguardando analise | Aguardando analise, apos revisao ou atendimento da notificacao | 75 |
| Aguardando analise | Analisado, aguardando atendimento a notificacao | 60 |
| Aguardando analise | Cancelado por decisao administrativa | 43 |
| Analisado, aguardando atendimento a notificacao | Aguardando analise, apos revisao ou atendimento da notificacao | 33 |
| Aguardando analise | Analisado, em conformidade com a Lei n 12.651/2012 | 12 |
| Analisado, aguardando regularizacao ambiental (Lei n 12.651/2012) | Aguardando analise | 12 |
| Analisado, aguardando atendimento a notificacao | Cancelado por solicitacao do proprietario/possuidor | 8 |

### Municípios com mais eventos

Eventos sem `mudanca_dat_atuali`; imóveis com qualquer evento.

| Município | Eventos | Imóveis com evento |
|---|---:|---:|
| Rio Verde | 614 | 629 |
| Jatai | 461 | 450 |
| Niquelandia | 434 | 428 |
| Cavalcante | 423 | 428 |
| Monte Alegre de Goias | 359 | 361 |
| Caiaponia | 351 | 348 |
| Catalao | 333 | 272 |
| Morrinhos | 332 | 281 |
| Itumbiara | 323 | 252 |
| Goias | 309 | 250 |

### Distribuição no tempo (eventos com data provável, todas as facetas)

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

Códigos parcialmente mascarados neste documento: imóvel pequeno pode ser de pessoa natural (LGPD; `docs/lgpd.md` em elaboração).
A consulta completa é feita pela API, que devolve o dado público oficial. Leitura descritiva dos campos publicados; não é
avaliação do cadastro e não substitui a análise do órgão estadual.

**1. Saída da notificação com perímetro redesenhado.** `GO-5212303-A59D…`, Leopoldo de Bulhões, inscrito em 2015.
Em maio: PE, "Analisado, aguardando atendimento a notificacao", 8,24 ha, dat_atuali de 2015.
Em novembro (dat_atuali 29/09/2026): AT, "Aguardando analise", 5,46 ha, perímetro com IoU 0,54 em relação ao anterior,
e uma segunda linha CA "Cancelado por duplicidade" com a mesma geometria nova. Entre as transições de condição, sair de
"aguardando atendimento a notificacao" para "Aguardando analise" é a mais comum (704 registros).

**2. Perímetro substituído sem mudança de situação.** `GO-5200100-A67B…`, Abadiânia, inscrito em 2023.
Continua AT, "Aguardando analise", mas a área declarada passou de 18,73 ha para 2,42 ha e o novo polígono não se sobrepõe ao
antigo (IoU 0; centróide deslocado cerca de 1,3 km), com dat_atuali 10/07/2026. Situação e condição não mudaram: só a comparação
de versões mostra a troca. O diff ainda registra isso como mudança de geometria; um tipo próprio de "substituição de perímetro"
está em avaliação.

**3. Área menor e cancelamento no mesmo intervalo.** `GO-5205406-5B9A…`, Ceres, inscrito em 2023.
Em maio: AT, 25,94 ha. Em novembro (dat_atuali 28/05/2026): CA, "Cancelado por decisao administrativa", 20,70 ha, IoU 0,80.
Com um único intervalo não dá para saber a ordem das duas mudanças; snapshots mensais resolvem isso.

## O que o diff mostra (GO, um intervalo)

- **Nenhum código sumiu.** Entre estes dois snapshots de GO, nenhum `cod_imovel` de maio deixou de existir em novembro;
  cancelamentos permaneceram na base como CA. A confirmar com outras UFs e intervalos.
- **dat_atuali data bem umas transições e mal outras.** AT→PE tem data no intervalo em só 20% dos casos, contra 60% em PE→AT e
  70% em AT→CA (tabela acima). Para os demais, a única datação é o intervalo entre snapshots; por isso a cadência de captura
  (mensal) define a precisão da linha do tempo. Quando há retificação no mesmo período, dat_atuali data a retificação, não
  necessariamente a mudança de situação.
- **63 registros novos têm dat_criaca anterior a 03/05/2026** (o mais antigo de 2014). Entraram na camada pública depois de
  inscritos; um deles é o código TO-1702000 presente na base de GO.
- O snapshot de maio não tem data de disponibilização confirmada. Os próximos (01/12, 01/01) terão, e permitirão diffs mensais.

## Limitações conhecidas do método

- Limiares relativos: 67 mudanças de área ficam abaixo de 0,1 ha; IoU fixo pesa mais em imóvel pequeno. Avaliar piso absoluto.
- Registros com `dat_atuali` exatamente igual à data inicial (6) ficam sem data provável.
- O sufixo ordinal de `id_registro` (só em linhas idênticas) depende da ordem das linhas no arquivo.
