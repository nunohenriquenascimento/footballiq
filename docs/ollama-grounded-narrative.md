# FI-009.2.2 — Narrativa fundamentada com Ollama

## Base verificada

Em 11/11/2026, `git fetch origin` terminou com código 0. A API GitHub confirmou
o PR #7 como `state=closed`, `merged=true`, integrado em
`2026-11-11T15:31:44Z`, commit `4b88f52fd752955eae4e60306079557f69c9f6ab`.
Esse commit coincide com `origin/main`. O diff de `contract.py` e dos seus testes
entre o commit de correção `e082b8132c51664180089b9da13da480d3472e04` e
`origin/main` estava vazio: a correção das referências foi preservada no squash.
Branch criada a partir de `origin/main`: `feature/ollama-grounded-narrative`.
O workspace não rastreado permanece local e não faz parte desta publicação.

## Arquitetura e fronteira de confiança

`FactualReport → build_available_facts → EvidenceBundle → prepare_plans → catálogo
mínimo → OllamaClient.chat → seleção → NarrativePlan → GroundedNarrativeValidator
→ render_plan → NarrativeResult`.

O bundle permanece no backend e é construído pelo contrato existente, incluindo
as tendências calculadas pelo motor. As identidades de evidência derivam do
snapshot, digest, facto, versão e proveniência originais. O digest identifica
conteúdo; não autentica a origem. Nem factual nem tendências são alterados.

Esta primeira integração usa **seleção de planos fechados**: o modelo propõe um
plano escolhendo um identificador, em vez de preencher o contrato v1 inteiro.
O contexto contém apenas `plan_id`, `topic=verified_goals_for` e a posição relativa
`recency=newest|older`. Nomes, resultados, versões, referências, timestamps e
texto livre não são enviados. Não há dados operacionais: o orquestrador exige
`source_instance_id=fictional-local-demo`. Esta marca não autentica dados; para
o ensaio manual deve usar-se exclusivamente a CLI com fixtures aprovadas por hash.

A resposta admitida é exatamente `{"plan_id":"plan:1"}`, com um identificador
do enum emitido nesse pedido. Campos extra, incluindo `evidence_id`, snapshot,
relações, números, frases ou um plano completo, são rejeitados. IDs pertencentes
a outros catálogos são rejeitados. O identificador curto só existe no pedido;
nunca funciona como referência persistente entre snapshots.

O backend recupera o plano tipado original e valida-o integralmente antes de
renderizar. Uma falha nunca produz texto parcial. `NarrativeResult` contém
`status`, `reason`, `text`, `plan` e `references` verificadas; não devolve o texto
bruto do modelo em mensagens de erro.

## Âmbito deliberado do catálogo

Até cinco planos candidatos, um por jogo com resultado verificado; a seleção
produz uma observação de golos marcados num jogo. `sample_size=1` e
`coverage=1/número de jogos selecionados`, nunca números fornecidos pelo modelo.
Exemplo de plano interno (IDs de evidência abreviados apenas nesta explicação):

```json
{
  "schema_version": "1.0",
  "evidence_snapshot_id": "<snapshot do relatório>",
  "evidence_digest": "<digest do bundle>",
  "coverage": 0.2,
  "sample_size": 1,
  "assertions": [{
    "assertion_type": "observation",
    "fact_ids": ["match:10"],
    "relation": "aggregate_result",
    "presentation_order": 1,
    "references": [{
      "fact_id": "match:10",
      "fact_version": "<versão factual>",
      "evidence_id": "evidence:<hash emitido pelo bundle>",
      "evidence_digest": "<digest do bundle>",
      "source": "factual-engine"
    }],
    "template": "observation_aggregate_result"
  }]
}
```

Para obter um exemplo executável com todos os valores reais da fixture:

```powershell
.\.venv\Scripts\python.exe -c "from footballiq.analyst_demo import load_demo_report; from footballiq.grounded_narrative import build_available_facts; from footballiq.grounded_narrative.orchestrator import prepare_plans; r=load_demo_report(); print(prepare_plans(r, build_available_facts(r))['plan:1'].model_dump_json(indent=2))"
```

O renderer v1 usa uma frase genérica de agregado; a CLI identifica explicitamente
a secção como observação de golos marcados num jogo. Não se disponibilizam
comparações, métricas compostas ou tendências como candidatos: os templates v1
e as pré-condições do validador não garantem toda a semântica dessas relações.
O contrato v1 não foi alterado. Não há conclusões táticas nem prosa generativa.

## Opt-in, limites e fallback

Por defeito, `narrate_report` devolve `disabled/opt_in_required` sem construir
cliente nem efetuar rede. A CLI mantém a saída factual anterior.

```powershell
.\.venv\Scripts\python.exe -m footballiq.analyst_demo
# Só executar o seguinte num ensaio real autorizado, com modelo já instalado:
.\.venv\Scripts\python.exe -m footballiq.analyst_demo --with-narrative --model gemma3:270m
```

`--fixture complete_five|partial_match|empty` conserva os cenários existentes.
`--with-narrative` não combina com `--with-llm`. A integração HTML da FI-009.2.3.1
aceita `--html --with-narrative`; consultar [dashboard fundamentado](grounded-narrative-dashboard.md).
`--ollama-url` conserva as restrições existentes.

O único cliente HTTP é o existente: liga a loopback literal, converte `localhost`
em `127.0.0.1`, ignora proxies e recusa redirects. Não inicia serviços nem instala
modelos. Limites existentes: pedido 32768 bytes, envelope 65536 bytes, conteúdo
8192 bytes, sem streaming, temperatura 0, `num_predict=512`.
`OllamaSettings.timeout` limita cada operação de socket (1–10 s, padrão 5);
`deadline` define orçamento total (1–30 s, padrão 15), verificado entre blocos
de leitura e após retorno do transporte. O prazo é cooperativo: não consegue
interromper transportes falsos bloqueantes nem impor um limite absoluto ao parser
de cabeçalhos da biblioteca HTTP. Não há promessa de cancelamento rígido.

Todas as falhas devolvem narrativa indisponível, sem plano, texto ou referências:

| Situação | Motivo |
| --- | --- |
| Sem jogos / sem resultados verificados | `no_facts` / `no_verified_facts` |
| Sem cliente / configuração inválida | `client_required` / `invalid_settings` |
| Modelo ausente / HTTP / servidor inacessível | `model_not_found` / `http_error` / `connection_unavailable` |
| Timeout / transporte | `timeout` / `transport_error` |
| JSON truncado, chaves duplicadas ou validação | `invalid_plan` |
| ID desconhecido, campos extra, plano vazio | `invalid_selection` |
| Limites de bytes | `request_too_large` / `response_too_large` |
| Envelope inválido | `invalid_response` |

O fallback é sempre o factual original, sem uma segunda chamada ao modelo.
Não existe SQL, RAG, execução de código ou ferramentas autónomas.

## Validação offline e limitações

Os testes usam fixtures aprovadas e clientes falsos: seleção válida, repetibilidade,
invariância do factual, bundle e tendências, campos extra, IDs desconhecidos,
JSON incompleto, chaves duplicadas, números, relações, falhas de transporte,
ausência de rede por defeito e orçamentos. Os testes do contrato existentes
cobrem evidence_id inventado, trocado, omitido, versões e snapshots incompatíveis,
e rejeição integral antes da renderização.

Ambiente Windows efetivo: Python **3.12.10**, MSC v.1943, AMD64.
O projeto declara Python >=3.14; **3.14 não foi validado**. Não se alteraram
dependências nem metadados. O Python do PATH não tinha pytest/Ruff, pelo que
se usou `.venv\Scripts\python.exe`. PostgreSQL operacional não foi utilizado.

Os caminhos de importação foram confirmados por `__file__` dentro do checkout
Windows: `src/footballiq/analytics.py`, `src/footballiq/ollama_client.py` e
`src/footballiq/grounded_narrative/orchestrator.py`. Os caminhos pessoais ficam
apenas nos registos locais, excluídos da publicação.

## Ensaios reais e revisão

As campanhas FI-009.2.2.1 e FI-009.2.2.2 usaram Ollama 0.40.16 com modelos já
instalados. Após quatro timeouts iniciais, o diagnóstico confirmou cinco planos
aprovados: Gemma 3/3 e Qwen 2/2, todos com `plan:1`. Factual, tendências e bundle
permaneceram iguais. Com modelos carregados, o transporte e defaults originais
responderam em 0,123 s (Gemma) e 0,371 s (Qwen). Um pedido mínimo Qwen a frio
demorou 21,256 s, incluindo 8,356 s de carregamento e 12,807 s de prefill.
Isto não demonstra suporte universal a cold start nem qualidade tática avançada.
O produto mantém timeout de 5 s e prazo cooperativo de 15 s; não há warmup ou
retries automáticos. Python 3.14 requer validação pelo CI do PR.

Metodologia, medições e limites: [resumo dos ensaios](validation/grounded-narrative/README.md).
Os registos publicados são agregados e anonimizados. Os 33 artefactos originais
permanecem locais, sem integrar o PR. Esta preparação não executou inferências.

Revisão recomendada: adequação da seleção fechada ao objetivo pedagógico,
semântica de cobertura por observação, limitação dos templates v1 e orçamento
cooperativo de tempo antes de expandir o catálogo na FI-009.2.3.

## Resultados registados

Comandos executados com `.\.venv\Scripts\python.exe`:

| Comando | Resultado literal final |
| --- | --- |
| `-m pytest -q` | `344 passed, 3 skipped in 3.54s` |
| `-m ruff check .` | `All checks passed!` |
| `-m ruff format --check .` | `49 files already formatted` |
| `-m pip check` | `No broken requirements found.` |
| `git diff --check` | Sem saída, código 0 |

Os três skips são QA opcional com Playwright não configurado e dois testes
PostgreSQL desativados por defeito. Também foram executados `git status`,
`git rev-parse`, `git remote -v`, `git log`, `git diff --cached --stat`, consulta
REST do PR, comparação do commit de correção, inspeção de módulos e demonstração
da fixture `empty`. `gh` não estava instalado; a API REST substituiu-o.
`git fetch` exigiu execução fora da sandbox por falta de escrita em `.git`.

Ficheiros alterados: `src/footballiq/analyst_demo.py`,
`src/footballiq/ollama_client.py`, `tests/test_analyst_interpretation.py`.
Ficheiros novos: `src/footballiq/grounded_narrative/orchestrator.py`,
`tests/test_grounded_narrative_orchestrator.py` e este documento.
O ficheiro de workspace já existia e foi preservado fora do staging.
