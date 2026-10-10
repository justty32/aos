"""事件保存端：同鎖追加、恢復、輪替；完整換行是保存邊界（spec.md）。"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "lib"))
from aos7_fs import N, OK, Unknown, fact, is_int, json_sha256, locked, now, test_point, write_json  # noqa: E402

DEFAULTS = {"keep_segments": 4, "segment_bytes": 1048576, "max_record_bytes": 65536}
CHANNELS = ("obs", "must")
LOCK_TIMEOUT = 5
MAX_KEEP = 4   # 每通道封存上限；2(4+1)+2＝12 檔（使用者硬約束）


def _config(config):
    """新建時只取已知正整數設定。"""
    cfg = dict(DEFAULTS)
    for k in DEFAULTS:
        if config is not None and k in config:
            if not is_int(config[k]) or config[k] <= 0:
                raise ValueError("%s 必須是正整數" % k)
            if k == "keep_segments" and config[k] > MAX_KEEP:
                raise ValueError("keep_segments 不得超過 %d（檔數上限 12）" % MAX_KEEP)
            cfg[k] = config[k]
    return cfg


def _valid(st):
    """壞 state 不猜、不覆蓋；必要欄位及型別都須完整。"""
    if not isinstance(st, dict) or (not is_int(st.get("v")) or st["v"] != 1) or not isinstance(st.get("node"), str) or not st["node"]:
        return False
    cfg, channels = st.get("config"), st.get("channels")
    if not isinstance(cfg, dict) or not all(is_int(cfg.get(k)) and cfg[k] > 0 for k in DEFAULTS):
        return False
    if cfg["keep_segments"] > MAX_KEEP:
        return False
    if not isinstance(channels, dict) or not isinstance(st.get("sample"), dict) or "daemon_log" not in st:
        return False
    if st.get("status_last") is not None and not isinstance(st["status_last"], str):
        return False
    if not all(isinstance(k, str) and is_int(v) for k, v in st["sample"].items()):
        return False
    dl = st["daemon_log"]
    if dl is not None and not (isinstance(dl, dict) and all(is_int(dl.get(k)) for k in ("offset", "dev", "ino"))):
        return False
    for ch in CHANNELS:
        c = channels.get(ch)
        keys = ("next_seq", "active_first", "active_bytes", "dropped_upto", "torn")
        keys += ("acked_upto", "refused") if ch == "must" else ()
        if not isinstance(c, dict) or not all(is_int(c.get(k)) and c[k] >= 0 for k in keys):
            return False
        if "torn_cut" in c and not (is_int(c["torn_cut"]) and c["torn_cut"] >= 0):
            return False
        segs = c.get("segments")
        if c["next_seq"] < 1 or c["active_first"] < 1 or not isinstance(segs, list):
            return False
        if not all(is_int(s) and s > 0 for s in segs) or segs != sorted(set(segs)):
            return False
    return True


def _state(d, node=None, config=None, create=True):
    """讀權威 state；不存在才新建。"""
    status, st = fact(os.path.join(d, "state.json"))
    if status == N:
        if not create:
            return None
        st = {"v": 1, "node": node, "config": _config(config), "channels": {}, "sample": {}, "daemon_log": None, "status_last": None}
        for ch in CHANNELS:
            st["channels"][ch] = {"next_seq": 1, "active_first": 1, "active_bytes": 0,
                                  "segments": [], "dropped_upto": 0, "torn": 0}
        st["channels"]["must"].update(acked_upto=0, refused=0)
    elif status != OK or not _valid(st):
        raise Unknown("events state 不可讀或缺欄")
    if node is not None and st["node"] != node:
        raise Unknown("events node 不符")
    return st


def _records(path):
    """只收完整換行、dict 且 seq 真整數的行；讀取錯誤往外傳。"""
    try:
        f = open(path, "rb")
    except FileNotFoundError:
        return
    with f:
        for line in f:
            if not line.endswith(b"\n"):
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict) and is_int(obj.get("seq")):
                yield obj


def status_key(ev):
    """daemon 最近事件的去重鍵（存 state.status_last，跨重起）。"""
    return json_sha256(ev)


def _derive(st, obj):
    """以已保存紀錄推回來源進度；gap 也有進度。"""
    src = obj.get("source")
    if not isinstance(src, dict):
        return
    if obj.get("capture") == "sample" and isinstance(src.get("node"), str) and is_int(src.get("round")):
        st["sample"][src["node"]] = src["round"]
    if obj.get("capture") == "source_log" and all(is_int(src.get(k)) for k in ("log_dev", "log_ino", "off_to")):
        st["daemon_log"] = {"offset": src["off_to"], "dev": src["log_dev"], "ino": src["log_ino"]}
    payload = obj.get("payload")
    if (obj.get("kind") == "daemon.status" and obj.get("capture") == "sample" and src.get("node") == ".aosd"
            and isinstance(payload, dict) and isinstance(payload.get("last_event"), dict)):
        st["status_last"] = status_key(payload["last_event"])


def _scan(st, c, path):
    """掃描一次；用掃描前門檻推導，保留檔內順序。"""
    old, first = c["next_seq"], None
    for obj in _records(path):
        if first is None:
            first = obj["seq"]
        if obj["seq"] >= old:
            c["next_seq"] = max(c["next_seq"], obj["seq"] + 1)
            _derive(st, obj)
    return first


def _segment(d, ch, seq):
    return os.path.join(d, "%s.%012d.jsonl" % (ch, seq))


def _recover(d, st):
    """持鎖恢復：清暫存、補段清單與尾端進度、裁半行。"""
    names, save = os.listdir(d), False
    for name in names:
        if name.startswith(".state.json.tmp."):
            os.unlink(os.path.join(d, name))
    for ch in CHANNELS:
        c = st["channels"][ch]
        pattern = re.compile(r"^" + ch + r"\.(\d{12})\.jsonl$")
        files = sorted(int(m.group(1)) for name in names if (m := pattern.fullmatch(name)))
        discovered = [s for s in files if s not in c["segments"]]
        for s in discovered:
            _scan(st, c, _segment(d, ch, s))
        c["segments"] = files
        active = os.path.join(d, ch + ".active.jsonl")
        pending = c.pop("torn_cut", None)
        save = save or pending is not None
        try:
            size = os.stat(active).st_size
        except FileNotFoundError:
            c["active_first"], c["active_bytes"] = c["next_seq"], 0
        else:
            if size != c["active_bytes"] or discovered or pending is not None:
                with open(active, "rb") as f:
                    data = f.read()
                if data and not data.endswith(b"\n"):
                    size = data.rfind(b"\n") + 1
                    if size != pending:
                        # torn 與截點同一次存，截檔前後被殺都不漏記、不重記（V2）。
                        c["torn"] += 1
                        c["torn_cut"] = size
                        write_json(os.path.join(d, "state.json"), st)
                        test_point("events:after-torn-save")
                        del c["torn_cut"]
                    os.truncate(active, size)
                    test_point("events:after-truncate")
                    save = True
                first = _scan(st, c, active)
                c["active_first"] = first if first is not None else c["next_seq"]
                c["active_bytes"] = size
        earliest = files[0] if files else c["active_first"]
        c["dropped_upto"] = max(c["dropped_upto"], earliest - 1)
        if ch == "obs":
            # rename 後、清段前被殺會多一段：恢復當下補清，檔數不超過上限。
            while len(c["segments"]) > st["config"]["keep_segments"]:
                _remove_first(d, ch, c)
    if save:
        # 截點標記不能留到之後的寫入：否則那時再撕裂、截在同一點會被當成已記過。
        write_json(os.path.join(d, "state.json"), st)


def _remove_first(d, ch, c):
    """先刪實檔再更新記憶體；被殺由恢復補回。"""
    os.unlink(_segment(d, ch, c["segments"][0]))
    test_point("events:after-unlink")
    c["segments"].pop(0)
    earliest = c["segments"][0] if c["segments"] else c["active_first"]
    c["dropped_upto"] = max(c["dropped_upto"], earliest - 1)


def _clean_must(d, c):
    """累積確認只清整段，遇未確認段立即停。"""
    while c["segments"]:
        following = c["segments"][1] if len(c["segments"]) > 1 else c["active_first"]
        if following - 1 > c["acked_upto"]:
            break
        _remove_first(d, "must", c)


def _result(why=None, seq=None, dup=False, ignored=False):
    result = {"ok": why is None, "seq": seq, "dup": dup, "why": why}
    if ignored:
        result["config_ignored"] = True
    return result


def _append(d, ch, rec, st, ignored):
    """鎖內寫一筆；所有可回復結果先保存恢復進度。"""
    path = os.path.join(d, "state.json")
    c, cfg = st["channels"][ch], st["config"]
    active = os.path.join(d, ch + ".active.jsonl")
    if "event_id" in rec:
        for p in [_segment(d, ch, s) for s in c["segments"]] + [active]:
            for obj in _records(p):
                if obj.get("event_id") == rec["event_id"]:
                    write_json(path, st)
                    return _result(seq=obj["seq"], dup=True, ignored=ignored)
    seq = c["next_seq"]
    obj = {"v": 1, "stream": st["node"] + "/" + ch, "seq": seq,
           "kind": rec.get("kind"), "capture": rec.get("capture")}
    if "event_id" in rec:
        obj["event_id"] = rec["event_id"]
    obj.update(source=rec.get("source"), at=rec.get("at", now()), payload=rec.get("payload"))
    obj.update({k: v for k, v in rec.items() if k not in obj})
    line = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
    if len(line) > cfg["max_record_bytes"]:
        write_json(path, st)
        return _result("too_large", ignored=ignored)
    if c["active_bytes"] >= cfg["segment_bytes"]:
        dest = _segment(d, ch, c["active_first"])
        if os.path.lexists(dest) or any(s >= c["active_first"] for s in c["segments"]):
            # 段範圍重疊＝state 與檔對不上；先判，任何清段之前就停（不覆蓋、不據此刪段）。
            raise Unknown("輪替目的已存在或段範圍重疊")
        if ch == "must" and len(c["segments"]) >= cfg["keep_segments"]:
            _clean_must(d, c)
            if len(c["segments"]) >= cfg["keep_segments"]:
                c["refused"] += 1
                write_json(path, st)
                return _result("full", ignored=ignored)
        os.rename(active, dest)
        test_point("events:after-rename")
        c["segments"].append(c["active_first"])
        c["active_first"], c["active_bytes"] = seq, 0
        if ch == "obs":
            while len(c["segments"]) > cfg["keep_segments"]:
                _remove_first(d, ch, c)
        else:
            _clean_must(d, c)
        # 先存輪替後的 state：之後寫入被殺時，新活躍段大小不會碰巧等於舊 active_bytes 而走快速路徑（astra E1 #1）。
        write_json(path, st)
    empty = c["active_bytes"] == 0
    with open(active, "ab") as f:
        k = len(line) // 2
        f.write(line[:k])
        f.flush()
        test_point("events:after-partial")
        f.write(line[k:])
        f.flush()
    test_point("events:after-append")
    c["next_seq"] += 1
    c["active_bytes"] += len(line)
    if empty:
        c["active_first"] = seq
    _derive(st, obj)
    write_json(path, st)
    return _result(seq=seq, ignored=ignored)


def append(events_dir, channel, rec, *, node, config=None):
    """保存確認；呼叫錯丟 ValueError，未知可能已保存，照 event_id 重送。"""
    if channel not in CHANNELS or not isinstance(rec, dict) or not isinstance(node, str) or not node:
        raise ValueError("channel、rec 或 node 不合")
    if any(k in rec for k in ("seq", "stream", "v")):
        raise ValueError("rec 不可帶保存端欄位")
    if rec.get("capture") == "published" and not (isinstance(rec.get("event_id"), str) and rec["event_id"]):
        raise ValueError("published 必須帶 event_id")
    ignored = False
    try:
        with locked(os.path.join(events_dir, "state.json"), timeout=LOCK_TIMEOUT):
            st = _state(events_dir, node, config)
            ignored = config is not None and any(st["config"].get(k) != v for k, v in config.items())
            _recover(events_dir, st)
            return _append(events_dir, channel, rec, st, ignored)
    except (Unknown, OSError):
        return _result("unknown", ignored=ignored)


def ack(events_dir, upto):
    """must 消費確認，累積且夾到已保存尾端；不刪段。"""
    if not is_int(upto):
        raise ValueError("upto 必須是整數")
    try:
        # 沒 state 的既有夾不拿鎖；不存在的夾沿用原行為。
        if os.path.isdir(events_dir) and fact(os.path.join(events_dir, "state.json"))[0] == N:
            return 0
        with locked(os.path.join(events_dir, "state.json"), timeout=LOCK_TIMEOUT):
            st = _state(events_dir, create=False)
            if st is None:
                return 0
            _recover(events_dir, st)
            c = st["channels"]["must"]
            c["acked_upto"] = max(c["acked_upto"], min(upto, c["next_seq"] - 1))
            write_json(os.path.join(events_dir, "state.json"), st)
            return c["acked_upto"]
    except OSError as e:
        raise Unknown(str(e)) from e


def load_state(events_dir):
    """唯讀、不鎖、不恢復；不存在或讀不出回 None。"""
    status, st = fact(os.path.join(events_dir, "state.json"))
    return st if status == OK and isinstance(st, dict) else None


def recover(events_dir, *, node, config=None):
    """取樣器拿權威進度；建檔／恢復並保存，未知回 None。"""
    if not isinstance(node, str) or not node:
        raise ValueError("node 必須是非空字串")
    try:
        with locked(os.path.join(events_dir, "state.json"), timeout=LOCK_TIMEOUT):
            st = _state(events_dir, node, config)
            _recover(events_dir, st)
            write_json(os.path.join(events_dir, "state.json"), st)
            return st
    except (Unknown, OSError):
        return None
