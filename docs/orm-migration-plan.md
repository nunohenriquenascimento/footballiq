# FI-007.1 — Plano de adoção de SQLAlchemy e Alembic

Estado: proposta para revisão do ChatGPT; sem implementação funcional.
Data de verificação: 9 de novembro de 2026.

## Ponto de partida e evidência

O workspace disponível é o checkout Windows do FootballIQ, em vez do caminho
macOS indicado na tarefa. O remoto é `nunohenriquenascimento/footballiq`.
Foram lidos `AGENTS.md`, `README.md`, `docs/architecture.md`, `pyproject.toml`,
`sql/schema/001_initial_schema.sql`, `docs/database-design.md`, os módulos
`db/config.py`, `db/connection.py`, `db/persistence.py`, `schemas/match.py`,
os testes PostgreSQL e `.github/workflows/ci.yml`.

- `main`, `HEAD` inicial e `origin/main` local: commit
  `cab31fa2effe7c51ede1c77ba203d7f54bed675a`.
- `git ls-remote origin refs/heads/main` confirmou o mesmo commit no servidor.
  O fetch inicial foi impedido pelas permissões de `.git/FETCH_HEAD`; a consulta
  direta ao remoto confirmou a sincronização sem atualizar referências locais.
- Working tree inicial limpo; branch criada depois das verificações:
  `feature/sqlalchemy-alembic`.
- [Workflow CI do push para main](https://github.com/nunohenriquenascimento/footballiq/actions/runs/42419023452):
  evento `push`, SHA acima, estado `completed`, conclusão `success`.
  O job `Python quality checks and PostgreSQL integration` terminou com sucesso
  em 7 de novembro de 2026, às 22:07:06 UTC.
- A API de jobs confirmou sucesso na preparação PostgreSQL, testes unitários,
  testes de integração, Ruff lint, verificação de formatação e `pip check`.
  Estes são resultados dos passos; não se inferem contagens de testes a partir
  do estado do job.

Não foi estabelecida qualquer ligação à base local. Não foram instaladas
dependências nem executadas migrações. Este documento é a única adição prevista.

## Conceitos e responsabilidades

**SQL direto** permite escrever exatamente a consulta pretendida. O projeto
usa Psycopg 3, o driver que transporta comandos e resultados entre Python e
PostgreSQL. O `UPSERT` atual é apropriado para ingestão idempotente.

**SQLAlchemy Core** permite construir expressões SQL em Python. O **ORM**
acrescenta o mapeamento entre classes e tabelas e acompanha objetos carregados.
Não elimina SQL nem torna uma ingestão automaticamente idempotente. A adoção do
ORM não obriga a substituir consultas existentes.

**Pydantic** valida o contrato de entrada: campos permitidos, tipos estritos,
nomes normalizados, identificador positivo, golos não negativos e estado final.
`FootballMatch` representa dados da fonte, com nomes de equipas e `match_id`.
**SQLAlchemy** representa linhas persistidas, com IDs internos e referências.
Os objetos ORM não devem substituir os dicionários públicos do ETL. As
constraints PostgreSQL continuam a proteger a integridade perante qualquer
cliente; anotações `Mapped` não substituem validação Pydantic.

Uma **Engine** é o ponto de acesso SQLAlchemy ao driver e gere normalmente um
pool de ligações; deve ser criada explicitamente, sem efeitos ao importar.
Uma **Connection** é uma ligação SQLAlchemy obtida dessa Engine e permite
executar SQL e controlar transações. Não é o mesmo tipo que
`psycopg.Connection`, atualmente aceite pela persistência.
Uma **Session** acompanha objetos ORM e coordena o seu envio à base através
de uma transação. Pode fazer `flush` antes de consultas; `flush` envia SQL,
mas não equivale a `commit`. Não partilhar uma Session global entre operações
ou tarefas concorrentes. A Engine pode ser reutilizada; a Session tem âmbito
curto e é fechada no fim da operação. Nesta transição não precisamos de usar
Session na escrita.

No **ORM declarativo**, cada classe declara tabela, colunas e relações.
`DeclarativeBase` agrega essas definições em `Base.metadata`: uma descrição
Python do schema pretendido, sem criar tabelas por si só.
Ver a [documentação declarativa SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html).

**Alembic** versiona alterações estruturais. Cada revisão tem `revision` e
`down_revision`, formando um histórico. `upgrade` aplica revisões seguintes;
`downgrade` executa a inversão explicitamente programada. Uma inversão pode
perder dados e não substitui backups. Git versiona os ficheiros; a tabela
`alembic_version` regista a revisão aplicada numa base concreta. Nenhum destes
mecanismos prova, por si só, que a estrutura real corresponde à revisão.

## Arquitetura proposta

Organização futura, ainda sem criar estes módulos:

```text
src/footballiq/
  schemas/match.py          # Contrato Pydantic existente.
  db/config.py              # DatabaseSettings existente.
  db/connection.py          # API Psycopg existente.
  db/persistence.py         # Único caminho funcional de escrita existente.
  db/base.py                # DeclarativeBase e metadata.
  db/models.py              # Competition, Team e Match.
  db/engine.py              # Fábrica explícita de Engine; sem ligação no import.
alembic.ini                 # Configuração sem credenciais.
migrations/
  env.py                    # Configuração e target_metadata.
  script.py.mako             # Template de revisões.
  versions/                 # Histórico revisto de alterações.
```

Manter uma única fonte de configuração: `DatabaseSettings` e variáveis
`FOOTBALLIQ_DB_*`. A fábrica futura usará o dialecto `postgresql+psycopg`;
deverá validar o utilizador explícito e construir uma URL estruturada, sem
concatenar a propriedade `dsn` nem registar passwords. Essa propriedade pode
conter a password, apesar da descrição atual. Não a usar em logs.
O ambiente de migração deve receber configuração explícita de uma role própria
com privilégios DDL; a role da aplicação mantém os privilégios mínimos atuais.
Não colocar a credencial de migração na configuração normal da aplicação.

`env.py` importará os modelos para preencher `Base.metadata`, usado como
`target_metadata`. Não executará `create_all()` nem importará o ETL para
inicializar o schema. A criação e evolução passarão por revisões Alembic após
aprovação. Não introduzir um segundo escritor nem um repositório ORM nesta fase.

## Modelo ORM proposto

O exemplo seguinte é desenho técnico dentro da documentação: não foi instalado,
importado nem validado como código executável. As classes futuras usarão
SQLAlchemy 2.x, tipos explícitos e nomes técnicos em inglês.

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Reúne a descrição das tabelas, sem abrir ligações ou executar DDL."""


class Competition(Base):
    """Representa uma competição opcional no contrato atual de jogos."""

    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(150), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class Team(Base):
    """Representa uma equipa cuja identidade interna não depende do nome."""

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class Match(Base):
    """Liga duas equipas distintas ao identificador do jogo na fonte."""

    __tablename__ = "matches"
    __table_args__ = (
        CheckConstraint("home_goals >= 0", name="matches_home_goals_check"),
        CheckConstraint("away_goals >= 0", name="matches_away_goals_check"),
        CheckConstraint("status = 'finished'", name="matches_status_check"),
        CheckConstraint(
            "home_team_id <> away_team_id", name="chk_matches_teams_different"
        ),
        UniqueConstraint(
            "source", "source_match_id", name="uq_matches_source_match_id"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    competition_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("competitions.id", name="fk_matches_competition"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_match_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    home_team_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("teams.id", name="fk_matches_home_team"), nullable=False
    )
    away_team_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("teams.id", name="fk_matches_away_team"), nullable=False
    )
    home_goals: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    away_goals: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'finished'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    competition: Mapped[Competition | None] = relationship(viewonly=True)
    home_team: Mapped[Team] = relationship(foreign_keys=[home_team_id], viewonly=True)
    away_team: Mapped[Team] = relationship(foreign_keys=[away_team_id], viewonly=True)
```

As duas relações para `teams` precisam de `foreign_keys` explícitas para
distinguir casa e visitante. As relações propostas são apenas de navegação
(`viewonly=True`); não propagam alterações a objetos relacionados. Não tornam
a Session inteira só de leitura. Não são propostas coleções inversas nem
propagação de eliminações. Cardinalidades: competição opcional por jogo e
muitos jogos por competição/equipa; duas equipas obrigatórias e diferentes.
As FKs mantêm a ação PostgreSQL por omissão, sem acrescentar ações de eliminação.

### Fidelidade e diferenças a verificar

| Aspeto | SQL existente e decisão para metadata |
| --- | --- |
| IDs | `BIGINT GENERATED ALWAYS AS IDENTITY`; usar `BigInteger` e `Identity(always=True)`, sem substituir por serial ou geração Python. |
| Golos | `SMALLINT` e checks não negativos; não inferir `Integer` a partir de `int`. |
| Datas | `TIMESTAMPTZ NOT NULL DEFAULT NOW()` nas três tabelas; usar timezone e default do servidor. |
| Texto | Preservar comprimentos 150/50/20; `slug` é `VARCHAR(150)` nullable, sem unicidade. |
| Estado | Texto com default e check `finished`; não introduzir um ENUM PostgreSQL. |
| Unicidade | Apenas PKs e par `(source, source_match_id)`; não tornar `teams.name` ou `competitions.slug` únicos. |
| Nulabilidade | Só `competition_id` e `slug` aceitam NULL entre as colunas atuais. |
| Constraints | Preservar os nomes explícitos das três FKs, do check de equipas e da unicidade composta. |
| Nomes implícitos | Os três checks de coluna e as PKs recebem nomes do PostgreSQL. Os nomes dos checks no exemplo são os esperados numa criação normal, não uma inspeção da base local. Confirmar no catálogo antes do baseline. |
| Schema | O SQL não qualifica tabelas; o projeto usa `public` nas consultas e no CI. Confirmar `search_path`; propor metadata sem qualificação explícita e contexto controlado em `public`, evitando diferenças artificiais na reflexão. |

O objetivo é diferença estrutural nula, não uma nova modelação. Não definir uma
convenção global de nomes que renomeie constraints existentes implicitamente.
Na revisão da implementação, comparar PKs, FKs, checks, defaults, identidades,
índices e nulabilidade com o catálogo de uma cópia isolada. Casts introduzidos
pelo PostgreSQL em defaults e checks podem ser equivalentes semanticamente.
Não gerar alterações apenas por diferenças de representação textual.

`docs/database-design.md` contém exemplos e um diagrama simplificados (por
exemplo, `slug` como text e exemplos sem todos os timestamps). O DDL
`001_initial_schema.sql` é a referência de implementação; não copiar essas
simplificações. README e architecture também têm descrições históricas já
ultrapassadas. A atualização desses ficheiros fica fora desta tarefa.

Pydantic não impõe os limites máximos PostgreSQL de `SMALLINT`, `BIGINT` ou
`VARCHAR`, e o SQL não impõe todas as regras de entrada (por exemplo,
`source_match_id >= 1` ou nomes não vazios). São diferenças existentes entre
contratos; não acrescentar checks ou validadores silenciosamente no baseline.

## Introduzir Alembic sem recriar tabelas existentes

Recomenda-se uma revisão inicial completa, com identificador fixo a decidir
(`initial_schema` neste plano), que reproduza o DDL atual numa base vazia.
`down_revision = None` identifica o início do histórico.
Gerar esta revisão a partir de uma base vazia e rever o resultado com o SQL;
gerá-la contra a base já preenchida pode produzir uma revisão vazia, incapaz
de preparar ambientes novos.

### Base existente

1. Numa futura tarefa autorizada, obter backup e trabalhar primeiro numa cópia
   isolada; confirmar explicitamente host, base, utilizador e `search_path`.
2. Inspecionar o schema real e compará-lo integralmente com o baseline aprovado,
   incluindo dados incompatíveis, objetos adicionais, ownership e privilégios.
   Comparar também com uma base nova criada pela revisão inicial.
3. Se houver diferenças, parar e preparar um plano de reconciliação revisto;
   não mascarar divergências com marcação de versão ou criação condicional.
4. Só quando a equivalência estiver demonstrada e a operação autorizada,
   aplicar conceptualmente `alembic stamp <initial_revision_id>`.
   O identificador deve ser o baseline exato, não `head` se existirem revisões
   posteriores ainda não aplicadas.
5. Verificar a revisão registada e só depois aplicar upgrades posteriores
   autorizados. Comparar schema e contagens/dados antes e depois em cópia.

`stamp` regista a revisão sem executar os passos `upgrade` dessa revisão;
pode criar/escrever `alembic_version`. Portanto, altera a base e não valida
nem corrige a estrutura. Não foi executado nesta tarefa.
Executar a migração inicial cegamente sobre tabelas existentes tentaria criá-las
de novo e falharia; contornar o erro com existência condicional pode esconder
schemas incompatíveis. O [cookbook Alembic](https://alembic.sqlalchemy.org/en/latest/cookbook.html)
explica a separação entre criação de estrutura e marcação de versão.

### Base nova

Criar previamente a database e a role de migração fora do histórico de tabelas.
Sobre um schema vazio e alvo confirmado, executar futuramente
`alembic upgrade head`: o baseline cria as três tabelas, seguido das revisões
posteriores. Não executar primeiro o SQL manual nem `create_all()` nesse mesmo
percurso. Manter o ficheiro SQL como referência histórica, sem o alterar nesta
tarefa; depois da transição, Alembic será a autoridade para evolução do schema.

Os privilégios da role da aplicação continuam a ser preparados explicitamente
pelo provisionamento/CI. O autogenerate não substitui esse trabalho, nem um
baseline de tabelas garante paridade de permissões.

### Upgrade, downgrade e revisão automática

Cada revisão futura deve explicar pré-condições, efeitos, reversibilidade e
impacto nos dados. Testar ida e volta de revisões reversíveis apenas em bases
descartáveis. O downgrade do baseline implicaria remover a estrutura e dados;
não deve ser usado para recuperar uma base existente marcada com `stamp`.
Qualquer operação destrutiva requer autorização específica. Não se inclui nem
executa aqui SQL destrutivo.

O autogenerate produz candidatos sujeitos a revisão humana. Não deteta de
forma completa todos os checks nem interpreta renomeações como intenção;
comparação de defaults precisa de configuração e análise. `alembic check`
poderá apoiar o CI, mas não prova equivalência total. Acrescentar inspeções
explícitas de constraints e identidades.
Ver [limitações do autogenerate](https://alembic.sqlalchemy.org/en/latest/autogenerate.html).

## Adoção gradual e contratos públicos

1. **FI-007.1 (esta tarefa):** aprovar arquitetura e baseline, sem dependências,
   DDL, alterações ao ETL ou segunda escrita.
2. **Próximo incremento recomendado:** adicionar apenas modelos/metadata e
   testes da sua fidelidade, após verificar versões SQLAlchemy 2.x, Alembic e
   Psycopg compatíveis com Python 3.14. Justificar faixas de versões antes de
   alterar dependências; não assumir compatibilidade por usarem Python moderno.
3. **Incremento seguinte:** configurar Alembic e revisão inicial, validando
   criação nova e adoção por stamp em ambientes descartáveis. Nenhum acesso à
   base local por efeitos de importação ou testes unitários.
4. **Depois da aprovação operacional:** migrar o provisionamento de CI para
   Alembic e preparar o procedimento manual revisto para bases existentes.
5. **Apenas por requisito posterior:** introduzir leituras ORM ou Core. Uma
   eventual substituição da escrita exige tarefa própria e testes de paridade;
   não manter duas implementações de escrita ativas nem fazer escrita dupla.

Preservar `DatabaseSettings`, `connect(settings=None)`,
`fetch_match_counts(source=None, settings=None)` e
`persist_matches(matches, source, *, connection=None, settings=None) -> int`.
Manter tipos de retorno, dicionários, erros públicos, aceitação de uma ligação
Psycopg externa, dados JSON, CLI e regras de `FootballMatch`. Não trocar essa
ligação por Engine/Session através de uma alteração de tipo silenciosa.
Preservar a contagem de registos processados, incluindo numa repetição, e a
chave de conflito `(source, source_match_id)`; `Session.merge()` não é um
substituto automático do UPSERT por chave de negócio.

A implementação real usa `connection.transaction()`: com transação externa
ativa, cria um âmbito aninhado/savepoint; sem transação ativa, pode confirmar
a transação que abre quando o bloco termina com sucesso. Com ligação própria,
o contexto Psycopg também gere o seu ciclo de vida. A frase do README que
atribui sempre a decisão ao chamador simplifica este comportamento. Preservar
esta semântica observada e testá-la antes de uma substituição, sem prometer
que a função nunca confirma transações. Não misturar gestores transacionais
Psycopg e Session sobre a mesma ligação sem um desenho posterior explícito.

Manter validação de todos os jogos antes da escrita, rejeição de nomes ambíguos,
atualizações limitadas à mesma fonte e `competition_id=None` no caminho atual.
A resolução de equipas por nome continua provisória; concorrência pode criar
nomes duplicados porque não existe unicidade. SQLAlchemy não resolve essa
limitação e o baseline não deve alterar a identidade das equipas.

## Testes e CI futuros

O CI atual usa Python 3.14, PostgreSQL 17 temporário, aplicação do SQL manual e
role de aplicação restrita. Os dois testes PostgreSQL verificam identidade da
ligação, inserção, repetição idempotente, atualização e rollback. O teste de
persistência exige tabelas inicialmente vazias e verifica que continuam vazias
no final. Não o executar numa base local com dados reais.
Os fakes unitários cobrem lógica de persistência, mas não demonstram semântica
transacional real nem integridade PostgreSQL.

Na implementação futura:

- Manter testes atuais de ETL, Pydantic, configuração, leituras e persistência.
- Adicionar testes de metadata: tipos, comprimentos, nulabilidade, defaults,
  identity, nomes de constraints e resolução das duas relações para equipas.
- Em PostgreSQL descartável, testar `upgrade head` desde vazio e comparar com
  o schema SQL legado, incluindo checks e identidades via catálogo.
- Num segundo ambiente descartável, aplicar SQL legado, inserir dados de teste,
  validar equivalência, marcar o baseline e aplicar revisões posteriores.
  Confirmar preservação de linhas e IDs; provar rejeição de schema divergente.
- Validar constraints com entradas inválidas diretamente no PostgreSQL, além
  da validação Pydantic, e manter testes de idempotência e isolamento de fontes.
- Usar a role de migração para DDL e a role restrita para testes de aplicação.
  Preservar grants de tabelas/colunas e comportamento das identidades.
- Substituir a aplicação do SQL manual pelo upgrade apenas após paridade;
  conservar temporariamente um percurso legado separado para testar adoção.
- Verificar revisão esperada, um único head e ausência de drift detetável,
  complementando `alembic check` com inspeções que este não cobre.
- Manter pytest, Ruff lint, Ruff format e `pip check`. Testar downgrade apenas
  quando reversível e aprovado num ambiente descartável, nunca na base local.

## Riscos e decisões para revisão do ChatGPT

| Risco ou decisão | Proposta a rever |
| --- | --- |
| Drift oculto numa base manual | Exigir equivalência comprovada antes de stamp; não assumir que o SQL no Git corresponde ao servidor. |
| Nomes gerados pelo PostgreSQL | Confirmar nomes reais dos checks e PKs; preservar nomes antes de adotar convenções novas. |
| Falsa segurança no autogenerate | Rever toda a revisão e testar constraints/identity explicitamente. |
| Transações incompatíveis | Manter Psycopg na escrita e documentar o comportamento efetivo dos contextos transacionais. |
| Identidade de equipas e concorrência | Preservar a regra atual; resolver num requisito posterior, sem unicidade nova no baseline. |
| Credenciais e privilégios | Fábrica explícita, URL estruturada, sem logs de segredos; role DDL separada da aplicação. |
| Compatibilidade Python 3.14 | Validar versões concretas antes de aprovar dependências; nenhuma foi instalada agora. |
| Autoridade do schema | Baseline fiel ao SQL; depois Alembic gere a evolução, sem dois mecanismos concorrentes de criação. |
| Relações ORM | Aprovar navegação unidirecional viewonly inicialmente; adiar coleções e Session de escrita. |
| Política de downgrade | Definir reversibilidade e recuperação por backup; impedir uso do baseline como rollback operacional de dados existentes. |
| Sequência de entrega | Aprovar primeiro modelos/metadata testados, depois configuração Alembic e baseline em bases descartáveis. |

A implementação só deve avançar depois da revisão destas decisões. A base
`footballiq_dev` permanece fora das operações desta tarefa.
