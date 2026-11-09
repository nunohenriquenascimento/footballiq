# FI-007.3 — Contrato Match Tracker → FootballIQ

Estado: proposta v1 para revisão do ChatGPT, sem implementação de interfaces.
Data: 9 de novembro de 2026. Exemplos integralmente fictícios.

## 1. Âmbito, evidência e estado

Esta tarefa acrescenta apenas este documento. Não altera o Match Tracker,
modelos, dependências, bases, serviços ou históricos de migração.

| Projeto | Checkout e estado observado |
| --- | --- |
| FootballIQ | `C:\Users\javai\OneDrive\Ambiente de Trabalho\FootballIQ\footballiq`; branch `feature/sqlalchemy-alembic`; HEAD `cab31fa2effe7c51ede1c77ba203d7f54bed675a`. |
| FI-007.2 pendente | `pyproject.toml` modificado; `docs/orm-migration-plan.md`, `src/footballiq/db/base.py`, `src/footballiq/db/models.py` e `tests/test_db_models.py` novos; staging vazio. |
| Match Tracker | `C:\Users\javai\OneDrive\Ambiente de Trabalho\SUB-19\ccdr-match-tracker`; raiz Git `SUB-19`; branch `feat/campeonato-fpf`; HEAD `8df6ac4cd3b1a97e8ace53cf0130d5dd41b80445`. |
| Alterações no segundo repositório | Pasta `ccdr-match-tracker` limpa; alterações anteriores na pasta irmã `ai-learning` preservadas. |

Foram lidas as instruções FootballIQ e `frontend/AGENTS.md` do Tracker; não foi
encontrado AGENTS na raiz do Tracker ou na raiz Git SUB-19. A instrução frontend
exige consultar os guias locais antes de escrever código Next.js; esta tarefa
não escreve frontend. Não foi consultada qualquer base operacional nem
confirmada a sincronização remota dos repositórios.

Evidências no FootballIQ: `schemas/match.py`, `db/models.py` e o SQL inicial
suportam jogos terminados, equipas, resultado e origem, mas não a data do jogo,
épocas, eventos ou autorização. O contrato atual do ETL mantém-se intacto.

Evidências no Tracker, relativas ao respetivo checkout:

- `backend/app/models.py`: jogos com `kickoff_at`, época, equipa/adversário,
  `is_home`, eventos e convocatórias; `Player` representa inscrição por época.
- `backend/app/enums.py`: estados e tipos de evento usados neste contrato.
- `backend/app/live_service.py`: relógio, eventos e resultado com autogolos.
- `backend/app/statistics_service.py` e `statistics_schemas.py`: cálculos
  existentes; resumo competitivo FINISHED, mas atividade e rankings de todos
  os jogos da época. Não são diretamente um relatório dos últimos cinco.
- `backend/app/competition_service.py`: liga calendário externo a jogos internos;
  resultados externos não equivalem a eventos individuais completos.
- `backend/app/auth.py`: autenticação e papéis, sem isolamento por clube.
- `backend/alembic/versions/0001_initial.py` a `0008_fpf_capture.py`: histórico
  próprio; não se copia para o FootballIQ.

Não há atualmente exportador v1, versões de conteúdo, garantia de completude,
permissões por clube ou relatório LLM de cinco jogos. `created_at` não é
`updated_at`. Não afirmar que estes requisitos já existem.

## 2. Arquitetura e fontes de verdade

```text
Match Tracker: registo operacional e autorização dos recursos
    → exportação v1, autenticada, consistente e só de leitura
FootballIQ: validação do contrato e cálculos reproduzíveis
    → factos, qualidade e referências aos jogos
AI Analyst: interpretação limitada às evidências
    → relatório factual + interpretação opcional na interface
```

Uma fonte de verdade é a aplicação responsável pela versão válida de um dado.
O Tracker mantém jogos internos, eventos, convocatórias, inscrições e datas.
As capturas FPF conservam a identidade de fonte externa; o Tracker não passa
a ser a entidade que certifica os resultados oficiais. O FootballIQ é
responsável pelos cálculos, versões do relatório e validação da integração;
o LLM não é fonte de verdade para números ou factos desportivos.

Manter bases, credenciais e migrações separadas. Sem tabelas partilhadas,
escrita dupla ou sincronização inversa de eventos. Inicialmente calcular sobre
o pacote exportado em memória; persistência analítica futura exige tarefa e
modelo próprios. Não passar o pacote v1 diretamente a `persist_matches`, nem
alterar a assinatura dessa função ou `FootballMatch`.

O contrato de integração tem DTOs próprios: objetos de transporte, distintos
das linhas ORM e do formato sample. A existência de Pydantic no FootballIQ
permite uma implementação futura de validação sem expor os modelos internos
do Tracker.

## 3. Fronteira e transporte propostos

API futura: `GET /api/integration/v1/teams/{team_id}/recent-matches`.
Parâmetros obrigatórios: `season_id`, `competition_scope=all|single` e
`as_of` (instante com offset). `competition_id` é obrigatório apenas em
`single`; `limit=5` é fixo. v1 exige uma época; várias épocas exigirão um
contrato futuro explícito, sem defaults para o contexto fixo de `roster.py`.

`as_of` limita o kickoff de jogos atualmente concluídos; não reconstrói o
estado histórico da base nesse instante. O Tracker não mantém um histórico
temporal suficiente para prometer essa reconstrução.

| Transporte | Benefícios | Limites e condição de adoção |
| --- | --- | --- |
| API autenticada | Verificação atual de permissões, nova seleção e deteção de correções em cada pedido. | Exige primeiro autorização por equipa/clube, exportador consistente e autenticação de integração. |
| Ficheiro JSON local | Mesmo contrato, reprodução de erros e testes sem servidor ou dependências novas. | Não prova autenticidade pelo conteúdo; não permite saber se os jogos foram corrigidos depois da exportação. |

Começar por fixtures fictícias em desenvolvimento. Um ficheiro real só pode
ser exportado por uma ação autorizada no produtor e entregue por um canal
confiável ao consumidor. Os campos de scope de um ficheiro são declarações,
não credenciais. Não guardar ficheiros reais no Git; no modo offline, apresentar
sempre a data da extração e a impossibilidade de confirmar atualidade.

API v1 é um recurso novo, não uma chamada aos endpoints estatísticos atuais
com semântica diferente. Respostas: 200 mesmo para zero jogos, 401 sem identidade,
403 para um scope não autorizado (ou 404 uniforme conforme política aprovada),
422 para filtros inválidos e 503 se não for possível obter snapshot consistente.
Sem tokens, passwords ou dados internos em erros; respostas privadas `no-store`.

## 4. Identidade, versão e regras comuns

- `schema_version="1.0"` identifica a forma do contrato. Alterar significado,
  tipos ou campos obrigatórios exige nova versão principal. Campos desconhecidos
  são rejeitados em v1; extensões exigem uma versão menor explicitamente suportada.
- IDs de origem são strings decimais positivas canónicas, padrão
  `[1-9][0-9]*`, sem booleanos, espaços ou zeros iniciais. Mantêm-se strings no
  transporte para não perder precisão em JavaScript. A ordenação do desempate
  usa o valor inteiro, não a ordem lexicográfica da string.
- Toda a identidade é composta por `source_system`, `source_instance_id`,
  tipo de entidade e ID de origem. `team:42` não é `player:42`; outra instalação
  pode ter os mesmos IDs. Nunca associar entidades entre projetos só pelo nome.
- `source_system` é o literal `match_tracker`. `source_instance_id` é uma string
  estável configurada para a instalação e validada por allowlist no consumidor.
- Instantes são strings ISO 8601 com offset explícito, normalizados para UTC
  com `Z` no transporte. `timezone` é uma zona IANA válida para apresentação,
  por exemplo `Europe/Lisbon`. Rejeitar datetimes sem timezone.
- Inteiros de contagens/tempos são estritos, não negativos; nomes são texto
  não vazio depois de trim. Não truncar silenciosamente nomes para caber no
  schema FootballIQ. Não mudar constraints existentes por causa do contrato.
- Objetos e arrays têm limites de dimensão a definir na implementação; o
  exportador nunca trunca eventos/convocatória silenciosamente. Se exceder o
  orçamento suportado, falhar explicitamente em vez de anunciar completude.

## 5. Estrutura normativa do pacote

Nas tabelas, O significa obrigatório; N significa que o campo deve existir mas
pode conter `null`; F significa facultativo. IDs são sempre de origem.

| Campo | Presença e tipo | Regra |
| --- | --- | --- |
| `schema_version` | O, string | `1.0`. |
| `source_system`, `source_instance_id` | O, strings | Identidade do produtor conforme secção 4. |
| `exported_at` | O, instante | Hora da extração, não hora da última alteração. |
| `snapshot_version` | O, string opaca não vazia | Token de conteúdo do conjunto selecionado e scope. |
| `authorized_scope` | O, objeto | Identidade atribuída pelo servidor; nunca concedida pelo pedido. |
| `selection` | O, objeto | Filtros efetivamente aplicados e número obtido. |
| `matches` | O, array | Entre zero e cinco jogos distintos, já ordenados. |

`authorized_scope` contém obrigatoriamente `scope_id`, `club_id`, `team_id`
e `permission="matches:export"`. `club_id` e `scope_id` são identificadores
opacos do registo de autorização futuro; não se inventa uma FK Club no modelo
atual. `team_id` é o ID decimal da equipa autorizada no Tracker. O scope é
associado à identidade autenticada no servidor. Não incluir sessões ou emails.

`selection` contém `team_id`, `season_id`, `competition_scope`,
`competition_id` (N, null apenas em `all`), `as_of`, `limit=5`, `returned_count`
e `order="kickoff_at_desc_source_match_id_numeric_desc"`. `returned_count`
deve coincidir com o tamanho de `matches`. Todas as equipas-alvo devem coincidir
com `authorized_scope.team_id`. A versão v1 seleciona apenas jogos internos,
não fixtures externos independentes.

### 5.1. Cada jogo

| Campo | Presença e tipo | Validação |
| --- | --- | --- |
| `source_match_id`, `team_id`, `season_id` | O, IDs | Únicos por namespace; team é o scope, não necessariamente a equipa da casa. |
| `competition_id` | N, ID | Resolver pela ligação ao fixture; null se sem associação. Em filtro single deve coincidir com o pedido. |
| `kickoff_at`, `timezone` | O, instante e string | Kickoff não posterior a `as_of`; zona válida. |
| `status` | O, enum | Só `FINISHED` nesta exportação. O modelo operacional conserva os outros estados. |
| `home_team`, `away_team` | O, objetos | Cada um contém `team_id` e `name`; IDs diferentes; um corresponde ao scope. |
| `score` | O, objeto | Golos casa/fora N, estado de qualidade e proveniência; ver abaixo. |
| `events` | O, array | Pode estar vazio; vazio não demonstra zero eventos realizados. |
| `squad` | N, array | null quando indisponível; vazio só é uma convocatória vazia se declarada completa. |
| `quality` | O, objeto | Todas as categorias da secção 5.4. |
| `data_version` | O, string opaca | Versão de todo o conteúdo relevante do jogo. |
| `updated_at` | N, instante | Última alteração conhecida; null enquanto não houver timestamp fiável. |
| `source_reference` | O, objeto | `resource="internal_match"`, `id` igual a source_match_id; `path` F, relativo e autorizado. |
| `external_references` | F, array | Referências a fixture/captura oficial, sem duplicar o jogo. |

`data_version` deve mudar se mudar data, estado, equipas, nome exibido, associação
competitiva, resultado, eventos (incluindo eliminação), convocatória ou qualidade.
Pode ser implementada por hash determinístico do conteúdo normalizado relevante;
o consumidor trata-a como opaca. Deve ser estável se nada relevante mudar, sem
incluir `exported_at`. A semântica é obrigatória; o algoritmo será revisto na
implementação. Nunca usar `created_at` como versão ou preencher `updated_at`
com a hora de exportação. Tokens fictícios do exemplo não são hashes reais.

### 5.2. Resultado e proveniência

`score` contém `home_goals`, `away_goals` (inteiros N, ambos preenchidos ou
ambos null), `status=verified|unverified|conflict|unavailable` e `provenance`.
`provenance` contém `method=events|official_capture|manual_verified|unknown`,
`reference_ids` (array de strings) e `verified_at` (instante N).

Só `verified` permite calcular resultado competitivo. Com método `events`,
exigir `quality.score_events.status=complete` e igualdade com o cálculo de
golos/autogolos. Uma lista vazia sem garantia de completude não valida um 0–0.
Uma captura oficial validada pode confirmar o resultado sem confirmar remates
ou autoria dos golos. `manual_verified` exige um processo auditável futuro;
não pressupõe que já exista. Conflitos entre fontes bloqueiam as métricas de
resultado desse jogo até reconciliação; não escolher uma fonte silenciosamente.

### 5.3. Eventos e convocatória

Cada evento tem obrigatoriamente `source_event_id`, `source_match_id`,
`event_type`, `team_id`, `period`, `elapsed_seconds`, `minute`,
`player` (N) e `related_player` (N). IDs de evento são únicos dentro da instalação
e referem o jogo do objeto pai. Ordenar por período, elapsed_seconds e ID numérico.

- `event_type`: `GOAL`, `OWN_GOAL`, `SHOT_ON_TARGET`, `SHOT_OFF_TARGET`,
  `SHOT_BLOCKED`, `CORNER`, `FREE_KICK`, `FOUL`, `YELLOW_CARD`, `RED_CARD`,
  `OFFSIDE`, `SUBSTITUTION`, `PENALTY` ou `SAVE`. Valores novos não são ignorados.
- `team_id` identifica a equipa que pratica o evento, uma das duas equipas;
  o adaptador converte US/OPPONENT relativamente a `team_id` do jogo.
- `period`: 1 ou 2 em v1. Sem suporte implícito a prolongamento ou desempate
  por penáltis; novos formatos exigem revisão do contrato.
- `elapsed_seconds` é tempo acumulado jogado, sem intervalo ou pausas, seguindo
  o relógio Tracker. `minute=floor(elapsed_seconds/60)` é apenas uma derivação
  técnica, não uma notação oficial como 45+2. Não inferir timestamps absolutos.
- `player` e `related_player`, quando presentes, contêm `source_player_id`
  (ID da inscrição por época), `team_id`, `season_id` e `name`. Devem pertencer
  à equipa do evento, à época e à convocatória quando esta for conhecida.
- Em GOAL, related_player é a assistência; em SUBSTITUTION, player sai e
  related_player entra. IDs diferentes na substituição. Outros tipos não
  admitem related_player. A autoria pode ser null se desconhecida: isso reduz
  a qualidade individual, sem fabricar um jogador.
- OWN_GOAL atribui o golo à equipa contrária à equipa do evento. Não contar
  o jogador como marcador de um golo normal nem inferir assistência.

Cada entrada de `squad` contém `source_squad_id`, `player` (objeto acima) e
`is_starter` (booleano estrito); sem inscrição repetida. A convocatória é a da
equipa autorizada. Não representa minutos jogados nem garante a validade de
todas as substituições. Não exportar passwords, emails ou notas livres em v1.

### 5.4. Disponibilidade e completude

`quality` contém exatamente: `score_events`, `shots`, `cards`, `substitutions`,
`other_events`, `player_attribution` e `squad`. Cada objeto contém
`status=complete|partial|unavailable|unknown`, `evidence` (string N, obrigatória
e não vazia se complete) e `assessed_at` (instante N).

Complete significa recolha verificada de toda a categoria no jogo e nos dois
lados, exceto squad e player_attribution, que se referem à equipa autorizada.
Unknown significa ausência de garantia; partial significa recolha conhecida
como incompleta; unavailable significa categoria não fornecida. Um array com
todos os registos atualmente na base não demonstra que todos os acontecimentos
reais foram registados. A interface atual não certifica esta completude:
exportar unknown por defeito e apenas elevar a complete mediante evidência.

Zero é um valor factual apenas com categoria completa. Categorias incompletas
podem preservar eventos observados, mas as métricas correspondentes ficam null
com motivo; nunca apresentar ausência de dados como zero.

### 5.5. Exemplo JSON fictício: menos de cinco jogos e recolha parcial

O exemplo contém um único jogo fora, um autogolo adversário e resultado não
verificado. Não permite concluir vitória nem calcular métricas competitivas.

```json
{
  "schema_version": "1.0",
  "source_system": "match_tracker",
  "source_instance_id": "fictional-local-demo",
  "exported_at": "2026-11-09T10:00:00Z",
  "snapshot_version": "demo-selection-v1",
  "authorized_scope": {
    "scope_id": "demo-scope-a",
    "club_id": "demo-club-a",
    "team_id": "42",
    "permission": "matches:export"
  },
  "selection": {
    "team_id": "42",
    "season_id": "7",
    "competition_scope": "all",
    "competition_id": null,
    "as_of": "2026-11-09T10:00:00Z",
    "limit": 5,
    "returned_count": 1,
    "order": "kickoff_at_desc_source_match_id_numeric_desc"
  },
  "matches": [
    {
      "source_match_id": "901",
      "team_id": "42",
      "season_id": "7",
      "competition_id": null,
      "kickoff_at": "2026-11-08T15:00:00Z",
      "timezone": "Europe/Lisbon",
      "status": "FINISHED",
      "home_team": {"team_id": "55", "name": "Clube Fictício B"},
      "away_team": {"team_id": "42", "name": "Clube Fictício A"},
      "score": {
        "home_goals": null,
        "away_goals": null,
        "status": "unverified",
        "provenance": {
          "method": "events",
          "reference_ids": ["event:3001"],
          "verified_at": null
        }
      },
      "events": [
        {
          "source_event_id": "3001",
          "source_match_id": "901",
          "event_type": "OWN_GOAL",
          "team_id": "55",
          "period": 1,
          "elapsed_seconds": 600,
          "minute": 10,
          "player": null,
          "related_player": null
        }
      ],
      "squad": null,
      "quality": {
        "score_events": {"status": "partial", "evidence": null, "assessed_at": null},
        "shots": {"status": "unknown", "evidence": null, "assessed_at": null},
        "cards": {"status": "unknown", "evidence": null, "assessed_at": null},
        "substitutions": {"status": "unknown", "evidence": null, "assessed_at": null},
        "other_events": {"status": "unknown", "evidence": null, "assessed_at": null},
        "player_attribution": {"status": "unknown", "evidence": null, "assessed_at": null},
        "squad": {"status": "unavailable", "evidence": null, "assessed_at": null}
      },
      "data_version": "demo-match-901-v1",
      "updated_at": null,
      "source_reference": {"resource": "internal_match", "id": "901"}
    }
  ]
}
```

Exemplo de resultado factual derivado desse pacote (formato de saída ilustrativo,
a formalizar na implementação, não um segundo contrato de exportação):

```json
{
  "requested_matches": 5,
  "selected_match_ids": ["901"],
  "verified_score_matches": 0,
  "competitive_metrics": null,
  "shots_total": null,
  "warnings": ["Apenas 1 jogo encontrado.", "Resultado não verificado.", "Remates sem garantia de completude."],
  "observations": [
    {
      "text": "Existe um autogolo registado a favor da equipa analisada; o resultado final não está confirmado.",
      "match_id": "901",
      "event_ids": ["3001"]
    }
  ],
  "interpretation_status": "not_requested"
}
```

## 6. Seleção consistente dos últimos cinco

1. Autenticar e autorizar a equipa antes de procurar jogos. Não confiar em
   team_id/club_id enviados no corpo para conceder acesso.
2. Resolver época e filtro competitivo explícitos. Em single, filtrar a relação
   com CompetitionFixture sem multiplicar jogos; em all, incluir jogos sem
   competição, assinalando-os. Uma linha externa ligada não é outro jogo.
3. Selecionar jogos internos da equipa com estado FINISHED e kickoff_at <= as_of.
   No modelo atual, a equipa analisada é Match.team_id; não incluir automaticamente
   jogos onde aparece como opponent_id, pois a convocatória/eventos usam outra
   perspetiva. Generalização futura requer um adaptador e autorização próprios.
4. Ordenar kickoff_at DESC, Match.id DESC e limitar a cinco numa seleção base,
   antes de juntar eventos, jogadores ou convocatórias. Um jogo com muitos
   eventos não pode ocupar várias posições na janela.
5. Obter conteúdo e versões desses jogos numa leitura coerente, por exemplo
   uma transação de leitura com snapshot consistente, a definir futuramente.
   Uma conclusão e os seus eventos não podem vir de momentos incompatíveis.
6. Não substituir um jogo incompleto pelo sexto para obter estatísticas melhores.
   A janela representa os cinco jogos mais recentes, com as suas limitações.
7. Devolver 0–4 jogos quando necessário, sem inventar jogos ou extrapolar para
   cinco. Sem jogos, métricas e médias ficam null, com mensagem explícita.

## 7. Métricas determinísticas e interpretação

Todos os cálculos são SQL/Python testados. O LLM recebe um pacote factual
validado, nunca calcula resultados a partir de notas livres ou SQL gerado.

| Métrica | Cálculo e condição |
| --- | --- |
| Golos a favor/contra | Selecionar home/away conforme o ID da equipa autorizada; apenas resultados verified. |
| Vitória/empate/derrota | Comparar GF e GA por jogo, sem usar o nome da equipa como identidade. |
| Totais e médias | Totais sobre resultados verificados; denominador explícito. Se nem todos forem verificados, resumo da janela completa fica null; pode existir subtotal claramente identificado com IDs e cobertura n/N. |
| Pontos | Soma por resultado com política explícita. Não assumir 3/1/0 como regulamento oficial. |
| Remates | À baliza + fora + bloqueados, apenas com shots complete. GOAL não acrescenta um remate automaticamente. |
| Cartões | Contagem de eventos amarelos e vermelhos, com cards complete. Não inferir expulsão por segundo amarelo se não registada. |
| Substituições | Contar eventos SUBSTITUTION com substitutions complete; não inferir minutos de utilização apenas da convocatória. |
| Jogadores | Exigir qualidade da categoria e player_attribution complete para totais exaustivos; inscrições de épocas distintas não são fundidas por nome. |

Na implementação do relatório, a política de pontos deverá ser um parâmetro
validado contendo `policy_id`, `win`, `draw`, `loss`, `is_official` e referência
da regra. Em single pode usar as regras exportadas futuramente pelo Tracker;
como v1 não exporta regras, exigir configuração aprovada no relatório. Na sua
ausência, points=null. Em all, não somar pontos de regulamentos diferentes como
classificação oficial. Uma política analítica 3/1/0 pode ser usada se apresentada
explicitamente como convencional, não oficial. Sanções não estão incluídas.

Cada valor conserva IDs dos jogos usados, categoria, fórmula/versão do cálculo
e cobertura. Cada interpretação referencia esses factos; referências completas
incluem sistema, instalação, jogo e data_version. Pode acrescentar eventos
específicos, sem permitir referências fora do pacote. Notas/documentos externos
são dados não confiáveis, nunca instruções para o LLM.

Resposta factual de reserva: lista dos jogos, métricas válidas, nulls, motivos
e cobertura, com `interpretation_status=unavailable` quando há timeout, resposta
inválida ou indisponibilidade do LLM. O sucesso do relatório factual é independente
do LLM. Não apresentar métricas de posse, xG ou posicionamento sem dados próprios.

## 8. Correções, versões e invalidação

`snapshot_version` representa filtros estáveis de seleção, ordem/IDs e versões
do conteúdo selecionado; muda se mudar qualquer destes elementos. As horas
voláteis da exportação não entram na identidade. A próxima exportação refaz a
seleção inteira: se um jogo for reaberto, cancelado, eliminado ou mudar de data,
pode sair da janela e ser substituído por outro. Verificar só os cinco IDs
anteriores não é suficiente. Mudar um evento elimina a validade do relatório
anterior mesmo que o resultado permaneça igual.

Cache de relatório, se introduzida futuramente, é segmentada por scope autorizado,
filtros, snapshot_version, versão das fórmulas, política de pontos e configuração
LLM. Reautorizar antes de devolver qualquer resultado, incluindo cache hits;
uma versão igual não concede acesso. Revalidar a seleção antes de apresentar
um relatório como atual; se houver mudança durante a geração, repetir de forma
limitada ou indicar que o relatório é de um snapshot anterior. Nunca sobrescrever
referências históricas para aparentarem corresponder à versão nova.

Ficheiros offline produzem relatórios do snapshot exportado, sem promessa de
invalidação automática. Notificações/polling são evolução futura; não há hoje
um mecanismo de atualização entre projetos.

## 9. Autenticação e isolamento

Bloqueio atual: ADMIN/COACH/VIEWER são papéis globais no Tracker; não provam
pertença a um clube. Não abrir a integração multi-clube antes de implementar
um registo de pertenças/permissões e filtros por recurso no backend.

Propor identidade de integração dedicada, credencial revogável, com permissão
de exportação e allowlist de scopes/equipas. O browser não recebe a credencial
de serviço. Para relatórios por utilizador, o backend FootballIQ deve cruzar
o utilizador autenticado com os scopes autorizados; a conta de serviço não
transforma qualquer team_id pedido pelo cliente num recurso permitido.
Transportar por HTTPS fora do desenvolvimento isolado. Formato/emissão da
credencial e eventual delegação de utilizador são decisões pendentes, sem
implementar tokens nesta tarefa.

Enquanto não houver clube no modelo, é possível preparar um modo limitado a
uma instalação dedicada a um clube e equipa explicitamente autorizada, se
essa limitação for aprovada e aplicada no servidor. Não o apresentar como
isolamento multi-clube. IDs opacos no JSON não fornecem isolamento por si só.

Não exportar dados pessoais desnecessários; jogadores podem ser menores.
Definir política de retenção e permissão para envio dos nomes ao LLM. Preferir
IDs/pseudónimos na interpretação quando os nomes não forem necessários.
LLM sem acesso direto a bases, credenciais, endpoints arbitrários ou ferramentas
de escrita. Referências/paths não são URLs a seguir automaticamente.

## 10. Reutilização e alterações necessárias

| Componente | Decisão | Trabalho necessário |
| --- | --- | --- |
| Tracker score() | Reutilizar | Preservar regra de autogolos e adaptar perspetiva casa/fora. |
| Tracker comparison(), player_totals() | Adaptar | Limitar aos IDs selecionados e aplicar qualidade por categoria. |
| Tracker season_statistics() | Não reutilizar diretamente | Âmbito atual inclui atividade de jogos não concluídos. |
| Tracker autenticação e papéis | Adaptar | Acrescentar autorização de recursos e identidade de integração. |
| Tracker UI de jogos/estatísticas | Reutilizar futuramente | Expor referências e vista de relatório; sem alterar nesta tarefa. |
| Tracker captura FPF | Reutilizar proveniência | Preservar separação de resultado oficial e eventos internos. |
| FootballIQ Pydantic/ETL | Reutilizar princípios e infraestrutura | Criar DTOs próprios; não alargar silenciosamente FootballMatch. |
| FootballIQ modelos FI-007.2 | Preservar | Continuam fiéis ao schema atual; persistência enriquecida exige desenho posterior. |
| Protótipo ai-learning | Avaliar/adaptar | Reaproveitar ideias de fundamentação, sem assumir integração com estatísticas. |
| Exportador, qualidade e versões | Implementar | Não existem atualmente com estas garantias. |
| Cálculo de janela e relatório factual | Implementar | Sem dependência funcional do LLM. |
| Fusão de migrations/tabelas ou escrita dupla | Rejeitar como estratégia | Manter fronteiras e autoridades separadas. |

## 11. Estratégia de testes futura

Não foram executados testes nem criados ficheiros de teste nesta tarefa documental.
As implementações seguintes devem comprovar:

1. Validação do JSON: tipos estritos, versões, IDs, referências, timezones,
   enums, duplicados, relações, nulabilidade e campos adicionais rejeitados.
2. Seleção: seis ou mais jogos, datas empatadas, IDs 9/10, offset UTC, estados
   não concluídos, épocas/competições diferentes, zero a quatro jogos e muitos
   eventos num só jogo. Limite aplicado antes dos joins, sem contar fixture duas vezes.
3. Cálculo: casa/fora, autogolos dos dois lados, vitória/empate/derrota, regras
   de pontos, médias com denominador correto e jogos sem resultado verificado.
4. Qualidade: ausência desconhecida não vira zero; categoria completa vazia
   pode virar zero; resultado oficial sem eventos não permite inferir remates;
   dados parciais não substituem o quinto jogo pelo sexto.
5. Autorização: credencial revogada, clube/equipa alheios, scope adulterado,
   IDs de jogadores/eventos fora do pacote e cache de outro utilizador/scope.
6. Versões: editar/apagar evento, alterar convocatória, reabrir/cancelar jogo,
   corrigir kickoff e criar um jogo mais recente alteram conteúdo/janela; extração
   repetida sem alterações mantém versões estáveis.
7. Consistência: não combinar seleção antiga com eventos novos; conflito de
   resultado é exposto e não resolvido por inferência do modelo.
8. LLM: timeout, JSON inválido, números e referências inventadas, instruções
   inseridas nos dados e modelo indisponível produzem fallback factual válido.
   Valores oficiais são renderizados pelo serviço, não copiados de prosa livre.
9. Transporte: ficheiro e API do mesmo snapshot geram o mesmo relatório factual;
   ficheiro não confiável não confere autorização e offline expõe a sua data.

Começar por testes puros com fixtures fictícias; validar queries e autorização
posteriormente em PostgreSQL descartável autorizado. Não usar testes que alterem
schemas operacionais. Testes existentes continuam a verificar os contratos antigos.

## 12. Plano incremental e critérios de entrega

1. **Revisão deste contrato:** aprovar identidade, scope, completude, política
   de pontos, relógio e semântica de versões. Sem Alembic nesta etapa.
2. **FI-007.4 proposta — núcleo factual offline:** implementar DTOs v1, fixtures
   fictícias e funções puras FootballIQ que validam o pacote e calculam a janela
   e métricas. Entrega: relatório reproduzível, cobertura/nulls e testes, sem
   PostgreSQL, HTTP, LLM ou alterações à persistência existente. O consumidor
   verifica ordenação/limites; não consegue provar que o produtor omitiu jogos.
3. **Tarefa própria no Tracker:** seleção consistente, exportação local controlada,
   evidência de qualidade e versões. Entrega: dados autorizados que respeitam v1,
   sem converter registos desconhecidos em completos.
4. **API segura:** implementar scopes/pertenças ou aprovar instalação de clube
   único, autenticação dedicada e leitura v1. Entrega: relatório FootballIQ com
   dados reais e testes de acesso negado a recursos alheios.
5. **AI Analyst:** consumir apenas factos validados, devolver referências e
   fallback; testar correções e revogações. Entrega: análise de até cinco jogos
   reais com proveniência e limites visíveis.
6. **Interface FootballIQ unificada:** integrar navegação e identidade de
   utilizador, mantendo módulos operacionais/analíticos separados. Não exige
   fusão de tabelas. Agentes/scouting/ML ficam para requisitos posteriores.

Uma eventual persistência analítica e as respetivas migrations só se desenham
depois do contrato aprovado. Nunca copiar o histórico Alembic do Tracker nem
executar o seu baseline sobre tabelas FootballIQ.

## 13. Riscos e decisões pendentes

| Tema | Decisão a rever pelo ChatGPT |
| --- | --- |
| Autorização | Instalação dedicada inicial ou pertenças multi-clube; formato de credenciais e delegação. |
| Qualidade | Quem certifica completude e resultado, com que evidência e procedimento. Sem certificação, conservar unknown/unverified. |
| Pontos | Política analítica ou regras competitivas versionadas; tratamento de competições distintas e sanções. |
| Âmbito | v1 de uma época e jogos internos; inclusão futura de jogos externos e de outras épocas. |
| Relógio | Validar acumulado Tracker e minuto derivado; formatos com prolongamento ficam fora de v1. |
| Versões | Algoritmo determinístico, snapshot de leitura, revalidação, limites de payload e prazo de retenção. |
| Identidade | Inscrição vs pessoa, nomes repetidos e namespace de instalação; sem fusão automática. |
| Privacidade | Uso de nomes de jogadores, destino LLM e retenção de exportações/relatórios. |
| Schema atual | Não representa o pacote enriquecido; manter integração offline antes de decidir persistência/migrações. |

Limitações desta proposta: nenhuma inspeção de dados reais, revisão Alembic
aplicada desconhecida, nenhuma prova de cinco jogos reais disponíveis e nenhuma
validação operacional da autenticação/exportação aqui desenhadas.

Aguardar revisão do ChatGPT antes da implementação.
