# Modelação relacional inicial do FootballIQ

## Objetivo

Esta documentação define a primeira arquitectura relacional em PostgreSQL para representar partidas de futebol de um modo simples, legível e extensível. O objetivo não é construir a base de dados ainda, mas preparar a estrutura lógica antes da implementação real.

A lógica do projeto atual já valida partidas em JSON com regras importantes: identificadores positivos, golos não negativos, equipas diferentes, estado final e sem campos extras. A modelação relacional serve para transformar esse mesmo conhecimento em tabelas, chaves e restrições explícitas, mantendo o formato JSON e o ETL existentes sem alterações.

## Dados atuais que já existem

O ficheiro de exemplo em `data/sample/matches.json` contém os seguintes campos por jogo:

- `match_id`: identificador do jogo na fonte de exemplo
- `home_team`: nome da equipa da casa
- `away_team`: nome da equipa visitante
- `home_goals`: golos marcados pela equipa da casa
- `away_goals`: golos marcados pela equipa visitante
- `status`: estado do jogo

O formato atual mostra um caso simples de resultados de partidas. Ainda não existe informação sobre competição, data, temporada, estádio, árbitro, liga, nem outra dimensão do domínio. Por isso, a primeira base de dados deve refletir o que já existe e deixar futuras extensões como campos opcionais ou tabelas adicionais sem forçar dados que ainda não existem.

## Objetivo pedagógico da modelação relacional

Uma base de dados relacional organiza informação em entidades e relações. Em vez de guardar tudo num único JSON, dividimos a informação em tabelas de domínio:

- `competitions`: lista as competições
- `teams`: lista as equipas
- `matches`: regista cada jogo, as equipas e os resultados

A vantagem principal é que a informação deixa de estar repetida e passa a ser referenciada por relações. Isso reduz inconsistências, melhora integridade e prepara a base para consultas analíticas mais expandidas no futuro.

## Entidades iniciais propostas

### 1) competitions

Representa o campeonato, taça ou liga a que um jogo pode pertencer.

A informação de competição ainda não existe no JSON atual, por isso esta tabela é tratada como uma extensão opcional. Quando a fonte incluir competição, a referência será adicionada ao registo do jogo; enquanto isso, a coluna pode ficar nula.

### 2) teams

Representa cada equipa do domínio.

A equipa é armazenada uma vez e depois referenciada em vários jogos. Isto reduz redundância e evita inconsistências de escrita, como "Benfica" vs " SL Benfica" ou nomes com espaços extras. Neste desenho, o nome da equipa continua a ser um valor de negócio útil, mas não constitui a garantia de identidade única. A identidade física continua a ser a chave interna `id`.

### 3) matches

Representa cada partida com os resultados finais e as referências às equipas.

A tabela de partidas liga:

- a equipa local;
- a equipa visitante;
- os golos das duas equipas;
- a origem do dado;
- o identificador do jogo na fonte;
- o estado do jogo.

## Relações e cardinalidades

A estrutura inicial pode ser interpretada assim:

- uma competição pode ter zero ou muitos jogos;
- um jogo pode pertencer a zero ou uma competição;
- uma equipa pode jogar zero ou muitos jogos como local;
- uma equipa pode jogar zero ou muitos jogos como visitante;
- um jogo envolve exactamente duas equipas diferentes.

Em termos formais:

- `competitions 1 -- 0..n matches`
- `teams 1 -- 0..n matches (home_team)`
- `teams 1 -- 0..n matches (away_team)`

Esta é a lógica típica de um modelo relacional: a equipa existe em `teams` e as partidas referenciam essa equipa por chave estrangeira.

## Primary keys, foreign keys e chaves de negócio

### Identificadores internos e externos

É útil distinguir dois tipos de identificadores:

1. Identificadores internos (`surrogate keys`):
   - servem para ligar tabelas internamente;
   - são gerados pela base de dados;
   - não dependem do dado de negócio;
   - estabilizam a identidade lógica do registo.

2. Identificadores externos (`business keys`):
   - vêm da fonte de dados;
   - servem para reconhecer um registo de negócio;
   - ajudam a reprocessar ou reconciliar dados sem depender do `id` interno.

Exemplo do modelo proposto:

- `teams.id` -> identificador interno
- `teams.name` -> nome da equipa, valor de negócio
- `matches.id` -> identificador interno
- `matches.source_match_id` -> identificador do jogo na fonte original
- `matches.source` -> nome do fornecedor, por exemplo `sample`

A mesma ideia vale para competições:

- `competitions.id` = chave interna
- `competitions.name` = nome de negócio da competição

### Diferença entre chave primária, chave estrangeira e chave de negócio

- `PRIMARY KEY`: identifica uma linha de forma única dentro da própria tabela.
- `FOREIGN KEY`: liga uma linha de uma tabela a uma linha de outra tabela.
- `chave de negócio`: identifica um valor que existe no domínio e que pode ser usado para deduplicar ou reconciliar dados entre execuções.

No desenho atual, a chave primária é sempre o `id` gerado pela base de dados; a chave estrangeira são as referências de `teams` e `competitions` em `matches`; a chave de negócio é a combinação de `source` e `source_match_id`.

## Restrições de integridade propostas

### 1) Equipas diferentes num jogo

A regra já existe no modelo Pydantic:

- `home_team_id` e `away_team_id` não podem ser iguais.

Em SQL, implementa-se assim:

```sql
CHECK (home_team_id <> away_team_id)
```

### 2) Golos não negativos

A regra de negócio é simples e forte:

```sql
CHECK (home_goals >= 0)
CHECK (away_goals >= 0)
```

### 3) Jogos sem identificadores duplicados

O ficheiro JSON usa `match_id` como identificador único por jogo. Em SQL, a regra correta nesta fase é: o mesmo identificador de negócio pode repetir apenas dentro de uma mesma fonte.

A premissa escolhida é:

```sql
UNIQUE (source, source_match_id)
```

A ideia é simples: um jogo só pode existir uma vez por fornecedor e por identificador daquele fornecedor. Se uma segunda fonte vier a existir, o mesmo `source_match_id` pode reaparecer, mas apenas com um `source` diferente.

### 4) Relações válidas entre tabelas

- `home_team_id` deve existir em `teams(id)`
- `away_team_id` deve existir em `teams(id)`
- `competition_id` deve existir em `competitions(id)` quando preenchido

Estas regras são implementadas por `FOREIGN KEY`.

## Necessidade de season, status e datas

### `status`

O JSON atual usa `"finished"` em todos os exemplos. Isso sugere que o estado do jogo é relevante e que pode ser normalizado em um campo de texto ou numa tabela de status.

Nesta versão inicial, a decisão aprovada é manter o campo limitado ao valor `finished`:

```sql
status VARCHAR(20) NOT NULL DEFAULT 'finished'
CHECK (status = 'finished')
```

### `season`

Ainda não existe no JSON atual. Se surgir no futuro, convém guardar em uma tabela de temporadas ou como coluna opcional. Nesta fase, não é obrigatório.

### `match_date`

Também não está presente no ficheiro atual. Não devemos inventá-la como obrigatória. Se a fonte vier a incluir datas, a modelação pode evoluir para `match_date TIMESTAMP` com `NULL` assumindo ausência de informação.

Conclusão: `status` é obrigatório nesta fase porque já existe no modelo; `season` e `match_date` são extensões futuras e não devem ser exigidas agora.

## Conversão do formato JSON para o modelo relacional

O JSON atual representa um registo de jogo como um objeto com campos simples. A conversão para SQL segue este raciocínio:

1. Criar a equipa na tabela `teams` se ainda não existir.
2. Guardar o nome da equipa na tabela `teams`.
3. Criar o registo da partida em `matches` apontando para as duas equipas.
4. Guardar `source`, `source_match_id`, `home_goals`, `away_goals` e `status`.
5. Se houver competição, guardar também `competition_id`.

Exemplo de mapeamento:

```text
JSON match:
{
  "match_id": 101,
  "home_team": "Benfica",
  "away_team": "Porto",
  "home_goals": 2,
  "away_goals": 1,
  "status": "finished"
}
```

Converte-se em:

- `teams`: `Benfica`, `Porto`
- `matches`: `source = 'sample'`, `source_match_id = 101`, `home_team_id = id(Benfica)`, `away_team_id = id(Porto)`, `home_goals = 2`, `away_goals = 1`, `status = 'finished'`

### Atenção importante sobre o nome das equipas

A resolução por nome é provisória e não deve ser tratada como garantia de identidade. A mesma equipa pode existir em fontes diferentes com nomes ligeiramente diferentes ou com pequenas variações ortográficas. O modelo atual usa o nome por conveniência da fase inicial, mas a robustez real virá com a distinção entre:

- identidade interna (`id`),
- nome de negócio (`name`),
- origem do dado (`source`).

## Evitar duplicações em execuções repetidas

Quando o pipeline for executado várias vezes, podem surgir entradas duplicadas. A abordagem escolhida para esta fase é:

- usar `source` e `source_match_id` como chave de negócio;
- usar `UNIQUE (source, source_match_id)` para impedir duplicações do mesmo jogo pela mesma fonte;
- usar `INSERT ... ON CONFLICT (source, source_match_id) DO UPDATE` para tornar a ingestão idempotente;
- manter o `JSON` e o ETL existentes sem alteração funcional.

Esta é a forma correta de garantir que a mesma execução repetida não cria linhas duplicadas na base de dados.

## Idempotência e atualização de resultados já existentes

Idempotência significa que a mesma operação executada várias vezes produz o mesmo resultado final. No contexto do ETL, isso é muito importante.

Se o mesmo ficheiro JSON for processado mais do que uma vez, a base de dados deve manter apenas uma linha por jogo da mesma fonte. Para isso, a regra de negócio escolhida é:

```sql
UNIQUE (source, source_match_id)
```

e a operação de ingestão deve ser um `UPSERT`:

```sql
INSERT ...
ON CONFLICT (source, source_match_id)
DO UPDATE SET
    home_team_id = EXCLUDED.home_team_id,
    away_team_id = EXCLUDED.away_team_id,
    home_goals = EXCLUDED.home_goals,
    away_goals = EXCLUDED.away_goals,
    status = EXCLUDED.status;
```

Assim, uma execução repetida atualiza os resultados em vez de criar duplicações.

## Tabela única vs modelo normalizado

### Opção 1: tabela única

Uma tabela simples poderia ter colunas como:

- `match_id`
- `home_team`
- `away_team`
- `home_goals`
- `away_goals`
- `status`

Ela funciona para um protótipo, mas tem problemas:

- repete o nome da equipa em vários registos;
- torna pedidos por equipa menos eficientes;
- dificulta normas de integridade;
- aumenta o risco de inconsistency de nomes e resultados.

### Opção 2: modelo normalizado

O modelo normalizado proposto separa dados em `teams` e `matches`, com relações explícitas. Esta abordagem é mais robusta, melhor para SQL e mais adequada a dashboards, análise e expansão futura.

A escolha correta para o FootballIQ é a segunda opção, porque o projeto evolui para Data Engineering, Analytics e IA e precisa de clareza e reusabilidade.

## Diagrama ER (Mermaid)

```mermaid
erDiagram
    COMPETITIONS ||--o{ MATCHES : contains
    TEAMS ||--o{ MATCHES : plays_home
    TEAMS ||--o{ MATCHES : plays_away

    COMPETITIONS {
        bigint id PK
        varchar name
        text slug
    }

    TEAMS {
        bigint id PK
        varchar name
        timestamp created_at
    }

    MATCHES {
        bigint id PK
        bigint competition_id FK "nullable"
        varchar source
        bigint source_match_id
        bigint home_team_id FK
        bigint away_team_id FK
        smallint home_goals
        smallint away_goals
        varchar status
        timestamp created_at
        unique(source, source_match_id)
    }
```

## Tabela de colunas e restrições propostas

| Tabela | Coluna | Tipo PostgreSQL | Constraints | Justificação |
| --- | --- | --- | --- | --- |
| competitions | id | `BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY` | `PRIMARY KEY` | Chave interna da competição |
| competitions | name | `VARCHAR(150)` | `NOT NULL` | Nome da competição |
| competitions | slug | `VARCHAR(150)` | `NULL` | Identificador legível para joins e futuras URLs; sem `UNIQUE` nesta fase |
| competitions | created_at | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | Registo de criação da competição |
| teams | id | `BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY` | `PRIMARY KEY` | Chave interna da equipa |
| teams | name | `VARCHAR(150)` | `NOT NULL` | Nome da equipa, usado provisoriamente para resolução de identidade |
| teams | created_at | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | Registo de criação |
| matches | id | `BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY` | `PRIMARY KEY` | Chave interna do jogo |
| matches | competition_id | `BIGINT` | `NULL`, `REFERENCES competitions(id)` | Competição opcional nesta fase |
| matches | source | `VARCHAR(50)` | `NOT NULL` | Origem do dado; exemplo: `sample` |
| matches | source_match_id | `BIGINT` | `NOT NULL` | Identificador do jogo na fonte original |
| matches | home_team_id | `BIGINT` | `NOT NULL`, `REFERENCES teams(id)`, `CHECK (home_team_id <> away_team_id)` | Equipa local |
| matches | away_team_id | `BIGINT` | `NOT NULL`, `REFERENCES teams(id)`, `CHECK (home_team_id <> away_team_id)` | Equipa visitante |
| matches | home_goals | `SMALLINT` | `NOT NULL`, `CHECK (home_goals >= 0)` | Golos da equipa da casa |
| matches | away_goals | `SMALLINT` | `NOT NULL`, `CHECK (away_goals >= 0)` | Golos da equipa visitante |
| matches | status | `VARCHAR(20)` | `NOT NULL DEFAULT 'finished'`, `CHECK (status = 'finished')` | Estado atual, consistente com o JSON |
| matches | created_at | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | Registo de criação |
| matches | unique | `UNIQUE (source, source_match_id)` | | Evita duplicações do mesmo jogo na mesma fonte |

## Exemplos educativos de SQL

### 1) CREATE TABLE

```sql
-- Cria a tabela de competições.
CREATE TABLE competitions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    slug VARCHAR(150)
);

-- Cria a tabela de equipas.
CREATE TABLE teams (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Cria a tabela de partidas.
CREATE TABLE matches (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    competition_id BIGINT REFERENCES competitions(id),
    source VARCHAR(50) NOT NULL,
    source_match_id BIGINT NOT NULL,
    home_team_id BIGINT NOT NULL REFERENCES teams(id),
    away_team_id BIGINT NOT NULL REFERENCES teams(id),
    home_goals SMALLINT NOT NULL CHECK (home_goals >= 0),
    away_goals SMALLINT NOT NULL CHECK (away_goals >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'finished' CHECK (status = 'finished'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (home_team_id <> away_team_id),
    UNIQUE (source, source_match_id)
);
```

### 2) INSERT

```sql
-- Insere uma competição apenas se a fonte vier a incluir competição.
INSERT INTO competitions (name, slug)
VALUES ('Primeira Liga', 'primeira-liga');

-- Insere as equipas. A resolução por nome é provisória, não um identificador obrigatório.
INSERT INTO teams (name)
VALUES ('Benfica'), ('Porto');

-- Insere o jogo da fonte fictícia chamada 'sample'.
INSERT INTO matches (
    competition_id,
    source,
    source_match_id,
    home_team_id,
    away_team_id,
    home_goals,
    away_goals,
    status
)
VALUES (
    1,
    'sample',
    101,
    1,
    2,
    2,
    1,
    'finished'
);
```

### 3) SELECT com JOIN

```sql
-- Mostra o resultado dos jogos com os nomes das equipas.
SELECT
    m.id,
    m.source,
    m.source_match_id,
    ht.name AS home_team,
    at.name AS away_team,
    m.home_goals,
    m.away_goals,
    m.status
FROM matches AS m
JOIN teams AS ht ON ht.id = m.home_team_id
JOIN teams AS at ON at.id = m.away_team_id
ORDER BY m.source, m.source_match_id;
```

### 4) UPSERT para idempotência

```sql
-- Evita duplicações em execuções repetidas do mesmo ficheiro.
INSERT INTO matches (
    competition_id,
    source,
    source_match_id,
    home_team_id,
    away_team_id,
    home_goals,
    away_goals,
    status
)
VALUES (
    1,
    'sample',
    101,
    1,
    2,
    2,
    1,
    'finished'
)
ON CONFLICT (source, source_match_id)
DO UPDATE SET
    competition_id = EXCLUDED.competition_id,
    home_team_id = EXCLUDED.home_team_id,
    away_team_id = EXCLUDED.away_team_id,
    home_goals = EXCLUDED.home_goals,
    away_goals = EXCLUDED.away_goals,
    status = EXCLUDED.status;
```

Este exemplo mostra uma boa prática de ingestão: repetir o mesmo processamento não cria registos duplicados; apenas atualiza o registo existente.

## Limitações e extensões futuras

A primeira versão do desenho é deliberadamente simples e segura para o contexto atual. No entanto, há algumas decisões que ainda não devem ser forçadas:

1. `season` não é obrigatório, porque o JSON atual não o inclui.
2. `match_date` não é obrigatório, porque a fonte atual não tem essa dimensão.
3. O nome da equipa resolve a identidade de forma provisória, mas não é uma garantia de unicidade em fontes diferentes.
4. `competitions` é uma extensão opcional e deve deixar de o ser quando a fonte incluir liga/campeonato formalmente.
5. Em fontes futuras, pode ser útil separar `source` em uma tabela de fornecedores, em vez de manter texto em cada jogo.
6. Em cubos analíticos, pode valer a pena separar resultados, calendário e dimensão de equipas em tabelas dedicadas.

## Conclusão

A primeira modelação relacional do FootballIQ deve ser simples, fiel ao que já existe no JSON e preparada para evoluir. O núcleo da solução é claro:

- `competitions` para organização;
- `teams` para entidades estáveis;
- `matches` para resultados e relações;
- `BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY` para chaves internas consistentes;
- `FOREIGN KEY` para integridade referencial;
- `CHECK` para golos, status e equipa local/visitante;
- `UNIQUE (source, source_match_id)` para idempotência por fornecedor;
- `created_at` em `competitions` para registo de criação, porque a tabela também precisa de observabilidade temporal.

Importante: neste primeiro desenho, `competitions.slug` não recebe `UNIQUE` porque a fonte atual não exige identidade de competição e a tabela é tratada como extensão opcional. Quando a fonte incluir competições de forma formal, essa decisão pode ser revisada e reforçada com uma restrição explícita.

Este desenho está alinhado com o objetivo educativo do projeto: aprender modelação relacional, garantir qualidade de dados e preparar o caminho para análises mais complexas sem inventar requisitos que ainda não existem.
