"""aos-llm 的檔案邊界與命令列解析。"""
import json
import os
from pathlib import Path
import sys

import aos_llm


def _cli_error(message):
    print("aos-llm: %s" % message, file=sys.stderr)
    return 2


def _read_json(source):
    data = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    return json.loads(data)


def _resolve_endpoint(spec):
    path_text, marker, name = spec.rpartition("#")
    path = Path(path_text if marker else spec)
    doc = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(doc, dict) and isinstance(doc.get("name"), str) and "base_url" in doc:
        if marker:
            raise ValueError("單一 endpoint 檔不能加 #name")
        return doc
    if not isinstance(doc, dict) or not isinstance(doc.get("endpoints"), list):
        raise ValueError("ENDPOINT 不是 endpoint 物件或 endpoints.json")
    selected = name if marker else doc.get("default")
    if not isinstance(selected, str) or not selected:
        raise ValueError("endpoints.json 沒有可用的 default")
    matches = [item for item in doc["endpoints"]
               if isinstance(item, dict) and item.get("name") == selected]
    if len(matches) != 1:
        raise ValueError("找不到唯一 endpoint：%s" % selected)
    return matches[0]


def _write_result(target, result):
    text = json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
    if target == "-":
        sys.stdout.write(text)
        return
    path = Path(target)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def _models(argv):
    if len(argv) != 1:
        return _cli_error("用法：aos-llm models ENDPOINT")
    try:
        endpoint = _resolve_endpoint(argv[0])
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _cli_error("ENDPOINT 解不開：%s" % exc)
    result = aos_llm.models(endpoint)
    if result["ok"]:
        for model_id in result["ids"]:
            print(model_id)
        return 0
    print("aos-llm: %s: %s" % (result["error"]["kind"], result["error"]["msg"]), file=sys.stderr)
    return 1


def _take_timeout(argv):
    if "--timeout-ms" not in argv:
        return None
    index = argv.index("--timeout-ms")
    if index + 1 >= len(argv):
        raise ValueError("--timeout-ms 缺少數值")
    try:
        timeout_ms = int(argv[index + 1])
    except ValueError:
        raise ValueError("--timeout-ms 必須是正整數") from None
    del argv[index:index + 2]
    if timeout_ms <= 0:
        raise ValueError("--timeout-ms 必須是正整數")
    return timeout_ms


def _call(argv):
    try:
        timeout_ms = _take_timeout(argv)
    except ValueError as exc:
        return _cli_error(str(exc))
    if len(argv) != 3:
        return _cli_error("用法：aos-llm call ENDPOINT REQ OUT [--timeout-ms N]")
    endpoint_spec, req_source, output = argv
    try:
        endpoint = _resolve_endpoint(endpoint_spec)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _cli_error("ENDPOINT 解不開：%s" % exc)
    try:
        req = _read_json(req_source)
    except (OSError, json.JSONDecodeError) as exc:
        return _cli_error("REQ 讀不到：%s" % exc)
    if timeout_ms is not None and isinstance(req, dict):
        req = dict(req)
        req["timeout_ms"] = timeout_ms
    result = aos_llm.call(endpoint, req)
    try:
        _write_result(output, result)
    except OSError as exc:
        return _cli_error("OUT 寫不進去：%s" % exc)
    if result["ok"]:
        return 0
    print("aos-llm: %s: %s" % (result["error"]["kind"], result["error"]["msg"]), file=sys.stderr)
    return 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("call", "models"):
        return _cli_error("用法：aos-llm call ENDPOINT REQ OUT [--timeout-ms N]；或 aos-llm models ENDPOINT")
    command = argv.pop(0)
    return _models(argv) if command == "models" else _call(argv)
