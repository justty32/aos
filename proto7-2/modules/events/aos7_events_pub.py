"""合作來源逐件發布；unknown 時以原 event_id 重送。"""
import argparse
import json
import os
import sys
import uuid

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


EPILOG = """例子（events 夾不存在會自動建）：
  aos7-events pub --events /tmp/demo/events --kind hello --payload '{"msg": "hi"}'
  aos7-events pub --events /tmp/demo/events --kind job.done --payload '{"id": 7}' --event-id job/7 --must

obs＝一般紀錄本，滿了丟最舊；must＝一定要有人讀完 ack 的本子，沒 ack 而滿了會拒收（退出碼 3）。
退出碼：0 存好（含重送 dup）／2 用法錯／3 must 滿了被拒／4 不確定存了沒（用同 --event-id 重送）。"""


def default_node(events_dir):
    """CLI 新建 events 夾時的 node：上一層資料夾名（<root>/<node>/events 慣例）。"""
    name = os.path.basename(os.path.dirname(os.path.abspath(events_dir)))
    return name or None


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aos7-events pub", description="寫一筆事件到 events 夾，印一行 JSON 結果（seq 是它的編號）。",
                                 epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--events", required=True, help="events 夾路徑（不存在會自動建）")
    ap.add_argument("--kind", required=True, help="事件種類，任意非空字串，例如 hello、job.done")
    ap.add_argument("--payload", required=True, help="事件內容，一段 JSON，例如 '{\"msg\": \"hi\"}'")
    ap.add_argument("--event-id", help="這件事的身分；同 id 重送不會多一筆（回 dup true）。不給就自動產生一個（印在結果的 event_id），那就不防重複")
    ap.add_argument("--must", action="store_true", help="寫進 must 本子（一定要有人讀完 ack）；不加就寫 obs")
    ap.add_argument("--source", help="來源資訊，JSON 物件（選用）")
    ap.add_argument("--node", help="node 名；省略時用已建 state 的，新建時用 events 夾上一層的資料夾名")
    a = ap.parse_args(argv)
    auto_id = a.event_id is None
    event_id = "auto/" + uuid.uuid4().hex if auto_id else a.event_id
    try:
        payload = json.loads(a.payload)
        source = json.loads(a.source) if a.source is not None else None
    except ValueError:
        result = {"ok": False, "seq": None, "dup": False, "why": "usage", "detail": "JSON 格式錯誤"}
    else:
        node = a.node
        if node is None and not (isinstance(source, dict) and "node" in source) \
                and not os.path.lexists(os.path.join(a.events, "state.json")):
            node = default_node(a.events)
        result = publish(a.events, a.kind, event_id, payload, must=a.must, source=source, node=node)
        if auto_id and result.get("why") != "usage":   # 存好或 unknown 都印，unknown 才能照同 id 重送
            result["event_id"] = event_id
    print(json.dumps(result, ensure_ascii=False))
    return exit_code(result)

if __name__ == "__main__":
    sys.exit(main())
