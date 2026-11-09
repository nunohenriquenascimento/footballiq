# FI-008.2.1 — Ensaio real do AI Analyst

Ensaio local de 2026-11-09, na branch `feature/ai-analyst-demo`, sobre a base
`82df0992b102f98317f39a25d31fe8479a8cfea2`. FI-008.1 e FI-008.2 permanecem
sem commit. Nenhuma alteração ao Tracker, PostgreSQL ou motor factual.

## Disponibilidade e âmbito

O executável Ollama já existia. Consultaram-se apenas `GET /api/version`,
`GET /api/tags` e `GET /api/ps` em `127.0.0.1:11434`, por `http.client`, sem
proxies ou redirects. Servidor ativo: versão `0.40.15`. Não havia modelo em RAM
na consulta inicial. Não se arrancaram serviços nem se descarregaram modelos.

Modelos instalados encontrados: `gpt-oss:latest`, `phi3:latest`, `gemma3:270m`,
`qwen3.5:4b`, `qwen3:8b` e `qwen3:4b`. Escolheu-se inicialmente `qwen3:4b`,
menor que a variante 8B. Depois dos timeouts, ensaiou-se `gemma3:270m`, já instalado.
Isto carrega modelos para inferência no servidor existente; não instala serviços.

Os pedidos usaram só as fixtures aprovadas pelo carregador FI-008.1. O contexto
minimizado não contém nomes, paths, credenciais ou texto livre da origem. A
seleção só é aceite pelo validador existente; não se apresentou prosa do modelo.

## Tempos reais

Um harness em memória chamou `load_demo_report`, `interpret_report` e o transporte
HTTP real. Mediu `perf_counter` desde a preparação/validação até ao resultado;
nenhum relógio global foi adicionado ao relatório. Guardaram-se apenas os valores
abaixo, não respostas brutas do servidor.

| Modelo | Cenário | Repetição | Total (s) | Estado | Referências válidas distintas |
| --- | --- | --- | --- | --- | --- |
| qwen3:4b | complete_five | 1 | 5.0219 | unavailable: timeout | 0 |
| qwen3:4b | complete_five | 2 | 5.0046 | unavailable: timeout | 0 |
| qwen3:4b | complete_five | 3 | 5.0146 | unavailable: timeout | 0 |
| qwen3:4b | partial_match | 1 | 5.0135 | unavailable: timeout | 0 |
| qwen3:4b | empty | 1 | <0.0001 | unavailable: sem jogos; zero pedidos | 0 |
| gemma3:270m | complete_five | 1 | 2.9557 | available | 5 |
| gemma3:270m | complete_five | 2 | 0.5303 | available | 5 |
| gemma3:270m | complete_five | 3 | 0.5587 | available | 5 |
| gemma3:270m | partial_match | 1 | 0.6568 | available | 1 |
| gemma3:270m | empty | 1 | <0.0001 | unavailable: sem jogos; zero pedidos | 0 |

As três seleções principais de Gemma foram iguais, na mesma ordem:
`match:10`, `match:9`, `match:8`, `match:7`, `match:6`. Cada resposta teve cinco
observações e cinco ocorrências de referências válidas. Não se observaram escolhas
diferentes nessas três repetições; isso não prova determinismo universal do modelo.

No cenário parcial, Gemma escolheu `match:901`, `metric:competitive`,
`metric:shots`, `metric:cards` e `metric:substitutions`: cinco referências válidas,
mas apenas um jogo distinto, `match:901`. Os textos continuaram a indicar totais
indisponíveis e cobertura 0/1. Não se inventaram números para completar a janela.

O servidor declarou `done_reason=stop` nas quatro respostas Gemma aceites. Na
primeira, `load_duration` foi 2.275 s; nas seguintes, 0.004–0.005 s. São metadados
observados do servidor, não um benchmark de hardware. Qwen não devolveu resposta
antes do timeout; não foi possível distinguir carregamento de inferência/carga.

Tempo só HTTP: Qwen 5.0194, 5.0038, 5.0139 e 5.0128 s; Gemma 2.9538, 0.5295,
0.5579 e 0.6559 s. O timeout de cinco segundos por operação corresponde aos
fallbacks observados, com pequena sobrecarga. Continua a não ser prazo absoluto
contra um servidor que envie bytes lentamente. Fechar a ligação não prova que o
servidor tenha cancelado imediatamente a inferência. Não se fizeram retries automáticos.

Os pedidos foram de 5661/4154 bytes para Qwen e 5664/4157 para Gemma
(cenários principal/parcial). Respostas Gemma: 704, 702, 702 e 742 bytes.
Os limites não foram atingidos pelo uso normal.

## Preservação e CLI

Para cada ensaio comparou-se `report.model_dump_json()` antes/depois e o prefixo
factual com `run_demo(scenario)` sem LLM. Todas as comparações foram iguais,
incluindo os quatro timeouts Qwen. A repetição principal não alterou fórmulas,
valores, datas, referências ou versões das fixtures.

Também se executou a CLI real em subprocessos, para cada um dos três cenários:

```powershell
.\.venv\Scripts\python.exe -B -m footballiq.analyst_demo --fixture complete_five
.\.venv\Scripts\python.exe -B -m footballiq.analyst_demo --fixture complete_five --with-llm --model gemma3:270m
.\.venv\Scripts\python.exe -B -m footballiq.analyst_demo --fixture partial_match --with-llm --model gemma3:270m
.\.venv\Scripts\python.exe -B -m footballiq.analyst_demo --fixture empty --with-llm --model gemma3:270m
```

Cada cenário foi comparado com a sua CLI sem LLM. Os tempos de ponta a ponta,
incluindo arranque Python, foram 1.1448 s, 0.8941 s e 0.2634 s, respetivamente.
Todos terminaram com exit 0 e prefixo factual integralmente igual. Principal e
parcial: `available`; vazio: `unavailable`, sem pedido ao modelo.

## Defeito corrigido e revisão de segurança

Faltava um teto explícito para a dimensão do pedido. A correção mínima acrescenta
`MAX_REQUEST_BYTES=32768`, verificado sobre o JSON UTF-8 completo antes do
transporte, e um aviso seguro de fallback. Não altera schema, opções de geração,
timeout, contrato factual ou comportamento normal da CLI.

Quatro regressões offline verificam o limite exato, o byte seguinte, Unicode
multibyte e a conservação do factual sem chamar o transporte. Mantêm-se os limites
de resposta 64 KiB e conteúdo 8 KiB. Os testes existentes cobrem JSON inválido,
referências inexistentes/duplicadas, quantidades inventadas e instruções maliciosas.

O destino real é um literal de loopback, mesmo quando a configuração usa
`localhost`; não se usa resolução DNS de nomes arbitrários. Não se seguem
redirects, não se consultam proxies e não se aceitam credenciais no URL. Não há
SQL, ferramentas ou execução de código gerado. O filtro de identidade fictícia
não constitui autenticação e não permite expor este adaptador como API de produção.

## Qualidade

Com `FOOTBALLIQ_DB_RUN_INTEGRATION=0`, `PYTHONDONTWRITEBYTECODE=1` e Python 3.12.10:

```text
python -B -m pytest -p no:cacheprovider -q -rs
218 passed, 2 skipped in 2.77s

ruff check --no-cache .
All checks passed!

ruff format --check --no-cache .
36 files already formatted

python -m pip check
No broken requirements found.

git diff --check
sem erros
```

Os dois skips são PostgreSQL, explicitamente desativado. Nenhuma base foi usada.
Os quatro casos novos elevam a suite de interpretação de 54 para 58 casos offline.
`py --list-paths` e `uv python list --only-installed --offline --no-cache`
não encontraram Python 3.14; há apenas 3.11 e 3.12. Não se instalou interpretador
ou dependência. A primeira procura uv encontrou limitações de acesso ao cache e
ao alias WindowsApps; a listagem offline posterior confirmou as versões instaladas.

## Decisão

A seleção real e o fallback ficaram demonstrados neste ambiente. É razoável
avançar para um protótipo visual leve, mantendo o factual central, o estado LLM
separado e os avisos de cobertura/referências. `gemma3:270m` é uma opção observada,
não uma dependência obrigatória ou garantia de qualidade tática.

Antes de publicar, validar em Python 3.14. Não aumentar o timeout para disfarçar
falhas nem alegar que Qwen passou. Uma interface de produção, dados reais e
prosa generativa exigem tarefas próprias. Não foram criados commits, pushes ou PRs.
