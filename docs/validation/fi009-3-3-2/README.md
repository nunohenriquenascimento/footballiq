# FI-009.3.3.2 — Adaptador seguro de apresentação Multi-Insights

17 de novembro de 2026. **Implementação offline concluída para revisão; sem HTML,
CSS, CLI ou publicação.** Quarenta e quatro testes novos passaram; suíte completa:
523 passed, 3 skipped, em Python 3.12.10. Nenhuma inferência Ollama ou instalação.

## Branch, base e preservação

Lidos AGENTS.md e o relatório FI-009.3.3.1. Origin confirmado pelo contexto Git:
https://github.com/nunohenriquenascimento/footballiq.git.
Executado git fetch origin sem mudar checkouts. Main remota atual confirmada em
`5750756d34f95483c5358cd40276b2932e56ba8d`; merge-base --is-ancestor da base aprovada
em origin/main terminou com exit code 0. Não existia branch de apresentação equivalente.

Criadas branch `feature/multi-insights-presentation-adapter` e worktree
`.worktrees/multi-insights-presentation-adapter` a partir de origin/main nesse SHA.
A nova branch acompanha inicialmente origin/main por configuração automática do Git.
Nenhum commit criado; staging vazio; nenhuma alteração a main local ou às seis
worktrees anteriores. A nova worktree é a sétima. As alterações históricas não
publicadas continuam na origem, sem stash, clean, reset ou eliminação de ficheiros.

## Ficheiros novos e limites

- `src/footballiq/insight_presentation.py`: contrato e adaptação/revalidação offline.
- `tests/test_insight_presentation.py`: 44 casos com fixtures sintéticas e sockets bloqueados.
- `docs/validation/fi009-3-3-2/README.md`: este relatório.
- `docs/validation/fi009-3-3-2/examples.json`: exemplos sintéticos de cartões e rejeições.

Nenhum ficheiro funcional anteriormente existente foi alterado. Em particular:
analyst_dashboard.py, analyst_demo.py, contrato v1, catálogo de insights, Analytics,
Trends, política Ollama, ORM/persistência e Match Tracker intactos. Não há nova
dependência, chamada de rede, leitura de .env ou consulta PostgreSQL no adaptador.
Não se criou HTML nem se ativou integração no dashboard.

## Contrato final

`prepare_insights_presentation(report, result) -> InsightsPresentation` aceita o
FactualReport atual e InsightNarrativeResult ou None. O dataclass de entrada não
é considerado prova de validação. A função não recebe cliente, modelo, URLs ou links.

Quatro estruturas novas, frozen e com slots, contendo apenas valores escalares,
tuplas e outras estruturas imutáveis:

| Estrutura | Conteúdo |
| --- | --- |
| InsightsPresentation | status not_requested/disabled/unavailable/available; reason_code seguro; mensagem local; items tuple; provenance ou None |
| InsightCard | ordinal, plan_id, family, scope, canonical_text, display_text, formatting_status, covered_matches, selected_matches, coverage, sample_size, subtotal_notice, descriptive_limit, fact_version, formula_version, match_refs, match_versions, match_event_ids, evidence_refs |
| EvidenceReferenceView | fact_id, fact_version, evidence_id, evidence_digest e source do plano verificado |
| SharedProvenance | snapshot_id, snapshot_version, evidence_digest, source, schema_version, catalog_version, source_system, source_instance_id e limite descritivo comum quando verificável |

Available só é produzido após concluir todos os cartões e comparar a seleção
integralmente. None resulta em not_requested; disabled resulta em disabled sem
cartões. Qualquer indisponibilidade/rejeição tem items=() e provenance=None.
Os construtores destas estruturas, como quaisquer dataclasses, não autenticam
chamadores arbitrários: a futura integração deve usar o adaptador como fronteira.
Não foi adicionado título livre nem qualquer link de modelo ao contrato.

## Revalidação implementada

1. Estados sem seleção não constroem bundle. Available exige origem da demonstração
   e dados disponíveis; ausência de elegíveis é tratada explicitamente.
2. Reconstrói exatamente um EvidenceBundle para a adaptação e obtém a shortlist
   pela implementação real existente.
3. Reutiliza `_validate_ids` e `_TOPICS` de multi_insights: cardinalidade 1–3,
   unicidade, IDs apresentados e famílias distintas. Não se duplicou a regra ou o mapa.
4. Exige snapshot_id e evidence_digest iguais aos do bundle atual.
5. Recupera cada plano fechado, verifica a identidade da asserção e chama
   render_insight com o mesmo bundle de adaptação para todos os cartões.
6. Recupera referências de jogos tanto por ID como por estruturas de referência
   temporal. Preserva ordem, versões e event_ids, reconfirmando versão, origem,
   instância e eventos contra as referências do relatório atual.
7. Deriva cobertura, amostra, âmbito, famílias, evidências e versões exclusivamente
   dos planos/factos atuais; não usa números ou texto livre de clientes.
8. Reconstrói o texto canónico completo e exige igualdade exata com result.text.
9. Exige igualdade exata da tupla de referências, incluindo ordem e multiplicidade.
10. Campos de proveniência comum só são agrupados quando iguais. Versões de catálogo
    incompatíveis entre cartões rejeitam toda a seleção. Fórmulas, amostras,
    denominadores, versões de jogos e eventos permanecem por cartão.

Nenhum cartão é devolvido antecipadamente. Falha no segundo/terceiro cartão
descarta a seleção inteira. Não há reparação, substituição de IDs, truncagem,
fallback determinístico automático ou retry.

O bundle de adaptação é adicional ao bundle interno que o seletor já construiu;
o adaptador não chama narrate_insights. Não se afirma que o percurso completo
seletor+adaptador constrói apenas um bundle. O texto e referências do resultado
available são verificados mesmo que o próprio resultado tenha sido construído
manualmente. A origem continua a ser confiável apenas no contexto da demonstração;
digests não certificam autenticidade operacional.

## Projeção textual exata

Para `footballiq.insights.v1`, reconstrói o sufixo literal do formato existente,
com cobertura/amostra, subtotal, limite descritivo, snapshot, versão do catálogo,
fórmula e pares ID@data_version na ordem original das referências. Só se o texto
terminar exatamente nesse sufixo, e restar corpo não vazio, a apresentação remove
esse sufixo por comprimento. O resultado é formatting_status=projected_v1.

canonical_text permanece integral. Nenhuma alteração a fact.text, planos, evidências
ou digest. Palavras Snapshot e Cobertura no corpo futebolístico são preservadas;
não há regex heurística, split por linhas, substituição genérica ou geração livre.

O cartão mantém cobertura/amostra e subtotal_notice próprios. descriptive_limit
contém a frase verificada e pode ser apresentado uma única vez a partir da
proveniência comum se todos os cartões partilharem esse valor.

Formato/versão desconhecido, sufixo divergente ou corpo vazio: display_text recebe
canonical_text completo, formatting_status=canonical_fallback. Esse fallback é
apenas de formatação; não transforma uma falha factual em sucesso. O limite comum
fica vazio se não for verificável em todos os cartões, e o texto canónico continua
a conter toda a informação original. Em seleções mistas, os cartões projetáveis
mantêm os seus limites próprios; o renderer futuro não deve inventar um limite comum.

## Estados e mensagens locais

None e disabled são distintos de unavailable. São reconhecidos no_facts,
no_eligible_insights, timeout, invalid_selection, insufficient_diversity,
invalid_plan, invalid_settings, connection_unavailable, model_not_found,
client_required e demo_only. Motivos desconhecidos, incluindo códigos de transporte
não apresentados especificamente, resultam em unavailable genérico.

Mensagens vêm de allowlist local, sem reason bruto, URL, stack trace ou credenciais.
Resultados rejeitados não expõem cartões, texto ou proveniência parciais. Exemplos
de timeout, invalid_selection, motivo desconhecido e texto adulterado constam do
JSON de demonstração. O adaptador não tenta apresentar narrativa alternativa.

## Exemplos offline de 1, 2 e 3 cartões

Os exemplos foram executados com a variante rich_four_distinct sintética e cliente
falso que fornece só plan_ids; a projeção e os factos são reais do backend local.
Não constituem inferências reais de Gemma/Qwen. A fixture em disco não foi editada.
Também existe teste específico de duas famílias na complete_five original.

### 1_cards

Estado: available; ordem: insight:form.

- 1. results — Forma recente: Vitórias: 2; Empates: 1; Derrotas: 1; Jogos sem sofrer golos: 1; Jogos sem marcar: 1; Média GF: 1,000; Média GA: 1,000. Médias por jogo coberto, arredondadas a três casas decimais.
  Cobertura 4/4; amostra 4; formato projected_v1.

### 2_cards

Estado: available; ordem: insight:form, insight:recent_vs_older.

- 1. results — Forma recente: Vitórias: 2; Empates: 1; Derrotas: 1; Jogos sem sofrer golos: 1; Jogos sem marcar: 1; Média GF: 1,000; Média GA: 1,000. Médias por jogo coberto, arredondadas a três casas decimais.
  Cobertura 4/4; amostra 4; formato projected_v1.
- 2. comparison — Comparação descritiva de médias por jogo (arredondadas a três casas decimais): Recentes (n=2): Média GF 1,500, Média GA 0,500; Antigos (n=2): Média GF 0,500, Média GA 1,500.
  Cobertura 4/4; amostra 4; formato projected_v1.

### 3_cards

Estado: available; ordem: insight:form, insight:recent_vs_older, insight:temporal_goals.

- 1. results — Forma recente: Vitórias: 2; Empates: 1; Derrotas: 1; Jogos sem sofrer golos: 1; Jogos sem marcar: 1; Média GF: 1,000; Média GA: 1,000. Médias por jogo coberto, arredondadas a três casas decimais.
  Cobertura 4/4; amostra 4; formato projected_v1.
- 2. comparison — Comparação descritiva de médias por jogo (arredondadas a três casas decimais): Recentes (n=2): Média GF 1,500, Média GA 0,500; Antigos (n=2): Média GF 0,500, Média GA 1,500.
  Cobertura 4/4; amostra 4; formato projected_v1.
- 3. timing — Distribuição temporal dos golos: Minutos 00-14 contra: 3; Minutos 00-14 a favor: 2; Minutos 15-29 contra: 0; Minutos 15-29 a favor: 1; Minutos 30-44 contra: 0; Minutos 30-44 a favor: 0; Minutos 45-59 contra: 0; Minutos 45-59 a favor: 1; Minutos 60-74 contra: 1; Minutos 60-74 a favor: 0; Minutos 75-89 contra: 0; Minutos 75-89 a favor: 0; Minutos 90+ contra: 0; Minutos 90+ a favor: 0; Período 1 contra: 3; Período 1 a favor: 3; Período 2 contra: 1; Período 2 a favor: 1.
  Cobertura 4/4; amostra 4; formato projected_v1.

O [examples.json](examples.json) inclui textos canónicos integrais, projeções,
proveniência, versões, referências e eventos por cartão, além de fallbacks seguros.
Os exemplos bloqueiam socket.connect e create_connection e verificam zero chamadas.

## Testes e resultados literais

44 casos específicos: um/dois/três cartões e ordem, unicidade/diversidade, IDs
inexistentes/externos/duplicados/quatro IDs, adulteração parcial, texto/referências,
ordem e multiplicidade das referências, snapshots/digests antigos, outro relatório,
versões incompatíveis, parcial temporal 4/5, preservação de denominadores, eventos,
termos Snapshot/Cobertura no corpo, sufixo exato e ordem de versões, formato futuro
e fallback integral/misto, estados, bundle único por adaptação, imutabilidade profunda
e factual/Trends/bundle preservados. Sockets bloqueados em autouse.

Durante a implementação, os testes identificaram e resolveram no novo módulo a
necessidade de tratar referências temporais estruturadas. O Ruff configurado para
3.14 também formatou inicialmente um except com sintaxe nova: substituiu-se pelo
padrão de constante de exceções já usado no projeto, compatível com o Python 3.12 local.
Não houve alteração ao catálogo para resolver estes casos. Outputs finais abaixo.

Ambiente virtual existente; imports confirmados no src da nova worktree.
Python **3.12.10** local. Não se executou nem se declara aprovado CI Python 3.14
nesta tarefa. Nenhuma dependência instalada.

### `python -V`

Exit code: 0.

```text
Python 3.12.10
```

### `python -m pytest -q -rs`

Exit code: 0.

```text
............................s........................................... [ 13%]
...............................................ss....................... [ 27%]
........................................................................ [ 41%]
........................................................................ [ 54%]
........................................................................ [ 68%]
........................................................................ [ 82%]
........................................................................ [ 95%]
......................                                                   [100%]
=========================== short test summary info ===========================
SKIPPED [1] tests\test_analyst_dashboard.py:373: Browser QA opcional exige FOOTBALLIQ_PLAYWRIGHT_MODULE já instalado
SKIPPED [1] tests\test_db_integration.py:72: integração PostgreSQL desativada por defeito; ativar FOOTBALLIQ_DB_RUN_INTEGRATION=1
SKIPPED [1] tests\test_db_integration.py:96: integração PostgreSQL desativada por defeito; ativar FOOTBALLIQ_DB_RUN_INTEGRATION=1
523 passed, 3 skipped in 5.01s
```

### `python -m ruff check .`

Exit code: 0.

```text
All checks passed!
```

### `python -m ruff format --check .`

Exit code: 0.

```text
66 files already formatted
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

### `python -m pytest -q tests/test_insight_presentation.py`

Exit code: 0.

```text
............................................                             [100%]
44 passed in 0.61s
```

Skips: browser opcional sem FOOTBALLIQ_PLAYWRIGHT_MODULE e dois testes PostgreSQL
desativados por defeito. Não se realizou browser QA ou PostgreSQL dedicado nesta tarefa.
O git diff --check normal não inclui ficheiros não rastreados; Ruff e formatação
verificaram os ficheiros novos. Staging continua vazio, sem adicionar ficheiros ao Git.

## Preservação, riscos e próximo passo

Comparados hashes de **586 ficheiros anteriores**, sem alterações ou remoções. Status e staging do checkout original e origem histórica preservados. Main local intacta. A única mudança de referências locais é a branch nova autorizada; registou-se a sétima worktree. Inventários completos ficam fora do repositório.

Riscos e limitações:

- O adaptador reutiliza duas APIs internas de multi_insights (_validate_ids e
  _TOPICS), para não duplicar política nem alterar o módulo existente nesta tarefa.
  Mudanças futuras nessas APIs exigem regressões; uma API pública mínima pode ser
  revista separadamente, sem copiar regras para a apresentação.
- A projeção está explicitamente ligada ao sufixo textual v1. Mudanças legítimas
  de formato causam fallback integral, não perda silenciosa de conteúdo.
- Reconstrução de bundle/planos e revalidação têm custo adicional offline; não se
  mediu desempenho nem se introduziu cache que pudesse misturar snapshots.
- Os dataclasses não fazem escaping nem geram links. A integração HTML futura
  deve escapar todo o texto e produzir apenas âncoras locais verificadas.
- Não existe integração dashboard/CLI nesta entrega. A origem é sintética e os
  testes locais são Python 3.12; CI 3.14 permanece pendente para futura publicação.

Recomenda-se revisão do ChatGPT e, após aprovação, avançar para **FI-009.3.3.3 — HTML**,
consumindo este adaptador sem confiar em dataclasses arbitrários, sem nova seleção
no renderer e mantendo atomicidade, proveniência e estados seguros. Não publicar
ou integrar automaticamente esta alteração. Sem commit, push, PR ou merge.

Artefactos externos locais desta tarefa: scripts de validação/relatório, checks,
exemplos e inventários em implementation-fi009-3-3-2-20261117. Não publicar inventários
privados. Documentação e exemplos sanitizados foram criados apenas na worktree nova.
