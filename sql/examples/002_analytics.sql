-- Consultas analíticas iniciais sobre os jogos sample do FootballIQ.
--
-- Estas queries usam JOIN, GROUP BY, CASE, COALESCE e agregações para responder
-- às primeiras perguntas úteis do projeto: quantos golos, quem marcou mais,
-- quantos jogos cada equipa jogou e como ficaria uma classificação provisória.

-- 1) Lista dos cinco jogos com nomes das equipas e resultado final.
SELECT
    m.source_match_id AS match_id,
    ht.name AS home_team,
    at.name AS away_team,
    m.home_goals,
    m.away_goals,
    m.home_goals + m.away_goals AS total_goals,
    m.status
FROM matches AS m
JOIN teams AS ht ON ht.id = m.home_team_id
JOIN teams AS at ON at.id = m.away_team_id
WHERE m.source = 'sample'
ORDER BY m.source_match_id;

-- 2) Total de golos por jogo.
SELECT
    m.source_match_id AS match_id,
    m.home_goals + m.away_goals AS total_goals
FROM matches AS m
WHERE m.source = 'sample'
ORDER BY m.source_match_id;

-- 3) Média de golos por jogo.
SELECT
    ROUND(AVG(m.home_goals + m.away_goals), 2) AS average_goals_per_match
FROM matches AS m
WHERE m.source = 'sample';

-- 4) Número de jogos por equipa.
WITH all_team_games AS (
    SELECT home_team_id AS team_id, 1 AS games_count FROM matches WHERE source = 'sample'
    UNION ALL
    SELECT away_team_id AS team_id, 1 AS games_count FROM matches WHERE source = 'sample'
)
SELECT
    t.name,
    SUM(atg.games_count) AS games_played
FROM all_team_games AS atg
JOIN teams AS t ON t.id = atg.team_id
GROUP BY t.name
ORDER BY games_played DESC, t.name;

-- 5) Golos marcados e sofridos por equipa.
WITH team_stats AS (
    SELECT
        h.team_id,
        SUM(h.goals_for) AS goals_for,
        SUM(h.goals_against) AS goals_against
    FROM (
        SELECT
            home_team_id AS team_id,
            home_goals AS goals_for,
            away_goals AS goals_against
        FROM matches
        WHERE source = 'sample'
        UNION ALL
        SELECT
            away_team_id AS team_id,
            away_goals AS goals_for,
            home_goals AS goals_against
        FROM matches
        WHERE source = 'sample'
    ) AS h
    GROUP BY h.team_id
)
SELECT
    t.name,
    ts.goals_for,
    ts.goals_against,
    ts.goals_for - ts.goals_against AS goal_difference
FROM team_stats AS ts
JOIN teams AS t ON t.id = ts.team_id
ORDER BY goal_difference DESC, t.name;

-- 6) Vitórias, empates e derrotas por equipa.
WITH team_results AS (
    SELECT
        home_team_id AS team_id,
        CASE
            WHEN home_goals > away_goals THEN 1
            WHEN home_goals = away_goals THEN 0
            ELSE 0
        END AS wins,
        CASE
            WHEN home_goals = away_goals THEN 1
            ELSE 0
        END AS draws,
        CASE
            WHEN home_goals < away_goals THEN 1
            ELSE 0
        END AS losses,
        CASE
            WHEN home_goals > away_goals THEN 3
            WHEN home_goals = away_goals THEN 1
            ELSE 0
        END AS points,
        home_goals - away_goals AS goal_difference
    FROM matches
    WHERE source = 'sample'
    UNION ALL
    SELECT
        away_team_id AS team_id,
        CASE
            WHEN away_goals > home_goals THEN 1
            WHEN away_goals = home_goals THEN 0
            ELSE 0
        END AS wins,
        CASE
            WHEN away_goals = home_goals THEN 1
            ELSE 0
        END AS draws,
        CASE
            WHEN away_goals < home_goals THEN 1
            ELSE 0
        END AS losses,
        CASE
            WHEN away_goals > home_goals THEN 3
            WHEN away_goals = home_goals THEN 1
            ELSE 0
        END AS points,
        away_goals - home_goals AS goal_difference
    FROM matches
    WHERE source = 'sample'
)
SELECT
    t.name,
    SUM(tr.wins) AS wins,
    SUM(tr.draws) AS draws,
    SUM(tr.losses) AS losses,
    SUM(tr.points) AS points,
    SUM(tr.goal_difference) AS goal_difference
FROM team_results AS tr
JOIN teams AS t ON t.id = tr.team_id
GROUP BY t.name
ORDER BY points DESC, goal_difference DESC, t.name;

-- 7) Como calcular diferença de golos.
-- A diferença de golos é a diferença entre golos marcados e golos sofridos.
-- Em SQL, pode ser calculada como:
--     goals_for - goals_against
-- e é útil para desempate em classificações.

-- 8) Classificação demonstrativa baseada nos cinco jogos sample.
-- Isto não é uma tabela oficial de campeonato; é apenas uma projeção pedagógica
-- para mostrar como a lógica de classificação pode ser obtida em SQL.
WITH team_results AS (
    SELECT
        home_team_id AS team_id,
        home_goals AS goals_for,
        away_goals AS goals_against,
        CASE
            WHEN home_goals > away_goals THEN 3
            WHEN home_goals = away_goals THEN 1
            ELSE 0
        END AS points,
        home_goals - away_goals AS goal_difference,
        CASE
            WHEN home_goals > away_goals THEN 1
            WHEN home_goals = away_goals THEN 0
            ELSE 0
        END AS wins,
        CASE
            WHEN home_goals = away_goals THEN 1
            ELSE 0
        END AS draws,
        CASE
            WHEN home_goals < away_goals THEN 1
            ELSE 0
        END AS losses
    FROM matches
    WHERE source = 'sample'
    UNION ALL
    SELECT
        away_team_id AS team_id,
        away_goals AS goals_for,
        home_goals AS goals_against,
        CASE
            WHEN away_goals > home_goals THEN 3
            WHEN away_goals = home_goals THEN 1
            ELSE 0
        END AS points,
        away_goals - home_goals AS goal_difference,
        CASE
            WHEN away_goals > home_goals THEN 1
            WHEN away_goals = home_goals THEN 0
            ELSE 0
        END AS wins,
        CASE
            WHEN away_goals = home_goals THEN 1
            ELSE 0
        END AS draws,
        CASE
            WHEN away_goals < home_goals THEN 1
            ELSE 0
        END AS losses
    FROM matches
    WHERE source = 'sample'
),
summary AS (
    SELECT
        team_id,
        SUM(goals_for) AS goals_for,
        SUM(goals_against) AS goals_against,
        SUM(points) AS points,
        SUM(goal_difference) AS goal_difference,
        SUM(wins) AS wins,
        SUM(draws) AS draws,
        SUM(losses) AS losses
    FROM team_results
    GROUP BY team_id
)
SELECT
    t.name,
    s.goals_for,
    s.goals_against,
    s.goal_difference,
    s.wins,
    s.draws,
    s.losses,
    s.points
FROM summary AS s
JOIN teams AS t ON t.id = s.team_id
ORDER BY s.points DESC, s.goal_difference DESC, t.name;
