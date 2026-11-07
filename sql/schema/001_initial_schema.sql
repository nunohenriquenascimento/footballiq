-- Esquema inicial do FootballIQ.
--
-- Este ficheiro representa a primeira estrutura relacional educativa do projeto.
-- O objetivo é reproduzir as regras já validadas em JSON em PostgreSQL, sem
-- adicionar dados de exemplo nem inventar requisitos que ainda não existem.
--
-- Futuramente, esta base será gerida com migrações e Alembic, em vez de criar
-- objetos diretamente a partir de ficheiros SQL manuais.

BEGIN;

-- DDL (Data Definition Language) define a estrutura da base de dados.
-- Cada CREATE TABLE cria uma entidade do domínio e as suas regras de consistência.

-- competitions: tabela opcional que representa a competição associada a um jogo.
-- A coluna competition_id em matches fica nullable porque o JSON atual ainda não
-- inclui informação de competição de forma obrigatória.
CREATE TABLE competitions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    slug VARCHAR(150),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- teams: armazena cada equipa uma vez e reutiliza a mesma linha em vários jogos.
-- O nome da equipa é um valor de negócio útil, mas não é a identidade única da
-- tabela; a identidade interna continua a ser o campo id.
CREATE TABLE teams (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- matches: tabela central que liga equipas, golos, origem do dado e identificador
-- do jogo na fonte.
--
-- PRIMARY KEY: identifica cada linha da tabela de forma única.
-- FOREIGN KEY: garante que o valor de todas as referências existe nas tabelas
-- relacionadas.
-- UNIQUE (source, source_match_id): evita duplicações do mesmo jogo dentro da
-- mesma fonte, mantendo a idempotência da ingestão.
-- CHECK: valida integridade sem depender da aplicação.
CREATE TABLE matches (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    competition_id BIGINT,
    source VARCHAR(50) NOT NULL,
    source_match_id BIGINT NOT NULL,
    home_team_id BIGINT NOT NULL,
    away_team_id BIGINT NOT NULL,
    home_goals SMALLINT NOT NULL CHECK (home_goals >= 0),
    away_goals SMALLINT NOT NULL CHECK (away_goals >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'finished' CHECK (status = 'finished'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_matches_competition
        FOREIGN KEY (competition_id) REFERENCES competitions(id),

    CONSTRAINT fk_matches_home_team
        FOREIGN KEY (home_team_id) REFERENCES teams(id),

    CONSTRAINT fk_matches_away_team
        FOREIGN KEY (away_team_id) REFERENCES teams(id),

    CONSTRAINT chk_matches_teams_different
        CHECK (home_team_id <> away_team_id),

    CONSTRAINT uq_matches_source_match_id
        UNIQUE (source, source_match_id)
);

COMMIT;
