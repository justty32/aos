"""無鎖讀完整事件行；游標不跨越未證明的缺號。"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "..", "lib")]
from aos7_events_cli import Parser, ack_main, missing, say
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
    proven = _number(st.get("dropped_upto"))   # 只有 dropped_upto 算淘汰證明；acked_upto 以前的紀錄可能還在磁碟上
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


READ_EPILOG = """例子：
  aos7-events read --events /tmp/demo/events --text
  aos7-events read --events /tmp/demo/events --channel must --text
  aos7-events ack --events /tmp/demo/events 1   # 印 {"acked_upto": 1}

讀到不算處理完；must 本子要 ack 才算，沒 ack 的會一直留著，滿了 pub --must 會被拒。"""


def main(argv=None):
    ap = Parser(prog="aos7-events read", description="讀 events 夾裡的事件；預設印一行 JSON，加 --text 一筆一行。",
                                 epilog=READ_EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--events", required=True, help="events 夾路徑")
    ap.add_argument("--channel", choices=("obs", "must"), default="obs", help="讀哪本：obs（預設）或 must")
    ap.add_argument("--cursor", type=int, help="從這個 seq 開始讀；把上次的 next_cursor 帶回來就接著讀")
    ap.add_argument("--round", type=int, help="只看這個回合的事件")
    ap.add_argument("--run", type=int, help="只看這個 run 的事件")
    ap.add_argument("--ack", type=int, help="（舊寫法，下一輪移除；改用 aos7-events ack）確認 seq ≤ 這個數的都處理完了；只做確認、不讀")
    ap.add_argument("--kind", help="只看這種 kind")
    ap.add_argument("--source", help="只看這個來源 node")
    ap.add_argument("--limit", type=int, default=100, help="最多幾筆（預設 100）")
    ap.add_argument("--text", action="store_true", help="一筆一行：seq kind node payload，最後一行 # next_cursor")
    a = ap.parse_args(argv)
    if a.ack is not None:
        if a.channel != "must" or a.ack < 0:
            ap.error("--ack 須使用 must 通道與非負整數")
        code = ack_main(a.events, a.ack)
        if code == 0:   # 失敗時 stderr 只留那一行錯誤（錯誤藍圖 §3）
            say("read --ack 是舊寫法，下一輪移除。改用 aos7-events ack --events %s %d" % (a.events, a.ack))
        return code
    try:
        result = read(a.events, a.channel, a.cursor, kind=a.kind, source=a.source, round=a.round, run=a.run, limit=a.limit)
    except ValueError as e:
        ap.error(str(e))
    if missing(a.events):   # 用法先判；拼錯路徑不該看起來像空帳本
        say("沒有這個 events 夾 %s。檢查 --events 路徑" % a.events)
        return 1
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
