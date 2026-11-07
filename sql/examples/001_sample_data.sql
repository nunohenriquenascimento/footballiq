-- Script pedagógico de carga do dataset sample do FootballIQ.
--
-- Objetivo: inserir os cinco jogos reais do ficheiro JSON de exemplo, mantendo a
-- ingestão idempotente para a fonte 'sample' e sem assumir que o nome da equipa
-- é uma identidade global única.
--
-- Regra importante: teams.name não tem UNIQUE porque a identidade interna continua
-- a ser o id gerado pela base de dados. O mapeamento de equipas para o dataset
-- sample é uma convenção temporária e pode ser revisitada quando a fonte incluir
-- identificadores oficiais de equipa.
--
-- Este ficheiro deve ser executado dentro de uma transação externa, por exemplo:
-- BEGIN; \i sql/examples/001_sample_data.sql; ROLLBACK;

-- Criamos um mapa temporário para guardar a relação entre nome de equipa e id do
-- registo que foi criado na base de dados. Esta abordagem permite gerir os cinco
-- jogos reais sem assumir sequências ou ids manuais. Como o script pode ser
-- executado mais do que uma vez na mesma transação de teste, limpamos também o
-- mapa antes de o preencher.
CREATE TEMP TABLE IF NOT EXISTS sample_team_map (
    team_name VARCHAR(150) PRIMARY KEY,
    team_id BIGINT NOT NULL
);
DELETE FROM sample_team_map;

-- Inserção de equipas do dataset sample, respetando a regra de que a mesma equipa
-- pode ser reutilizada em vários jogos sem criar duplicados indevidos.
WITH source_teams(team_name) AS (
    VALUES
        ('Benfica'),
        ('Porto'),
        ('Sporting'),
        ('Braga'),
        ('Ajax'),
        ('PSV'),
        ('Arsenal'),
        ('Chelsea'),
        ('Real Madrid'),
        ('Barcelona')
),
new_teams AS (
    INSERT INTO teams (name)
    SELECT DISTINCT st.team_name
    FROM source_teams st
    WHERE NOT EXISTS (
        SELECT 1
        FROM teams t
        WHERE t.name = st.team_name
    )
    RETURNING id, name
)
INSERT INTO sample_team_map (team_name, team_id)
SELECT name, id
FROM new_teams
UNION ALL
SELECT st.team_name, t.id
FROM source_teams st
JOIN teams t ON t.name = st.team_name
LEFT JOIN sample_team_map m ON m.team_name = st.team_name
WHERE m.team_name IS NULL;

-- Carga dos cinco jogos sample.
-- A estratégia usa source e source_match_id como chave de negócio, e ON CONFLICT
-- garante idempotência para a mesma fonte e o mesmo identificador externo.
INSERT INTO matches (
    source,
    source_match_id,
    home_team_id,
    away_team_id,
    home_goals,
    away_goals,
    status,
    competition_id
)
VALUES
    (
        'sample',
        101,
        (SELECT team_id FROM sample_team_map WHERE team_name = 'Benfica'),
        (SELECT team_id FROM sample_team_map WHERE team_name = 'Porto'),
        2,
        1,
        'finished',
        NULL
    ),
    (
        'sample',
        102,
        (SELECT team_id FROM sample_team_map WHERE team_name = 'Sporting'),
        (SELECT team_id FROM sample_team_map WHERE team_name = 'Braga'),
        1,
        1,
        'finished',
        NULL
    ),
    (
        'sample',
        103,
        (SELECT team_id FROM sample_team_map WHERE team_name = 'Ajax'),
        (SELECT team_id FROM sample_team_map WHERE team_name = 'PSV'),
        0,
        3,
        'finished',
        NULL
    ),
    (
        'sample',
        104,
        (SELECT team_id FROM sample_team_map WHERE team_name = 'Arsenal'),
        (SELECT team_id FROM sample_team_map WHERE team_name = 'Chelsea'),
        2,
        0,
        'finished',
        NULL
    ),
    (
        'sample',
        105,
        (SELECT team_id FROM sample_team_map WHERE team_name = 'Real Madrid'),
        (SELECT team_id FROM sample_team_map WHERE team_name = 'Barcelona'),
        1,
        1,
        'finished',
        NULL
    )
ON CONFLICT (source, source_match_id)
DO UPDATE SET
    home_team_id = EXCLUDED.home_team_id,
    away_team_id = EXCLUDED.away_team_id,
    home_goals = EXCLUDED.home_goals,
    away_goals = EXCLUDED.away_goals,
    status = EXCLUDED.status,
    competition_id = EXCLUDED.competition_id;

-- Não há COMMIT aqui. Este ficheiro é pensado para ser executado dentro de uma
-- transação de teste e depois revertido com ROLLBACK, mantendo o ambiente limpo.
