# FI-007.4 — Motor factual offline

Implementação isolada do [contrato v1](match-tracker-integration-contract.md).
Não usa PostgreSQL, Engine, Session, HTTP, autenticação real, Ollama ou LLM.
Não altera FootballMatch, a CLI ETL, persist_matches ou os modelos FI-007.2.
Não foram acrescentadas dependências.

## Organização e utilização

- `src/footballiq/schemas/integration.py`: DTOs Pydantic v1 e validação de
  coerência. Um DTO transporta dados; não representa uma linha ORM nem concede
  permissões. Campos nullable continuam obrigatórios quando o contrato o exige.
- `src/footballiq/analytics.py`: validate_package, analyze_recent_matches e
  report_json. Funções puras: os resultados dependem apenas dos argumentos;
  sem leituras de ficheiros, relógio global, escrita ou consultas externas.
- `tests/fixtures/integration/`: pacotes exclusivamente fictícios, sem pessoas,
  clubes ou resultados reais. complete_five, partial_match e empty cobrem cinco,
  um e zero jogos. Variações de qualidade/âmbito são construídas nos testes.

Exemplo a executar pelo chamador, com o pacote já instalado na `.venv`:

```python
from pathlib import Path

from footballiq.analytics import analyze_recent_matches, report_json

payload = Path("tests/fixtures/integration/complete_five.json").read_text(
    encoding="utf-8"
)
report = analyze_recent_matches(payload)
print(report_json(report))
```

Pode fornecer-se um dicionário, JSON str/bytes ou ExportPackage. O motor revalida
instâncias para detetar mutações posteriores. Não valida a autenticidade de
source_instance_id nem a allowlist operacional: são responsabilidades da futura
fronteira autenticada. O relatório indica authorization_verified=false.

O consumidor aceita apenas a janela já selecionada de zero a cinco jogos e
confirma a sua ordem. Rejeita, em vez de filtrar silenciosamente, jogos não
terminados, fora da época/competição, após as_of, duplicados ou fora de ordem.
Não aceita um sexto jogo para substituir um jogo incompleto. Não pode provar
que o produtor não omitiu outro jogo mais recente na base de origem.

## Resultados e fórmulas

Na fixture complete_five, IDs 10 e 9 têm kickoff igual; o desempate é numérico,
10 antes de 9. Há jogos em casa/fora, autogolos dos dois lados, resultados
2–1, 0–1, 1–1, 2–0 e 0–0 na perspetiva casa/visitante.

Resultado competitivo esperado para a equipa-alvo:

```json
{
  "wins": 2,
  "draws": 2,
  "losses": 1,
  "goals_for": 4,
  "goals_against": 4,
  "goal_difference": 0,
  "average_goals_for": 0.8,
  "average_goals_against": 0.8
}
```

Cada MetricSummary contém values (total da janela), covered_values (subtotal
conhecido), covered_matches e selected_matches, referências e motivos por jogo
em falta. A cobertura é n/N, em que N é o número efetivamente selecionado,
não necessariamente cinco. Com zero jogos, ambos os valores são null.

Se um dos cinco resultados não estiver verificado, values é null e o subtotal
dos quatro restantes continua identificado. As médias são GF/n e GA/n, onde
n é o número de resultados verificados. Não extrapolar os subtotais para cinco.
Os valores em ponto flutuante não têm arredondamento de apresentação imposto.

| Métrica | Regra |
| --- | --- |
| competitive | Só score verified; GF/GA convertidos pela identidade casa/fora. Vitória se GF>GA, empate se iguais, derrota se GF<GA; diferença GF−GA. |
| points | Só resultados verificados e política explícita: V×win + E×draw + D×loss. Sem política, null. |
| shots | Só quality.shots complete; total = on_target + off_target + blocked, para cada lado. Golos não criam remates. |
| cards | Só quality.cards complete; contagem de amarelos e vermelhos por lado, sem inferir segundo amarelo. |
| substitutions | Só quality.substitutions complete; contagem por lado, sem inferir minutos de utilização. |
| temporal_goals | Só quality.score_events complete; golos/autogolos por período e intervalos de 15 minutos de tempo acumulado, com cauda 90+. |

Em temporal_goals, OWN_GOAL beneficia a equipa contrária à do evento. Os intervalos
00–14, 15–29, etc. usam minute=elapsed_seconds//60; não são a notação oficial
45+2 nem demonstram a duração real de cada parte. Não deduzir xG, posse,
distâncias, posicionamento ou taxas por minuto sem os dados necessários.

Complete com zero eventos permite zero factual. Unknown/partial não permite
essa conclusão. Um resultado oficial verificado pode permitir cálculo competitivo
enquanto remates e distribuição temporal permanecem null.

## Política explícita de pontos

```python
report = analyze_recent_matches(
    payload,
    points_policy={
        "policy_id": "synthetic-3-1-0",
        "win": 3,
        "draw": 1,
        "loss": 0,
        "is_official": False,
        "reference": "Convenção analítica fictícia, sem sanções",
        "competition_id": None,
    },
)
assert report.metrics["points"].values == {"points": 8}
```

Uma política oficial exige competition_id e seleção single para a mesma
competição. Uma convenção sem competição pode ser usada sobre o âmbito all,
mas o relatório avisa que não é classificação oficial. Uma declaração oficial
no ficheiro não prova a existência ou validade do regulamento externo.

## Clarificações adotadas sem mudar o contrato de exportação

O documento v1 deixa detalhes de implementação em aberto. Neste núcleo:

1. Score verified exige golos, método conhecido, verified_at e reference_ids
   não vazios. Por eventos exige score_events complete e reconciliação. Para
   um 0–0 completo sem eventos, pode referenciar match:ID como evidência do
   jogo certificado; não é necessário fabricar um evento.
2. Referências a eventos usam event:ID e têm de existir no jogo. Capturas usam
   official_capture:ID e exigem entrada external_references com resource
   official_capture e id correspondente. ExternalReference tipa resource como
   competition_fixture ou official_capture; id é texto opaco não vazio.
3. Um resultado verificado contraditório com eventos declarados completos é
   rejeitado, mesmo que provenha de captura oficial. O produtor deve exportar
   conflict até reconciliar, em vez de escolher uma fonte silenciosamente.
4. Uma categoria unavailable não pode fornecer eventos dessa categoria; a
   categoria unknown pode conter acontecimentos observados sem garantir totais.
5. Se a autoria individual é declarada complete, GOAL e SUBSTITUTION da equipa
   analisada exigem jogador; SUBSTITUTION exige também o jogador que entra.
   Autoria desconhecida pode ser null. Convocatória conhecida é verificada.
6. Timestamps são normalizados para UTC, zonas IANA são verificadas e datas de
   atualização/verificação posteriores à exportação são rejeitadas. Não se
   inventa updated_at quando é null.

O relatório mantém referências compostas, caminhos internos como dados,
proveniência de resultado, versões da origem e versão das fórmulas. report_json
usa ordenação de chaves e não acrescenta hora de execução; a mesma entrada e
política produzem a mesma saída, sem alterar os argumentos.

## Limitações e próximo incremento

Não há autorização, certificação de qualidade, assinatura do ficheiro, cache,
revalidação na origem ou verificação criptográfica dos tokens de versão. Os
tokens são preservados como declarações do produtor. Um relatório é sempre
do snapshot fornecido; alterações posteriores só são conhecidas num novo pacote.
Não há interpretação LLM nesta tarefa: interpretation_status=not_requested.
O relatório factual já funciona autonomamente como base para o fallback futuro.

O ambiente Windows disponível usa Python 3.12.10 e Pydantic 2.14.3 na `.venv`.
O mínimo do projeto continua Python 3.14; a execução local em 3.12 não valida
3.14. Testes PostgreSQL devem manter-se desativados nesta validação offline.

Próxima entrega recomendada: exportador Tracker numa tarefa própria, começando
por seleção consistente, versões e qualidade explícita, com testes de contrato;
API e autenticação por recurso só depois da decisão de isolamento.
