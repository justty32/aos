#!/usr/bin/env python3
# ledger_sum.py：Summarize ledger calls and tokens by endpoint and sender.

import json
import sys
from collections import defaultdict


def main():
    if len(sys.argv) != 2:
        print("usage: ledger_sum.py LEDGER.jsonl", file=sys.stderr)
        return 2

    path = sys.argv[1]
    groups = defaultdict(lambda: [0, 0])
    total_calls = 0
    total_tokens = 0

    try:
        with open(path, encoding="utf-8") as ledger:
            for line_number, line in enumerate(ledger, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    record = None
                if not isinstance(record, dict):
                    print(
                        f"ledger_sum: line {line_number}: not JSON, skipped",
                        file=sys.stderr,
                    )
                    continue

                endpoint = record.get("endpoint", "-")
                sender = record.get("sender", "-")
                tokens = record.get("usage", {}).get("total_tokens", 0)
                group = groups[(endpoint, sender)]
                group[0] += 1
                group[1] += tokens
                total_calls += 1
                total_tokens += tokens
    except (OSError, UnicodeError) as error:
        print(f"ledger_sum: cannot read {path}: {error}", file=sys.stderr)
        return 2

    for (endpoint, sender), (calls, tokens) in sorted(groups.items()):
        print(f"{endpoint} {sender} {calls} {tokens}")
    print(f"TOTAL - {total_calls} {total_tokens}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
