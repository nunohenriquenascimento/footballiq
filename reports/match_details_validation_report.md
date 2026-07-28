# Relatório de validação dos detalhes dos jogos

## Estatísticas gerais

| Métrica | Valor |
|---|---:|
| Jogos esperados | 92 |
| Jogos encontrados | 92 |
| `match_id` únicos | 92 |
| Erros técnicos | 0 |
| `parser_error` | 0 |
| `structural_error` | 0 |
| `source_inconsistency` | 9 |
| `data_quality_warning` | 0 |
| Jogos problemáticos | 9 |

## Completude dos campos

| Campo | Preenchidos | Total | Completude |
|---|---:|---:|---:|
| `match_id` | 92 | 92 | 100.00% |
| `fixture_id` | 92 | 92 | 100.00% |
| `serie_id` | 92 | 92 | 100.00% |
| `round` | 92 | 92 | 100.00% |
| `competition.competition_id` | 92 | 92 | 100.00% |
| `competition.season_id` | 92 | 92 | 100.00% |
| `competition.name` | 92 | 92 | 100.00% |
| `scheduled_at.date` | 92 | 92 | 100.00% |
| `scheduled_at.time` | 92 | 92 | 100.00% |
| `venue.name` | 92 | 92 | 100.00% |
| `teams.home.name` | 92 | 92 | 100.00% |
| `teams.home.score` | 92 | 92 | 100.00% |
| `teams.away.name` | 92 | 92 | 100.00% |
| `teams.away.score` | 92 | 92 | 100.00% |
| `lineups.home.starters` | 92 | 92 | 100.00% |
| `lineups.home.substitutes` | 92 | 92 | 100.00% |
| `lineups.home.staff` | 92 | 92 | 100.00% |
| `lineups.away.starters` | 92 | 92 | 100.00% |
| `lineups.away.substitutes` | 92 | 92 | 100.00% |
| `lineups.away.staff` | 92 | 92 | 100.00% |
| `officials` | 92 | 92 | 100.00% |
| `events` | 92 | 92 | 100.00% |
| `periods` | 92 | 92 | 100.00% |
| `source.url` | 92 | 92 | 100.00% |

## Erros do parser

Nenhum.

## Erros estruturais

Nenhum.

## Inconsistências da fonte FPF

| Jogo | Validação | Problema | Evidência | Valor FPF |
|---:|---|---|---|---|
| 2453114 | substitution | Jogador de saída não existe no plantel de away: 'Gonçalo Nobre'. | O jogador está publicado no plantel de home, mas a substituição está associada a away. | Preservado |
| 2453126 | substitution | Jogador de saída não existe no plantel de away: 'Dinis Pereira'. | O jogador está publicado no plantel de home, mas a substituição está associada a away. | Preservado |
| 2453131 | substitution | Jogador de saída não existe no plantel de away: 'Gabriel Fernandes'. | O jogador está publicado no plantel de home, mas a substituição está associada a away. | Preservado |
| 2453142 | score | O resultado publicado não coincide com a contagem de todos os eventos de golo. | Resultado FPF: 0-2; resultado reconstruído pelos eventos: 2-0; eventos de golo publicados: 2. | Preservado |
| 2484519 | substitution | Jogador de saída não existe no plantel de away: 'Vicente Dias'. | O jogador está publicado no plantel de home, mas a substituição está associada a away. | Preservado |
| 2484523 | lineup | away tem 12 titulares; ideal: 11. | A secção Equipas Iniciais da FPF contém 12 jogadores para away. | Preservado |
| 2484524 | score | O resultado publicado não coincide com a contagem de todos os eventos de golo. | Resultado FPF: 0-1; resultado reconstruído pelos eventos: 0-0; eventos de golo publicados: 0. | Preservado |
| 2484527 | substitution | Jogador de saída não existe no plantel de away: 'Rodrigo Dias'. | O jogador está publicado no plantel de home, mas a substituição está associada a away. | Preservado |
| 2484535 | substitution | Jogador de saída não existe no plantel de away: 'Lucas Mendes'. | O jogador está publicado no plantel de home, mas a substituição está associada a away. | Preservado |

## Avisos de qualidade dos dados

Nenhum.

Os valores publicados pela FPF são preservados nas inconsistências da fonte; o validador apenas as assinala.

## Jogos problemáticos

- `2453114`
- `2453126`
- `2453131`
- `2453142`
- `2484519`
- `2484523`
- `2484524`
- `2484527`
- `2484535`
