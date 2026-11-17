# FI-009.3.3.3 — Integração HTML segura de Multi-Insights

17 de novembro de 2026. **Renderer integrado e validado offline; sem publicação.**
554 testes passaram, 3 skips; 31 casos novos de HTML passaram. As 11 comparações
com o renderer anterior, sem insights, preservaram o HTML byte a byte.

## Git e limites

Branch existente `feature/multi-insights-presentation-adapter`, worktree
`.worktrees/multi-insights-presentation-adapter`, HEAD e origin/main em
`5750756d34f95483c5358cd40276b2932e56ba8d`.
`git ls-remote origin refs/heads/main` confirmou a mesma main remota sem fetch.
Staging vazio antes/depois. Lidos AGENTS.md, auditoria FI-009.3.3.1 e relatório
FI-009.3.3.2; adaptador, testes e documentação anteriores estavam presentes e não
commitados, como esperado. Não se encontraram alterações inesperadas nos ficheiros
funcionais. Não se criou nova branch/worktree.

Ficheiros desta tarefa:

- Alterado `src/footballiq/analyst_dashboard.py`: parâmetro keyword-only insights,
  painel revalidado, títulos locais e CSS exclusivo do modo insights.
- Criado `tests/test_multi_insights_dashboard.py`: 31 casos HTML offline.
- Criados nesta pasta: README.md, legacy-comparison.json, 1-insights.html,
  2-insights.html, 3-insights.html e timeout.html.

O adaptador e os 44 testes anteriores ficaram byte a byte preservados, assim como
os seus relatórios e exemplos. Não se alteraram analyst_demo.py, CLI/argparse,
contrato v1, catálogo, multi_insights.py, Analytics, Trends, OllamaClient,
ORM/persistência ou Match Tracker. Sem instalações, inferências Ollama, browser QA,
commit, push, PR ou merge. Não se modificou a main local.

## API e revalidação

```python
render_dashboard(
    report,
    interpretation=None,
    *,
    narrative=None,
    insights: InsightNarrativeResult | None = None,
) -> str
```

No máximo uma camada não None entre interpretation, narrative e insights; qualquer
par é rejeitado com ValueError. Com insights=None o caminho antigo, incluindo CSS,
fica rigorosamente igual. O adaptador não é chamado nesse caminho.

Quando insights é fornecido, `_multi_insights_ai(report, result)` invoca
prepare_insights_presentation(report, result) na fronteira do renderer. Não se
aceita um InsightsPresentation arbitrário como prova: se for passado por engano
como insights, o adaptador rejeita-o sem expor o seu conteúdo. Não há seleção nova,
cliente, configuração, .env, PostgreSQL ou rede no renderer. narrate_insights não
é executado pelo renderer; os testes bloqueiam qualquer tentativa de o fazer.

A revalidação conserva o contrato do adaptador: shortlist real, cardinalidade,
famílias, texto/referências exatos, snapshot/digest atuais, planos e evidências.
O bundle de adaptação é separado do bundle interno da seleção. Os planos/cartões
não são reparados nem escolhidos novamente. Uma falha rejeita toda a seleção.

## Layout e proveniência

Um único painel AI Analyst, id analyst, um h2 analyst-title, e uma lista ordenada
com 1–3 artigos empilhados. Cada cartão tem um h3 com ordinal e título local
derivado da família/âmbito validado: forma recente, casa/fora, comparação temporal,
distribuição de golos ou sequência recente. O renderer preserva a ordem recebida
do adaptador; não gera títulos com modelos nem inferências causais.

Cada cartão apresenta display_text, cobertura n/N e amostra específicas, aviso de
subtotal quando aplicável e ligações aos jogos correspondentes. details/summary
por cartão disponibiliza texto canónico integral, estado da projeção, plano/facto,
família/âmbito, versão do facto, fórmula, coverage, versões de jogos, eventos e
referências completas das evidências, sem perder associação por observação.

A proveniência comum aparece numa secção details única: snapshot, versão,
digest, origem, sistema/instância, contrato e catálogo. O limite descritivo aparece
uma vez fora dos cartões apenas se confirmado como comum pelo adaptador. Se só
for verificável num cartão, permanece nesse cartão. Não se agregam fórmulas,
denominadores ou versões de jogos diferentes num valor comum inventado.
O texto canónico conserva os seus metadados originais nos detalhes; isso é uma
representação integral auditável, não uma segunda narrativa.

O CSS novo só é acrescentado quando o argumento insights é fornecido. Cartões
empilhados com espaçamento, borda e quebra de texto; reutiliza-se a grelha responsiva
existente. Impressão solicita evitar dividir cartões e herda o tratamento de details
da página. Não se alteraram fontes, navegação ou secções factuais.

## Segurança HTML e estados

Todos os valores dinâmicos passam por html.escape, incluindo texto, metadados,
atributos, mensagens e versões. IDs de cartão são locais, por ordinal validado,
insight-title-1 a insight-title-3. IDs de evidência não se tornam IDs HTML.
Só se geram links #match-N quando a referência existe no relatório renderizado.
Nenhum link externo, recurso remoto, JavaScript ou nova permissão CSP. A CSP
existente, script-src none e connect-src none, continua intacta.

Details/summary nativos reutilizam foco visível e semântica por teclado. A lista
ordenada e h3 preservam sequência/hierarquia. Acessibilidade visual, contraste e
impressão reais não foram medidos num browser nesta tarefa; não se apresentam
testes estruturais como prova de browser QA.

Estados:

- insights=None: renderer anterior, sem novo painel/camada.
- not_requested do adaptador: reutiliza o painel factual antigo, sem cartões novos.
- disabled: estado discreto Não solicitada, mensagem segura, zero cartões.
- unavailable: mensagem local segura do adaptador, sem cartões ou proveniência.
  Timeout, seleção inválida/diversidade, plano inválido, ausência de dados/elegíveis,
  configuração, ligação, modelo ausente e motivos desconhecidos não expõem o reason bruto.
- canonical_fallback num cartão validado: display_text integral e nota nos detalhes
  de que a projeção visual não está disponível. Não é apresentado como falha factual.

Texto, IDs, referências e snapshots rejeitados nunca são apresentados, nem em details.
Sem retry, escolha automática alternativa ou narrativa parcial. Estatísticas, jogos,
Trends, qualidade e referências factuais ficam intactos em todos os estados.

## Exemplos HTML

Todos gerados offline com fixtures sintéticas e clientes falsos; não são inferências
reais de modelos. A variante rica usa os primeiros quatro jogos de complete_five,
returned_count=4 e primeiro kickoff ajustado em memória para 2026-11-08T16:00:00Z,
como nos testes aprovados. Nenhuma fixture em disco foi editada.

- [1 insight](1-insights.html): form.
- [2 insights](2-insights.html): form, recent_vs_older.
- [3 insights](3-insights.html): form, recent_vs_older, temporal_goals.
- [Timeout](timeout.html): painel indisponível seguro; factual e Trends preservados.

Para gerar HTML por API Python, o chamador fornece o resultado da seleção e chama
render_dashboard(report, insights=result). Esta tarefa **não** ativa --html --insights;
a CLI continua com as restrições anteriores até FI-009.3.3.4.

## Testes e comparação antes/depois

31 testes novos cobrem um/dois/três cartões, ordem, painel/título únicos, IDs sem
colisões, textos canónicos, cobertura/amostra/subtotal, metadados/evidências/versões,
escaping e valores adversariais, CSP, ausência de scripts/recursos remotos, links
internos existentes, fallback de formatação, rejeição factual integral e motivos
de indisponibilidade. Incluem a recusa dos três pares de camadas e de uma
InsightsPresentation arbitrária, além da invariância factual/Trends/bundle.
Autouse bloqueia socket.connect, create_connection e construção de OllamaClient.

Comparação independente com a cópia do renderer anterior guardada antes da edição:
11 casos com HTML idêntico byte a byte. Três fixtures (complete_five, partial_match,
empty), cada uma no modo default, narrativa disabled e interpretação unavailable;
mais narrativa available e interpretação available na fixture completa.
Hashes e resultados em [legacy-comparison.json](legacy-comparison.json).
Os testes também comparam todas as secções fora do painel nos caminhos Multi-Insights,
removendo apenas o novo painel e o CSS exclusivo desse modo.

## Outputs literais de qualidade

Ambiente virtual existente; imports confirmados a partir do src da worktree
correta. Python local **3.12.10**, não 3.14. Nenhuma execução de CI nesta tarefa.

### `python -V`

Exit code: 0.

```text
Python 3.12.10
```

### `python -m pytest -q -rs`

Exit code: 0.

```text
............................s........................................... [ 12%]
...............................................ss....................... [ 25%]
........................................................................ [ 38%]
........................................................................ [ 51%]
........................................................................ [ 64%]
........................................................................ [ 77%]
........................................................................ [ 90%]
.....................................................                    [100%]
=========================== short test summary info ===========================
SKIPPED [1] tests\test_analyst_dashboard.py:373: Browser QA opcional exige FOOTBALLIQ_PLAYWRIGHT_MODULE já instalado
SKIPPED [1] tests\test_db_integration.py:72: integração PostgreSQL desativada por defeito; ativar FOOTBALLIQ_DB_RUN_INTEGRATION=1
SKIPPED [1] tests\test_db_integration.py:96: integração PostgreSQL desativada por defeito; ativar FOOTBALLIQ_DB_RUN_INTEGRATION=1
554 passed, 3 skipped in 5.56s
```

### `python -m ruff check .`

Exit code: 0.

```text
All checks passed!
```

### `python -m ruff format --check .`

Exit code: 0.

```text
68 files already formatted
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

### `python -m pytest -q tests/test_multi_insights_dashboard.py`

Exit code: 0.

```text
...............................                                          [100%]
31 passed in 0.48s
```

Os três skips são browser QA opcional sem FOOTBALLIQ_PLAYWRIGHT_MODULE e dois
testes PostgreSQL desativados por defeito. Não houve PostgreSQL dedicado. Após a
execução completa, reforçou-se apenas o bloqueio de construção do cliente no teste
novo; os 31 testes focados passaram novamente. Nenhum código funcional mudou depois
dos checks completos. git diff --check normal não cobre ficheiros não rastreados;
Ruff/formatação verificaram os ficheiros Python novos.

## Preservação e próximo passo

Inventário inicial desta tarefa: **669 ficheiros existentes**. A única alteração de conteúdo foi analyst_dashboard.py nesta worktree, conforme autorizado. Os restantes hashes, incluindo adaptador, testes anteriores, relatórios, backups e artefactos históricos, ficaram iguais. Referências Git e sete worktrees mantiveram-se idênticas; staging vazio. Inventários completos e cópia anterior do renderer permanecem na pasta externa local implementation-fi009-3-3-3-20261117, sem publicação.

Limitações: sem browser QA real ou CI Python 3.14; dados exclusivamente sintéticos;
dependência da projeção versionada e das APIs internas do seletor já documentadas
na tarefa anterior. Os exemplos não provam acessibilidade visual no browser nem
sucesso de qualquer modelo real.

Recomenda-se revisão do ChatGPT e avanço para **FI-009.3.3.4 — Integração da CLI/API
de demonstração**, mantendo seleção fora do renderer, opt-in explícito, compatibilidade
dos modos antigos e nenhuma mudança à política factual. Não publicar ou fazer merge
automaticamente. Nenhum commit, push, PR ou merge foi realizado.
