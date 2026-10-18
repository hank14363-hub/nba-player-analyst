"""Shared, dependency-free I/O, identity resolution, and data contracts."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_SCHEMA_VERSION = "0.1.0"
VERSION = DATA_SCHEMA_VERSION  # Backward-compatible schema alias; never a release number.
SKILL_ROOT = Path(__file__).resolve().parents[1]
RELEASE_VERSION = json.loads((SKILL_ROOT / "PACKAGE_INFO.json").read_text(encoding="utf-8"))["release_version"]
TABLES = {
    "player_base": ("P_BASE", "Totals"),
    "player_advanced": ("P_ADV", "Totals"),
    "player_per100": ("P_100", "Per100Possessions"),
    "player_scoring": ("P_SCORE", "Totals"),
    "team_base": ("T_BASE", "Totals"),
    "team_advanced": ("T_ADV", "Totals"),
    "tracking_catchshoot": ("TR_CATCH", "PerGame"),
    "tracking_pullup": ("TR_PULL", "PerGame"),
    "tracking_passing": ("TR_PASS", "PerGame"),
    "tracking_drives": ("TR_DRIVE", "PerGame"),
    "player_onoff": ("P_ONOFF", "Totals"),
    "player_shots": ("P_SHOT", "Events"),
}
SEASON_TYPES = ("Regular Season", "Playoffs")


class DataError(ValueError):
    """Input or provider data cannot support the requested computation."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise DataError(f"Cannot read JSON {path}: {exc}") from exc


def write_json(path: Path, data: Any) -> None:
    """Atomic replace; callers are responsible for output-directory ownership."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def digest(data: Any) -> str:
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def number(value: Any, field: str = "value", optional: bool = False) -> float | None:
    if value is None or (isinstance(value, str) and value.strip().lower() in {"", "null", "none", "na", "n/a"}):
        if optional:
            return None
        raise DataError(f"Missing numeric field: {field}")
    if isinstance(value, bool):
        raise DataError(f"Boolean is not numeric: {field}")
    try:
        n = float(value)
    except (ValueError, TypeError) as exc:
        raise DataError(f"Invalid numeric field {field}: {value!r}") from exc
    if not math.isfinite(n):
        raise DataError(f"Non-finite number in {field}")
    return n


def integer(value: Any, field: str) -> int:
    n = number(value, field)
    if n is None or n != int(n):
        raise DataError(f"Expected integer {field}, got {value!r}")
    return int(n)


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).casefold()
    return "".join(c for c in text if c.isalnum())


def validate_season(season: str, season_type: str) -> None:
    if not re.fullmatch(r"\d{4}-\d{2}", season):
        raise DataError("Use an explicit season such as 2024-25.")
    if (int(season[:4]) + 1) % 100 != int(season[5:]):
        raise DataError(f"Invalid consecutive-year season: {season}")
    if season_type not in SEASON_TYPES:
        raise DataError("v0.1 supports Regular Season or Playoffs only; do not mix them.")


def resolve_player(rows: list[dict], query: str | None, player_id: int | None) -> tuple[int, str]:
    candidates: dict[int, str] = {}
    for row in rows:
        pid = integer(row.get("PLAYER_ID"), "PLAYER_ID")
        if not row.get("PLAYER_NAME"):
            raise DataError("PLAYER_NAME is required in player_base.")
        candidates[pid] = str(row["PLAYER_NAME"])
    if not candidates:
        raise DataError("No players in the requested sample.")
    if player_id is not None:
        if player_id not in candidates:
            raise DataError(f"Player ID {player_id} is absent from the requested sample.")
        if query:
            resolved, _ = resolve_player(rows, query, None)
            if resolved != player_id:
                raise DataError("Player name and player ID disagree.")
        return player_id, candidates[player_id]
    if not query:
        raise DataError("Supply --player or --player-id.")
    aliases = read_json(SKILL_ROOT / "references" / "player_aliases.json")
    lookup = {normalize_name(k): v for k, v in aliases.items()}
    normalized = normalize_name(lookup.get(normalize_name(query), query))
    exact = [(pid, name) for pid, name in candidates.items() if normalize_name(name) == normalized]
    matches = exact or [(pid, name) for pid, name in candidates.items() if normalized in normalize_name(name)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise DataError(f"Ambiguous player; use --player-id. Candidates: {matches[:15]}")
    raise DataError(f"Unknown player {query!r}; use the full English name or NBA player ID. Chinese aliases are limited.")


def player_row(rows: list[dict], player_id: int, team_id: int = 0) -> dict:
    matches = [r for r in rows if integer(r.get("PLAYER_ID"), "PLAYER_ID") == player_id]
    if team_id:
        matches = [r for r in matches if integer(r.get("TEAM_ID"), "TEAM_ID") == team_id]
    if not matches:
        raise DataError("Player row is missing for the requested team/sample.")
    if len(matches) == 1:
        return matches[0]
    totals = [r for r in matches if integer(r.get("TEAM_ID", -1), "TEAM_ID") == 0
              or str(r.get("TEAM_ABBREVIATION", "")).upper() in {"TOT", "2TM", "3TM", "4TM", "5TM"}]
    if not team_id and len(totals) == 1:
        return totals[0]
    raise DataError("Multiple player rows without one unambiguous total. Supply a team-filtered sample; never average percentages or double-count TOT.")


def validate_bundle(bundle: dict, season: str, season_type: str, team_id: int = 0) -> None:
    validate_season(season, season_type)
    if bundle.get("schema_version") != VERSION:
        raise DataError(f"Expected schema_version {VERSION}.")
    if bundle.get("season") != season or bundle.get("season_type") != season_type:
        raise DataError("Input season/season_type differs from the request.")
    if bundle.get("data_kind") not in {"nba", "synthetic"}:
        raise DataError("data_kind must explicitly be nba or synthetic.")
    if integer(bundle.get("player_team_id", 0), "player_team_id") != team_id:
        raise DataError("Input player_team_id differs from --team-id. A team stint requires a separately filtered dataset.")
    tables, sources = bundle.get("tables"), bundle.get("sources")
    if not isinstance(tables, dict) or not isinstance(sources, dict):
        raise DataError("Bundle needs tables and sources dictionaries.")
    if not tables.get("player_base"):
        raise DataError("player_base is required and must not be empty.")
    for key, rows in tables.items():
        if key not in TABLES:
            raise DataError(f"Unknown table {key}; see references/input_schema.md.")
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise DataError(f"{key} must be a list of row dictionaries.")
        if not rows:
            continue
        sid, mode = TABLES[key]
        source = sources.get(sid, {})
        for required in ("provider", "url", "retrieved_at", "season", "season_type", "per_mode"):
            if not source.get(required):
                raise DataError(f"Source {sid} is missing {required}.")
        if source.get("season") != season or source.get("season_type") != season_type:
            raise DataError(f"Source {sid} uses a different season or season type.")
        if source.get("per_mode") != mode:
            raise DataError(f"Source {sid} must use {mode}, not {source.get('per_mode')}.")
        if source.get("status", "ok") != "ok":
            raise DataError(f"Source {sid} has rows but is not marked ok.")
        try:
            dt = datetime.fromisoformat(source["retrieved_at"].replace("Z", "+00:00"))
            if dt.tzinfo is None:
                raise ValueError("timezone required")
        except (ValueError, TypeError) as exc:
            raise DataError(f"Source {sid} needs an ISO timestamp with timezone.") from exc
        expected_hash = source.get("sha256_rows")
        if expected_hash and digest(rows) != expected_hash:
            raise DataError(f"Source {sid} row checksum mismatch.")

    if bundle.get('kaggle_import') is not None:
        from import_kaggle import validate_import
        validate_import(bundle)
    if bundle.get('sumitro_import') is not None:
        from import_sumitro import validate_import as validate_sumitro
        validate_sumitro(bundle)
    if bundle.get('epm_import') is not None:
        from import_epm import validate_import as validate_epm
        validate_epm(bundle)
    if bundle.get('historical_epm_import') is not None:
        from historical_epm import validate_import as validate_historical_epm
        validate_historical_epm(bundle)


def load_bundle(path: Path) -> dict:
    if path.is_file():
        bundle = read_json(path)
        if not isinstance(bundle, dict):
            raise DataError("Bundle JSON must contain an object.")
        return bundle
    if not path.is_dir():
        raise DataError(f"Input does not exist: {path}")
    bundle = read_json(path / "metadata.json")
    bundle["tables"] = {}
    for table in TABLES:
        csv_path = path / f"{table}.csv"
        if csv_path.exists():
            with csv_path.open(encoding="utf-8-sig", newline="") as handle:
                bundle["tables"][table] = list(csv.DictReader(handle))
    return bundle


def write_metrics_csv(path: Path, metrics: list[dict]) -> None:
    columns = ["metric_id", "label", "value", "display", "unit", "status", "source_ids", "formula", "reason"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for metric in metrics:
            row = {k: metric.get(k, "") for k in columns}
            row["source_ids"] = "|".join(metric.get("source_ids", []))
            for key, value in row.items():
                if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
                    row[key] = "'" + value
            writer.writerow(row)
