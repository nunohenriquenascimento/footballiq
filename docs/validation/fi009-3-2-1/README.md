# FI-009.3.2.1 — Relatório para revisão do ChatGPT

## Estado Git e preservação

Implementação local, **sem commit, push, PR ou merge** nesta tarefa.
Branch `feature/ollama-multi-insights`, worktree `.worktrees/ollama-multi-insights`,
criada de `origin/main` em `66e9d3a46fd7d306aeb44ae6a523b37ff05587a1`.
O HEAD permanece nessa base e o staging está vazio.

O objeto Git confirma o merge do PR #10 e os pais aprovados `9d33498` e
`0113cef`. A referência local origin/main contém esse merge. Não foi necessário
atualizar main local, fazer fetch ou alterar os checkouts anteriores.
O checkout original permanece em `feature/grounded-narrative-dashboard/fcc7e58`,
main local em `4b88f52`, e o worktree anterior em
`feature/football-insights-catalog/0113cef`.

Foi guardado um inventário local dos 45 ficheiros originais, dos quatro artefactos
excluídos e dos artefactos/backups do worktree anterior, para comparação final.
O inventário com caminhos e hashes permanece apenas em `results`, fora deste
relatório. Não se apagaram ficheiros, branches, worktrees ou backups.

## Inspeção e arquitetura

Inspecionadas as APIs reais de insights, contrato, orquestrador, OllamaClient,
analyst_demo, dashboard, Analytics, Trends, testes e documentação associados.

O catálogo constrói um EvidenceBundle profundamente imutável. Os planos fechados
existentes usam um facto composto por observação e relação AGGREGATE_RESULT.
O orquestrador antigo seleciona um plan_id e renderiza uma observação individual
de golos num jogo. Esse fluxo não foi alterado.

A integração aditiva está em `grounded_narrative/multi_insights.py`:

1. Opt-in e restrição à origem da demonstração antes de usar um cliente.
2. Uma chamada a `build_insights` constrói o bundle canónico do pedido.
3. `prepare_insight_candidates` reutiliza `prepare_insight_plans` e filtra elegibilidade.
4. O modelo devolve apenas `{"plan_ids":[...]}`, ou o modo determinístico escolhe IDs.
5. O backend verifica 1–3 IDs reais distintos, no máximo um por família.
6. Cada plano passa por `render_insight`, que reutiliza GroundedNarrativeValidator
   e exige igualdade com o plano fechado no mesmo bundle.
7. Só após todos passarem é criado InsightNarrativeResult disponível.

Não foram alterados o contrato v1, insights.py, Analytics, Trends, OllamaClient,
ORM, persistência, Match Tracker ou dashboard. Não se combinam os planos num
novo contrato composto nem se duplicam regras de evidência ou transporte HTTP.

## APIs e ficheiros

Novas APIs no módulo multi_insights:

- `InsightNarrativeResult`: status, reason, text, plan_ids, references, snapshot_id,
  evidence_digest; dataclass congelada, strings e tuplos.
- `prepare_insight_candidates(bundle)`: planos elegíveis em ordem determinística.
- `narrate_insights(report, *, enabled=False, client=None, deterministic=False)`.

`run_demo` recebe o novo keyword opcional `insights=None|"ollama"|"deterministic"`.
A CLI acrescenta `--insights ollama|deterministic`, incompatível com HTML e com
os outros modos opcionais de interpretação. A API/CLI anterior mantém defaults.

Ficheiros alterados ou acrescentados:

- `src/footballiq/grounded_narrative/multi_insights.py` — novo orquestrador aditivo;
- `src/footballiq/analyst_demo.py` — opção explícita de CLI textual;
- `tests/test_multi_insights.py` — 60 casos offline;
- `docs/ollama-multi-insights.md` — arquitetura, política, comandos e ensaio posterior;
- `docs/football-insights-catalog.md` — ligação à nova integração textual;
- `docs/validation/fi009-3-2-1/examples.json` — seis cenários sintéticos;
- `docs/validation/fi009-3-2-1/README.md` — este relatório.

## Relevância, exemplos e fallback

Quatro famílias locais, sem alterar o contrato: results, comparison, timing e
sequence. form/competitive/home/away partilham results; as duas comparações
partilham comparison. Evita-se selecionar descrições muito semelhantes juntas.
Uma só observação é válida; a disponibilidade real pode ser inferior a três.

Mínimo dois jogos. Cobertura dos agregados >=80% do grupo; é uma regra de
apresentação, sem garantia de significância estatística. Sequências verificadas
têm exceção porque a sua cobertura mede o sufixo sobre a janela, não dados em
falta. A ordem determinística usa cobertura, amostra e prioridade fixa documentada
no guia. O modelo pode escolher e ordenar os candidatos elegíveis.

Exemplo válido de uma observação, cliente falso sobre a fixture completa:

```json
{"plan_ids":["insight:form"]}
```

Exemplo válido de três observações, cliente falso sobre variante sintética com
quatro jogos, eventos e datas distintas:

```json
{"plan_ids":["insight:form","insight:recent_vs_older","insight:temporal_goals"]}
```

O texto exato e evidências constam de `examples.json`. A fixture completa oferece
apenas duas famílias: as datas empatadas omitem sequências e o jogo sem eventos
omite distribuição temporal. Não se inventa um terceiro candidato.

Referências, números, texto livre e campos adicionais nunca são aceites do LLM.
IDs falsos/duplicados, estruturas inválidas, mais de três IDs ou seleção vazia
são recusados integralmente. Famílias repetidas devolvem insufficient_diversity.
Planos de outro snapshot/bundle ou com evidências trocadas/inventadas devolvem
invalid_plan, mesmo quando outra observação da seleção era válida.

Timeout, Ollama indisponível ou erro de transporte devolvem apenas motivos
seguros; o factual permanece disponível. Não há retries nem fallback determinístico
automático. O modo determinístico exige escolha explícita e não chama o cliente.
O bundle não é exposto ao modelo, e referências de outro digest não são misturadas.

## Testes, comandos e outputs literais

O Python da venv existente foi reutilizado, sem instalar dependências. PYTHONPATH
apontou para `src` deste worktree. Os caminhos absolutos de Analytics, Trends,
contrato, catálogo, multi_insights, analyst_demo e OllamaClient foram resolvidos
e verificados por assertions como pertencentes a este worktree.
O requisito Python >=3.14 mantém-se intacto; a versão local é 3.12.10.

`python -V` — exit 0:

```text
Python 3.12.10
```

`python -m pytest -q` — exit 0:

```text
............................s........................................... [ 15%]
...............................................ss....................... [ 31%]
........................................................................ [ 46%]
........................................................................ [ 62%]
........................................................................ [ 78%]
........................................................................ [ 93%]
.............................                                            [100%]
458 passed, 3 skipped in 4.25s
```

`python -m ruff check .` — exit 0:

```text
All checks passed!
```

`python -m ruff format --check .` — exit 0 após formatar o exemplo Python no guia:

```text
61 files already formatted
```

`python -m pip check` — exit 0:

```text
No broken requirements found.
```

`git diff --check` — exit 0, stdout e stderr vazios.

Suíte nova isolada: `60 passed in 0.63s`.
Os três skips existentes são browser opcional sem FOOTBALLIQ_PLAYWRIGHT_MODULE e
dois testes PostgreSQL desativados por defeito. Não foram ocultados ou ativados
serviços para os executar. Todos os testes novos bloqueiam ligações de rede.

Cobertura das regressões: uma/três observações; excesso de IDs; IDs repetidos,
falsos ou de catálogo incompatível; famílias repetidas; referências falsas,
trocadas, duplicadas e de outro digest; snapshot de plano ou facto errado; falha
num plano intermédio sem saída parcial; catálogos pequenos; cobertura parcial
ou insuficiente; fixture vazia; empates temporais; timeout; transporte; opt-in;
API/CLI antiga; factual/Trends/bundle imutáveis; render repetível; ordem do modelo;
seleção determinística; configuração de endpoint externo rejeitada; cliente HTTP
existente com transporte falso e defaults inalterados.

Execuções CLI reais sem rede, exit 0:

```text
python -m footballiq.analyst_demo --insights deterministic
insights_status=available; reason=deterministic

python -m footballiq.analyst_demo --fixture empty --insights deterministic
insights_status=unavailable; reason=no_facts
```

Durante o desenvolvimento, Ruff format aplicou inicialmente a sintaxe de except
de Python 3.14, incompatível com o intérprete local 3.12. Corrigiu-se usando tuplos
de exceções nomeados, como no código existente, sem mudar requisitos ou config.
Uma expectativa inicial de teste sobre disponibilidade de famílias também foi
corrigida: as duas comparações coexistem na variante de quatro jogos e a rejeição
correta é insufficient_diversity. As execuções finais acima passaram.
Os logs brutos e inventários permanecem localmente em results, não nesta documentação.

## Limitações e recomendação

- Python 3.14 e inferência Ollama real não foram executados nesta tarefa.
- O isolamento local depende de PYTHONPATH porque a instalação editável existente
  aponta para o checkout original; os imports efetivos foram verificados.
- O limiar 80%, o mínimo dois e as famílias são uma política conservadora de
  apresentação; não garantem significância estatística nem máxima relevância.
- O contexto mínimo permite escolher tópicos/cobertura, não interpretar resultados
  numéricos ou produzir análise tática. Sobreposição parcial entre famílias é possível.
- Mantêm-se as limitações do catálogo: origem confiável, hashes sem autenticação,
  ausência de payloads de eventos e omissão temporal deliberada sem IDs.
- Não há validação de cold start ou latência de modelos reais; timeouts continuam
  5 s e deadline 15 s, com o caráter cooperativo já documentado no cliente existente.

Recomenda-se ao ChatGPT rever a política de famílias/cobertura, a rejeição atómica,
os exemplos e a compatibilidade. Após aprovação, validar Python 3.14 em CI e só
depois autorizar uma campanha manual com modelo já instalado, segundo o guia.
Entrega sem publicação, a aguardar revisão.

## Revisão final FI-009.3.2.2 — preparação de PR draft

A implementação offline acima foi aprovada para commit, push sem force e PR
draft. O merge não está autorizado. Esta secção regista a revisão de publicação;
as secções anteriores conservam os resultados históricos da FI-009.3.2.1.

A revisão das APIs, código, testes e exemplos confirmou o bundle canónico único,
seleção de 1–3 IDs autorizados, rejeição de famílias repetidas e validação atómica
de snapshot, digest e referências. O modelo só escolhe IDs; números, evidências
e prosa são produzidos pelo backend. Falhas não apresentam fragmentos aprovados
isoladamente nem alteram factual ou Trends. O modo determinístico não usa rede.

Confirmados mínimo de dois jogos, cobertura >=80% dos agregados e exceção para
sufixos consecutivos verificados. A compatibilidade da API/CLI antiga permanece
coberta pelos testes. Dashboard, Analytics, Trends, contrato v1, ORM,
persistência, fixtures e cliente HTTP não foram alterados. Não foram identificados
defeitos demonstrados que exigissem alterações adicionais de código nesta revisão.

Serão publicados apenas os sete ficheiros inventariados acima. Inventários de
preservação, backups, logs brutos, caminhos pessoais, hashes de ficheiros locais
e payloads de ensaios ficam excluídos em results. Os exemplos publicados contêm
apenas resultados validados de dados sintéticos, com identificadores de evidência
necessários para demonstrar o contrato. Não houve inferência Ollama real nem
instalação de dependências ou modelos.

Os imports absolutos foram novamente verificados no src deste worktree. O Python
local continua a ser 3.12.10; não se declara Python 3.14 validado localmente.
O requisito >=3.14 mantém-se, e o CI do PR deverá validar essa versão, incluindo
PostgreSQL dedicado. O estado remoto final é registado no relatório de publicação;
não se confunde a aprovação offline com a conclusão do CI.

Os comandos seguintes são os outputs literais desta revisão, com códigos de saída.

### `python -V`

```text
Python 3.12.10
```

Exit code: `0`.

### `python -m pytest -q -rs`

```text
............................s........................................... [ 15%]
...............................................ss....................... [ 31%]
........................................................................ [ 46%]
........................................................................ [ 62%]
........................................................................ [ 78%]
........................................................................ [ 93%]
.............................                                            [100%]
=========================== short test summary info ===========================
SKIPPED [1] tests\test_analyst_dashboard.py:373: Browser QA opcional exige FOOTBALLIQ_PLAYWRIGHT_MODULE já instalado
SKIPPED [1] tests\test_db_integration.py:72: integração PostgreSQL desativada por defeito; ativar FOOTBALLIQ_DB_RUN_INTEGRATION=1
SKIPPED [1] tests\test_db_integration.py:96: integração PostgreSQL desativada por defeito; ativar FOOTBALLIQ_DB_RUN_INTEGRATION=1
458 passed, 3 skipped in 4.17s
```

Exit code: `0`.

### `python -m ruff check .`

```text
All checks passed!
```

Exit code: `0`.

### `python -m ruff format --check .`

```text
61 files already formatted
```

Exit code: `0`.

### `python -m pip check`

```text
No broken requirements found.
```

Exit code: `0`.

### `git diff --check`

```text
(stdout/stderr vazios)
```

Exit code: `0`.
