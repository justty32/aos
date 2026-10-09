"""無鎖讀完整事件行；游標不跨越未證明的缺號。"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "..", "lib")]
from aos7_fs import read_json  # noqa: E402


def _number(value, default=0):
    return value if type(value) is int and value >= 0 else default


def _snapshot(events_dir, channel):
    """列段與活躍檔；保留壞行的位置，尾端半行不算紀錄。"""
    rows, errors = [], []
    path = os.path.join(events_dir, "state.json")
    state = read_json(path)
    if not isinstance(state, dict):
        if os.path.lexists(path):
            errors.append({"kind": "state_unreadable"})
        state = {}
    channels = state.get("channels")
    st = channels.get(channel, {}) if isinstance(channels, dict) else {}
    st = st if isinstance(st, dict) else {}
    proven = max(_number(st.get("dropped_upto")), _number(st.get("acked_upto")))
    try:
        names = sorted(n for n in os.listdir(events_dir) if re.fullmatch(channel + r"\.[0-9]{12}\.jsonl", n))
    except FileNotFoundError:
        names = []
    except OSError:
        names = []
        errors.append({"kind": "dir_unreadable"})
    names.append(channel + ".active.jsonl")
    for name in names:
        try:
            with open(os.path.join(events_dir, name), "rb") as f:
                offset = 0
                for line in f:
                    if not line.endswith(b"\n"):
                        break
                    try:
                        rec = json.loads(line)
                        if not isinstance(rec, dict) or type(rec.get("seq")) is not int or rec["seq"] <= 0:
                            raise ValueError()
                    except ValueError:
                        errors.append({"kind": "bad_line", "file": name, "offset": offset})
                        rec = None
                    rows.append((rec, name, offset))
                    offset += len(line)
        except FileNotFoundError:
            pass  # 輪替／刪段的缺號由第二次快照判定。
        except OSError:
            errors.append({"kind": "file_unreadable", "file": name})
    earliest = min((r["seq"] for r, _, _ in rows if r is not None), default=None)
    return rows, errors, proven, earliest if earliest is not None else _number(st.get("next_seq"), proven + 1) or 1


def _scan(events_dir, channel, cursor, kind, source, round, run, limit, final):
    """final=False 時任何洞（含看似已淘汰）都先回報要重列；第二次才以 state 的淘汰界線判 retention。"""
    rows, errors, proven, earliest = _snapshot(events_dir, channel)
    # 不給游標＝從最早仍保留者讀起，但不晚於已證明淘汰界線之後（列檔與輪替交錯時列到的最小 seq 可能偏晚）。
    expected = min(earliest, proven + 1) if cursor is None else cursor
    result = {"records": [], "next_cursor": expected, "earliest_cursor": earliest,
              "coverage": [], "gaps": [], "errors": errors}
    if expected < earliest and earliest - 1 <= proven and final:
        result["gaps"].append({"kind": "retention", "from": expected, "to": earliest - 1})
        expected = earliest
    elif expected < earliest and not any(rec is not None for rec, _, _ in rows):
        errors.append({"kind": "seq_hole", "from": expected, "to": earliest - 1})
        return result, True
    result["next_cursor"] = expected
    seen, bad, previous = set(), 0, None
    for rec, name, offset in rows:
        if rec is None:
            bad += 1
            continue
        seq = rec["seq"]
        # 起點前的紀錄不消耗游標；起點後倒退的紀錄仍須攔住。
        if previous is None and seq < expected:
            bad = 0
            continue
        if previous is not None and seq <= previous:
            errors.append({"kind": "seq_order", "seq": seq, "previous": previous, "file": name, "offset": offset})
            break
        if seq > expected and seq - expected > bad:
            if not final:
                return result, True
            if seq - 1 <= proven:
                result["gaps"].append({"kind": "retention", "from": expected, "to": seq - 1})
            else:
                errors.append({"kind": "seq_hole", "from": expected, "to": seq - 1})
                return result, True
        bad, previous, expected = 0, seq, seq + 1
        result["next_cursor"] = expected
        src = rec.get("source")
        src = src if isinstance(src, dict) else {}
        capture, nid = rec.get("capture"), src.get("node")
        # 使用相等比較，未知格式的來源也不會使讀者崩潰。
        group = json.dumps([capture, nid], sort_keys=True)
        if group not in seen:
            seen.add(group)
            mode = {"sample": "sampled", "source_log": "log_tail", "published": "per_event"}.get(capture, "unknown") if isinstance(capture, str) else "unknown"
            result["coverage"].append({"capture": capture, "source": nid, "mode": mode, "from_seq": seq})
        matches = all(want is None or src.get(key) == want for key, want in (("node", source), ("round", round), ("run", run)))
        payload = rec.get("payload")
        if matches and rec.get("kind") == "gap" and isinstance(payload, dict):
            gap = {"kind": payload.get("why"), "seq": seq, "source": src}
            if payload.get("why") == "round_skip":
                gap.update({k: payload.get(k) for k in ("from", "to")})
            result["gaps"].append(gap)
        if matches and (kind is None or rec.get("kind") == kind):
            result["records"].append(rec)
            if len(result["records"]) >= limit:
                break
    return result, False


def read(events_dir, channel, cursor=None, *, kind=None, source=None, round=None, run=None, limit=100):
    """回紀錄、覆蓋方式、缺口與下一游標；有洞時重新列檔一次。"""
    if channel not in ("obs", "must") or (cursor is not None and (type(cursor) is not int or cursor < 1)):
        raise ValueError("channel 或 cursor 不合法")
    if type(limit) is not int or limit < 1:
        raise ValueError("limit 須為正整數")
    args = (events_dir, channel, cursor, kind, source, round, run, limit)
    result, hole = _scan(*args, False)
    return _scan(*args, True)[0] if hole else result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--events", required=True)
    ap.add_argument("--channel", choices=("obs", "must"), default="obs")
    for name in ("cursor", "round", "run", "ack"):
        ap.add_argument("--" + name, type=int)
    for name in ("kind", "source"):
        ap.add_argument("--" + name)
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--text", action="store_true")
    a = ap.parse_args(argv)
    if a.ack is not None:
        if a.channel != "must" or a.ack < 0:
            ap.error("--ack 須使用 must 通道與非負整數")
        import aos7_events_store as store
        print(json.dumps({"acked_upto": store.ack(a.events, a.ack)}))
        return 0
    try:
        result = read(a.events, a.channel, a.cursor, kind=a.kind, source=a.source, round=a.round, run=a.run, limit=a.limit)
    except ValueError as e:
        ap.error(str(e))
    if a.text:
        for rec in result["records"]:
            src = rec.get("source")
            print(rec["seq"], rec.get("kind"), src.get("node") if isinstance(src, dict) else None,
                  json.dumps(rec.get("payload"), ensure_ascii=False))
        for key, label in (("gaps", "gap"), ("errors", "error")):
            for entry in result[key]:
                print("#", label, json.dumps(entry, ensure_ascii=False))
        print("# next_cursor", result["next_cursor"])
    else:
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
