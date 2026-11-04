"""llm-cpu 請求的 ID、讀取、碰撞位置與穩定指紋。"""
import hashlib
import json
from pathlib import Path
import re

ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def read_json(path):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def validate_id(request_id):
    return (bool(request_id) and ID_RE.fullmatch(request_id) is not None
            and request_id not in (".", "..")
            and not request_id.endswith(".tmp"))


def request_sha256(request):
    """算使用者請求的穩定指紋，不把排程器自己的 _aos 欄位算進去。"""
    value = request
    if isinstance(request, dict):
        value = dict(request)
        meta = value.get("_aos")
        if isinstance(meta, dict):
            meta = {key: item for key, item in meta.items()
                    if key not in ("request_sha256", "endpoint", "pid", "started", "submitted")}
            if meta:
                value["_aos"] = meta
            else:
                value.pop("_aos", None)
    packed = json.dumps(value, ensure_ascii=False, sort_keys=True,
                        separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(packed).hexdigest()


def existing_request(root, request_id):
    """回 (位置種類, path)，done 對使用者算 results。"""
    root = Path(root)
    candidates = (
        ("requests", root / "requests" / (request_id + ".json")),
        ("running", root / "requests" / "running" / (request_id + ".json")),
        ("results", root / "results" / (request_id + ".json")),
        ("results", root / "requests" / "done" / (request_id + ".json")),
    )
    return next(((kind, path) for kind, path in candidates if path.exists()),
                (None, None))


def existing_request_sha256(root, request_id):
    kind, path = existing_request(root, request_id)
    if path is None:
        return kind, None
    try:
        value = read_json(path)
        if kind == "results":
            result_hash = value.get("request_sha256") if isinstance(value, dict) else None
            if isinstance(result_hash, str):
                return kind, result_hash
        meta = value.get("_aos") if isinstance(value, dict) else None
        saved = meta.get("request_sha256") if isinstance(meta, dict) else None
        return kind, saved if isinstance(saved, str) else request_sha256(value)
    except (OSError, ValueError, TypeError):
        return kind, None
