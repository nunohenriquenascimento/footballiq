# FI-009.1 — Tendências competitivas descritivas

O módulo `footballiq.trends` recebe um `FactualReport` produzido pelo Analytics
Engine, sem alterar o relatório ou o contrato JSON de exportação v1. Não abre
ficheiros, rede, PostgreSQL ou Ollama. Não acrescenta dependências. Os resultados
usam a versão de fórmula `footballiq.trends.v1`.

## Dados e cobertura

Utilizam-se exclusivamente os zero a cinco jogos já selecionados pelo contrato.
Não se procuram jogos adicionais para substituir resultados incompletos. A
perspetiva da equipa (`goals_for`, `goals_against`, `outcome`, `is_home`) vem do
motor existente: não se reinterpreta o marcador casa/visitante nem os eventos.
As comparações por grupo agregam os resultados individuais existentes; não
substituem as métricas oficiais do relatório factual. Testes confirmam igualdade
das médias e contagens da janela completa com o Analytics Engine.

Um jogo só contribui se `score_status == verified`, com ambos os golos e outcome
disponíveis. A validação não autentica a declaração de qualidade da origem.
Resultados `unverified`, `conflict` ou `unavailable` não são zeros; os campos
competitivos desse jogo ficam `null` nas tendências.

Cada `TrendSample` contém `selected_ids` e `used_ids`: cobertura =
`len(used_ids) / len(selected_ids)`. `values` é `null` quando falta qualquer
resultado da amostra selecionada. `covered_values` mantém apenas estatísticas
dos resultados verificados, com os IDs explícitos. Sem resultados verificados,
ambos são `null`, incluindo a amostra vazia (0/0 não é uma taxa calculável).
Uma seleção de um jogo pode ter cobertura 1/1: isso não representa cinco jogos
nem permite extrapolar para a época.

`TrendReport` conserva instalação/sistema de origem, equipa, época e snapshot;
cada jogo conserva data UTC, ID e versão dos dados. É uma estrutura interna
separada do DTO v1. O chamador deve fornecer o relatório do motor, não construir
relatórios com seleções ou agregados contraditórios. São rejeitadas janelas com
mais de cinco jogos ou IDs repetidos.

## Fórmulas e pré-condições

| Indicador | Fórmula e amostra |
| --- | --- |
| Sequência | Ordenação crescente por `(kickoff_at, int(match_id))`: mais antigo primeiro. Em empate de instante, ID numérico crescente, inverso da ordenação do produtor. Datas apresentadas em UTC. |
| GF e GA por jogo | Valores já calculados pelo motor para a equipa selecionada. |
| Diferença por jogo | `GF - GA`, apenas com resultado verificado. |
| Jogos sem sofrer | Soma de `GA == 0` entre os resultados verificados. |
| Jogos sem marcar | Soma de `GF == 0` entre os resultados verificados. Um 0–0 pertence a ambas as contagens. |
| V/E/D por grupo | Contagens dos `outcome` existentes; nenhum sistema de pontos é aplicado. |
| Média GF e GA por grupo | Soma dos valores verificados dividida por `n` resultados verificados desse grupo. Nunca se divide implicitamente por cinco. |
| Amplitude da diferença | `max(GF - GA) - min(GF - GA)`, com pelo menos dois resultados verificados. |
| Variância populacional | `sum((diferença_i - média_das_diferenças)^2) / n`, com pelo menos dois resultados verificados. Descreve a janela; não estima a variância da época. |
| Estabilidade simples | Número de pares cronologicamente adjacentes com o mesmo outcome, acompanhado do número de pares com ambos os resultados verificados. Não é uma probabilidade ou classificação de consistência. |
| Casa/fora | Duas amostras por `is_home`; cada subtotal tem denominador e IDs próprios. A comparação exige dois resultados verificados por local e cobertura completa nos dois grupos. |
| Comparação temporal | Com `N >= 4`, grupo antigo com os primeiros `floor(N/2)` jogos e grupo recente com os restantes. Diferença das médias = recente menos antigo, para GF e GA. Exige todos os resultados verificados e instantes diferentes na fronteira. |

Amplitude/variância sem dois resultados e estabilidade sem pares verificados
não têm valores numéricos: há motivos separados (`variability_reason` e
`stability_reason`). Não se unem jogos através de uma lacuna não verificada.
Na amostra casa/fora, a adjacência refere-se aos jogos desse local; na janela
refere-se a todos os jogos selecionados. IDs e datas permitem auditar os pares.

Os grupos temporais podem ter dimensão 2/3; com quatro jogos têm 2/2. Não se
divide uma fronteira de jogos simultâneos só para produzir uma comparação.
Os grupos e seus subtotais podem ser consultados mesmo quando a comparação é
indisponível; isso não torna a diferença temporal válida. Os motivos são códigos
fechados na estrutura e frases em português no dashboard.

## Exemplo exclusivamente fictício

`complete_five` contém, por ordem antiga → recente:

| ID | Resultado da equipa | GF | GA | Diferença |
| --- | --- | --- | --- | --- |
| 6 | E | 0 | 0 | 0 |
| 7 | D | 0 | 2 | -2 |
| 8 | E | 1 | 1 | 0 |
| 9 | V | 1 | 0 | 1 |
| 10 | V | 2 | 1 | 1 |

Cobertura 5/5: dois jogos sem sofrer, dois sem marcar, amplitude 3 e variância
populacional 1,2. Há um par com outcome igual em quatro pares adjacentes.
Os antigos (6,7) têm médias GF=0 e GA=1; os recentes (8,9,10), GF=4/3 e GA=2/3.
As diferenças são +4/3 e -1/3. São descrições destes jogos fictícios, não prova
de melhoria sustentável nem explicação tática, física ou psicológica.

## Catálogo, dashboard e execução

O catálogo acrescenta `trend:window`, `trend:home`, `trend:away`,
`trend:sequence` e, quando elegível, `trend:temporal`. Factos sem resultados
utilizáveis não são emitidos, exceto a sequência que pode indicar indisponibilidade.
Cada facto identifica cobertura, IDs, versões, snapshot e fórmula. O contexto
estruturado conserva também os motivos e as amostras utilizadas. Não envia nomes
ou texto livre das fixtures. As validações prévias de versões permanecem ativas.

O LLM continua limitado a selecionar IDs do catálogo com referências exatas.
Não devolve números ou frases livres; a apresentação vem exclusivamente de
frases locais. Referências inventadas, incompletas ou desconhecidas causam
fallback e não alteram o relatório factual.

O dashboard acrescenta a secção de tendências às existentes, com headings,
listas e `dl`, escaping e grelha responsiva já utilizada. Não usa gráficos,
frameworks, scripts ou CDNs. Mantém a identificação DADOS FICTÍCIOS e a política
de gravação/abertura opt-in. A sequência anterior continua identificada como
mais recente primeiro; a nova secção é explicitamente mais antigo primeiro.

```powershell
python -m footballiq.analyst_demo --html --fixture complete_five --open
python -m footballiq.analyst_demo --html --fixture partial_match
python -m footballiq.analyst_demo --html --fixture empty
```

A CLI factual textual existente mantém-se estável; os novos indicadores estão
disponíveis por `calculate_trends`, no catálogo opcional e no dashboard HTML.
Não é necessário ligar Ollama para gerar o HTML. Não há exportação autenticada,
dados reais ou interpretação tática generativa neste incremento.

## Validação e futuro

`tests/test_trends.py` cobre fórmulas, um/zero/cinco jogos, quatro jogos elegíveis,
qualidade, cobertura, casa/fora, desempates numéricos, fronteira temporal,
versões, referências, fallback, escape e ausência de rede. A suite existente
continua a cobrir o núcleo factual e as opções de gravação. O CI Python 3.14
permanece intacto. A verificação de browser existente é opcional; testes de HTML
não substituem ensaios de acessibilidade, impressão ou leitores de ecrã.

Para FI-009.2, qualquer prosa generativa precisa de uma especificação e validação
separadas: manter os factos e referências imutáveis, separar descrição de hipótese,
recusar quantidades ou causas não suportadas e preservar fallback sem LLM.

### Verificação local FI-009.1 — histórico

Python 3.12.10, sem novas dependências, PostgreSQL ou Ollama. Executou-se:

```powershell
$env:FOOTBALLIQ_DB_RUN_INTEGRATION = '0'
$env:PYTHONDONTWRITEBYTECODE = '1'
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q -rs --tb=short
.\.venv\Scripts\ruff.exe check --no-cache .
.\.venv\Scripts\ruff.exe format --check --no-cache .
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Resultado: `271 passed, 3 skipped in 3.48s`; Ruff: `All checks passed!`;
formatação: `43 files already formatted`; pip: `No broken requirements found.`;
diff sem erros. Há 25 casos novos de tendências. Os três skips são o ensaio de
browser opcional sem configuração e os dois testes PostgreSQL desativados.
Não houve nova inspeção visual de páginas ou certificação de acessibilidade.
Python 3.14 e CI remoto deste incremento continuam pendentes; não houve commit,
push ou PR. A versão mínima e o workflow existente não foram alterados.

### Revisão final FI-009.1.1

A conferência independente leu os marcadores casa/visitante diretamente da fixture
e utilizou frações exatas, sem chamar o módulo de tendências: diferenças
`[0, -2, 0, 1, 1]`, média zero, soma dos quadrados 6 e variância populacional
`6/5 = 1,2`; amplitude 3. Casa tem três jogos, médias GF=1 e GA=2/3; fora tem
dois jogos, GF=1/2 e GA=1. As contagens sem sofrer/sem marcar são ambas 2.
Para quatro jogos (6,7,8,9), a diferença temporal das médias é GF=+1 e GA=-1/2.

Correções de apresentação: ligação direta para Tendências; tradução do código
de resultado não verificado; valores numéricos da secção apresentados com até
três decimais e `≈` quando há arredondamento. Os dados estruturados permanecem
inalterados. A interface esclarece que resultados iguais em pares adjacentes
não constituem um índice de estabilidade nem uma previsão. O desempate por ID
não prova precedência temporal entre jogos simultâneos.

Acrescentaram-se quatro regressões: unicidade/estabilidade dos factos e rejeição
de factos indisponíveis; janela inteiramente não verificada; navegação e
arredondamento explícito sem mutação; comparação temporal exata de quatro jogos.

Validação final em Python 3.12.10:

```text
275 passed, 3 skipped in 3.71s
All checks passed!
43 files already formatted
No broken requirements found.
git diff --check: sem erros
```

Os mesmos três skips continuam esperados. O teste Playwright opcional foi
ignorado pela suite; uma auditoria visual separada foi executada com Edge
157.0.4341.42 e Node 24.19.0 já instalados, por DevTools pipe, sem dependências
novas, scripts de outros projetos ou servidor HTTP. As páginas fictícias não
efetuaram pedidos HTTP; a auditoria bloqueava esses destinos.

Inspecionaram-se capturas de complete_five, partial_match e empty em 1440×900 e
390×844; também zoom CSS de 200%. Não foi detetado overflow horizontal nos
elementos da secção. O contraste mínimo medido no texto da secção foi 6,17:1.
Verificaram-se link de salto, foco visível, ligação para Tendências, ativação de
details por Enter e visibilidade das referências em impressão. Foi gerado PDF.
Isto não certifica WCAG, leitores de ecrã, zoom nativo ou outros browsers.

Evidências locais temporárias, fora do repositório:
`C:\Users\javai\AppData\Local\Temp\footballiq-trends-final-7c2fszox`.
Contém HTML dos três cenários, `audit.json`, o harness próprio `audit.js`,
`desktop-*-zoom1.png`, `mobile-*-zoom1.png`, variantes `zoom2.png` e
`complete-print.pdf`. Estes artefactos não devem entrar num futuro commit.

O ficheiro independente footballiq.code-workspace manteve o SHA-256
`6BEF6A96F55DC8D340E2CC9369D7B0FE268124484C1156CB746FCE3C827979CD`.
Python 3.14 deste incremento e CI remoto permanecem por executar. Não houve
commit, push, PR, alteração de branch ou acesso a PostgreSQL/Ollama operacional.
