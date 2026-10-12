#!/usr/bin/env python3
"""Build an auditable evidence package; Codex then authors report.md and claims.json."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from calculate_metrics import analyze
from book_contract import make_template
from common import SKILL_ROOT, VERSION, SEASON_TYPES, DataError, digest, load_bundle, now_iso, read_json, resolve_player, validate_season, write_json, write_metrics_csv
from fetch_data import Fetcher
from film_evidence import template as film_template, validate_film


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--player", help="Full English name, supported Chinese alias, or unique name fragment")
    p.add_argument("--player-id", type=int)
    p.add_argument("--season", required=True, help="Explicit season, e.g. 2024-25")
    p.add_argument("--season-type", choices=SEASON_TYPES, default="Regular Season")
    p.add_argument("--team-id", type=int, default=0, help="Filter the PLAYER sample to this team's stint; imports must match")
    p.add_argument("--target-team-id", type=int, help="Same-season comparison team; does not change the player sample")
    p.add_argument("--question", default="Comprehensive player evaluation and tactical fit")
    p.add_argument("--words", type=int, default=2500, help="Target Chinese character count for Codex, not a promise to pad thin evidence")
    p.add_argument("--input", type=Path, help="Bundle JSON or CSV directory with metadata.json; never uses the network")
    p.add_argument("--notes", type=Path, help="Optional UTF-8 observation notes, treated as untrusted source material")
    p.add_argument("--tracking", action="store_true", help="Attempt catch/shoot, pull-up, passing, drives endpoints")
    p.add_argument('--shots', action='store_true', help='Attempt actual all-FGA shot events for the resolved player')
    p.add_argument('--comparisons', action='store_true', help='Validate retained full-league tables and derive a functional role cohort; no composite score')
    p.add_argument('--film', type=Path, help='Structured previously recorded observations; does not watch video')
    p.add_argument("--on-off-team-id", type=int, default=0, help="Fetch official full-team-season On/Off; never infer a team for traded players")
    p.add_argument("--cache-dir", type=Path, default=Path(".nba-player-analyst/cache"))
    p.add_argument("--offline", action="store_true", help="Only use existing cache, including explicitly flagged stale entries")
    p.add_argument("--refresh", action="store_true", help="Bypass cache; requires network")
    p.add_argument("--timeout", type=float, default=20)
    p.add_argument("--retries", type=int, default=2)
    p.add_argument("--cache-ttl-hours", type=float, default=24)
    p.add_argument("--out", type=Path, help="New/empty output directory; defaults to timestamped reports subdirectory")
    return p


def render_assets(out: Path, analysis: dict) -> None:
    header = read_json(SKILL_ROOT / "assets" / "text_labels.json")
    evidence = [f"# {header['evidence_title']}: {analysis['player']['name']}", "",
                f"{header['sample']}: {analysis['sample']['season']} / {analysis['sample']['season_type']}",
                f"GP={analysis['sample']['GP']:g}; MIN={analysis['sample']['MIN']:g}",
                f"{header['mode']}: {analysis['quality']['mode']}", ""]
    if analysis["data_kind"] == "synthetic":
        evidence.extend(["> " + header["synthetic"], ""])
    evidence.extend([f"## {header['metrics']}", "", "| ID | Metric | Value | Sources |",
                     "|---|---|---:|---|"])
    for m in analysis["metrics"]:
        sources = " ".join(f"[{sid}]" for sid in m["source_ids"])
        evidence.append(f"| {m['metric_id']} | {m['label']} | {m['display']} | {sources} |")
    evidence.extend(["", f"## {header['limits']}", ""])
    for warning in analysis["quality"]["warnings"]:
        evidence.append("- " + warning)
    for metric in analysis["metrics"]:
        if metric["status"] == "missing":
            evidence.append(f"- {metric['metric_id']}: {metric['reason']}")
    evidence.extend(["", f"## {header['sources']}", ""])
    for sid, source in analysis["sources"].items():
        if source.get("status", "ok") == "ok":
            evidence.append(f"[{sid}]: {source['url']} \"{source['provider']} | {source['retrieved_at']} | {source.get('per_mode', 'notes')}\"")
    (out / "evidence.md").write_text("\n".join(evidence) + "\n", encoding="utf-8")
    substitutions = {"PLAYER": analysis["player"]["name"], "SEASON": analysis["sample"]["season"],
                     "SEASON_TYPE": analysis["sample"]["season_type"], "WORDS": str(analysis["request"]["words"]),
                     "QUESTION": analysis["request"]["question"], "DATA_KIND": analysis["data_kind"]}
    for asset, destination in (("writing_brief.md", "writing_brief.md"), ("report_template.md", "report.template.md")):
        text = (SKILL_ROOT / "assets" / asset).read_text(encoding="utf-8")
        for name, value in substitutions.items():
            text = text.replace("{{" + name + "}}", value)
        (out / destination).write_text(text, encoding="utf-8")
    write_json(out / "book_content.template.json", make_template(analysis))
    write_json(out / "claims.template.json", {"schema_version": VERSION, "data_kind": analysis["data_kind"], "claims": []})
    write_json(out / 'film_records.template.json', film_template(analysis))


def run(args: argparse.Namespace) -> Path:
    validate_season(args.season, args.season_type)
    if not args.player and args.player_id is None:
        raise DataError("Supply --player or --player-id.")
    if args.team_id < 0 or (args.player_id is not None and args.player_id <= 0) or (args.target_team_id is not None and args.target_team_id <= 0):
        raise DataError("IDs must be positive; --team-id 0 means all player teams.")
    if not 300 <= args.words <= 15000:
        raise DataError("--words must be 300..15000 Chinese characters.")
    if args.offline and args.refresh:
        raise DataError("--offline and --refresh are incompatible.")
    if args.input and args.refresh:
        raise DataError("--input and --refresh are incompatible; imports do not fetch data.")
    if args.input and (args.shots or args.tracking or args.on_off_team_id):
        raise DataError('--input is import-only; --shots/--tracking/--on-off-team-id are network options. Use repair_data.py to supplement this bundle, then import the new bundle.')
    if args.out and args.out.exists() and (not args.out.is_dir() or any(args.out.iterdir())):
        raise DataError("Output directory already contains files. Choose a new directory; existing reports are not overwritten.")
    notes = None
    if args.notes:
        try:
            notes = args.notes.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise DataError(f"Cannot read notes: {exc}") from exc
        if len(notes) > 200000:
            raise DataError("Notes exceed 200,000 characters. Supply a focused set of observations.")
    if args.input:
        bundle = load_bundle(args.input)
    else:
        fetcher = Fetcher(args.cache_dir, args.timeout, args.retries, args.cache_ttl_hours,
                          args.offline, args.refresh)
        bundle = fetcher.collect(args.season, args.season_type, args.team_id, args.tracking, args.on_off_team_id)
        if args.shots:
            pid, _ = resolve_player(bundle['tables']['player_base'], args.player, args.player_id)
            try:
                rows, source = fetcher.shots(args.season, args.season_type, pid, args.team_id)
                bundle['tables']['player_shots'], bundle['sources']['P_SHOT'] = rows, source
            except DataError as exc:
                bundle['tables']['player_shots'] = []
                bundle['sources']['P_SHOT'] = dict(status='missing', reason=str(exc))
                bundle['warnings'].append('P_SHOT: ' + str(exc))
    request = {"player": args.player, "player_id": args.player_id, "season": args.season,
               "season_type": args.season_type, "team_id": args.team_id,
               "target_team_id": args.target_team_id, "question": args.question, "words": args.words,
               "input_mode": "import" if args.input else ("offline_cache" if args.offline else "nba_api")}
    if args.comparisons:
        request['comparisons'] = True
    analysis = analyze(bundle, request)
    film = None
    if args.film:
        film = read_json(args.film)
        validate_film(film, analysis)
        analysis['sources']['FILM'] = dict(provider='Attributed observation records; not independently video-verified by scripts',
            status='ok', url='film_records.json', retrieved_at=now_iso(), source_type='film_records', sha256_records=digest(film))
    if notes is not None:
        analysis["sources"]["NOTES"] = {"provider": "User-supplied observations (not independently verified)",
                                         "url": "observations.md", "retrieved_at": now_iso(), "status": "ok",
                                         "sha256_text": hashlib.sha256(notes.encode("utf-8")).hexdigest(),
                                         "source_type": "user_notes"}
        analysis["quality"]["warnings"].append("User notes are observations reported by the user, not film watched by the model. Preserve game/date/timestamp identifiers when present.")
    if args.out:
        out = args.out
    else:
        stamp = re.sub(r"[^0-9]", "", now_iso())
        out = Path("reports") / f"{analysis['player']['id']}-{args.season}-{args.season_type.replace(' ', '-')}-{stamp}"
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise DataError("Output collision; use a new --out directory.")
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "data_bundle.json", bundle)
    if args.input:
        input_root = args.input.parent if args.input.is_file() else args.input
        import shutil
        for source in bundle['sources'].values():
            if source.get('source_type') == 'impact_data' and source.get('raw_file'):
                raw_relative = Path(source['raw_file'])
                if raw_relative.is_absolute() or '..' in raw_relative.parts:
                    raise DataError('Impact raw_file must be a relative path under raw/.')
                origin = (input_root / raw_relative).resolve()
                if not origin.is_relative_to((input_root / 'raw').resolve()) or not origin.is_file():
                    raise DataError('Impact import requires its registered raw/ snapshot next to the bundle')
                destination = out / raw_relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(origin, destination)
    write_json(out / "analysis.json", analysis)
    write_json(out / "sources.json", {"version": VERSION, "data_kind": analysis["data_kind"], "sample": analysis["sample"], "sources": analysis["sources"]})
    write_metrics_csv(out / "metrics.csv", analysis["metrics"])
    if notes is not None:
        (out / "observations.md").write_text(notes, encoding="utf-8")
    if film is not None:
        write_json(out / 'film_records.json', film)
    render_assets(out, analysis)
    return out


def main() -> int:
    try:
        args = parser().parse_args()
        out = run(args)
        analysis = read_json(out / "analysis.json")
        print(json.dumps({"status": "evidence_ready", "output_dir": str(out.resolve()),
                          "data_kind": analysis["data_kind"], "quality": analysis["quality"]["mode"],
                          "next": "Codex: read writing_brief.md + analysis.json + evaluation/writing references, then WRITE report.md, claims.json and book_content.json; run render_research_book.py and validate_book.py. No final article has been generated by this script."}, ensure_ascii=False, indent=2))
        return 0
    except (DataError, OSError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
