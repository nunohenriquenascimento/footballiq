import argparse
import json
import math
import os
import random
import tempfile
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
from requests import Response, Session

from app.transformations.fpf_match_parser import parse_match_details


MATCHES_PATH = Path(
    "data/processed/matches_sub16_fdm_2025_2026.json"
)
OUTPUT_PATH = Path(
    "data/processed/match_details_sub16_fdm_2025_2026.json"
)
CACHE_DIR = Path("data/raw/matches")
FPF_MATCH_URL = (
    "https://resultados.fpf.pt/Match/GetMatchInformation"
)
FPF_REFERER = (
    "https://resultados.fpf.pt/Competition/Details"
    "?competitionId=28712&seasonId=105"
)
REQUEST_TIMEOUT_SECONDS = 30
REQUEST_DELAY_SECONDS = 5.0
REQUEST_JITTER_SECONDS = 1.0
MAX_RETRIES = 3


class RateLimitError(RuntimeError):
    """Raised when the FPF blocks further collection with HTTP 429."""


def _browser_headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/149.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
        "Referer": FPF_REFERER,
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }


def _initial_navigation_headers() -> dict[str, str]:
    browser_headers = _browser_headers()
    return {
        "User-Agent": browser_headers["User-Agent"],
        "Accept-Language": browser_headers["Accept-Language"],
    }


def _read_json_list(path: Path, description: str) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"{description} não existe: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"{description} está vazio: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{description} contém JSON inválido: {path}"
        ) from exc

    if not isinstance(data, list):
        raise ValueError(f"{description} deve conter uma lista: {path}")
    return data


def load_source_matches(path: Path = MATCHES_PATH) -> list[dict]:
    records = _read_json_list(path, "O ficheiro de jogos")
    matches_by_id: dict[int, dict] = {}

    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Foi encontrado um jogo inválido na origem.")

        match_id = record.get("match_id")
        fixture_id = record.get("fixture_id")
        serie_id = record.get("serie_id")
        round_name = record.get("round")
        if not isinstance(match_id, int) or match_id <= 0:
            raise ValueError(f"match_id inválido: {match_id!r}")
        if not isinstance(fixture_id, int) or fixture_id <= 0:
            raise ValueError(
                f"fixture_id inválido no jogo {match_id}: "
                f"{fixture_id!r}"
            )
        if not isinstance(serie_id, int) or serie_id <= 0:
            raise ValueError(
                f"serie_id inválido no jogo {match_id}: {serie_id!r}"
            )
        if not isinstance(round_name, str) or not round_name.strip():
            raise ValueError(
                f"round inválido no jogo {match_id}: {round_name!r}"
            )

        matches_by_id.setdefault(match_id, record)

    return list(matches_by_id.values())


def load_existing_details(path: Path = OUTPUT_PATH) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []

    details = _read_json_list(path, "O ficheiro de detalhes")
    details_by_id: dict[int, dict] = {}
    for detail in details:
        if not isinstance(detail, dict):
            raise ValueError(
                "Foi encontrado um detalhe inválido no JSON final."
            )
        match_id = detail.get("match_id")
        if not isinstance(match_id, int) or match_id <= 0:
            raise ValueError(
                f"match_id inválido no JSON final: {match_id!r}"
            )
        details_by_id.setdefault(match_id, detail)
    return list(details_by_id.values())


def _atomic_write_json(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            json.dump(
                records,
                temporary_file,
                ensure_ascii=False,
                indent=2,
            )
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_path = Path(temporary_file.name)

        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def match_cache_path(
    match_id: int,
    cache_dir: Path = CACHE_DIR,
) -> Path:
    return cache_dir / f"{match_id}.html"


def load_cached_html(
    match_id: int,
    cache_dir: Path = CACHE_DIR,
) -> str | None:
    path = match_cache_path(match_id, cache_dir)
    if not path.exists() or path.stat().st_size == 0:
        return None
    html = path.read_text(encoding="utf-8").strip()
    return html or None


def save_cached_html(
    match_id: int,
    html: str,
    cache_dir: Path = CACHE_DIR,
) -> None:
    if not html or not html.strip():
        raise ValueError(
            f"Não é possível guardar HTML vazio do jogo {match_id}."
        )

    path = match_cache_path(match_id, cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(html.strip() + "\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_path = Path(temporary_file.name)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _retry_after_seconds(response: Response) -> float | None:
    retry_after = response.headers.get("Retry-After")
    if retry_after is None:
        return None

    try:
        delay = float(retry_after)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(retry_after)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        delay = (
            retry_at - datetime.now(timezone.utc)
        ).total_seconds()

    if math.isfinite(delay) and delay > 0:
        return delay
    return None


def _get_with_rate_limit(
    session: Session,
    url: str,
    *,
    params: dict | None = None,
    headers: dict[str, str] | None = None,
    is_first_request: bool = False,
) -> Response:
    for attempt in range(MAX_RETRIES + 1):
        response = session.get(
            url,
            params=params,
            headers=headers or _browser_headers(),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code != 429:
            response.raise_for_status()
            return response

        retry_delay = _retry_after_seconds(response)
        if is_first_request and attempt == 0 and retry_delay is None:
            raise RateLimitError(
                "O primeiro pedido recebeu HTTP 429 sem um "
                "Retry-After útil; a execução foi interrompida."
            )
        if attempt == MAX_RETRIES:
            raise RateLimitError(
                f"A FPF continuou a devolver HTTP 429 após "
                f"{MAX_RETRIES} tentativas."
            )

        if retry_delay is None:
            retry_delay = float(2**attempt)
        print(
            "HTTP 429; nova tentativa dentro de "
            f"{retry_delay:.1f} segundos."
        )
        time.sleep(retry_delay)

    raise RateLimitError("Limite de tentativas excedido.")


def prime_session(session: Session) -> None:
    try:
        _get_with_rate_limit(
            session,
            FPF_REFERER,
            headers=_initial_navigation_headers(),
            is_first_request=True,
        )
    except RateLimitError:
        raise
    except requests.Timeout as exc:
        raise RuntimeError(
            "O pedido inicial à FPF excedeu "
            f"{REQUEST_TIMEOUT_SECONDS} segundos."
        ) from exc
    except requests.HTTPError as exc:
        status_code = (
            exc.response.status_code if exc.response is not None else "?"
        )
        raise RuntimeError(
            f"O pedido inicial à FPF devolveu erro HTTP "
            f"({status_code})."
        ) from exc
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Não foi possível iniciar a sessão com a FPF: {exc}"
        ) from exc


def fetch_match_html(
    match_id: int,
    session: Session,
    *,
    is_first_match_request: bool = False,
) -> str:
    if not isinstance(match_id, int) or match_id <= 0:
        raise ValueError(f"match_id inválido: {match_id!r}")

    try:
        response = _get_with_rate_limit(
            session,
            FPF_MATCH_URL,
            params={"matchId": match_id},
            is_first_request=is_first_match_request,
        )
    except RateLimitError:
        raise
    except requests.Timeout as exc:
        raise RuntimeError(
            f"O pedido do jogo {match_id} excedeu "
            f"{REQUEST_TIMEOUT_SECONDS} segundos."
        ) from exc
    except requests.HTTPError as exc:
        status_code = (
            exc.response.status_code if exc.response is not None else "?"
        )
        raise RuntimeError(
            f"O jogo {match_id} devolveu erro HTTP ({status_code})."
        ) from exc
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Não foi possível obter o jogo {match_id}: {exc}"
        ) from exc

    content_type = response.headers.get("Content-Type", "").lower()
    if "html" not in content_type:
        raise ValueError(
            f"O jogo {match_id} não devolveu HTML "
            f"(Content-Type: {content_type or 'em falta'})."
        )
    html = response.text.strip()
    if not html:
        raise ValueError(f"O jogo {match_id} devolveu HTML vazio.")
    return html


def _new_stats() -> dict[str, int]:
    return {
        "cached_matches": 0,
        "downloaded_matches": 0,
        "skipped_matches": 0,
        "successful_matches": 0,
        "failed_matches": 0,
        "offline_missing_html": 0,
        "rate_limited": 0,
    }


def collect_match_details(
    source_path: Path = MATCHES_PATH,
    output_path: Path = OUTPUT_PATH,
    cache_dir: Path = CACHE_DIR,
    *,
    offline: bool = False,
    limit: int | None = None,
    stats: dict[str, int] | None = None,
) -> list[dict]:
    source_matches = load_source_matches(source_path)
    if limit is not None:
        if limit <= 0:
            raise ValueError("O limite deve ser superior a zero.")
        source_matches = source_matches[:limit]

    run_stats = stats if stats is not None else {}
    run_stats.update(_new_stats())

    existing_details = load_existing_details(output_path)
    details_by_id = {
        detail["match_id"]: detail for detail in existing_details
    }
    session_primed = False
    downloaded_requests = 0

    with requests.Session() as session:
        for source_match in source_matches:
            match_id = source_match["match_id"]
            if match_id in details_by_id:
                run_stats["skipped_matches"] += 1
                continue

            html = load_cached_html(match_id, cache_dir)
            if html is not None:
                run_stats["cached_matches"] += 1
            elif offline:
                run_stats["offline_missing_html"] += 1
                run_stats["failed_matches"] += 1
                print(
                    f"HTML em falta no modo offline: "
                    f"{match_cache_path(match_id, cache_dir)}"
                )
                continue
            else:
                try:
                    if not session_primed:
                        prime_session(session)
                        session_primed = True
                        time.sleep(
                            REQUEST_DELAY_SECONDS
                            + random.uniform(
                                0,
                                REQUEST_JITTER_SECONDS,
                            )
                        )
                    elif downloaded_requests:
                        time.sleep(
                            REQUEST_DELAY_SECONDS
                            + random.uniform(
                                0,
                                REQUEST_JITTER_SECONDS,
                            )
                        )

                    html = fetch_match_html(
                        match_id,
                        session,
                        is_first_match_request=(
                            downloaded_requests == 0
                        ),
                    )
                    downloaded_requests += 1
                    save_cached_html(match_id, html, cache_dir)
                    run_stats["downloaded_matches"] += 1
                except RateLimitError as exc:
                    run_stats["failed_matches"] += 1
                    run_stats["rate_limited"] = 1
                    print(exc)
                    print(
                        "Recolha interrompida para preservar o "
                        "progresso e evitar novos pedidos."
                    )
                    break
                except (RuntimeError, ValueError) as exc:
                    run_stats["failed_matches"] += 1
                    downloaded_requests += 1
                    print(f"Falha no jogo {match_id}: {exc}")
                    continue

            try:
                detail = parse_match_details(
                    html,
                    fixture_id=source_match["fixture_id"],
                    serie_id=source_match["serie_id"],
                    round_name=source_match["round"],
                )
                if (
                    not isinstance(detail, dict)
                    or detail.get("match_id") != match_id
                ):
                    raise ValueError(
                        "O parser não devolveu o match_id esperado."
                    )
            except Exception as exc:
                run_stats["failed_matches"] += 1
                print(
                    f"Falha no parser do jogo {match_id}: "
                    f"{type(exc).__name__}: {exc}"
                )
                continue

            details_by_id[match_id] = detail
            ordered_details = sorted(
                details_by_id.values(),
                key=lambda record: record["match_id"],
            )
            _atomic_write_json(output_path, ordered_details)
            run_stats["successful_matches"] += 1

    return sorted(
        details_by_id.values(),
        key=lambda record: record["match_id"],
    )


def _positive_limit(value: str) -> int:
    try:
        limit = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "O limite deve ser um número inteiro."
        ) from exc
    if limit <= 0:
        raise argparse.ArgumentTypeError(
            "O limite deve ser superior a zero."
        )
    return limit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recolhe e normaliza detalhes de jogos da FPF."
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Processa exclusivamente HTML existente na cache.",
    )
    parser.add_argument(
        "--limit",
        type=_positive_limit,
        help="Limita o número de jogos considerados.",
    )
    return parser.parse_args()


def print_summary(stats: dict[str, int]) -> None:
    print("\nResumo:")
    print(f"Jogos lidos da cache: {stats['cached_matches']}")
    print(f"Jogos descarregados: {stats['downloaded_matches']}")
    print(
        "Jogos ignorados por já existirem: "
        f"{stats['skipped_matches']}"
    )
    print(
        "Jogos processados com sucesso: "
        f"{stats['successful_matches']}"
    )
    print(f"Jogos falhados: {stats['failed_matches']}")
    print(
        "HTML em falta no modo offline: "
        f"{stats['offline_missing_html']}"
    )
    print(f"JSON final: {OUTPUT_PATH}")


def main() -> int:
    try:
        args = parse_args()
        stats: dict[str, int] = {}
        collect_match_details(
            offline=args.offline,
            limit=args.limit,
            stats=stats,
        )
        print_summary(stats)
        return 1 if stats["rate_limited"] else 0
    except KeyboardInterrupt:
        print(
            "\nExecução interrompida pelo utilizador. "
            "O progresso já guardado foi preservado."
        )
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
