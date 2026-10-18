"""Research-book content contract and reproducibility checks (standard library only)."""
from __future__ import annotations

import copy
import re
from datetime import datetime
from pathlib import Path

from calculate_metrics import analyze
from common import DataError, digest, read_json
from validate_report import validate as validate_report
from film_evidence import load_registered_film

BOOK_VERSION = "0.2.0"
DIMENSIONS = ("scoring", "creation", "off_ball", "defense", "tactical_fit")
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
DIMENSION_NAMES = {'scoring': '得分与效率',
 'creation': '组织与传球',
 'off_ball': '不持球时怎么打',
 'defense': '防守还有哪些不清楚',
 'tactical_fit': '放进球队怎么用'}


def dictionary(path: Path) -> dict:
    value = read_json(path)
    if not isinstance(value, dict):
        raise DataError(f"{path.name} must contain a JSON object")
    return value


def make_template(analysis: dict) -> dict:
    """Prepare a clearly unfinished editorial sidecar; never invent conclusions."""
    return {
        "schema_version": BOOK_VERSION,
        "status": "draft",
        "data_kind": analysis["data_kind"],
        "identity": {"player_id": analysis["player"]["id"],
                     "season": analysis["sample"]["season"],
                     "season_type": analysis["sample"]["season_type"]},
        "title": "\u7403\u5458\u7814\u7a76\u518c",
        "subtitle": "\u7edf\u8ba1\u8868\u73b0\u3001\u80fd\u529b\u8fb9\u754c\u4e0e\u6218\u672f\u4f7f\u7528\u6761\u4ef6",
        "executive_claim_ids": [],
        "dimensions": [{"dimension": d, "headline": DIMENSION_NAMES[d], "claim_ids": []} for d in DIMENSIONS],
        "challenges": [],
        "strategies": [],
        "next_actions": [],
        "summary_claim_ids": [],
        **({'percentile_presentation':'radar'} if analysis.get('percentile_context') else {}),
    }


def load_context(run_dir: Path, min_chars: int = 1200) -> tuple[dict, dict, str, dict]:
    """Recompute original metrics, then validate claims and source registration."""
    saved = dictionary(run_dir / "analysis.json")
    bundle = dictionary(run_dir / "data_bundle.json")
    fresh = analyze(bundle, saved["request"])
    for field in ("data_kind", "player", "sample", "target_team", "metrics"):
        if digest(fresh[field]) != digest(saved[field]):
            raise DataError(f"analysis.json {field} differs from deterministic recomputation. Do not edit metric values or identity by hand.")
    if digest(fresh.get('shot_context')) != digest(saved.get('shot_context')):
        raise DataError('Shot coordinates/zones differ from deterministic recomputation.')
    if digest(fresh.get('comparison_context')) != digest(saved.get('comparison_context')):
        raise DataError('Comparison cohort/axes differ from deterministic recomputation.')
    if digest(fresh.get('impact_context')) != digest(saved.get('impact_context')):
        raise DataError('Impact provider/model/date/sample differs from deterministic recomputation.')
    if digest(fresh.get('percentile_context')) != digest(saved.get('percentile_context')):
        raise DataError('Advanced percentile population/method differs from deterministic recomputation.')
    if digest(fresh.get('stat_leader_context')) != digest(saved.get('stat_leader_context')):
        raise DataError('Statistic league leader scope/ties differs from deterministic recomputation.')
    if saved.get('percentile_context') and (run_dir/'advanced_percentiles.json').exists():
        if digest(dictionary(run_dir/'advanced_percentiles.json')) != digest(saved['percentile_context']):
            raise DataError('advanced_percentiles.json differs from registered analysis context.')
    if saved['request'].get('advanced_percentiles'):
        from advanced_percentiles import verify_files
        verify_files(bundle, run_dir)
    from retained_raw import verify_retained
    verify_retained(saved, run_dir, include_audit=False)
    if bundle.get('epm_import') is not None:
        from import_epm import validate_files
        validate_files(bundle, run_dir)
    if bundle.get('historical_epm_import') is not None:
        from historical_epm import validate_files as validate_historical_files
        validate_historical_files(bundle, run_dir)
    sources_file = dictionary(run_dir / "sources.json")
    if sources_file.get("data_kind") != saved["data_kind"] or sources_file.get("sample") != saved["sample"]:
        raise DataError("sources.json sample/data_kind differs from analysis.json")
    sources = sources_file.get("sources", {})
    if not isinstance(sources, dict):
        raise DataError("sources.json.sources must be an object")
    for sid, source in saved["sources"].items():
        if sources.get(sid) != source:
            raise DataError(f"Registered base source {sid} was modified or removed in sources.json")
    analysis = copy.deepcopy(saved)
    for sid, source in sources.items():
        if not IDENTIFIER.fullmatch(sid) or not isinstance(source, dict):
            raise DataError("Unsafe source ID or invalid source object")
        if sid not in saved["sources"] and not sid.startswith("EXT_"):
            raise DataError(f"Only EXT_ sources can be added after collection: {sid}")
        if sid.startswith("EXT_"):
            for field in ("provider", "url", "retrieved_at", "status"):
                if not isinstance(source.get(field), str) or not source[field].strip():
                    raise DataError(f"{sid} lacks {field}")
            try:
                date = datetime.fromisoformat(source["retrieved_at"].replace("Z", "+00:00"))
                if date.tzinfo is None:
                    raise ValueError("timezone required")
            except ValueError as exc:
                raise DataError(f"{sid} needs a timezone-aware retrieved_at") from exc
        analysis["sources"][sid] = source
    claims = dictionary(run_dir / "claims.json")
    report = (run_dir / "report.md").read_text(encoding="utf-8-sig")
    report_check = validate_report(report, claims, analysis, min_chars, load_registered_film(run_dir, analysis))
    if report_check["status"] != "pass":
        raise DataError("Report validation failed: " + "; ".join(report_check["errors"]))
    for claim in claims["claims"]:
        if not IDENTIFIER.fullmatch(claim["id"]):
            raise DataError("Claim IDs must be safe alphanumeric identifiers")
    return analysis, claims, report, report_check


def validate_content(content: dict, analysis: dict, claims: dict) -> list[str]:
    """Validate references and editorial intent, not the truth of basketball inferences."""
    errors: list[str] = []
    if not isinstance(content, dict):
        return ["book_content.json must be an object"]
    if content.get("schema_version") != BOOK_VERSION or content.get("status") != "ready":
        errors.append("Set book schema_version=0.2.0 and status=ready only after authoring; a draft cannot be published")
    if content.get("data_kind") != analysis["data_kind"]:
        errors.append("Book data_kind mismatch")
    expected = {"player_id": analysis["player"]["id"], "season": analysis["sample"]["season"],
                "season_type": analysis["sample"]["season_type"]}
    if content.get("identity") != expected:
        errors.append("Book player/season/type differs from the analyzed sample")
    known = {c["id"] for c in claims["claims"]}

    def text(value, label: str, maximum: int = 500) -> None:
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            errors.append(f"{label}: expected nonempty text up to {maximum} characters")
        elif any(marker in value for marker in ("{{", "[WRITE", "NOT_FINAL")):
            errors.append(f"{label}: unfinished placeholder")
        elif re.search(r"\d", value):
            errors.append(f"{label}: put quantitative findings in registered claims, not editorial free text")

    def refs(value, label: str, allowed: set, required: bool = True) -> None:
        if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
            errors.append(f"{label}: expected a list of IDs")
            return
        if required and not value:
            errors.append(f"{label}: at least one reference is required")
        if len(value) != len(set(value)) or any(v not in allowed for v in value):
            errors.append(f"{label}: duplicate or unknown reference")

    def strings(value, label: str) -> None:
        if not isinstance(value, list) or not value:
            errors.append(f"{label}: expected a nonempty list of text")
            return
        for v in value:
            text(v, label)

    for key in ("title", "subtitle"):
        text(content.get(key), key, 120)
    if 'core_metrics' in content:
        core=content['core_metrics']
        available={m['metric_id'] for m in analysis['metrics'] if m['status']=='ok'}
        if not isinstance(core,list) or len(core)!=4 or not all(isinstance(c,dict) for c in core):
            errors.append('core_metrics must contain exactly four evidence-backed metric objects')
        else:
            seen_core=set()
            by_claim={c['id']:c for c in claims['claims']}
            for c in core:
                mid=c.get('metric_id')
                if mid not in available or mid in seen_core:errors.append('Unknown/missing/duplicate core metric')
                seen_core.add(mid)
                text(c.get('label'),'core metric label',55);text(c.get('note'),'core metric note',180)
                refs(c.get('claim_ids'),'core metric claim_ids',known)
                if not any(mid in by_claim.get(cid,{}).get('metric_ids',[]) for cid in c.get('claim_ids',[]) if isinstance(cid,str)):
                    errors.append('Core metric must be supported by its registered claim')
    if content.get('presentation') not in (None,'integrated'):
        errors.append('Unknown presentation mode')
    if content.get('percentile_presentation') not in (None,'bars','radar'):
        errors.append('Unknown percentile presentation mode')
    commentary=content.get('commentary_cards',[])
    if 'commentary_research' in content:
        from commentary_workflow import validate as validate_commentary
        errors.extend(validate_commentary(content['commentary_research'],analysis['sources'],analysis))
    if not isinstance(commentary,list) or not all(isinstance(v,dict) for v in commentary):
        errors.append('commentary_cards must be a list of objects')
    else:
        by_claim={c['id']:c for c in claims['claims']}
        for card in commentary:
            for field in ('title','view','response','question'):
                text(card.get(field),'commentary '+field)
            sid=card.get('source_id')
            source=analysis['sources'].get(sid,{}) if isinstance(sid,str) else {}
            if source.get('source_type')!='commentary_article' or source.get('status')!='ok' or source.get('direct_page_verified') is not True:
                errors.append('Commentary requires a directly verified registered article')
            for field in ('author','published_at','title'):
                if not isinstance(source.get(field),str) or not source[field].strip():errors.append('Commentary source lacks '+field)
            refs(card.get('claim_ids'),'commentary claim_ids',known)
            cids=card.get('claim_ids',[])
            if isinstance(cids,list) and not any(sid in by_claim.get(cid,{}).get('source_ids',[]) for cid in cids if isinstance(cid,str)):
                errors.append('Commentary source must support a registered attributed claim')
    refs(content.get("executive_claim_ids"), "executive_claim_ids", known)
    refs(content.get("summary_claim_ids"), "summary_claim_ids", known)
    dimensions = content.get("dimensions", [])
    if not isinstance(dimensions, list):
        dimensions = []
    seen = []
    for dimension in dimensions:
        if not isinstance(dimension, dict):
            errors.append("Invalid dimension object")
            continue
        seen.append(dimension.get("dimension"))
        text(dimension.get("headline"), "dimension headline", 100)
        refs(dimension.get("claim_ids"), "dimension claim_ids", known, required=False)
        if 'reading_cards' in dimension:
            cards = dimension['reading_cards']
            if not isinstance(cards, list) or not cards or not all(isinstance(v, dict) for v in cards):
                errors.append('dimension reading_cards: expected a nonempty list of objects')
                continue
            scoped = set(v for v in dimension.get('claim_ids', []) if isinstance(v, str)) if isinstance(dimension.get('claim_ids'), list) else set()
            covered_cards = set()
            for card in cards:
                text(card.get('title'), 'reading card title', 80)
                if card.get('chart_key') not in (None,'efficiency','shot_mix','scoring_mix','creation','assisted','tracking','onoff','team_context','shot_zones'):
                    errors.append('Unsupported reading card chart_key')
                if 'shot_zone' in card:
                    if card['shot_zone'] not in ('all','RA','PAINT','MID','LC3','RC3','ATB3','BACK','UNRESOLVED','2PT','3PT'):
                        errors.append('Unsupported reading card shot_zone')
                    if not analysis.get('shot_context') or content.get('presentation')!='integrated':
                        errors.append('Reading card shot_zone requires validated shot events and integrated presentation')
                refs(card.get('claim_ids'), 'reading card claim_ids', scoped)
                if isinstance(card.get('claim_ids'), list):
                    covered_cards.update(v for v in card['claim_ids'] if isinstance(v, str))
                for field in ('interpretation', 'application', 'boundary'):
                    text(card.get(field), 'reading card ' + field)
            if scoped - covered_cards:
                errors.append('reading_cards must cover all dimension claims')
        if 'deck' in dimension:
            text(dimension['deck'], 'dimension deck', 200)
        if 'key_metric_ids' in dimension:
            scoped_claims = dimension.get('claim_ids', [])
            supported_metrics = {m for c in claims['claims'] if c['id'] in scoped_claims for m in c['metric_ids']} if isinstance(scoped_claims, list) else set()
            refs(dimension['key_metric_ids'], 'dimension key_metric_ids', supported_metrics)
            if isinstance(dimension['key_metric_ids'], list) and len(dimension['key_metric_ids']) > 4:
                errors.append('dimension key_metric_ids: at most four metrics')
    if set(seen) != set(DIMENSIONS) or len(seen) != len(DIMENSIONS):
        errors.append("Exactly five unique dimensions are required; empty evidence is shown explicitly")
    challenges = content.get("challenges", [])
    strategies = content.get("strategies", [])
    actions = content.get("next_actions", [])
    for key, value in (("challenges", challenges), ("strategies", strategies), ("next_actions", actions)):
        if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
            errors.append(f"{key} must be a list of objects")
            return errors
    qids, sids = set(), set()
    for challenge in challenges:
        qid = challenge.get("id", "")
        if not isinstance(qid, str) or not IDENTIFIER.fullmatch(qid) or qid in qids:
            errors.append("Challenge needs a unique safe ID")
        else:
            qids.add(qid)
        for key in ("title", "question"):
            text(challenge.get(key), "challenge " + key)
        refs(challenge.get("claim_ids"), "challenge claim_ids", known)
    covered = set()
    for strategy in strategies:
        sid = strategy.get("id", "")
        if not isinstance(sid, str) or not IDENTIFIER.fullmatch(sid) or sid in sids:
            errors.append("Strategy needs a unique safe ID")
        else:
            sids.add(sid)
        for key in ("title", "action"):
            text(strategy.get(key), "strategy " + key)
        refs(strategy.get("challenge_ids"), "strategy challenge_ids", qids)
        refs(strategy.get("claim_ids"), "strategy claim_ids", known)
        for key in ("conditions", "tradeoffs", "validation_plan"):
            strings(strategy.get(key), "strategy " + key)
        if isinstance(strategy.get("challenge_ids"), list):
            covered.update(v for v in strategy["challenge_ids"] if isinstance(v, str))
    if not actions:
        errors.append("At least one concrete evidence-collection next_action is required")
    for action in actions:
        for key in ("question", "evidence_needed", "decision_rule"):
            text(action.get(key), "next_action " + key)
        refs(action.get("challenge_ids"), "next_action challenge_ids", qids, required=False)
        if isinstance(action.get("challenge_ids"), list):
            covered.update(v for v in action["challenge_ids"] if isinstance(v, str))
    if qids - covered:
        errors.append("Each challenge needs a linked strategy or evidence-collection action")
    return errors
