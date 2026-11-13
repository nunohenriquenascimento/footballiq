# Football Insights Catalog

O catálogo acrescenta observações determinísticas ao AI Analyst sem alterar os
contratos existentes, Analytics, Trends, persistência ou dashboard. A
[seleção múltipla](ollama-multi-insights.md) permite usar Ollama explicitamente
na CLI textual. O dashboard continua sem integração com este catálogo.

## Utilização no backend

```python
from footballiq.grounded_narrative.insights import (
    build_insights,
    prepare_insight_plans,
    render_insight,
)

bundle = build_insights(report)  # FactualReport produzido pelo Analytics Engine.
plans = prepare_insight_plans(bundle)
for identity, plan in plans.items():
    text = render_insight(plan, bundle)
```

As três funções são offline. Não recebem clientes de rede nem executam modelos.
Um relatório vazio ou sem dados suficientes produz um catálogo de planos vazio.

## Observações e fontes

| Facto | Fonte existente | Condições |
| --- | --- | --- |
| `insight:form` | `trends.window.covered_values` | Vitórias, empates, derrotas, jogos sem marcar/sofrer e médias GF/GA dos resultados verificados |
| `insight:home`, `insight:away` | `trends.home/away.covered_values` | Mesmos indicadores, na perspetiva da equipa, com denominador do grupo |
| `insight:competitive` | `metrics['competitive'].covered_values` | Totais e médias GF/GA, com referências exatas do Analytics |
| `insight:temporal_goals` | `metrics['temporal_goals'].covered_values` | Contagens por períodos 1/2 e minutos 00-14, 15-29, 30-44, 45-59, 60-74, 75-89, 90+, com IDs de eventos |
| `insight:recent_vs_older` | `trends.newer/older` | Pelo menos quatro resultados verificados, sem empate temporal na fronteira |
| `insight:home_vs_away` | `trends.home/away` | Pelo menos dois resultados verificados em cada local e cobertura completa dos grupos |
| `insight:winning_run`, `drawing_run`, `losing_run`, `winless_run` | `trends.games` | Sufixo final verificado com pelo menos dois jogos, sem timestamps empatados |

As contagens consecutivas são a única nova derivação descritiva. Usam os jogos
ordenados por Trends, interrompem-se num resultado desconhecido e não afirmam a
duração da sequência fora da janela exportada. Não se recalculam os agregados
analíticos já disponíveis. Não são atribuídas causas táticas nem feitas previsões.

## Cobertura e insuficiência

Dados desconhecidos não são convertidos em zero nos novos insights. Subtotais
declaram a amostra usada e a cobertura sobre o grupo selecionado. Comparações
mostram as médias, os dois denominadores e a composição de ambos os grupos;
uma amostra de um jogo permite descrição, mas não comparação ou tendência.
Os valores completos são preservados; médias apresentadas arredondam a três casas.

Os mínimos das comparações são os definidos em Trends. Qualquer empate temporal
na janela omite as novas sequências; um empate na fronteira dos grupos omite a
comparação recente/antigo. Offsets diferentes não desfazem um empate de instantes.

Agregados sem referências resolúveis, com referências duplicadas ou incompatíveis
com as dos jogos, ou com denominadores incompatíveis são omitidos.
Distribuições temporais sem IDs de eventos em algum jogo coberto são omitidas
deliberadamente, mesmo para um zero legítimo. Não se fabricam eventos a partir
de um agregado. A fixture completa tem um jogo sem eventos e demonstra esta
limitação; a variante sintética com quatro jogos mostra o caso suportado.

## Proveniência, versões e compatibilidade

`build_insights` conserva os factos `match:*`, `metric:*` e `trend:*` existentes e
acrescenta `insight:*`, versão `footballiq.insights.v1`. Cada novo facto conserva
origem, snapshot, fórmula, versões dos jogos, referências, valores, amostra e
cobertura. O `EvidenceBundle` continua profundamente imutável.

Os planos v1 representam uma observação de um facto composto do backend através
de `AGGREGATE_RESULT`. Não representam relações numéricas livres escolhidas por
um modelo. `GroundedNarrativeValidator` verifica snapshot, digest, versões e o
conjunto exato de evidence_ids. `render_insight` exige também correspondência
exata com o plano fechado, incluindo cobertura, amostra e template, e apresenta
apenas o texto local imutável. Para estes planos, deve usar-se `render_insight`,
pois o renderer genérico `render_plan` não descreve os novos factos compostos.

A expansão do bundle altera o seu digest e, consequentemente, **todos os IDs de
evidência**, incluindo os dos factos antigos preservados. Uma futura integração
Ollama deve construir e selecionar planos a partir do mesmo bundle expandido;
não pode reutilizar planos ou evidence_ids de outro bundle. As funções antigas
continuam a gerar o seu catálogo e planos anteriores, sem alterações.

Reutilizam-se `_plain_fact_value` e `_content_digest` do contrato para conservar
a canonização existente. Os testes verificam a compatibilidade atual; estes
helpers são internos e uma alteração futura exige nova verificação.

O relatório é entrada confiável do backend. Os hashes identificam conteúdo,
mas não autenticam a origem. MatchFacts conserva IDs e não os payloads completos
dos eventos, pelo que não se recalculam minutos nesta camada nem se certifica
autorização, atualidade ou completude da exportação.

## Exemplos e validação

Os [exemplos sintéticos](validation/fi009-3-1/examples.json) contêm 24 observações
em cinco cenários, com texto, planos, digests e evidence_ids reproduzíveis.
Podem ser regenerados com:

```shell
python docs/validation/fi009-3-1/generate_examples.py
```

As fixtures originais permanecem intactas. Os resultados da revisão e os outputs
literais dos testes constam do [relatório FI-009.3.1.1](validation/fi009-3-1-1/README.md).
O requisito do projeto mantém-se **Python >=3.14**.
