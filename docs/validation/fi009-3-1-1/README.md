# FI-009.3.1.1 ? Revis?o para publica??o em PR draft

## ?mbito

Base aprovada: `9d33498a24f068c6ed4b11255b9e5549f9801a1a`.
Branch: `feature/football-insights-catalog`. Publica??o apenas em PR draft;
merge n?o autorizado. Requisito mantido: **Python >=3.14**.

O cat?logo n?o est? integrado com Ollama nem com o dashboard. A revis?o n?o
alterou Analytics, Trends, contrato v1, ORM, persist?ncia ou Match Tracker.
N?o foram instaladas depend?ncias nem executados modelos ou agentes.

## Revis?o t?cnica

- Confirmadas as APIs reais `build_insights`, `prepare_insight_plans` e
  `render_insight`, com regress?es de compatibilidade do cat?logo anterior.
- Totais e distribui??o temporal prov?m de Analytics; forma, m?dias e grupos
  prov?m de Trends. Os sufixos consecutivos derivam dos jogos j? ordenados de
  Trends, sem recalcular os agregados existentes.
- Factos compostos conservam snapshot, origem, vers?es, f?rmula, valores,
  refer?ncias e denominadores. EvidenceBundle continua profundamente imut?vel.
- AGGREGATE_RESULT representa uma observa??o de um facto composto determin?stico
  do backend, n?o uma rela??o comparativa livre. N?o h? causas t?ticas ou previs?es.
- GroundedNarrativeValidator rejeita refer?ncias inventadas, duplicadas, trocadas
  ou incompletas. O renderer exige ainda igualdade com o plano fechado.
- Desconhecidos n?o se tornam zeros nos insights. Subtotais s?o identificados;
  sequ?ncias interrompem-se em desconhecidos e s?o omitidas com datas empatadas.
- Compara??es mant?m os dois n e a composi??o dos grupos; m?nimos de amostra e
  empate na fronteira temporal seguem Trends.
- A omiss?o de distribui??o temporal sem IDs de eventos ? deliberada, incluindo
  zeros leg?timos sem eventos. N?o se fabricam evid?ncias a partir de agregados.
- Os helpers internos do contrato preservam a canoniza??o existente. Nenhuma
  incompatibilidade foi demonstrada; o acoplamento permanece documentado.
- Expandir o bundle altera digest e IDs de evid?ncia, mesmo preservando os factos
  antigos. Futuros planos Ollama ter?o de usar o mesmo bundle desde a prepara??o
  at? ? sele??o e renderiza??o, sem transportar IDs de outro bundle.

Foram corrigidos apenas dois defeitos de texto: concord?ncia em sequ?ncias e
men??o a m?dias numa distribui??o temporal de contagens. Acrescentaram-se dez
regress?es, incluindo proveni?ncia exata, adultera??o de refer?ncias, digest,
empates entre fusos hor?rios e os textos corrigidos. O cat?logo tem 35 testes
pr?prios, executados com liga??es de rede bloqueadas.

## Imports e ambiente local

N?o existe uma venv pr?pria neste worktree. Foi reutilizado o int?rprete da venv
j? dispon?vel, com PYTHONPATH a apontar para o src deste worktree, sem instala??o.
Os caminhos absolutos de `footballiq`, `analytics`, `trends`, `contract` e
`insights` foram resolvidos e verificados por assertions como pertencentes a
`<worktree>/src/footballiq`. Nenhum m?dulo foi importado do checkout original.
O Python dispon?vel ? 3.12.10: estes resultados locais n?o substituem a valida??o
Python 3.14 do CI. O workflow existente configura Python 3.14 e executa testes
gerais, PostgreSQL dedicado, Ruff, formata??o e pip check no evento pull_request.
O estado e o HEAD do workflow devem ser consultados nos checks do PR.

## Outputs literais locais

### `python -V`

```text
Python 3.12.10
```

Exit code: `0`.

### `python -m pytest -q -rs`

```text
............................s........................................... [ 17%]
...............................................ss....................... [ 35%]
........................................................................ [ 53%]
........................................................................ [ 71%]
........................................................................ [ 89%]
.........................................                                [100%]
=========================== short test summary info ===========================
SKIPPED [1] tests\test_analyst_dashboard.py:373: Browser QA opcional exige FOOTBALLIQ_PLAYWRIGHT_MODULE já instalado
SKIPPED [1] tests\test_db_integration.py:72: integração PostgreSQL desativada por defeito; ativar FOOTBALLIQ_DB_RUN_INTEGRATION=1
SKIPPED [1] tests\test_db_integration.py:96: integração PostgreSQL desativada por defeito; ativar FOOTBALLIQ_DB_RUN_INTEGRATION=1
398 passed, 3 skipped in 3.67s
```

Exit code: `0`.

### `python -m ruff check .`

```text
All checks passed!
```

Exit code: `0`.

### `python -m ruff format --check .`

```text
57 files already formatted
```

Exit code: `0`.

### `python -m pip check`

```text
No broken requirements found.
```

Exit code: `0`.

### `git diff --check`

```text
(stdout e stderr vazios)
```

Exit code: `0`.

Os tr?s skips s?o os testes opcionais de browser e PostgreSQL indicados acima;
n?o foram ocultados nem ativados servi?os locais. A integra??o PostgreSQL ?
validada separadamente pelo workflow remoto.

## Invent?rio public?vel

Inclu?dos por caminhos expl?citos:

- `src/footballiq/grounded_narrative/insights.py`;
- `tests/test_football_insights.py`;
- `docs/football-insights-catalog.md`;
- `docs/validation/fi009-3-1/generate_examples.py`;
- `docs/validation/fi009-3-1/examples.json`;
- `docs/validation/fi009-3-1-1/README.md`.

Exclu?dos: README de diagn?stico anterior, checks.json anterior,
environment-attempt.json, preservation.json e ferramentas/logs locais de results.
N?o se publicam caminhos pessoais, hashes de ficheiros locais, credenciais ou
invent?rios de ambiente. Os digests e evidence_ids dos exemplos s?o identificadores
reproduz?veis de conte?do sint?tico, necess?rios para demonstrar o contrato.
As fixtures existentes n?o foram alteradas.

## Preserva??o e limites

O checkout original, main, branches e worktrees existentes foram preservados.
Os 45 ficheiros originalmente n?o rastreados foram inventariados antes da revis?o
para compara??o local posterior; esse invent?rio e respetivos hashes n?o s?o
publicados. Nenhum ficheiro foi apagado.

O relat?rio factual continua a ser uma entrada confi?vel do backend; os hashes
n?o autenticam a origem, e MatchFacts n?o conserva os payloads completos dos
eventos. N?o se certificam completude, atualidade ou autoriza??o da exporta??o.
O renderer gen?rico v1 n?o deve ser usado para os novos factos compostos; a API
espec?fica e as consequ?ncias para uma integra??o futura est?o documentadas no
[guia do cat?logo](../../football-insights-catalog.md).
