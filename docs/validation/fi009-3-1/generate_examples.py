"""Regenera exemplos apenas a partir de dados fictícios, sem rede ou Ollama."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from footballiq.analytics import analyze_recent_matches
from footballiq.grounded_narrative.insights import (
    build_insights,
    prepare_insight_plans,
    render_insight,
)


def main() -> None:
    """Guarda texto, planos e evidências das variantes sintéticas documentadas."""
    root = Path(__file__).resolve().parents[3]
    fixture = root / "tests/fixtures/integration/complete_five.json"
    complete = json.loads(fixture.read_text(encoding="utf-8"))
    partial = deepcopy(complete)
    partial["matches"][2]["score"]["status"] = "unverified"
    four = deepcopy(complete)
    four["matches"] = four["matches"][:4]
    four["selection"]["returned_count"] = 4
    distinct = deepcopy(complete)
    distinct["matches"][0]["kickoff_at"] = "2026-11-08T16:00:00Z"
    empty = json.loads((fixture.parent / "empty.json").read_text(encoding="utf-8"))
    output = {}
    for name, payload in (
        ("complete_five", complete),
        ("partial_score", partial),
        ("four_with_event_ids", four),
        ("distinct_dates", distinct),
        ("empty", empty),
    ):
        bundle = build_insights(analyze_recent_matches(payload))
        output[name] = {
            "snapshot": bundle.snapshot_id,
            "digest": bundle.evidence_digest,
            "observations": {
                identity: {
                    "text": render_insight(plan, bundle),
                    "plan": plan.model_dump(mode="json"),
                }
                for identity, plan in prepare_insight_plans(bundle).items()
            },
        }
    destination = Path(__file__).with_name("examples.json")
    destination.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Generated {sum(len(case['observations']) for case in output.values())} observations across {len(output)} synthetic scenarios."
    )


if __name__ == "__main__":
    main()
