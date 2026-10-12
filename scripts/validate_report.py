#!/usr/bin/env python3
"""Structural report/claim checks. This is NOT a semantic truth or film-validation model."""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

from common import VERSION, DataError, read_json, write_json
from film_evidence import load_registered_film


def validate(report: str, claims: dict, analysis: dict, min_chars: int = 1200, film_records: dict | None = None) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    metrics = {m["metric_id"]: m for m in analysis["metrics"]}
    sources = {k: v for k, v in analysis["sources"].items() if v.get("status", "ok") == "ok"}
    han_count = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", report))
    if han_count < min_chars:
        errors.append(f"Only {han_count} Chinese characters; minimum is {min_chars}. Short reports need an explicit justified --min-chars setting.")
    if "{{" in report or "[WRITE" in report or "NOT_FINAL" in report:
        errors.append("Unfilled report template detected.")
    if len(re.findall(r"^## ", report, flags=re.M)) < 4:
        errors.append("Need at least four substantive second-level report sections.")
    if analysis["data_kind"] == "synthetic" and not any(s in report for s in ("SYNTHETIC", "\u5408\u6210\u6d4b\u8bd5\u6570\u636e", "\u865a\u6784\u6d4b\u8bd5\u6570\u636e")):
        errors.append("Synthetic report must prominently disclose synthetic test data.")
    if claims.get("schema_version") != VERSION or claims.get("data_kind") != analysis["data_kind"]:
        errors.append("Claim schema_version/data_kind mismatch.")
    items = claims.get("claims")
    if not isinstance(items, list) or not items:
        errors.append("claims.json must contain an auditable, nonempty claims list.")
        items = []
    known_pattern = r"\[(P_[A-Z0-9]+|T_[A-Z0-9]+|TR_[A-Z0-9]+|NOTES|FILM|EXT_[A-Z0-9_]+)\]"
    cited = set(re.findall(known_pattern, report))
    for sid in cited - sources.keys():
        errors.append(f"Report cites missing/unregistered source [{sid}].")
    if not cited:
        errors.append("No registered source citations in report.")
    claim_ids = set()
    numerical_facts = 0
    for index, item in enumerate(items):
        prefix = f"claim {index + 1}"
        if not isinstance(item, dict):
            errors.append(prefix + " is not an object")
            continue
        claim_id = item.get("id")
        if not claim_id or claim_id in claim_ids:
            errors.append(prefix + " needs a unique id")
        claim_ids.add(claim_id)
        quote = item.get("report_quote", "")
        if not quote or quote not in report:
            errors.append(prefix + ": report_quote must exactly occur in report.md")
        kind = item.get("kind")
        if kind not in {"fact", "inference", "observation"}:
            errors.append(prefix + ": invalid kind")
        if item.get("confidence") not in {"high", "moderate", "low"}:
            errors.append(prefix + ": confidence must be high/moderate/low")
        mids, sids = item.get("metric_ids", []), item.get("source_ids", [])
        if not isinstance(mids, list) or not isinstance(sids, list):
            errors.append(prefix + ": metric_ids/source_ids must be lists")
            continue
        if not sids:
            errors.append(prefix + ": no source_ids")
        for sid in sids:
            if sid not in sources:
                errors.append(prefix + f": unknown or missing source {sid}")
        for mid in mids:
            if mid not in metrics or metrics[mid]["status"] != "ok":
                errors.append(prefix + f": metric {mid} is absent or missing")
            elif not set(metrics[mid]["source_ids"]).issubset(sids):
                errors.append(prefix + f": sources incomplete for {mid}")
        if kind in {"inference", "observation"} and not item.get("caveats"):
            errors.append(prefix + ": inference/observation requires caveats")
        if kind == "observation" and not item.get("observation_reference"):
            errors.append(prefix + ": observation needs game/date/quarter/clock or a precise note locator")
        if kind == 'observation' and 'FILM' in sids:
            oids = item.get('observation_ids')
            if not isinstance(oids, list) or not oids or any(not isinstance(o, str) or o not in (film_records or {}) for o in oids):
                errors.append(prefix + ': FILM observation needs valid structured observation_ids')
        for fact in item.get("numeric_facts", []):
            numerical_facts += 1
            mid = fact.get("metric_id")
            metric = metrics.get(mid)
            if not metric or metric["status"] != "ok" or mid not in mids:
                errors.append(prefix + f": numeric fact {mid} has no available registered metric")
                continue
            value = fact.get("value")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                errors.append(prefix + f": numeric fact {mid} must contain a finite raw numeric value")
            elif not math.isclose(value, metric["value"], rel_tol=1e-7, abs_tol=1e-7):
                errors.append(prefix + f": numeric fact {mid} does not match analysis.json (use raw units, not display percentages)")
    if not numerical_facts:
        errors.append("At least one registered numeric fact is required.")
    warnings.append("Automated checks validate schema, quote presence, IDs and declared numeric facts only. Codex must manually audit EVERY numerical statement, each citation's support, inference wording, and factual claims not represented in claims.json.")
    return {"status": "pass" if not errors else "fail", "chinese_characters": han_count,
            "claim_count": len(items), "numeric_fact_count": numerical_facts,
            "errors": errors, "warnings": warnings}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--min-chars", type=int, default=1200)
    args = p.parse_args()
    try:
        if args.min_chars < 0:
            raise DataError("--min-chars cannot be negative")
        analysis = read_json(args.run_dir / "analysis.json")
        # Allow Codex to register actually consulted external sources in sources.json.
        source_file = read_json(args.run_dir / "sources.json")
        for sid, source in source_file.get("sources", {}).items():
            if sid.startswith("EXT_"):
                for field in ("provider", "url", "retrieved_at", "status"):
                    if not source.get(field):
                        raise DataError(f"External source {sid} lacks {field}")
                analysis["sources"][sid] = source
        result = validate((args.run_dir / "report.md").read_text(encoding="utf-8"),
                          read_json(args.run_dir / "claims.json"), analysis, args.min_chars, load_registered_film(args.run_dir, analysis))
        write_json(args.run_dir / "validation.json", result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "pass" else 1
    except (OSError, DataError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
