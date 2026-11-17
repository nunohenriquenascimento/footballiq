# FI-009.3.2.3.2 — Transporte da shortlist e validação real Gemma/Qwen

17 de novembro de 2026. **Objetivo funcional demonstrado por ambos os modelos:**
6/6 chamadas reais produziram pelo menos dois insights aceites; 3/6 produziram três.
Todas terminaram em `available / validated`, com JSON e schema válidos, IDs exclusivamente
da shortlist e famílias distintas. FactualReport, Trends e EvidenceBundle preservados em 6/6.

## Git, transporte e preservação

Lido AGENTS.md. Origin confirmado como
`https://github.com/nunohenriquenascimento/footballiq.git`.
Executado `git fetch origin`, exit code 0, sem output e sem mudar checkouts.
origin/main permaneceu em `44dbab0e1613dc9390215d95f35ac2f4db5b3b30`.
O PR #11 foi integrado em 16/11/2026; a campanha atual avalia uma correção posterior.
Não existia branch corretiva de shortlist na inspeção inicial.

Criada `fix/ollama-insight-shortlist`, baseada em origin/main, na nova worktree
`.worktrees/ollama-insight-shortlist`. HEAD continua no commit base; alterações não commitadas.
A branch ficou inicialmente a acompanhar origin/main por configuração automática do Git;
não se fez qualquer push nem se alterou a branch main.
As cinco worktrees anteriores e todas as branches existentes foram preservadas.

Gerou-se um patch restrito a três ficheiros rastreados; `git apply --check`
passou e o patch foi aplicado apenas na worktree nova. Os dois testes não rastreados
foram copiados explicitamente, com verificação de ausência de colisões e hashes.
Não se copiaram results ou relatórios históricos. Só a documentação transportada
foi atualizada para indicar o PR integrado e distinguir campanhas.

| Ficheiro transportado | Tratamento |
| --- | --- |
| src/footballiq/grounded_narrative/multi_insights.py | Patch aprovado; sem mudanças funcionais adicionais |
| tests/test_multi_insights.py | Patch aprovado |
| docs/ollama-multi-insights.md | Patch aprovado e atualização explícita do estado/documentação |
| tests/test_multi_insight_shortlist.py | Cópia byte a byte |
| tests/test_shortlist_review_regressions.py | Cópia byte a byte |

Hashes SHA-256 de origem, destino após transporte e destino final:

- `src/footballiq/grounded_narrative/multi_insights.py`
  - origem: `4189f2ce89f056c514086a3686dff556e2dadbd264992937052cdceee1b77d13`
  - após transporte: `35e72e555f197026eb85e804da3520fbebfc1701a16fc803b6458702b5639fda`
  - final: `35e72e555f197026eb85e804da3520fbebfc1701a16fc803b6458702b5639fda`
- `tests/test_multi_insights.py`
  - origem: `fe51004efcecc4ec6eda1a412f37b450d40a47d6188068259d6a59c0efadd3f9`
  - após transporte: `d04633f6bfd9bcb94c84607af7ac83dca9a31cd87e7bd0fa32d99e8d6666de2a`
  - final: `d04633f6bfd9bcb94c84607af7ac83dca9a31cd87e7bd0fa32d99e8d6666de2a`
- `docs/ollama-multi-insights.md`
  - origem: `f18d9452165b58d64517157b3e405709a39f1a0528002d34cfdeb29b888699e6`
  - após transporte: `5785a7ae1d2326ad984218a272b81e597e45f3409d7a6b40e46135d6438e5e9e`
  - final: `a2ecf3c1b9d0620b467513489fc1ff275cde3c6440b7c197a3cdacb530123f4c`
- `tests/test_multi_insight_shortlist.py`
  - origem: `9404a45f33350884ffe56dbd9ecd5088a2a4ad41476d59f4165f9bc9d7446570`
  - após transporte: `9404a45f33350884ffe56dbd9ecd5088a2a4ad41476d59f4165f9bc9d7446570`
  - final: `9404a45f33350884ffe56dbd9ecd5088a2a4ad41476d59f4165f9bc9d7446570`
- `tests/test_shortlist_review_regressions.py`
  - origem: `c52abdd3e89a604132da528ffa5f228b49cf48aba68f0ec5cec77c10e027431f`
  - após transporte: `c52abdd3e89a604132da528ffa5f228b49cf48aba68f0ec5cec77c10e027431f`
  - final: `c52abdd3e89a604132da528ffa5f228b49cf48aba68f0ec5cec77c10e027431f`

Nos três ficheiros rastreados, Git normalizou LF/CRLF no destino: os hashes brutos
divergem, mas o conteúdo era idêntico após normalizar finais de linha, antes da
atualização documental. Nos dois ficheiros copiados, os hashes são idênticos.
A origem não foi normalizada nem editada.

O inventário inicial abrangeu **507 ficheiros existentes**, incluindo os 506 anteriores
e a regressão acrescentada na revisão. A verificação final não encontrou alterações
nem remoções nesses ficheiros. Incluem-se os 45 ficheiros originais, artefactos
excluídos, backups e relatórios das worktrees anteriores. Status e staging da origem
permanecem iguais; HEAD da main preservado. .git, .venv e caches não foram hashados
integralmente: fetch e criação de branch/worktree modificam metadados Git conforme autorizado.
Nenhum reset, stash, clean, commit, push, PR ou merge foi executado.

## Validação offline e política transportada

Imports apontaram explicitamente para o src da **nova** worktree, também confirmado
antes da campanha real. Ambiente virtual existente; Python 3.12.10, sem instalações.
479 testes aprovados, 3 skips; 81 casos focados de Multi-Insights aprovados.

A shortlist mantém o primeiro elegível de cada família, seguindo cobertura decrescente,
amostra decrescente e prioridade fixa. Critérios de amostra/cobertura, catálogo e
validador não foram alterados. Contexto e schema contêm apenas os representantes;
IDs externos são rejeitados integralmente. O modo modelo aceita 1–3 IDs, sem exigir
preencher três; o modo determinístico mantém a política anterior.

Os testes confirmam rejeição atómica, IDs externos/duplicados, famílias repetidas
em estado manipulado, fallback sem texto fabricado, bundle único e compatibilidade
CLI/API. As demonstrações com clientes falsos produziram duas famílias em complete_five,
três em rich_four_distinct e rejeitaram form+competitive por competitive não ser oferecido.
Os exemplos offline e checks completos ficam locais e são distintos dos ensaios reais.
Não se modificaram Analytics, Trends, contrato v1, ORM, persistência, dashboard ou Match Tracker.

## Ambiente real e limites

Ollama já ativo em `http://127.0.0.1:11434`, versão **0.40.16**.
Consultas diretas `/api/version`, `/api/tags`, `/api/ps`; sem proxies ou redirects.
Só se usaram modelos já instalados, identificados pelos digests em results.json.
Não se iniciou serviço nem se descarregou modelo.

- gemma3:270m: 268.10M, Q8_0; digest `e7d36fb2c3b3293cfe56d55889867a064b3a2b22e98335f2e6e8a387e081d6be`.
- qwen3:4b: 4.0B, Q4_K_M; digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.

Ambos os modelos estavam ausentes de /api/ps antes da sua preparação, pelo que foi
necessário um warmup voluntário por modelo: POST /api/chat com messages=[], stream=false,
keep_alive=5m, orçamento diagnóstico separado de 30 s. HTTP 200 e done_reason=load;
residência confirmada antes da primeira inferência. Essa preparação não pediu narrativa.

| Modelo | Preparação explícita (s) | Primeira inferência residente (s) |
| --- | ---: | ---: |
| gemma3:270m | 1.927403 | 0.206678 |
| qwen3:4b | 2.820023 | 0.604525 |

Não se mediu uma narrativa integralmente a frio. Primeira inferência residente não
implica caches/prefill totalmente aquecidos; as seguintes são repetições warm.
Qwen foi preparado depois da utilização de Gemma. Não se extrapolam estes valores.

Defaults preservados: timeout socket 5 s, deadline cooperativo 15 s; limites de pedido
32768 bytes, envelope 65536, conteúdo 8192; temperature=0, num_predict=512,
stream=false, think=false. Sem retries, mudança de prompt ou shortlist durante a campanha.
O transporte observado foi o _post original do OllamaClient; a API usada foi
narrate_insights real da nova worktree. O schema é o real plan_ids, não texto livre.

Fixtures exclusivamente sintéticas, sem alterações em disco:

- rich_four_distinct: quatro primeiros jogos de complete_five, returned_count=4,
  primeiro kickoff ajustado em memória para 2026-11-08T16:00:00Z, como nos testes aprovados.
  Shortlist: form/results, recent_vs_older/comparison, temporal_goals/timing,
  winning_run/sequence. Até três escolhas permitidas.
- complete_five: fixture original; shortlist form/results e recent_vs_older/comparison.
  Até duas escolhas permitidas; não se inventou uma terceira família.

## Todas as inferências reais

IDs na tabela omitem apenas o prefixo insight:. Todas as linhas: JSON/schema válidos,
status available, reason validated, evidências autorizadas e invariantes preservadas.
Shortlist, schema e envelope completos observados permanecem nos logs locais;
results.json contém shortlist/famílias, JSON, IDs, estado, duração e proveniência por chamada.

| Modelo | Nº | Fixture | Estado | Segundos | IDs aceites | Famílias |
| --- | ---: | --- | --- | ---: | --- | ---: |
| gemma3:270m | 1 | rich_four_distinct | resident_first_inference | 0.206678 | form, recent_vs_older | 2 |
| gemma3:270m | 2 | rich_four_distinct | warm_repeated | 0.181640 | form, recent_vs_older, temporal_goals | 3 |
| gemma3:270m | 3 | complete_five | warm_repeated | 0.140964 | form, recent_vs_older | 2 |
| qwen3:4b | 1 | rich_four_distinct | resident_first_inference | 0.604525 | form, recent_vs_older, temporal_goals | 3 |
| qwen3:4b | 2 | rich_four_distinct | warm_repeated | 0.420933 | form, recent_vs_older, temporal_goals | 3 |
| qwen3:4b | 3 | complete_five | warm_repeated | 0.370495 | form, recent_vs_older | 2 |

## JSONs reais e observações efetivamente aceites

As observações abaixo são o texto efetivamente devolvido pelo backend após validação
das seleções dos modelos reais. Não são prosa livre gerada pelo modelo nem exemplos simulados.

### gemma3:270m — chamada 1 (rich_four_distinct)

```json
{"plan_ids": ["insight:form", "insight:recent_vs_older"]}
```

```text
Forma recente: Vitórias: 2; Empates: 1; Derrotas: 1; Jogos sem sofrer golos: 1; Jogos sem marcar: 1; Média GF: 1,000; Média GA: 1,000. Médias por jogo coberto, arredondadas a três casas decimais. Cobertura 4/4; amostra 4. Descrição da janela exportada; não constitui previsão. Snapshot synthetic-five-v1; catálogo footballiq.insights.v1; fórmula footballiq.trends.v1; versões 7@synthetic-match-7-v1; 8@synthetic-match-8-v1; 9@synthetic-match-9-v1; 10@synthetic-match-10-v1.
Comparação descritiva de médias por jogo (arredondadas a três casas decimais): Recentes (n=2): Média GF 1,500, Média GA 0,500; Antigos (n=2): Média GF 0,500, Média GA 1,500. Cobertura 4/4; amostra 4. Descrição da janela exportada; não constitui previsão. Snapshot synthetic-five-v1; catálogo footballiq.insights.v1; fórmula footballiq.trends.v1; versões 9@synthetic-match-9-v1; 10@synthetic-match-10-v1; 7@synthetic-match-7-v1; 8@synthetic-match-8-v1.
```

### gemma3:270m — chamada 2 (rich_four_distinct)

```json
{"plan_ids": ["insight:form", "insight:recent_vs_older", "insight:temporal_goals"]}
```

```text
Forma recente: Vitórias: 2; Empates: 1; Derrotas: 1; Jogos sem sofrer golos: 1; Jogos sem marcar: 1; Média GF: 1,000; Média GA: 1,000. Médias por jogo coberto, arredondadas a três casas decimais. Cobertura 4/4; amostra 4. Descrição da janela exportada; não constitui previsão. Snapshot synthetic-five-v1; catálogo footballiq.insights.v1; fórmula footballiq.trends.v1; versões 7@synthetic-match-7-v1; 8@synthetic-match-8-v1; 9@synthetic-match-9-v1; 10@synthetic-match-10-v1.
Comparação descritiva de médias por jogo (arredondadas a três casas decimais): Recentes (n=2): Média GF 1,500, Média GA 0,500; Antigos (n=2): Média GF 0,500, Média GA 1,500. Cobertura 4/4; amostra 4. Descrição da janela exportada; não constitui previsão. Snapshot synthetic-five-v1; catálogo footballiq.insights.v1; fórmula footballiq.trends.v1; versões 9@synthetic-match-9-v1; 10@synthetic-match-10-v1; 7@synthetic-match-7-v1; 8@synthetic-match-8-v1.
Distribuição temporal dos golos: Minutos 00-14 contra: 3; Minutos 00-14 a favor: 2; Minutos 15-29 contra: 0; Minutos 15-29 a favor: 1; Minutos 30-44 contra: 0; Minutos 30-44 a favor: 0; Minutos 45-59 contra: 0; Minutos 45-59 a favor: 1; Minutos 60-74 contra: 1; Minutos 60-74 a favor: 0; Minutos 75-89 contra: 0; Minutos 75-89 a favor: 0; Minutos 90+ contra: 0; Minutos 90+ a favor: 0; Período 1 contra: 3; Período 1 a favor: 3; Período 2 contra: 1; Período 2 a favor: 1. Cobertura 4/4; amostra 4. Descrição da janela exportada; não constitui previsão. Snapshot synthetic-five-v1; catálogo footballiq.insights.v1; fórmula footballiq.analytics.v1; versões 10@synthetic-match-10-v1; 9@synthetic-match-9-v1; 8@synthetic-match-8-v1; 7@synthetic-match-7-v1.
```

### gemma3:270m — chamada 3 (complete_five)

```json
{"plan_ids": ["insight:form", "insight:recent_vs_older"]}
```

```text
Forma recente: Vitórias: 2; Empates: 2; Derrotas: 1; Jogos sem sofrer golos: 2; Jogos sem marcar: 2; Média GF: 0,800; Média GA: 0,800. Médias por jogo coberto, arredondadas a três casas decimais. Cobertura 5/5; amostra 5. Descrição da janela exportada; não constitui previsão. Snapshot synthetic-five-v1; catálogo footballiq.insights.v1; fórmula footballiq.trends.v1; versões 6@synthetic-match-6-v1; 7@synthetic-match-7-v1; 8@synthetic-match-8-v1; 9@synthetic-match-9-v1; 10@synthetic-match-10-v1.
Comparação descritiva de médias por jogo (arredondadas a três casas decimais): Recentes (n=3): Média GF 1,333, Média GA 0,667; Antigos (n=2): Média GF 0,000, Média GA 1,000. Cobertura 5/5; amostra 5. Descrição da janela exportada; não constitui previsão. Snapshot synthetic-five-v1; catálogo footballiq.insights.v1; fórmula footballiq.trends.v1; versões 8@synthetic-match-8-v1; 9@synthetic-match-9-v1; 10@synthetic-match-10-v1; 6@synthetic-match-6-v1; 7@synthetic-match-7-v1.
```

### qwen3:4b — chamada 1 (rich_four_distinct)

```json
{"plan_ids": ["insight:form", "insight:recent_vs_older", "insight:temporal_goals"] }
```

```text
Forma recente: Vitórias: 2; Empates: 1; Derrotas: 1; Jogos sem sofrer golos: 1; Jogos sem marcar: 1; Média GF: 1,000; Média GA: 1,000. Médias por jogo coberto, arredondadas a três casas decimais. Cobertura 4/4; amostra 4. Descrição da janela exportada; não constitui previsão. Snapshot synthetic-five-v1; catálogo footballiq.insights.v1; fórmula footballiq.trends.v1; versões 7@synthetic-match-7-v1; 8@synthetic-match-8-v1; 9@synthetic-match-9-v1; 10@synthetic-match-10-v1.
Comparação descritiva de médias por jogo (arredondadas a três casas decimais): Recentes (n=2): Média GF 1,500, Média GA 0,500; Antigos (n=2): Média GF 0,500, Média GA 1,500. Cobertura 4/4; amostra 4. Descrição da janela exportada; não constitui previsão. Snapshot synthetic-five-v1; catálogo footballiq.insights.v1; fórmula footballiq.trends.v1; versões 9@synthetic-match-9-v1; 10@synthetic-match-10-v1; 7@synthetic-match-7-v1; 8@synthetic-match-8-v1.
Distribuição temporal dos golos: Minutos 00-14 contra: 3; Minutos 00-14 a favor: 2; Minutos 15-29 contra: 0; Minutos 15-29 a favor: 1; Minutos 30-44 contra: 0; Minutos 30-44 a favor: 0; Minutos 45-59 contra: 0; Minutos 45-59 a favor: 1; Minutos 60-74 contra: 1; Minutos 60-74 a favor: 0; Minutos 75-89 contra: 0; Minutos 75-89 a favor: 0; Minutos 90+ contra: 0; Minutos 90+ a favor: 0; Período 1 contra: 3; Período 1 a favor: 3; Período 2 contra: 1; Período 2 a favor: 1. Cobertura 4/4; amostra 4. Descrição da janela exportada; não constitui previsão. Snapshot synthetic-five-v1; catálogo footballiq.insights.v1; fórmula footballiq.analytics.v1; versões 10@synthetic-match-10-v1; 9@synthetic-match-9-v1; 8@synthetic-match-8-v1; 7@synthetic-match-7-v1.
```

### qwen3:4b — chamada 2 (rich_four_distinct)

```json
{"plan_ids": ["insight:form", "insight:recent_vs_older", "insight:temporal_goals"] }
```

```text
Forma recente: Vitórias: 2; Empates: 1; Derrotas: 1; Jogos sem sofrer golos: 1; Jogos sem marcar: 1; Média GF: 1,000; Média GA: 1,000. Médias por jogo coberto, arredondadas a três casas decimais. Cobertura 4/4; amostra 4. Descrição da janela exportada; não constitui previsão. Snapshot synthetic-five-v1; catálogo footballiq.insights.v1; fórmula footballiq.trends.v1; versões 7@synthetic-match-7-v1; 8@synthetic-match-8-v1; 9@synthetic-match-9-v1; 10@synthetic-match-10-v1.
Comparação descritiva de médias por jogo (arredondadas a três casas decimais): Recentes (n=2): Média GF 1,500, Média GA 0,500; Antigos (n=2): Média GF 0,500, Média GA 1,500. Cobertura 4/4; amostra 4. Descrição da janela exportada; não constitui previsão. Snapshot synthetic-five-v1; catálogo footballiq.insights.v1; fórmula footballiq.trends.v1; versões 9@synthetic-match-9-v1; 10@synthetic-match-10-v1; 7@synthetic-match-7-v1; 8@synthetic-match-8-v1.
Distribuição temporal dos golos: Minutos 00-14 contra: 3; Minutos 00-14 a favor: 2; Minutos 15-29 contra: 0; Minutos 15-29 a favor: 1; Minutos 30-44 contra: 0; Minutos 30-44 a favor: 0; Minutos 45-59 contra: 0; Minutos 45-59 a favor: 1; Minutos 60-74 contra: 1; Minutos 60-74 a favor: 0; Minutos 75-89 contra: 0; Minutos 75-89 a favor: 0; Minutos 90+ contra: 0; Minutos 90+ a favor: 0; Período 1 contra: 3; Período 1 a favor: 3; Período 2 contra: 1; Período 2 a favor: 1. Cobertura 4/4; amostra 4. Descrição da janela exportada; não constitui previsão. Snapshot synthetic-five-v1; catálogo footballiq.insights.v1; fórmula footballiq.analytics.v1; versões 10@synthetic-match-10-v1; 9@synthetic-match-9-v1; 8@synthetic-match-8-v1; 7@synthetic-match-7-v1.
```

### qwen3:4b — chamada 3 (complete_five)

```json
{"plan_ids": ["insight:form", "insight:recent_vs_older"]}
```

```text
Forma recente: Vitórias: 2; Empates: 2; Derrotas: 1; Jogos sem sofrer golos: 2; Jogos sem marcar: 2; Média GF: 0,800; Média GA: 0,800. Médias por jogo coberto, arredondadas a três casas decimais. Cobertura 5/5; amostra 5. Descrição da janela exportada; não constitui previsão. Snapshot synthetic-five-v1; catálogo footballiq.insights.v1; fórmula footballiq.trends.v1; versões 6@synthetic-match-6-v1; 7@synthetic-match-7-v1; 8@synthetic-match-8-v1; 9@synthetic-match-9-v1; 10@synthetic-match-10-v1.
Comparação descritiva de médias por jogo (arredondadas a três casas decimais): Recentes (n=3): Média GF 1,333, Média GA 0,667; Antigos (n=2): Média GF 0,000, Média GA 1,000. Cobertura 5/5; amostra 5. Descrição da janela exportada; não constitui previsão. Snapshot synthetic-five-v1; catálogo footballiq.insights.v1; fórmula footballiq.trends.v1; versões 8@synthetic-match-8-v1; 9@synthetic-match-9-v1; 10@synthetic-match-10-v1; 6@synthetic-match-6-v1; 7@synthetic-match-7-v1.
```

## Métricas, segurança e qualidade analítica

| Métrica | Gemma | Qwen |
| --- | ---: | ---: |
| JSON/schema válidos | 3/3 | 3/3 |
| Seleções integralmente aprovadas | 3/3 (100%) | 3/3 (100%) |
| Seleções múltiplas reais (>=2) | 3/3 | 3/3 |
| Seleções de três insights | 1/3 | 2/3 |
| Média de observações aceites por seleção | 2,333 | 2,667 |
| Famílias distintas por seleção | 2, 3, 2 | 3, 3, 2 |
| Mesmos IDs nas duas chamadas ricas | Não | Sim |
| Latência média após load, incluindo primeira residente (s) | 0.176427 | 0.465317 |
| Latência média das duas repetições warm, fixtures diferentes (s) | 0.161302 | 0.395714 |

Nenhuma seleção repetiu família. Todos os IDs pertenceram à shortlist efetivamente
apresentada; o JSON respeitou o enum, cardinalidade e unicidade. Cada resultado foi
comparado com render_insight sobre o bundle de baseline: texto idêntico, referências
exatamente autorizadas, snapshot/digest correspondentes. O bundle interno continua
único por chamada, como verificado nos testes; as baselines externas servem só para comparação.

Baselines completas foram guardadas antes das inferências. Em 6/6 preservaram-se
FactualReport, Trends e EvidenceBundle, com igualdade de conteúdo e proveniência.
Nenhum texto ou referência não autorizados foi exposto. Snapshot e digest completos
constam por chamada no JSON sanitizado. Os digests identificam conteúdo, não certificam
a autenticidade da origem.

A campanha histórica 0/6 avaliou código anterior; agora o objetivo funcional foi
demonstrado, mas esta pequena amostra não prova uma taxa de sucesso populacional
de 100% nem isola causalmente todos os fatores entre campanhas. Gemma variou de
duas para três escolhas apesar de temperature=0; não se promete determinismo de
inferência. Nenhum modelo selecionou sequence. A política pode excluir âmbitos úteis
da mesma família e não elimina toda a sobreposição entre famílias. O contexto contém
metadados, não valores factuais completos; não se demonstra entendimento tático,
causalidade, previsões ou superioridade analítica de Qwen.

## Outputs literais de qualidade

Checks executados após o transporte e atualização documental, antes do ensaio real.
Python local **3.12.10**, não 3.14; requisito >=3.14 permanece e falta validação dessa
versão para esta alteração. Não se executou o CI anterior como parte desta campanha.

### `python -V`

Exit code: 0.

```text
Python 3.12.10
```

### `python -m pytest -q -rs`

Exit code: 0.

```text
............................s........................................... [ 14%]
...............................................ss....................... [ 29%]
........................................................................ [ 44%]
........................................................................ [ 59%]
........................................................................ [ 74%]
........................................................................ [ 89%]
..................................................                       [100%]
=========================== short test summary info ===========================
SKIPPED [1] tests\test_analyst_dashboard.py:373: Browser QA opcional exige FOOTBALLIQ_PLAYWRIGHT_MODULE já instalado
SKIPPED [1] tests\test_db_integration.py:72: integração PostgreSQL desativada por defeito; ativar FOOTBALLIQ_DB_RUN_INTEGRATION=1
SKIPPED [1] tests\test_db_integration.py:96: integração PostgreSQL desativada por defeito; ativar FOOTBALLIQ_DB_RUN_INTEGRATION=1
479 passed, 3 skipped in 5.24s
```

### `python -m ruff check .`

Exit code: 0.

```text
All checks passed!
```

### `python -m ruff format --check .`

Exit code: 0.

```text
63 files already formatted
```

### `python -m pip check`

Exit code: 0.

```text
No broken requirements found.
```

### `git -c safe.directory=* diff --check`

Exit code: 0.

```text
(stdout/stderr vazios)
```

### `python -m pytest -q -rs tests/test_multi_insights.py tests/test_multi_insight_shortlist.py tests/test_shortlist_review_regressions.py`

Exit code: 0.

```text
........................................................................ [ 88%]
.........                                                                [100%]
81 passed in 0.90s
```

Skips: browser opcional sem FOOTBALLIQ_PLAYWRIGHT_MODULE e dois testes PostgreSQL
desativados por defeito. Sem integração PostgreSQL dedicada nesta campanha.

## Ficheiros finais, limitações e recomendação

Na nova worktree: os cinco ficheiros transportados acima, mais
docs/validation/fi009-3-2-3-2/README.md e results.json, criados nesta campanha.
Não foram transportados relatórios anteriores. Os relatórios públicos contêm só
fixtures sintéticas e metadados técnicos sanitizados.
Na pasta externa local evaluation-fi009-3-2-3-2-20261117 ficam patch, hashes,
inventários, scripts, checks completos, exemplos offline, baselines, consultas
de modelos, warmups, seis trials e seis pedidos/envelopes completos. Não publicar
essa pasta, pois contém paths pessoais e inventários locais. O runner importa o
harness anterior somente para observação, com ROOT/LOCAL dirigidos à campanha nova;
os imports de produção foram confirmados na nova worktree. Não repetir a campanha:
o limite autorizado de três chamadas narrativas por modelo foi cumprido.

Recomenda-se preparar um **PR corretivo** com a shortlist e os testes transportados:
o critério de pelo menos uma seleção múltipla real aprovada por modelo foi atingido,
sem regressões offline identificadas. Ainda são necessários revisão do ChatGPT e
validação em Python 3.14/CI antes de recomendar integração final. Nenhum commit,
push ou PR foi criado. A autorização para esses passos não se presume desta tarefa.
