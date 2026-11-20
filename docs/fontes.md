# Fontes de dados do CAR e geoserviços oficiais

Levantamento feito em 2026-11-20, por acesso direto aos endereços públicos (sem login e sem contornar captcha).
O que depende de login gov.br ficou marcado como pendente de conferência manual.

## 1. Base de downloads por UF (fonte usada pelo CAR Aberto)

- Consulta pública do Sicar, base de downloads por UF: shapefile zipado por camada (ex.: `AREA_IMOVEL.zip`), com data de
  disponibilização exibida na página.
- Download manual, com captcha. O CAR Aberto não automatiza o captcha.
- Só a versão atual de cada UF fica disponível. Versões anteriores precisam ser guardadas por quem baixou
  (ver [historico.md](historico.md)).
- Observação técnica: `consultapublica.car.gov.br/publico/imoveis/index` responde com redirecionamento circular
  http ↔ https para clientes automatizados (301 para https, 302 de volta para http). No navegador funciona.

## 2. Nova plataforma de consulta pública: menu Geoserviços

Endereço: `https://consulta.car.gov.br/`, aplicação web com rota `/geoservices`, rotulada "Baixe os dados públicos do SICAR".
O que dá para afirmar a partir do código público da página (`/assets/index-DSFSP634.js`, coletado em 2026-11-20):

| Item | O que existe |
|---|---|
| Acesso | Exige login gov.br ("Faça o login com gov.br para ter acesso ao conteudo de geosserviço") e reCAPTCHA |
| Recorte | Por UF, município e tema ambiental (o front envia `{uf, city, themes}`) |
| Formatos de download | CSV e GPKG (botões da tabela de temas) |
| Como o arquivo é gerado | O backend devolve um link de GeoServer por recorte (`geoServices/getGeoServerLayerLink`, campo `linkWfs`) |
| Outras chamadas | `geoServices/getGeoServerLayerNames`, `geoServices/getImageGeoservice/{id}` (imagem), `map/getLayers` |
| Mapa | WMS do GeoServer com filtro `CQL_FILTER` e `viewParams` por código do imóvel; camadas citadas no front: imóveis rurais, terras indígenas, unidades de conservação, embargos |

## 3. GeoServer do CAR acessado sem login

`https://geoserver.car.gov.br/geoserver/ows`

| Serviço | Resposta anônima em 2026-11-20 |
|---|---|
| WMS 1.3.0 GetCapabilities | 200, mas só a camada raiz "GeoServer Web Map Service": **nenhuma camada publicada** |
| WFS 2.0.0 GetCapabilities | 200, **nenhum FeatureType publicado**; limite padrão `CountDefault = 10000`; saída GML 3.2 |

Conclusão: o GeoServer existe e é a origem dos downloads e do mapa da nova plataforma, mas não oferece camada OGC aberta
para acesso anônimo. O acesso passa pela aplicação, com login e captcha.

## 4. APIs SICAR no catálogo Conecta

O catálogo Conecta gov.br lista APIs SICAR (consulta por CPF/CNPJ, por imóvel e por tema). São voltadas a órgãos públicos
integrados ao Conecta. O CAR Aberto as complementa e não concorre com elas.
- https://www.gov.br/conecta/catalogo/apis/sicar-imovel
- https://www.gov.br/conecta/catalogo/apis/sicar-tema
- https://www.gov.br/conecta/catalogo/apis/consulta-sicar-cpf-cnpj

## 5. Frequência de atualização

| Fonte | Frequência observada |
|---|---|
| Base de downloads por UF | Em nov/2026 todas as UFs com disponibilização em 01 ou 02/11. Indício de ciclo mensal, a confirmar em 01/12 |
| Geoserviços da nova plataforma | **Pendente.** Não verificável sem login; conferir manualmente se os arquivos indicam data de referência |
| GeoServer anônimo | Não se aplica: sem camadas públicas |

## Pendências (conferência manual com login gov.br)

1. Abrir `/geoservices` logado e anotar: temas disponíveis, se o recorte por município inclui AREA_IMOVEL, tamanho de um
   download de município, se o arquivo informa data de referência, se o `linkWfs` funciona fora da sessão e por quanto tempo.
2. Conferir se a nova plataforma oferece algum histórico ou versão anterior.
3. Registrar aqui, com print, sem mostrar o captcha.

## O que isso muda para o CAR Aberto

- A oferta oficial melhorou: o recorte por município reduz o download em relação ao zip da UF.
- Continua sem: acesso anônimo e automatizável, consulta pontual por código ou coordenada, API OGC aberta, histórico entre
  versões e leitura parcial por HTTP. É esse o espaço do CAR Aberto, como padrão que o próprio SFB/MGI pode adotar para publicar
  a base em formato cloud-native, reaproveitando o GeoServer existente como fonte.
