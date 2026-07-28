import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from app.transformations.fpf_match_parser import (
    extract_match_id,
    parse_match_details,
)


HTML_PATH = (
    Path(__file__).resolve().parents[1]
    / "data/raw/matches/2484514.html"
)


class FPFMatchParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        html = HTML_PATH.read_text(encoding="utf-8")
        cls.match = parse_match_details(
            html,
            fixture_id=626607,
            serie_id=93565,
            round_name="3",
        )

    def test_match_identity_and_context(self) -> None:
        self.assertEqual(self.match["match_id"], 2484514)
        self.assertEqual(self.match["fixture_id"], 626607)
        self.assertEqual(self.match["serie_id"], 93565)
        self.assertEqual(self.match["round"], "3")
        self.assertEqual(
            self.match["competition"]["competition_id"],
            28712,
        )
        self.assertEqual(
            self.match["competition"]["season_id"],
            105,
        )

    def test_extracts_match_id_from_input(self) -> None:
        soup = BeautifulSoup(
            '<input id="Request_MatchId" value="2484514">',
            "html.parser",
        )
        self.assertEqual(extract_match_id(soup), 2484514)

    def test_extracts_match_id_from_open_graph_url(self) -> None:
        soup = BeautifulSoup(
            '<meta property="og:url" content="'
            "https://resultados.fpf.pt/Match/"
            'GetMatchInformation?matchId=2453110">',
            "html.parser",
        )
        self.assertEqual(extract_match_id(soup), 2453110)

    def test_extracts_match_id_from_structured_attribute(self) -> None:
        soup = BeautifulSoup(
            '<a href="/Match/GetMatchInformation?matchId=2453111">'
            "Jogo</a>",
            "html.parser",
        )
        self.assertEqual(extract_match_id(soup), 2453111)

    def test_rejects_inconsistent_match_ids(self) -> None:
        soup = BeautifulSoup(
            '<input id="Request_MatchId" value="2453110">'
            '<meta property="og:url" content="'
            "https://resultados.fpf.pt/Match/"
            'GetMatchInformation?matchId=2453111">',
            "html.parser",
        )
        with self.assertRaisesRegex(
            ValueError,
            "match_id inconsistentes",
        ):
            extract_match_id(soup)

    def test_returns_none_without_match_id(self) -> None:
        soup = BeautifulSoup(
            "<html><body>Sem identificador</body></html>",
            "html.parser",
        )
        self.assertIsNone(extract_match_id(soup))

    def test_result(self) -> None:
        self.assertEqual(self.match["teams"]["home"]["score"], 2)
        self.assertEqual(self.match["teams"]["away"]["score"], 3)

    def test_starting_lineups(self) -> None:
        self.assertEqual(
            len(self.match["lineups"]["home"]["starters"]),
            11,
        )
        self.assertEqual(
            len(self.match["lineups"]["away"]["starters"]),
            11,
        )

    def test_events(self) -> None:
        events = self.match["events"]
        self.assertEqual(
            sum(event["type"] == "goal" for event in events),
            5,
        )
        self.assertEqual(
            sum(event["type"] == "yellow_card" for event in events),
            3,
        )
        self.assertEqual(
            sum(event["type"] == "red_card" for event in events),
            0,
        )
        self.assertEqual(
            sum(event["type"] == "substitution" for event in events),
            10,
        )

        penalty = next(
            event
            for event in events
            if event["type"] == "goal"
            and event.get("detail") == "penalty"
        )
        self.assertEqual(penalty["player_name"], "Goncalo Martins")
        self.assertEqual(penalty["phase"], "second_half")
        self.assertEqual(penalty["source_section"], "2ª parte")
        self.assertEqual(penalty["display_minute"], "45'")

        project_root = Path(__file__).resolve().parents[1]
        penalties_match = parse_match_details(
            (
                project_root
                / "data/raw/matches/2453130.html"
            ).read_text(encoding="utf-8")
        )
        supplemental_penalty = next(
            event
            for event in penalties_match["events"]
            if event.get("source_section") == "Penaltis"
        )
        self.assertEqual(supplemental_penalty["type"], "goal")
        self.assertEqual(supplemental_penalty["detail"], "penalty")
        self.assertIsNone(supplemental_penalty["minute"])
        self.assertIsNone(supplemental_penalty["display_minute"])
        self.assertEqual(
            supplemental_penalty["player_name"],
            "Francisco Silva",
        )

        half_time_match = parse_match_details(
            (
                project_root
                / "data/raw/matches/2453137.html"
            ).read_text(encoding="utf-8")
        )
        half_time_card = next(
            event
            for event in half_time_match["events"]
            if event["type"] == "yellow_card"
            and event["player_name"] == "Jorge Santos"
        )
        self.assertEqual(half_time_card["phase"], "half_time")
        self.assertEqual(half_time_card["minute"], 0)
        self.assertEqual(half_time_card["display_minute"], "0'")
        self.assertEqual(
            half_time_card["source_section"],
            "1º intervalo",
        )

        post_match = parse_match_details(
            (
                project_root
                / "data/raw/matches/2453134.html"
            ).read_text(encoding="utf-8")
        )
        post_match_cards = [
            event
            for event in post_match["events"]
            if event["type"] == "red_card"
            and event["phase"] == "post_match"
        ]
        self.assertEqual(len(post_match_cards), 2)
        self.assertTrue(
            all(
                event["source_section"] == "Depois do Jogo"
                and event["display_minute"] == "0'"
                for event in post_match_cards
            )
        )

    def test_referee(self) -> None:
        referee = next(
            official
            for official in self.match["officials"]
            if official["role"] == "referee"
        )
        self.assertEqual(referee["name"], "Dinis Vieira")

    def test_normalised_schedule(self) -> None:
        self.assertEqual(
            self.match["scheduled_at"]["date"],
            "2026-04-26",
        )
        self.assertEqual(
            self.match["scheduled_at"]["time"],
            "10:00",
        )


if __name__ == "__main__":
    unittest.main()
