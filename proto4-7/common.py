#!/usr/bin/env python3
"""proto4-7 共用的檔案小工具。"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def read_json(path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=1)
        stream.write("\n")
    os.replace(tmp, path)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def timestamp_name():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")

