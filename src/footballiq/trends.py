"""Tendências descritivas puras sobre resultados já tratados pelo motor factual."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC
from statistics import pvariance
from typing import Any

from footballiq.analytics import FactualReport, MatchFacts

FORMULA_VERSION = "footballiq.trends.v1"

TREND_LABELS = {
    "wins": "Vitórias",
    "draws": "Empates",
    "losses": "Derrotas",
    "clean_sheets": "Jogos sem sofrer golos",
    "failed_to_score": "Jogos sem marcar",
    "average_goals_for": "Média GF",
    "average_goals_against": "Média GA",
    "goal_difference_range": "Amplitude da diferença de golos",
    "goal_difference_population_variance": "Variância populacional da diferença de golos",
    "equal_adjacent_outcomes": "Pares adjacentes com resultado igual",
    "adjacent_pairs": "Pares adjacentes verificados",
}

UNAVAILABLE_REASONS = {
    "no_games": "Não há jogos nesta amostra.",
    "unverified_results": "Existem resultados não verificados; total indisponível.",
    "insufficient_sample_min_2": "Exige pelo menos dois resultados verificados.",
    "no_verified_adjacent_pairs": "Não há pares adjacentes com ambos os resultados verificados.",
    "insufficient_sample_min_4": "Exige pelo menos quatro jogos, todos com resultado verificado.",
    "tied_temporal_boundary": "Os jogos na fronteira dos grupos têm a mesma data e hora.",
    "insufficient_sample_min_2_per_venue": "Exige pelo menos dois jogos verificados em casa e dois fora.",
}


@dataclass(frozen=True)
class TrendGame:
    """Conserva ordem, perspetiva e evidência; desconhecido permanece null."""

    match_id: str
    data_version: str
    kickoff_at: str
    is_home: bool
    outcome: str | None
    goals_for: int | None
    goals_against: int | None
    goal_difference: int | None
    reason: str | None


@dataclass(frozen=True)
class TrendSample:
    """Distingue a janela total do subtotal dos resultados verificados."""

    selected_ids: tuple[str, ...]
    used_ids: tuple[str, ...]
    values: dict[str, int | float] | None
    covered_values: dict[str, int | float] | None
    reason: str | None
    variability_reason: str | None
    stability_reason: str | None


@dataclass(frozen=True)
class TrendReport:
    """Resultado separado do contrato v1, sem alterar o relatório de entrada."""

    snapshot_version: str
    source_system: str
    source_instance_id: str
    team_id: str
    season_id: str
    games: tuple[TrendGame, ...]
    window: TrendSample
    home: TrendSample
    away: TrendSample
    older: TrendSample
    newer: TrendSample
    temporal_change: dict[str, float] | None
    temporal_reason: str | None
    venue_reason: str | None
    formula_version: str = FORMULA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Produz dados estruturados com cobertura, IDs e versões auditáveis."""
        return asdict(self)


def _sample(games: tuple[TrendGame, ...]) -> TrendSample:
    used = tuple(g for g in games if g.reason is None)
    values: dict[str, int | float] | None = None
    if used:
        gf = [g.goals_for for g in used]
        ga = [g.goals_against for g in used]
        gd = [g.goal_difference for g in used]
        assert all(v is not None for v in (*gf, *ga, *gd))
        values = {
            "wins": sum(g.outcome == "win" for g in used),
            "draws": sum(g.outcome == "draw" for g in used),
            "losses": sum(g.outcome == "loss" for g in used),
            "clean_sheets": sum(v == 0 for v in ga),
            "failed_to_score": sum(v == 0 for v in gf),
            "average_goals_for": sum(gf) / len(used),
            "average_goals_against": sum(ga) / len(used),
        }
        if len(used) >= 2:
            values["goal_difference_range"] = max(gd) - min(gd)
            values["goal_difference_population_variance"] = pvariance(gd)
            pairs = [
                (a, b)
                for a, b in zip(games, games[1:], strict=False)
                if a.reason is None and b.reason is None
            ]
            if pairs:
                values["equal_adjacent_outcomes"] = sum(
                    a.outcome == b.outcome for a, b in pairs
                )
                values["adjacent_pairs"] = len(pairs)
    reason = (
        "no_games"
        if not games
        else "unverified_results"
        if len(used) != len(games)
        else None
    )
    return TrendSample(
        tuple(g.match_id for g in games),
        tuple(g.match_id for g in used),
        values if reason is None else None,
        values,
        reason,
        None if len(used) >= 2 else "insufficient_sample_min_2",
        None
        if values is not None and "adjacent_pairs" in values
        else "no_verified_adjacent_pairs",
    )


def calculate_trends(report: FactualReport) -> TrendReport:
    """Descreve exclusivamente a janela selecionada, sem rede nem inferências.

    Reutiliza golos/outcomes do Analytics Engine. A ordem ascendente inverte o
    desempate numérico do contrato. Uma fronteira temporal empatada não é dividida.
    """
    report = FactualReport.model_validate(report.model_dump())
    ordered = sorted(
        report.matches, key=lambda m: (m.kickoff_at, int(m.reference.source_match_id))
    )
    if len(ordered) > 5 or len({m.reference.source_match_id for m in ordered}) != len(
        ordered
    ):
        raise ValueError("A janela exige no máximo cinco jogos distintos.")
    games = tuple(_game(m) for m in ordered)
    window = _sample(games)
    home = _sample(tuple(g for g in games if g.is_home))
    away = _sample(tuple(g for g in games if not g.is_home))
    split = len(games) // 2
    older, newer = _sample(games[:split]), _sample(games[split:])
    reason = None
    if len(games) < 4:
        reason = "insufficient_sample_min_4"
    elif window.values is None:
        reason = "unverified_results"
    elif games[split - 1].kickoff_at == games[split].kickoff_at:
        reason = "tied_temporal_boundary"
    change = None
    if reason is None:
        assert older.values is not None and newer.values is not None
        change = {
            key: float(newer.values[key] - older.values[key])
            for key in ("average_goals_for", "average_goals_against")
        }
    venue_reason = None
    if min(len(home.used_ids), len(away.used_ids)) < 2:
        venue_reason = "insufficient_sample_min_2_per_venue"
    elif home.values is None or away.values is None:
        venue_reason = "unverified_results"
    return TrendReport(
        report.snapshot_version,
        report.source_system,
        report.source_instance_id,
        report.selection.team_id,
        report.selection.season_id,
        games,
        window,
        home,
        away,
        older,
        newer,
        change,
        reason,
        venue_reason,
    )


def _game(match: MatchFacts) -> TrendGame:
    valid = (
        match.score_status == "verified"
        and match.outcome is not None
        and match.goals_for is not None
        and match.goals_against is not None
    )
    return TrendGame(
        match.reference.source_match_id,
        match.reference.data_version,
        match.kickoff_at.astimezone(UTC).isoformat(),
        match.is_home,
        match.outcome if valid else None,
        match.goals_for if valid else None,
        match.goals_against if valid else None,
        match.goals_for - match.goals_against if valid else None,
        None if valid else "unverified_result",
    )


def trend_descriptions(
    trends: TrendReport,
) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """Cria frases locais: o LLM só poderá selecionar estes factos e evidências."""
    result = []
    for name, sample in (
        ("window", trends.window),
        ("home", trends.home),
        ("away", trends.away),
    ):
        if not sample.used_ids:
            continue
        values = sample.covered_values or {}
        title = {"window": "Janela", "home": "Casa", "away": "Fora"}[name]
        text = (
            f"{title}: jogos sem sofrer golos: {values['clean_sheets']}; "
            f"jogos sem marcar: {values['failed_to_score']}. "
            f"Cobertura {len(sample.used_ids)}/{len(sample.selected_ids)}; "
            f"total {'disponível' if sample.values is not None else 'indisponível; apenas subtotal'}. "
        )
        versions = "; ".join(
            f"{g.match_id}@{g.data_version}"
            for g in trends.games
            if g.match_id in sample.used_ids
        )
        text += f"Snapshot {trends.snapshot_version}; versões {versions}; fórmula {trends.formula_version}."
        text += (
            " Estatísticas descritivas da amostra coberta: "
            + "; ".join(
                f"{TREND_LABELS[key]}: {value}" for key, value in values.items()
            )
            + "."
        )
        result.append(
            (f"trend:{name}", text, tuple(f"match:{mid}" for mid in sample.used_ids))
        )
    if trends.games:
        result.append(
            (
                "trend:sequence",
                "Ordem mais antigo primeiro; GF/GA/diferença: "
                + "; ".join(
                    f"{g.match_id}@{g.data_version}: "
                    + (
                        f"{g.outcome}, {g.goals_for}/{g.goals_against}/{g.goal_difference}"
                        if g.reason is None
                        else "resultado indisponível"
                    )
                    for g in trends.games
                )
                + f". Cobertura {len(trends.window.used_ids)}/{len(trends.games)}; snapshot {trends.snapshot_version}; fórmula {trends.formula_version}.",
                tuple(f"match:{g.match_id}" for g in trends.games),
            )
        )
    if trends.temporal_change is not None:
        result.append(
            (
                "trend:temporal",
                "Diferença recente menos antigo nas médias de golos: "
                + "; ".join(
                    f"{TREND_LABELS[key]}: {value}"
                    for key, value in trends.temporal_change.items()
                )
                + f". Grupos antigos {trends.older.used_ids}, recentes {trends.newer.used_ids}; cobertura {len(trends.games)}/{len(trends.games)}. "
                f"Snapshot {trends.snapshot_version}; versões "
                + "; ".join(f"{g.match_id}@{g.data_version}" for g in trends.games)
                + f"; fórmula {trends.formula_version}.",
                tuple(f"match:{g.match_id}" for g in trends.games),
            )
        )
    return tuple(result)
