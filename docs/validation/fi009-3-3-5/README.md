# FI-009.3.3.5 — Revisão final e Browser QA Multi-Insights

17 de novembro de 2026. **Revisão favorável à preparação de PR draft, após revisão
do ChatGPT; nenhuma publicação executada.** Sem defeitos funcionais bloqueantes
identificados. Suíte final: **578 passed, 2 skipped**; focados: **99 passed**.
Browser QA real: **14 cenários sem falhas**, com oito capturas sanitizadas.

## Estado Git e inventário

Lidos AGENTS.md e relatórios FI-009.3.3.2, .3 e .4. Branch
feature/multi-insights-presentation-adapter, worktree existente
.worktrees/multi-insights-presentation-adapter. HEAD e origin/main:
5750756d34f95483c5358cd40276b2932e56ba8d. git ls-remote confirmou esse SHA no
servidor, sem fetch nem alteração de referências. Origin:
https://github.com/nunohenriquenascimento/footballiq.git. Imports dirigidos e
confirmados no src desta worktree, com o ambiente virtual já existente.
Staging vazio e alterações ainda não commitadas.

Inventário inicial: quatro ficheiros rastreados modificados e quinze não
rastreados, todos esperados das fases anteriores. Diff rastreado: 188 inserções,
36 remoções. Inclui os seguintes ficheiros funcionais/documentais centrais:

| Estado | Ficheiro | Responsabilidade revista |
| --- | --- | --- |
| modificado | docs/ollama-multi-insights.md | Utilização HTML/CLI e limites |
| modificado | src/footballiq/analyst_dashboard.py | Renderer opcional, revalidação e cartões |
| modificado | src/footballiq/analyst_demo.py | Helper partilhado de seleção, API/CLI HTML |
| modificado | tests/test_multi_insights.py | Restrição HTML antiga substituída por rejeição de camadas concorrentes |
| novo | src/footballiq/insight_presentation.py | Adaptador e projeção v1 exata |
| novo | tests/test_insight_presentation.py | 44 testes de adaptação |
| novo | tests/test_multi_insights_dashboard.py | 31 testes HTML |
| novo | tests/test_multi_insights_demo.py | 24 testes CLI/API |

Os restantes onze ficheiros iniciais são relatórios, exemplos sintéticos e
comparações em docs/validation/fi009-3-3-2, fi009-3-3-3 e fi009-3-3-4.
Nesta revisão acrescentaram-se apenas documentação de QA, resultados sanitizados,
inventário de publicação e capturas em fi009-3-3-5. Nenhum código ou teste foi alterado.

O [inventário exato de candidatos a publicação](publication-files.txt) enumera
todos os caminhos, incluindo documentação e oito PNG. É uma proposta explícita
para staging futuro, **não autorização de publicação**. O inventário Git privado,
scripts de QA, temporários, caches, logs completos e outputs com paths pessoais
ficam fora do repositório em review-fi009-3-3-5-20261117 e devem ser excluídos.

## Revisão de arquitetura e compatibilidade

Confirmada uma seleção por geração HTML habilitada. Texto e HTML partilham
_select_insights, que chama narrate_insights uma vez; o renderer não volta a
selecionar. O modo determinístico não constrói cliente. O modo modelo é exercitado
nos testes apenas com clientes falsos. Ausência de dados/elegíveis não chama chat.

render_dashboard aceita resultado bruto de seleção e invoca o adaptador; não aceita
InsightsPresentation arbitrária como prova. Available é reconfirmado contra o
relatório atual: shortlist, famílias, planos, texto e referências exatos, incluindo
ordem/multiplicidade, snapshot/digest e versões. Qualquer falha rejeita tudo.
O adaptador reconstrói um bundle na fronteira de apresentação; isso não é uma
segunda seleção e não altera o bundle interno do seletor.

Reconfirmadas projeção v1 por sufixo reconstruído exato, canonical_text integral
nos detalhes e fallback integral apenas de formatação. Sem regex heurística,
alteração do catálogo, digest ou evidências. Cobertura/amostra/subtotal e versões
específicas permanecem por cartão; apenas metadados comprovadamente comuns são
agrupados. As referências temporais conservam eventos e versões.

Os testes completos preservam os modos antigos, CLI textual, segurança de escrita,
abertura explícita e exclusão de camadas concorrentes. Comparações já capturadas
nas fases anteriores continuam válidas porque os hashes do código não mudaram:
11 outputs do renderer e 12 da demonstração idênticos byte a byte aos anteriores.
Não se apresentam essas comparações antigas como uma recaptura nesta revisão.
O comando --html --insights deterministic mantém dois cartões em complete_five.

## Segurança e fallback

Revisão dos diffs e ficheiros novos confirmou html.escape em conteúdo/atributos
dinâmicos, IDs locais por ordinal, âncoras #match-N apenas para jogos existentes,
CSP restritiva preservada e ausência de scripts ou recursos remotos. A política
de evidências, catálogo, Analytics, Trends, contrato v1, persistência e Match Tracker
não foram alterados pelo conjunto de implementação.

Factual, Trends e jogos permanecem disponíveis perante no_facts, no_eligible_insights,
timeout, invalid_selection, insufficient_diversity, invalid_plan e motivos desconhecidos.
Mensagens do adaptador são locais e sanitizadas, sem URL, reason bruto, evidências
rejeitadas ou fragmentos. Sem retry, reparação ou alternativa determinística automática.
Fixtures sintéticas, falsos clientes e sockets bloqueados nos testes de integração.

## Browser QA executado

Playwright já instalado **1.63.0**; Microsoft Edge existente
**157.0.4341.60**, executado headless sem instalação. A variável do módulo
foi definida apenas no processo de teste, sem alterar configuração persistente.
O teste browser antigo da suíte também executou com sucesso.

QA específico: sete fixtures por viewport, total 14 casos, em **1440×900** e
**390×844**. Incluiu 1, 2 e 3 cartões válidos, timeout, invalid_selection, motivo
desconhecido e ausência de jogos. As páginas foram geradas pelo código atual,
exclusivamente com fixtures sintéticas e clientes falsos. Resultado detalhado em
[browser-results.json](browser-results.json).

Todos passaram:

- Um h1, um h2 no painel e cardinalidade correta, sem IDs HTML duplicados.
- Zero overflow horizontal com zoom CSS 100% e 200%, em ambos os viewports.
- Foco visível e abertura/fecho de cada details do painel com Enter.
- Links de cartões clicados, hash de destino confirmado e jogos existentes.
- CSP com script-src/connect-src none; nenhum script ou src; **zero requests HTTP(S)**,
  intercetados e bloqueados caso ocorressem no contexto da página.
- Contraste calculado para títulos, texto, links, estado e summaries visíveis
  do painel: mínimo observado **5.640:1**, superior a 4,5:1.
- Media print: sidebar oculta, texto canónico de details fechado disponível e
  cartões com break-inside avoid. O teste antigo acrescentou verificações de
  impressão, contraste e conteúdo longo nas páginas factuais.

Foram guardadas seis capturas de página completa (1–3 cartões × desktop/mobile)
e duas capturas do painel de três cartões. Não incluem browser chrome, caminhos
pessoais, dados operacionais ou credenciais. As capturas do desktop e do painel
mobile de três cartões foram inspecionadas visualmente. O cartão temporal é denso,
mas legível, sem corte ou overflow; simplificá-lo seria revisão de conteúdo futura,
não alteração autorizada à política nesta tarefa.

Capturas:

- [1440-1-cards.png](screenshots/1440-1-cards.png)
- [1440-2-cards.png](screenshots/1440-2-cards.png)
- [1440-3-cards-panel.png](screenshots/1440-3-cards-panel.png)
- [1440-3-cards.png](screenshots/1440-3-cards.png)
- [390-1-cards.png](screenshots/390-1-cards.png)
- [390-2-cards.png](screenshots/390-2-cards.png)
- [390-3-cards-panel.png](screenshots/390-3-cards-panel.png)
- [390-3-cards.png](screenshots/390-3-cards.png)

A captura foi estabilizada no topo antes de gravar a página completa, evitando
artefactos de scroll suave após cliques de âncoras. O QA voltou a passar 14/14.
O zoom testado é CSS zoom, como no teste de browser existente; não se afirma que
foi usado o controlo nativo de zoom do navegador. A impressão foi testada por
emulação de media/visibilidade, não por inspeção de PDF paginado ou impressora.
Zero requests refere-se ao contexto das páginas, não à telemetria externa do SO/browser.

## Outputs literais dos checks finais

Python local **3.12.10**, não 3.14. Nenhum CI executado ou declarado aprovado.
A primeira tentativa encontrou erros de acesso nos temporários pytest existentes
e avisos de cache. Outputs completos foram preservados localmente. Não eram
falhas de asserções do produto. A execução final usou diretórios novos e exclusivos
para --basetemp e cache_dir por PYTEST_ADDOPTS, fora do repositório. Não se apagaram
temporários anteriores nem se alterou código para fazer os testes passar.

### `python -V`

Exit code: 0.

```text
Python 3.12.10
```

### `python -m pytest -q -rs`

Exit code: 0.

```text
........................................................................ [ 12%]
...............................................ss....................... [ 24%]
........................................................................ [ 37%]
........................................................................ [ 49%]
........................................................................ [ 62%]
........................................................................ [ 74%]
........................................................................ [ 86%]
........................................................................ [ 99%]
....                                                                     [100%]
=========================== short test summary info ===========================
SKIPPED [1] tests\test_db_integration.py:72: integração PostgreSQL desativada por defeito; ativar FOOTBALLIQ_DB_RUN_INTEGRATION=1
SKIPPED [1] tests\test_db_integration.py:96: integração PostgreSQL desativada por defeito; ativar FOOTBALLIQ_DB_RUN_INTEGRATION=1
578 passed, 2 skipped in 7.27s
```

### `python -m pytest -q -rs tests/test_insight_presentation.py tests/test_multi_insights_dashboard.py tests/test_multi_insights_demo.py`

Exit code: 0.

```text
........................................................................ [ 72%]
...........................                                              [100%]
99 passed in 0.97s
```

### `python -m ruff check .`

Exit code: 0.

```text
All checks passed!
```

### `python -m ruff format --check .`

Exit code: 0.

```text
71 files already formatted
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

O total anterior 577 passed/3 skipped passou a 578 passed/2 skipped porque o
browser QA opcional já instalado foi ativado e passou. Os dois skips restantes são
os testes PostgreSQL desativados por defeito; não houve PostgreSQL dedicado.
Os 99 focados correspondem a 44 adaptador + 31 HTML + 24 CLI/API.
Ruff e formatação incluem ficheiros Python não rastreados; git diff --check normal
abrange os rastreados. Nenhuma instalação de dependências/modelos ou Ollama real.

## Defeitos, limitações e prontidão

**Nenhum defeito funcional objetivo bloqueante identificado nesta revisão.**
O problema de permissões do ambiente foi contornado com isolamento de temporários,
sem tocar em ficheiros anteriores. Não se fizeram correções funcionais nesta tarefa.

Limitações pendentes: Python 3.14/CI para o conjunto ainda não publicado; browser
QA em apenas uma versão Edge/Windows; zoom CSS; impressão sem PDF paginado;
PostgreSQL dedicado omitido. Dados exclusivamente sintéticos e ausência de nova
inferência real. O custo adicional da revalidação não foi medido. O adaptador usa
APIs internas do seletor e uma projeção ligada ao formato v1; mudanças futuras
devem continuar a passar os testes e preservar fallback integral.

Recomendação: **pronto para preparar um PR draft**, condicionado à revisão do
ChatGPT, staging explícito do inventário sanitizado e posterior CI Python 3.14.
Não significa aprovação de merge nem publicação automática. Não foi criado commit,
push, PR ou merge. Mantêm-se as autorizações separadas dessas operações.

## Preservação

Comparados hashes de **680 ficheiros anteriores**: zero alterações ou remoções. Referências Git, sete worktrees e status do checkout original/origem histórica preservados; staging vazio. O código funcional, testes, relatórios e artefactos anteriores não foram editados. Só se acrescentaram artefactos de revisão/QA. .git, ambientes virtuais e caches não integram o inventário de conteúdo; temporários novos ficam separados.

Termina-se com este relatório para revisão do ChatGPT, sem publicação.
