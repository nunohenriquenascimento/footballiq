import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.collectors.fpf_match_details import (
    MATCHES_PATH,
    _atomic_write_json,
    collect_match_details,
    load_source_matches,
)


SAMPLE_MATCH = {
    "fixture_id": 617695,
    "serie_id": 91321,
    "round": "1",
    "match_id": 2453109,
    "home_team": "Gd Trancoso",
    "away_team": "Gd Vila Nova Foz Coa",
    "match_date": "29 out",
    "match_time": None,
    "venue": "Estadio Municipal Dr Fernando Lopes",
    "home_score": 8,
    "away_score": 0,
    "status": None,
}


class FPFMatchDetailsTests(unittest.TestCase):
    def test_reads_real_source_json(self) -> None:
        matches = load_source_matches(MATCHES_PATH)
        self.assertEqual(len(matches), 92)
        self.assertEqual(matches[0]["match_id"], 2453109)
        self.assertEqual(matches[0]["fixture_id"], 617695)
        self.assertEqual(matches[0]["serie_id"], 91321)
        self.assertEqual(matches[0]["round"], "1")

    def test_source_is_deduplicated_by_match_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "matches.json"
            source_path.write_text(
                json.dumps([SAMPLE_MATCH, SAMPLE_MATCH]),
                encoding="utf-8",
            )
            matches = load_source_matches(source_path)
        self.assertEqual(len(matches), 1)

    def test_cache_and_parser_context_in_offline_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "matches.json"
            output_path = root / "details.json"
            cache_dir = root / "cache"
            cache_dir.mkdir()
            source_path.write_text(
                json.dumps([SAMPLE_MATCH]),
                encoding="utf-8",
            )
            (cache_dir / "2453109.html").write_text(
                "<html><body>cached</body></html>",
                encoding="utf-8",
            )
            parsed = {"match_id": 2453109, "events": []}
            stats: dict[str, int] = {}

            with (
                patch(
                    "app.collectors.fpf_match_details."
                    "parse_match_details",
                    return_value=parsed,
                ) as parser,
                patch(
                    "app.collectors.fpf_match_details."
                    "fetch_match_html"
                ) as fetch,
            ):
                result = collect_match_details(
                    source_path,
                    output_path,
                    cache_dir,
                    offline=True,
                    stats=stats,
                )

            fetch.assert_not_called()
            parser.assert_called_once_with(
                "<html><body>cached</body></html>",
                fixture_id=617695,
                serie_id=91321,
                round_name="1",
            )
            self.assertEqual(result, [parsed])
            self.assertEqual(stats["cached_matches"], 1)
            self.assertEqual(stats["successful_matches"], 1)

    def test_offline_missing_html_does_not_request_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "matches.json"
            output_path = root / "details.json"
            source_path.write_text(
                json.dumps([SAMPLE_MATCH]),
                encoding="utf-8",
            )
            stats: dict[str, int] = {}

            with patch(
                "app.collectors.fpf_match_details.fetch_match_html"
            ) as fetch:
                result = collect_match_details(
                    source_path,
                    output_path,
                    root / "cache",
                    offline=True,
                    stats=stats,
                )

            fetch.assert_not_called()
            self.assertEqual(result, [])
            self.assertEqual(stats["offline_missing_html"], 1)
            self.assertEqual(stats["failed_matches"], 1)
            self.assertFalse(output_path.exists())

    def test_existing_match_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "matches.json"
            output_path = root / "details.json"
            detail = {"match_id": 2453109}
            source_path.write_text(
                json.dumps([SAMPLE_MATCH]),
                encoding="utf-8",
            )
            output_path.write_text(
                json.dumps([detail]),
                encoding="utf-8",
            )
            stats: dict[str, int] = {}

            result = collect_match_details(
                source_path,
                output_path,
                root / "cache",
                offline=True,
                stats=stats,
            )

            self.assertEqual(result, [detail])
            self.assertEqual(stats["skipped_matches"], 1)
            self.assertEqual(stats["successful_matches"], 0)

    def test_parser_match_id_must_match_requested_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "matches.json"
            output_path = root / "details.json"
            cache_dir = root / "cache"
            cache_dir.mkdir()
            source_path.write_text(
                json.dumps([SAMPLE_MATCH]),
                encoding="utf-8",
            )
            (cache_dir / "2453109.html").write_text(
                "<html><body>cached</body></html>",
                encoding="utf-8",
            )
            stats: dict[str, int] = {}

            with patch(
                "app.collectors.fpf_match_details."
                "parse_match_details",
                return_value={"match_id": 9999999},
            ):
                result = collect_match_details(
                    source_path,
                    output_path,
                    cache_dir,
                    offline=True,
                    stats=stats,
                )

            self.assertEqual(result, [])
            self.assertEqual(stats["failed_matches"], 1)
            self.assertEqual(stats["successful_matches"], 0)
            self.assertFalse(output_path.exists())

    def test_atomic_write_uses_os_replace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "details.json"
            real_replace = os.replace
            with patch(
                "app.collectors.fpf_match_details.os.replace",
                wraps=real_replace,
            ) as replace:
                _atomic_write_json(path, [{"match_id": 1}])

            replace.assert_called_once()
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                [{"match_id": 1}],
            )
            self.assertEqual(list(path.parent.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
