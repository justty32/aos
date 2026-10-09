"""Summarize node llmcall receipts without changing the node."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


def read_object(path):
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def amount(value):
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("expected an integer or null")
    return value


def period_for(call_dir, by):
    path = call_dir / "raw.json"
    if not path.exists() and not path.is_symlink():
        return "-"
    raw = read_object(path)
    at = raw.get("at")
    if isinstance(at, bool) or not isinstance(at, (int, float)):
        raise ValueError("invalid raw timestamp")
    stamp = datetime.fromtimestamp(at, tz=timezone.utc)
    return stamp.strftime("%Y-%m-%d" if by == "day" else "%Y-%m-%dT%H")


def directories(path):
    if not path.is_dir():
        return []
    return [child for child in path.iterdir() if child.is_dir()]


def summarize(node, by):
    groups = {}
    gaps = []
    totals = {}
    llmcall = node / "llmcall"
    budget_names = {path.name for path in directories(node / "budget")}
    for budget_dir in directories(llmcall):
        budget = budget_dir.name
        budget_names.add(budget)
        totals.setdefault(budget, 0)
        for call_dir in directories(budget_dir):
            if not (call_dir / "request.json").is_file():
                continue
            call_id = call_dir.name
            try:
                request = read_object(call_dir / "request.json")
                model = request.get("request")
                model = model.get("model") if isinstance(model, dict) else None
                if not isinstance(model, str):
                    model = request.get("endpoint")
                holder = request.get("holder")
                if not isinstance(model, str) or not isinstance(holder, str):
                    raise ValueError("invalid request fields")
                receipt_path = call_dir / "receipt.json"
                if not receipt_path.is_file():
                    gaps.append({"budget": budget, "call_id": call_id, "why": "no_receipt"})
                    continue
                receipt = read_object(receipt_path)
                if "used" not in receipt or "overrun" not in receipt:
                    raise ValueError("missing receipt amount")
                used = amount(receipt["used"])
                overrun = amount(receipt["overrun"])
                period = period_for(call_dir, by)
            except (OSError, UnicodeError, ValueError, OverflowError):
                gaps.append({"budget": budget, "call_id": call_id, "why": "bad_json"})
                continue
            key = (model, holder, period)
            if key not in groups:
                groups[key] = {"model": model, "holder": holder, "period": period,
                               "calls": 0, "used": 0, "overrun": 0}
            groups[key]["calls"] += 1
            groups[key]["used"] += used
            groups[key]["overrun"] += overrun
            totals[budget] += used
            if overrun > 0:
                gaps.append({"budget": budget, "call_id": call_id, "why": "overrun"})

    budgets = {}
    for name in sorted(budget_names):
        try:
            ledger = read_object(node / "budget" / name / "ledger.json")
            ledger_used = ledger.get("used")
            if isinstance(ledger_used, bool) or not isinstance(ledger_used, int):
                ledger_used = None
        except (OSError, UnicodeError, ValueError):
            ledger_used = None
        receipts_used = totals.get(name, 0)
        budgets[name] = {"receipts_used": receipts_used, "ledger_used": ledger_used,
                         "diff": None if ledger_used is None else ledger_used - receipts_used}
    return {"v": 1, "by": by, "groups": [groups[key] for key in sorted(groups)],
            "budgets": budgets,
            "gaps": sorted(gaps, key=lambda gap: (gap["budget"], gap["call_id"], gap["why"]))}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Summarize node llmcall usage (read-only)")
    parser.add_argument("node", type=Path)
    parser.add_argument("--by", choices=("day", "hour"), default="day")
    args = parser.parse_args(argv)
    if not args.node.is_dir():
        parser.error("node is not a directory")
    print(json.dumps(summarize(args.node, args.by), ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
