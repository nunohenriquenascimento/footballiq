# FI-009.3.3.4 — Integração CLI/API de demonstração Multi-Insights

17 de novembro de 2026. **Integração concluída offline, sem publicação.**
O comando pedido é agora suportado:

```shell
python -m footballiq.analyst_demo --html --insights deterministic --open
```

Na fixture predefinida complete_five, produz **dois cartões validados**: form e
recent_vs_older, famílias results e comparison. Não consulta Ollama.
577 testes passaram, 3 skips; 24 testes específicos novos passaram.

## Git e ficheiros

Lido AGENTS.md. Mantida a branch feature/multi-insights-presentation-adapter na
worktree existente .worktrees/multi-insights-presentation-adapter.
HEAD e referência local origin/main confirmados em
5750756d34f95483c5358cd40276b2932e56ba8d. Não houve consulta remota nesta tarefa;
não se confunde essa referência local com nova confirmação do servidor.
Staging vazio; nenhuma branch ou worktree criada. As alterações anteriores de
adaptador e renderer foram inventariadas e preservadas.

Ficheiros alterados nesta tarefa:

- src/footballiq/analyst_demo.py: helper seletor comum, argumento insights na API
  HTML e remoção da incompatibilidade específica entre --html e --insights.
- tests/test_multi_insights.py: mantém os testes de camadas concorrentes; remove
  apenas o caso que exigia rejeitar a combinação HTML agora autorizada.
- docs/ollama-multi-insights.md: exemplo de utilização e compatibilidade atualizada.

Ficheiros novos:

- tests/test_multi_insights_demo.py: 24 testes offline da API/CLI.
- docs/validation/fi009-3-3-4/README.md: este relatório.
- docs/validation/fi009-3-3-4/complete-five.html: dashboard produzido pela CLI real.
- docs/validation/fi009-3-3-4/legacy-comparison.json: 12 comparações de compatibilidade.

Sem alterações ao renderer ou adaptador aprovados, catálogo, elegibilidade,
validador, evidências, contratos, Analytics, Trends, OllamaClient, ORM/persistência
ou Match Tracker. Sem dependências, commits, pushes, PRs ou merges.

## API e fluxo implementados

`render_demo_dashboard(..., insights="deterministic"|"ollama"|None, ...) -> str`
é uma extensão keyword-only; o valor predefinido None mantém o caminho anterior.

O helper `_select_insights(report, insights, model, ollama_url, client)` é partilhado
por run_demo e render_demo_dashboard. Reutiliza narrate_insights, sem alterar
parâmetros ou política, e preserva o tratamento anterior de invalid_settings.
No modo determinístico não constrói cliente nem o consulta, mesmo se fornecido.
No modo ollama apenas constrói o cliente existente quando não há cliente injetado;
nenhuma chamada real desse modo ocorreu nesta tarefa.

O fluxo HTML carrega uma fixture aprovada, executa uma seleção e passa o resultado
ao renderer com insights=result. O renderer revalida pelo adaptador existente.
Não se faz segunda seleção, retry, reparação ou substituição automática.
Falhas devolvem o painel seguro sem cartões, mantendo o factual disponível.

A CLI permite --html --insights deterministic e --html --insights ollama com
configuração explícita. Continua a recusar --insights com --with-llm ou
--with-narrative; a API também rejeita modos concorrentes/desconhecidos.
Não se acrescentaram fixtures, parâmetros de política, timeouts ou defaults.

save_dashboard, --output, --overwrite e --open mantêm o comportamento anterior:
destino temporário por defeito; sobrescrita exige flag; abertura só depois de guardar
com sucesso e apenas com --open. A API devolve HTML sem guardar ou abrir o navegador.
Os testes anteriores de paths, symlinks e falha de navegador continuam na suíte.

## Prova do comando e exemplos

Um subprocesso executou a CLI real, com --html --insights deterministic e --output
explícito para complete-five.html. Exit code 0; o ficheiro contém dois artigos
insight-card e data-insights-status=available. O [dashboard gerado](complete-five.html)
é exclusivamente sintético e não depende de recursos remotos.

O comando exato com --open também foi testado através de main, com abertura de
navegador simulada. Confirmou-se que o destino predefinido é delegado como None
à função de gravação e que webbrowser.open recebe apenas o URI file do HTML local.
Outro teste com destino explícito confirma o mesmo comportamento. Não se abriu
um navegador real nem se apresenta essa simulação como browser QA.

O modo ollama foi exercitado só com clientes falsos: dois cartões aceites e uma
chamada por pedido; respostas inválidas e timeout rejeitados sem retry ou fragmentos.
A API com variante rica sintética em memória demonstra três cartões sem alterar
fixtures aprovadas ou introduzir essa variante na CLI.

## Testes e compatibilidade

24 casos novos: dois cartões determinísticos sem cliente, comando exato com --open,
destino explícito, cliente falso do modo ollama, seleção partilhada chamada uma vez
por saída, dados vazios/parciais sem chat, JSON/IDs inválidos, timeout, configuração
inválida, camadas concorrentes, modo desconhecido, sobrescrita/abertura segura,
opções que continuam a exigir --html e três cartões via API com fixture rica.
socket.connect e create_connection bloqueados em autouse.

Comparação independente com analyst_demo.py guardado antes da edição: **12 outputs
idênticos byte a byte**, em complete_five, partial_match e empty. Por fixture,
compararam-se texto factual, texto determinístico, texto com cliente falso do modo
ollama e HTML predefinido. Resultados em legacy-comparison.json. Os testes legados
de interpretação e narrativa também passaram na suíte completa.

O total mudou de 554 para 577: 24 casos novos e remoção de um caso antigo que
exigia recusar --html --insights. As rejeições de camadas concorrentes permanecem.

## Outputs literais finais

Ambiente virtual existente, imports confirmados no src da worktree correta.
Python local **3.12.10**, não 3.14. Sem execução ou alegação de CI nesta tarefa.

### `python -V`

Exit code: 0.

```text
Python 3.12.10
```

### `python -m pytest -q -rs`

Exit code: 0.

```text
............................s........................................... [ 12%]
...............................................ss....................... [ 24%]
........................................................................ [ 37%]
........................................................................ [ 49%]
........................................................................ [ 62%]
........................................................................ [ 74%]
........................................................................ [ 86%]
........................................................................ [ 99%]
....                                                                     [100%]
=========================== short test summary info ===========================
SKIPPED [1] tests\test_analyst_dashboard.py:373: Browser QA opcional exige FOOTBALLIQ_PLAYWRIGHT_MODULE já instalado
SKIPPED [1] tests\test_db_integration.py:72: integração PostgreSQL desativada por defeito; ativar FOOTBALLIQ_DB_RUN_INTEGRATION=1
SKIPPED [1] tests\test_db_integration.py:96: integração PostgreSQL desativada por defeito; ativar FOOTBALLIQ_DB_RUN_INTEGRATION=1
577 passed, 3 skipped in 5.84s
```

### `python -m ruff check .`

Exit code: 0.

```text
All checks passed!
```

### `python -m ruff format --check .`

Exit code: 0.

```text
70 files already formatted
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

### `python -m pytest -q tests/test_multi_insights_demo.py`

Exit code: 0.

```text
........................                                                 [100%]
24 passed in 0.46s
```

Skips: browser opcional sem FOOTBALLIQ_PLAYWRIGHT_MODULE e dois testes PostgreSQL
desativados por defeito. Não se executou browser QA nem PostgreSQL dedicado.
O git diff --check normal não abrange ficheiros não rastreados; Ruff e formatação
incluíram os testes novos. O output completo da CLI, com paths locais, permanece
apenas na evidência externa privada.

## Preservação e limitações

Comparados hashes de **676 ficheiros existentes**. Só mudaram os três caminhos autorizados acima; nenhum ficheiro foi removido. O adaptador, renderer, testes prévios de apresentação/HTML, relatórios, exemplos e artefactos históricos mantiveram os hashes. Referências Git e sete worktrees idênticas; staging vazio; main local e alterações históricas intactas. .git, ambiente virtual e caches excluídos do inventário de conteúdo.

Artefactos de avaliação desta tarefa ficaram na pasta externa local
implementation-fi009-3-3-4-20261117: cópia anterior da demonstração, scripts,
checks, prova da CLI e inventários. Não publicar inventários privados ou logs locais.

Limitações: fixtures sintéticas; nenhum Ollama real; abertura do navegador simulada
nos testes; sem validação visual real ou CI Python 3.14 nesta tarefa. A integração
não altera as garantias e limites do adaptador ou a política de evidências.

Recomenda-se revisão do ChatGPT da integração CLI/API concluída antes de qualquer
publicação ou fase seguinte. Nenhum commit, push, PR ou merge foi realizado.
