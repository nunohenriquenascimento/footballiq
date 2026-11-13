# FI-009.3.2.1 — Seleção fundamentada de múltiplos insights

O modo textual permite escolher e ordenar **1 a 3 observações**, todas geradas
pelo backend. O modelo só fornece identificadores; não escreve a narrativa.
O dashboard HTML e a integração narrativa anterior permanecem intactos.

## Arquitetura e APIs reais

```text
FactualReport → build_insights → um EvidenceBundle canónico
→ prepare_insight_plans → prepare_insight_candidates
→ OllamaClient.chat ou seleção determinística explícita
→ validar IDs e famílias → render_insight para cada plano
→ InsightNarrativeResult disponível apenas se todos passarem
```

O novo módulo `footballiq.grounded_narrative.multi_insights` disponibiliza:

- `prepare_insight_candidates(bundle)`: filtra e ordena planos já existentes.
- `narrate_insights(report, *, enabled=False, client=None, deterministic=False)`:
  controla opt-in, seleção, validação e apresentação atómica.
- `InsightNarrativeResult`: resultado imutável com `status`, `reason`, `text`,
  `plan_ids`, `references`, `snapshot_id` e `evidence_digest`.

O bundle é construído uma única vez por chamada habilitada. O mesmo objeto é
usado para preparar todos os planos e renderizar cada selecionado. O renderer
existente invoca GroundedNarrativeValidator e exige correspondência com o plano
fechado, incluindo cobertura e amostra. Não são aceites bundles ou planos
fornecidos pelo modelo. Não se combina tudo num novo NarrativePlan: preservam-se
os planos v1 individuais, sem alterar as suas relações AGGREGATE_RESULT.

O fallback não apresenta fragmentos: se o segundo ou terceiro plano falhar,
o resultado inteiro fica indisponível, sem texto, IDs, snapshot ou referências.
O factual, Trends e EvidenceBundle não são modificados.

## Contrato de seleção

Resposta admitida, sem outros campos:

```json
{"plan_ids":["insight:form","insight:recent_vs_older","insight:temporal_goals"]}
```

Cada ID tem de pertencer aos candidatos preparados para esse pedido. O schema
usa enum, uniqueItems, minItems=1 e maxItems igual ao menor de três e do número
de famílias disponíveis. O backend volta a validar essas regras, sem confiar
no suporte do modelo a JSON Schema. Rejeita IDs repetidos, IDs desconhecidos,
seleção vazia, campos extra, tipos errados, JSON inválido, constantes não JSON e
chaves JSON duplicadas. Não admite texto, números, relações ou referências
produzidos pelo modelo. A ordem de uma seleção válida é preservada.

O contexto do modelo contém apenas IDs fechados, família, âmbito, cobertura e
dimensão de amostra produzidos pelo backend. Não contém nomes, resultados,
timestamps, texto das observações, snapshots, versões ou evidence_ids. Os IDs
são selecionáveis apenas dentro da operação; uma resposta antiga só pode escolher
o candidato atual correspondente, nunca recuperar evidências antigas.

## Relevância e diversidade

Política `FI-009.3.2.1`, deliberadamente conservadora:

| Família | Candidatos | Justificação |
| --- | --- | --- |
| `results` | form, competitive, home, away | As descrições repetem contagens e médias; escolher uma |
| `comparison` | recent_vs_older, home_vs_away | Escolher um contraste por seleção |
| `timing` | temporal_goals | Contagens de eventos por períodos/minutos |
| `sequence` | winning_run, winless_run, drawing_run, losing_run | Escolher uma descrição do sufixo final |

No máximo um candidato por família. Uma seleção de uma só observação é válida;
não se exige preencher três posições nem incluir todas as famílias. A política
reduz repetição entre candidatos compostos, mas não promete eliminar qualquer
sobreposição de números entre famílias. Por exemplo, resultados e comparação
podem ambos mencionar médias; descrevem âmbitos diferentes.

Cada candidato exige pelo menos dois jogos. Agregados exigem cobertura de pelo
menos **80% do seu grupo selecionado**, sem extrapolar o subtotal. Este limiar é
uma regra de apresentação, não uma garantia de significância estatística.
Os mínimos mais exigentes das comparações continuam a pertencer a Trends.
Numa sequência, cobertura é a fração da janela incluída no sufixo, não a proporção
de resultados conhecidos: aceitam-se os dois jogos consecutivos já verificados
pelo catálogo mesmo com cobertura inferior a 80%.

A ordenação determinística usa cobertura decrescente, depois amostra decrescente
e, em empate, esta prioridade fixa: form, competitive, home, away,
recent_vs_older, home_vs_away, temporal_goals, winning_run, winless_run,
drawing_run, losing_run. Seleciona até três famílias. O LLM pode escolher e ordenar
outros candidatos elegíveis, sem repetir família.

Só entram insights gerais ou de grupos/sufixos; não se misturam observações
individuais `match:*` com agregados. A API antiga continua a disponibilizar os
factos individuais. A perspetiva da equipa, as regras de casa/fora, empates,
proveniência temporal e amostra são as do catálogo existente. Não se inferem
causas táticas nem previsões. Nenhuma alteração de contrato é necessária para
categorias: a família é metadado local da seleção, não uma afirmação nova.

## Fallback e opt-in

| Situação | Resultado/motivo |
| --- | --- |
| Sem opt-in | disabled / opt_in_required, sem sequer construir bundle |
| Origem fora da demonstração | unavailable / demo_only |
| Fixture vazia | unavailable / no_facts |
| Sem dados ou cobertura/amostra insuficiente | unavailable / no_eligible_insights |
| Modo modelo sem cliente | unavailable / client_required |
| Seleção malformada, vazia, IDs falsos ou duplicados | unavailable / invalid_selection |
| Famílias repetidas | unavailable / insufficient_diversity |
| Plano, referências, snapshot ou digest incompatível | unavailable / invalid_plan |
| Timeout | unavailable / timeout |
| Ollama indisponível ou erro conhecido | unavailable / código seguro do cliente |
| Erro de transporte não reconhecido | unavailable / transport_error |
| Conteúdo excessivo | unavailable / response_too_large |

Não há retry, warmup, mudança automática para seleção determinística ou
apresentação de texto bruto de erro. O modo determinístico exige escolha explícita
e nunca chama o cliente, mesmo que este seja fornecido.

O modo Ollama reutiliza o cliente existente, sem duplicar HTTP. Mantém HTTP de
loopback, recusa credenciais/proxies/redirects, timeout de 5 s e deadline de 15 s,
pedido de 32768 bytes, envelope de 65536 e conteúdo de 8192. Não instala modelos
nem inicia serviços. A validação de configurações e transporte não foi alterada.

## Demonstração e exemplos sintéticos

Com ambiente do projeto ativo e imports a apontar para este checkout:

```shell
python -m footballiq.analyst_demo
python -m footballiq.analyst_demo --insights deterministic
python -m footballiq.analyst_demo --fixture empty --insights deterministic
```

Para usar um cliente falso e selecionar uma observação, sem rede:

```python
from unittest.mock import Mock
from footballiq.analyst_demo import load_demo_report
from footballiq.grounded_narrative.multi_insights import narrate_insights

report = load_demo_report()
client = Mock(chat=Mock(return_value='{"plan_ids":["insight:form"]}'))
result = narrate_insights(report, enabled=True, client=client)
assert result.status == "available"
print(result.text)
```

A fixture completa dá duas famílias elegíveis: resultados e comparação.
Os timestamps empatados omitem sequências e o jogo sem IDs de eventos omite a
distribuição temporal. O backend não inventa uma terceira opção.

Para demonstrar três observações com a fixture sintética real e o Analytics:

```python
import json
from pathlib import Path
from unittest.mock import Mock
from footballiq.analytics import analyze_recent_matches
from footballiq.grounded_narrative.multi_insights import narrate_insights

data = json.loads(
    Path("tests/fixtures/integration/complete_five.json").read_text(encoding="utf-8")
)
data["matches"] = data["matches"][:4]
data["selection"]["returned_count"] = 4
data["matches"][0]["kickoff_at"] = "2026-11-08T16:00:00Z"
report = analyze_recent_matches(data)
client = Mock(
    chat=Mock(
        return_value=json.dumps(
            {
                "plan_ids": [
                    "insight:form",
                    "insight:recent_vs_older",
                    "insight:temporal_goals",
                ]
            }
        )
    )
)
result = narrate_insights(report, enabled=True, client=client)
assert len(result.plan_ids) == 3
print(result.text)
```

Não se alteram as fixtures em disco. Os [resultados sintéticos completos](validation/fi009-3-2-1/examples.json)
incluem uma e três observações, seleção determinística e fixture vazia.
`run_demo(..., insights="deterministic"|"ollama")` é a extensão aditiva da API CLI.
`--insights` não combina com `--with-llm`, `--with-narrative` ou `--html`.
Os comandos e resultados das opções antigas permanecem compatíveis.

## Ensaio real posterior e limites

Somente após revisão, com Ollama já instalado e modelo previamente disponível,
poderá executar-se manualmente:

```shell
python -m footballiq.analyst_demo --insights ollama --model gemma3:270m
```

Este comando real **não foi executado nesta tarefa**. O plano de ensaio é repetir
seleções de uma e várias famílias, incluindo fixture vazia e cobertura parcial,
registar aceitação, latência e motivos de indisponibilidade, e verificar invariância
do factual/bundle. Não mudar timeouts, instalar modelos ou fazer retries automáticos.

Os testes falsos demonstram segurança e repetibilidade, não qualidade de escolha
de um modelo real ou latência de cold start. Continuam as limitações de origem
confiável, autenticidade não certificada e ausência de payloads completos de eventos.
O backend aplica relevância descritiva, sem significância estatística ou análise
tática. Python >=3.14 mantém-se como requisito; quando indisponível localmente,
a sua validação fica pendente para um CI posterior.
