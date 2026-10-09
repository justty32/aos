"""合作來源逐件發布；unknown 時以原 event_id 重送。"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "..", "lib")]
import aos7_events_store as store  # noqa: E402


def publish(events_dir, kind, event_id, payload, *, must=False, source=None, node=None, config=None):
    """驗證並交給保存端；用法錯誤不 append，也不修改來源字典。"""
    def usage(detail):
        return {"ok": False, "seq": None, "dup": False, "why": "usage", "detail": detail}

    if not isinstance(event_id, str) or not event_id or len(event_id) > 128:
        return usage("event_id 須為 1～128 字元的字串")
    if not isinstance(kind, str) or not kind:
        return usage("kind 須為非空字串")
    if source is not None and not isinstance(source, dict):
        return usage("source 須為物件")
    try:
        json.dumps(payload, allow_nan=False)
    except (TypeError, ValueError, OverflowError):
        return usage("payload 須可 JSON 化")
    src = dict(source or {})
    if node is None:
        node = src.get("node")
    if node is None:
        state = store.load_state(events_dir)
        node = state.get("node") if isinstance(state, dict) else None
    if not isinstance(node, str) or not node:
        return usage("缺少有效 node")
    src.setdefault("node", node)
    rec = {"kind": kind, "capture": "published", "event_id": event_id, "source": src, "payload": payload}
    try:
        return store.append(events_dir, "must" if must else "obs", rec, node=node, config=config)
    except ValueError as e:   # store 判定的呼叫錯（例如 config 不合）：沒寫
        return usage(str(e))


def exit_code(result):
    """保存成功含重送回 0，其餘依原因分流。"""
    return 0 if result["ok"] else {"full": 3, "unknown": 4}.get(result.get("why"), 2)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    for flag in ("events", "kind", "event-id", "payload"):
        ap.add_argument("--" + flag, required=True)
    ap.add_argument("--must", action="store_true")
    ap.add_argument("--source")
    ap.add_argument("--node")
    a = ap.parse_args(argv)
    try:
        payload = json.loads(a.payload)
        source = json.loads(a.source) if a.source is not None else None
    except ValueError:
        result = {"ok": False, "seq": None, "dup": False, "why": "usage", "detail": "JSON 格式錯誤"}
    else:
        result = publish(a.events, a.kind, a.event_id, payload, must=a.must, source=source, node=a.node)
    print(json.dumps(result, ensure_ascii=False))
    return exit_code(result)


if __name__ == "__main__":
    sys.exit(main())
