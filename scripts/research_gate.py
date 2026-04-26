#!/usr/bin/env python3
"""Validate that downstream routines have fresh agent research to act on."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORT_DIR = ROOT / "memory" / "research-reports"
VALID_GRADES = {"A", "B"}
VALID_SETUPS = {
    "catalyst_driven_breakdown",
    "sentiment_extreme_greed_fade",
    "funding_flip_divergence",
    "onchain_distribution_top",
}
REQUIRED_TOP_LEVEL = {
    "ts",
    "bias",
    "confidence",
    "rubric",
    "numeric_context",
    "trade_ideas",
    "data_health",
}
REQUIRED_RUBRIC = {
    "catalyst",
    "sentiment_extreme_or_divergence",
    "onchain_or_structure",
    "macro_aligned",
    "technical_level",
    "score",
    "grade",
}
REQUIRED_DATA_HEALTH = {
    "fetched_at",
    "missing_slots",
    "websearch_gaps",
    "stale_warnings",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def parse_utc(value: str) -> datetime:
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0)


def fmt_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def dec(value, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be decimal") from exc


def load_report(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        report = json.load(f)
    if not isinstance(report, dict):
        raise ValueError("research report must be a JSON object")
    return report


def latest_report_path(report_dir: Path = DEFAULT_REPORT_DIR) -> Path:
    reports = sorted(report_dir.glob("*.json"))
    if not reports:
        raise FileNotFoundError(f"no research reports found in {report_dir}")
    return reports[-1]


def report_fetched_at(report: dict) -> datetime:
    data_health = report.get("data_health")
    fetched_at = data_health.get("fetched_at") if isinstance(data_health, dict) else None
    ts = fetched_at or report.get("ts")
    if not ts:
        raise ValueError("research report missing data_health.fetched_at or ts")
    return parse_utc(str(ts))


def _trade_idea_errors(report: dict) -> list[str]:
    errors: list[str] = []
    rubric = report.get("rubric") if isinstance(report.get("rubric"), dict) else {}
    report_grade = str(rubric.get("grade", "")).upper()
    if rubric.get("technical_level") is not True:
        errors.append("research rubric technical_level must be true for trade ideas")
    ideas = report.get("trade_ideas")
    if not isinstance(ideas, list):
        return ["trade_ideas must be a list"]

    actionable = 0
    for index, idea in enumerate(ideas):
        if not isinstance(idea, dict):
            errors.append(f"trade_ideas[{index}] must be an object")
            continue

        setup = idea.get("playbook_setup")
        if setup not in VALID_SETUPS:
            errors.append(f"trade_ideas[{index}].playbook_setup is not a v2 setup")

        grade = str(idea.get("grade", report_grade)).upper()
        if grade not in VALID_GRADES:
            errors.append(f"trade_ideas[{index}] grade must be A or B")

        for field in (
            "sell_trigger_price",
            "rebuy_limit_price",
            "worst_case_rebuy_price",
        ):
            if field not in idea:
                errors.append(f"trade_ideas[{index}].{field} is required")
                continue
            try:
                if dec(idea[field], field) <= 0:
                    errors.append(f"trade_ideas[{index}].{field} must be positive")
            except ValueError as exc:
                errors.append(f"trade_ideas[{index}].{exc}")

        if "btc_r_r" in idea:
            try:
                if dec(idea["btc_r_r"], "btc_r_r") < Decimal("2.0"):
                    errors.append(f"trade_ideas[{index}].btc_r_r must be at least 2.0")
            except ValueError as exc:
                errors.append(f"trade_ideas[{index}].{exc}")

        if setup in VALID_SETUPS and grade in VALID_GRADES:
            actionable += 1

    if actionable == 0:
        errors.append("no actionable A/B trade idea in research report")
    return errors


def validate_schema(report: dict) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_TOP_LEVEL - set(report))
    if missing:
        errors.append("research report missing required keys: " + ", ".join(missing))

    rubric = report.get("rubric")
    if not isinstance(rubric, dict):
        errors.append("rubric must be an object")
    else:
        missing_rubric = sorted(REQUIRED_RUBRIC - set(rubric))
        if missing_rubric:
            errors.append("rubric missing required keys: " + ", ".join(missing_rubric))
        if rubric.get("grade") not in {"A", "B", "C", "D", "F", "SKIP", "HOLD"}:
            errors.append("rubric.grade must be A, B, C, D, F, SKIP, or HOLD")

    data_health = report.get("data_health")
    if not isinstance(data_health, dict):
        errors.append("data_health must be an object")
    else:
        missing_health = sorted(REQUIRED_DATA_HEALTH - set(data_health))
        if missing_health:
            errors.append("data_health missing required keys: " + ", ".join(missing_health))
        for key in ("missing_slots", "websearch_gaps", "stale_warnings"):
            if key in data_health and not isinstance(data_health[key], list):
                errors.append(f"data_health.{key} must be a list")

    ideas = report.get("trade_ideas")
    if not isinstance(ideas, list):
        errors.append("trade_ideas must be a list")
    elif ideas:
        # Validate v2 field names even when the caller is not requiring an
        # actionable idea. A stale v1 entry/stop/target report must fail early.
        for index, idea in enumerate(ideas):
            if not isinstance(idea, dict):
                errors.append(f"trade_ideas[{index}] must be an object")
                continue
            for old_field in ("entry", "stop", "target"):
                if old_field in idea:
                    errors.append(f"trade_ideas[{index}] uses stale v1 field {old_field}")
            for field in (
                "playbook_setup",
                "sell_trigger_price",
                "rebuy_limit_price",
                "worst_case_rebuy_price",
            ):
                if field not in idea:
                    errors.append(f"trade_ideas[{index}].{field} is required")

    return errors


def validate_research_report(
    path: Path,
    *,
    now: datetime | None = None,
    max_age_minutes: Decimal = Decimal("45"),
    require_trade_idea: bool = False,
) -> dict:
    now = now or utc_now()
    errors: list[str] = []
    warnings: list[str] = []
    report = load_report(path)
    errors.extend(validate_schema(report))

    fetched_at = report_fetched_at(report)
    age = now - fetched_at
    if fetched_at > now + timedelta(minutes=5):
        errors.append("research report timestamp is in the future")
    elif age > timedelta(minutes=float(max_age_minutes)):
        errors.append("research report is stale")

    if not isinstance(report.get("rubric"), dict):
        errors.append("research report missing rubric")
    if not isinstance(report.get("data_health"), dict):
        warnings.append("research report missing data_health")

    data_health = report.get("data_health") if isinstance(report.get("data_health"), dict) else {}
    missing_slots = set(data_health.get("missing_slots") or [])
    if missing_slots:
        warnings.append("research missing_slots: " + ", ".join(sorted(missing_slots)))
    stale_warnings = data_health.get("stale_warnings") or []
    for warning in stale_warnings:
        warnings.append(str(warning))

    if require_trade_idea:
        errors.extend(_trade_idea_errors(report))

    ideas = report.get("trade_ideas")
    trade_idea_count = len(ideas) if isinstance(ideas, list) else None
    return {
        "ok": not errors,
        "path": path.as_posix(),
        "fetched_at_utc": fmt_utc(fetched_at),
        "age_seconds": int(age.total_seconds()),
        "max_age_minutes": str(max_age_minutes),
        "require_trade_idea": require_trade_idea,
        "trade_idea_count": trade_idea_count,
        "errors": errors,
        "warnings": warnings,
    }


def print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2))


def cmd_latest(args) -> int:
    path = latest_report_path(args.report_dir)
    report = validate_research_report(
        path,
        now=parse_utc(args.now) if args.now else utc_now(),
        max_age_minutes=dec(args.max_age_minutes, "max_age_minutes"),
        require_trade_idea=args.require_trade_idea,
    )
    print_json(report)
    return 0 if report["ok"] else 1


def cmd_validate(args) -> int:
    report = validate_research_report(
        args.report,
        now=parse_utc(args.now) if args.now else utc_now(),
        max_age_minutes=dec(args.max_age_minutes, "max_age_minutes"),
        require_trade_idea=args.require_trade_idea,
    )
    print_json(report)
    return 0 if report["ok"] else 1


def cmd_schema(args) -> int:
    report = load_report(args.report)
    errors = validate_schema(report)
    print_json({"ok": not errors, "path": args.report.as_posix(), "errors": errors})
    return 0 if not errors else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate agent research artifacts")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("latest", help="Validate the newest research report")
    p.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    p.add_argument("--max-age-minutes", default="45")
    p.add_argument("--require-trade-idea", action="store_true")
    p.add_argument("--now")
    p.set_defaults(func=cmd_latest)

    p = sub.add_parser("validate", help="Validate a specific research report")
    p.add_argument("report", type=Path)
    p.add_argument("--max-age-minutes", default="45")
    p.add_argument("--require-trade-idea", action="store_true")
    p.add_argument("--now")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("schema", help="Validate research report schema only")
    p.add_argument("report", type=Path)
    p.set_defaults(func=cmd_schema)

    args = parser.parse_args()
    try:
        code = args.func(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print_json({"ok": False, "error": str(exc)})
        code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()
