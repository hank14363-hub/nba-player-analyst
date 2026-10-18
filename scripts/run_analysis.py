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
from common import SKILL_ROOT, RELEASE_VERSION, VERSION, SEASON_TYPES, DataError, digest, load_bundle, now_iso, read_json, resolve_player, validate_season, write_json, write_metrics_csv
from fetch_data import Fetcher, FetchError
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
    comparison_flags = p.add_mutually_exclusive_group()
    comparison_flags.add_argument('--comparisons', dest='comparisons', action='store_true', help='Validate retained full-league tables (default); no composite score')
    comparison_flags.add_argument('--no-comparisons', dest='comparisons', action='store_false', help='Explicitly omit role comparisons for this research scope')
    p.set_defaults(comparisons=True)
    percentile_flags = p.add_mutually_exclusive_group()
    percentile_flags.add_argument('--advanced-percentiles', dest='advanced_percentiles', action='store_true', help='Compute retained advanced-stat distributions (default)')
    percentile_flags.add_argument('--no-advanced-percentiles', dest='advanced_percentiles', action='store_false', help='Omit advanced-stat distributions')
    p.set_defaults(advanced_percentiles=True)
    impact_flags=p.add_mutually_exclusive_group()
    impact_flags.add_argument('--impact',dest='impact',action='store_true',help='Attempt matching public impact data (online default)')
    impact_flags.add_argument('--no-impact',dest='impact',action='store_false',help='Explicitly skip optional public impact collection')
    p.set_defaults(impact=True)
    p.add_argument('--impact-cutoff',help='Explicit YYYY-MM-DD date for optional historical DARKO prediction')
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
    audit=analysis.get('impact_collection',{})
    if audit:
        evidence.append('- 高阶数据默认采集状态：'+audit['status']+'；各模型结果见 impact_collection_audit.json。')
    elif analysis['request'].get('impact_policy')=='retained_only':
        evidence.append('- 本次为离线/导入模式，高阶数据仅读已保留模型；未发起网络补采。')
    context = analysis.get('comparison_context', {})
    if context.get('status') == 'ok':
        evidence.append('- 同角色比较已核验；正文应说明实际值、中位数和门槛敏感性，百分位不是能力评分。')
    elif analysis['request'].get('comparisons'):
        evidence.append('- 同角色比较已尝试，未通过：' + context.get('reason', '未知原因'))
    else:
        evidence.append('- 本次未启用同角色比较；这不表示数据缺失。')
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
    if any(d['family']=='EPM_HISTORICAL' for d in analysis.get('impact_context',{}).get('datasets',[])):
        from historical_epm import NOTE
        with (out / 'writing_brief.md').open('a', encoding='utf-8') as handle:
            handle.write('\n## 历史 EPM 使用备注\n\n'+NOTE+'\n正文引用历史读数时就近写“口径待核验”，并在claims保留限制；不得把其作为Actual或已验证预测。\n')
    write_json(out / "book_content.template.json", make_template(analysis))
    if analysis.get('percentile_context'):
        write_json(out/'advanced_percentiles.json', analysis['percentile_context'])
        with (out/'writing_brief.md').open('a',encoding='utf-8') as handle:
            handle.write('\n## 高阶数值百分位\n\n读取advanced_percentiles.json；引用PCTL_指标并登记claims，说明各项N、门槛、同值处理及方向。百分位不是能力分；失误、球队失分和角色负荷高值不等于优势。历史EPM必须就近写“口径待核验”，说明混合记录日期、无GP/MIN门槛及归档样本限制。\n')
    write_json(out / "claims.template.json", {"schema_version": VERSION, "data_kind": analysis["data_kind"], "claims": []})
    write_json(out / 'film_records.template.json', film_template(analysis))
    if analysis['request'].get('media_research_audit'):
        with (out/'writing_brief.md').open('a',encoding='utf-8') as handle:
            handle.write('\n## 图片检索与落地\n\n按references/image_research.md实际查阅原页并保存media_research.json；单一下载403只停止该途径，继续正常可访问的独立素材或摄影者来源。采用后检查本地文件、署名、许可和media_content映射；运行scripts/media_research.py。不得只保存候选链接就标为配图完成。\n')
    from commentary_workflow import template as commentary_template
    write_json(out/'commentary_research.template.json',commentary_template(analysis))


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
    if args.impact_cutoff:
        from datetime import date
        try:date.fromisoformat(args.impact_cutoff)
        except ValueError as exc:raise DataError('--impact-cutoff requires YYYY-MM-DD') from exc
    impact_blobs={}
    if args.notes:
        try:
            notes = args.notes.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise DataError(f"Cannot read notes: {exc}") from exc
        if len(notes) > 200000:
            raise DataError("Notes exceed 200,000 characters. Supply a focused set of observations.")
    if args.input:
        bundle = load_bundle(args.input)
        from retained_raw import verify_retained
        verify_retained(bundle, args.input.parent if args.input.is_file() else args.input)
        if args.advanced_percentiles:
            from advanced_percentiles import verify_files
            verify_files(bundle, args.input.parent if args.input.is_file() else args.input)
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
    if args.impact and not args.input and not args.offline:
        from default_impact import collect as collect_impact
        pid,name=resolve_player(bundle['tables']['player_base'],args.player,args.player_id)
        bundle,_,impact_blobs=collect_impact(bundle,pid,name,args.timeout,args.impact_cutoff)
    request = {"player": args.player, "player_id": args.player_id, "season": args.season,
               "season_type": args.season_type, "team_id": args.team_id,
               "target_team_id": args.target_team_id, "question": args.question, "words": args.words,
               "input_mode": "import" if args.input else ("offline_cache" if args.offline else "nba_api")}
    request['impact_policy']='disabled' if not args.impact else 'retained_only' if args.input or args.offline else 'attempt_public'
    request['advanced_percentiles'] = args.advanced_percentiles
    request['stat_leaders'] = args.advanced_percentiles
    request['partial_shot_locations'] = True
    request['media_research_audit'] = True
    if args.on_off_team_id:
        request['on_off_team_id'] = args.on_off_team_id
    if args.comparisons:
        request['comparisons'] = True
    else:
        request['comparisons'] = False
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
    if bundle.get('impact_collection'):
        write_json(out/'impact_collection_audit.json',bundle['impact_collection'])
    for relative,payload in impact_blobs.items():
        destination=out/relative;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(payload)
    if args.input:
        input_root = args.input.parent if args.input.is_file() else args.input
        from retained_raw import copy_retained
        copy_retained(bundle, input_root, out)
    write_json(out / "analysis.json", analysis)
    write_json(out / "sources.json", {"version": VERSION, "producer_release": RELEASE_VERSION, "data_kind": analysis["data_kind"], "sample": analysis["sample"], "sources": analysis["sources"]})
    write_metrics_csv(out / "metrics.csv", analysis["metrics"])
    if notes is not None:
        (out / "observations.md").write_text(notes, encoding="utf-8")
    if film is not None:
        write_json(out / 'film_records.json', film)
    render_assets(out, analysis)
    from repair_plan import plan
    repair = plan(bundle, analysis, out)
    write_json(out/'repair_commands.json',repair)
    (out/'repair_commands.md').write_text('# 补抓命令\n\n'+repair['note']+'\n\n'+''.join('## '+c['table']+'\n\n```powershell\n'+c['powershell']+'\n```\n\n' for c in repair['commands'])+''.join('- '+b['table']+': '+b['reason']+'\n' for b in repair['blocked']),encoding='utf-8')
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
    except FetchError as exc:
        if args.out and (not args.out.exists() or (args.out.is_dir() and not any(args.out.iterdir()))):
            from repair_plan import command, new_destination
            argv=[sys.executable,str(SKILL_ROOT/'scripts/run_analysis.py')]+sys.argv[1:]
            index=argv.index('--out') if '--out' in argv else None
            destination=str(new_destination(args.out.with_name(args.out.name+'-retry')).resolve())
            if index is not None:argv[index+1]=destination
            else:
                argv=[('--out='+destination) if token.startswith('--out=') else token for token in argv]
            if args.out:
                args.out.mkdir(parents=True,exist_ok=True)
                write_json(args.out/'fetch_failure.json',dict(status='fetch_failed',category=exc.category,attempts=exc.attempts,automatic_execution=False,argv=argv,powershell=command(argv),note='Required base fetch failed; no repairable bundle exists. Retry the initial collection into a new output directory.'))
        print(f"ERROR: {exc}",file=sys.stderr)
        return 2
    except (DataError, OSError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
