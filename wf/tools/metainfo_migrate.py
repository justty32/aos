#!/usr/bin/env python3
"""Move legacy metainfo estimates and execution limits into separate fields."""
import argparse
import json
import os
from pathlib import Path


def migrate(meta):
    """Update one metadata object while preserving unrelated keys and their order."""
    if not isinstance(meta, dict) or "time_ms" not in meta:
        return False
    old = meta["time_ms"]
    if isinstance(old, (int, float)) and not isinstance(old, bool):
        estimate, limit = old, None
    elif isinstance(old, dict) and set(old) <= {"val", "max"}:
        estimate, limit = old.get("val"), old.get("max")
    else:
        raise ValueError("unsupported legacy time_ms value")
    cost = meta.get("cost", {})
    if not isinstance(cost, dict):
        raise ValueError("cost must be an object")
    if estimate is not None:
        if "time_ms" in cost and cost["time_ms"] != estimate:
            raise ValueError("conflicting cost.time_ms values")
        cost["time_ms"] = estimate
        meta["cost"] = cost
    if limit is not None:
        if "timeout_ms" in meta and meta["timeout_ms"] != limit:
            raise ValueError("conflicting timeout_ms values")
        meta["timeout_ms"] = limit
    del meta["time_ms"]
    return True


def migrate_tree(root):
    """Migrate JSON metadata below root, excluding historical and Git directories."""
    changed = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in {"thinking", "archive", ".git", "user-advice"})
        for name in sorted(files):
            path = Path(directory) / name
            if path.suffix != ".json" or path.is_symlink():
                continue
            raw = path.read_text(encoding="utf-8")
            try:
                data = json.loads(raw)
            except ValueError:
                if name == "_metainfo.json":
                    raise ValueError("%s: invalid JSON" % path)
                continue
            meta = data if name == "_metainfo.json" else data.get("_metainfo") if isinstance(data, dict) else None
            if migrate(meta):
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                changed.append(path)
                print("Updated %s" % path)
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    if not args.root.is_dir():
        parser.error("root must be a directory")
    try:
        migrate_tree(args.root)
    except (OSError, ValueError) as error:
        parser.exit(1, "metainfo_migrate: error: FileBad %s\n" % error)


if __name__ == "__main__":
    main()
