"""llm-cpu 的家、原子檔案、submit 與給人看的 ls。"""
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import time

PROGRAM = Path(__file__).with_name("llm-cpu").resolve()
ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def atomic_json(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def read_json(path):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def now_text():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")


def endpoint_document():
    return {
        "default": "local",
        "endpoints": [
            {"name": "local", "kind": "openai",
             "base_url": "http://localhost:1234/v1",
             "model": "loaded-model-id", "max_concurrent": 1,
             "timeout_ms": 300000},
            {"name": "deepseek", "kind": "openai",
             "base_url": "https://api.deepseek.com/v1",
             "model": "deepseek-chat", "max_concurrent": 2,
             "timeout_ms": 300000, "api_key_env": "DEEPSEEK_API_KEY",
             "strict_model": False},
            {"name": "pi", "kind": "process", "argv": ["pi", "-p"],
             "enabled": False},
        ],
    }


def init_home(directory):
    root = Path(directory).absolute()
    if root.exists():
        print("llm-cpu init: DIR 已經存在：%s" % root, file=sys.stderr)
        return 1
    try:
        (root / "requests" / "running").mkdir(parents=True)
        (root / "requests" / "done").mkdir()
        (root / "results").mkdir()
        (root / "log").mkdir()
        atomic_json(root / "endpoints.json", endpoint_document())
        atomic_json(root / "inst.json", {
            "argv": [str(PROGRAM), "tick", "."],
            "cwd": str(root), "stderr": "tick.err",
        })
        atomic_json(root / "state.json", {
            "ticks": 0, "running": 0, "endpoints": {},
        })
        (root / "usage.jsonl").touch()
        (root / "llm-cpu.log").touch()
    except OSError as exc:
        print("llm-cpu init: %s" % exc, file=sys.stderr)
        return 1
    print("建好了：%s" % root)
    return 0


def validate_id(request_id):
    return (bool(request_id) and ID_RE.fullmatch(request_id) is not None
            and request_id not in (".", "..")
            and not request_id.endswith(".tmp"))


def submit(directory, source, requested_id=None):
    root = Path(directory).absolute()
    if not (root / "requests").is_dir():
        print("llm-cpu submit: 這不是 llm-cpu 的家：%s" % root,
              file=sys.stderr)
        return 1
    request_id = requested_id or str(time.time_ns())
    if not validate_id(request_id):
        print("llm-cpu submit: --name 只能用英數、點、底線、減號", file=sys.stderr)
        return 1
    try:
        data = sys.stdin.buffer.read() if source == "-" else Path(source).read_bytes()
    except OSError as exc:
        print("llm-cpu submit: 讀不到請求：%s" % exc, file=sys.stderr)
        return 1
    targets = [root / "requests" / (request_id + ".json"),
               root / "requests" / "running" / (request_id + ".json"),
               root / "requests" / "done" / (request_id + ".json"),
               root / "results" / (request_id + ".json")]
    if any(path.exists() for path in targets):
        print("llm-cpu submit: id 已經存在：%s" % request_id, file=sys.stderr)
        return 1
    tmp = targets[0].with_name(targets[0].name + ".tmp")
    try:
        with open(tmp, "xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, targets[0])
    except OSError as exc:
        try:
            tmp.unlink()
        except OSError:
            pass
        print("llm-cpu submit: 寫不進去：%s" % exc, file=sys.stderr)
        return 1
    print("投進去了：requests/%s.json；結果會在 results/%s.json" %
          (request_id, request_id))
    return 0


def load_endpoints(root):
    doc = read_json(Path(root) / "endpoints.json")
    if not isinstance(doc, dict) or not isinstance(doc.get("endpoints"), list):
        raise ValueError("endpoints.json 要有 endpoints 陣列")
    endpoints = {}
    for item in doc["endpoints"]:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise ValueError("endpoint 每筆都要有字串 name")
        if item["name"] in endpoints:
            raise ValueError("endpoint 名字重複：%s" % item["name"])
        endpoints[item["name"]] = item
    if not isinstance(doc.get("default"), str):
        raise ValueError("endpoints.json 要有字串 default")
    return doc["default"], endpoints


def emergency_tick_log(directory, exc):
    try:
        root = Path(directory).absolute()
        root.mkdir(parents=True, exist_ok=True)
        with open(root / "llm-cpu.log", "a", encoding="utf-8") as stream:
            stream.write("%s tick error=%s\n" % (now_text(), str(exc).replace("\n", " ")))
    except BaseException:
        pass


def _running_counts(root):
    counts = {}
    rows = []
    for path in sorted((root / "requests" / "running").glob("*.json")):
        try:
            req = read_json(path)
            meta = req.get("_aos", {})
            endpoint = meta.get("endpoint", "?")
            counts[endpoint] = counts.get(endpoint, 0) + 1
            rows.append((path.stem, endpoint,
                         max(0, int(time.time() - float(meta.get("started", time.time()))))))
        except Exception:
            rows.append((path.stem, "?", 0))
    return counts, rows


def show(directory):
    root = Path(directory).absolute()
    try:
        default, endpoints = load_endpoints(root)
    except Exception as exc:
        print("llm-cpu ls: %s" % exc, file=sys.stderr)
        return 1
    counts, running = _running_counts(root)
    print("endpoints:")
    for name, ep in endpoints.items():
        mark = " (default)" if name == default else ""
        print("  %s%s  model=%s  %s/%s  enabled=%s" % (
            name, mark, ep.get("model", "-"), counts.get(name, 0),
            ep.get("max_concurrent", "-"), ep.get("enabled", True)))
    queued = []
    for path in (root / "requests").glob("*.json"):
        try:
            req = read_json(path)
            priority = req.get("priority", 0) if isinstance(req, dict) else 0
        except Exception:
            priority = 0
        queued.append((-priority if isinstance(priority, int) else 0,
                       path.stat().st_mtime_ns, path.name, path.stem))
    queued.sort()
    print("queued: %d" % len(queued))
    for _, _, _, request_id in queued[:10]:
        print("  %s" % request_id)
    print("running: %d" % len(running))
    for request_id, endpoint, seconds in running:
        print("  %s  endpoint=%s  %ds" % (request_id, endpoint, seconds))
    done = sorted((root / "requests" / "done").glob("*.json"),
                  key=lambda p: p.stat().st_mtime_ns, reverse=True)
    print("done (recent):")
    for path in done[:5]:
        try:
            result = read_json(root / "results" / path.name)
            error = result.get("error") or {}
            print("  %s  ok=%s  kind=%s" %
                  (path.stem, result.get("ok"), error.get("kind", "-")))
        except Exception:
            print("  %s  ok=?  kind=?" % path.stem)
    return 0
