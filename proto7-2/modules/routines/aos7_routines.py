"""tick 驅動的兩張事務表：先寫執行證據，放鎖後同步執行；未知保留到下一回合。"""
import argparse
import datetime as dt
import math
import os
import re
import sys
TOP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [os.path.join(TOP, "lib"), os.path.join(TOP, "modules", "tools")]
from aos7_fs import N, OK, Unknown, edit_json, fact, test_point  # noqa: E402
from aos7_taskside import task_env, wait_tock  # noqa: E402
from aos_exec import run_target  # noqa: E402
KINDS = ("routines", "schedule")
ENTRY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aos7-routines")
def instant(value):
    """本地無時區與帶時區的 ISO 都換成同一條時間軸。"""
    return (dt.datetime.fromisoformat(value) if isinstance(value, str) else value).astimezone()
def interval(value):
    m = re.fullmatch(r"([1-9][0-9]*)([rsmhd])", value)
    if not m:
        raise ValueError("every 要正整數加 r/s/m/h/d")
    return int(m[1]) * {"r": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}[m[2]], m[2] == "r"
def short(t):
    """顯示用：到秒、本地時區。"""
    return t.astimezone().strftime("%Y-%m-%d %H:%M:%S")
def table(value):
    if not isinstance(value, dict) or not isinstance(value.get("rows"), list):
        raise Unknown('表不是 {"rows": [...]}')
    return value
def empty(kind):
    cols = ["name", "every", "inst", "last_round", "last_time", "last_code"] if kind == "routines" else ["name", "at", "inst", "claimed"]
    return dict(contract="wf-table/1", source="workflows/" + kind + ".md", extracted=dt.date.today().isoformat(), columns=cols, rows=[])
def load(path):
    state, value = fact(path)
    if state == N:
        return None
    if state != OK:
        raise Unknown(str(value))
    return table(value)
def due(row, kind, round, now):
    if not isinstance(row, dict) or not isinstance(row.get("name"), str) or not row["name"].strip() or not row.get("inst"):
        raise ValueError("name／inst 缺失")
    if not all(isinstance(v, str) for v in row.values()):
        raise ValueError("欄位必須是字串")
    seconds = float(row.get("timeout") or "600")
    if not math.isfinite(seconds) or not 0 < seconds <= 1e9:
        raise ValueError("timeout 要 0～1e9 秒")
    if kind == "schedule":
        return bool(row.get("claimed")) or instant(row["at"]) <= now
    n, rounds = interval(row.get("every", ""))
    if rounds and round is None:
        return False  # 手動 ls --run 沒有回合，r 型只交給 daemon
    last = row.get("last_round" if rounds else "last_time", "")
    delta = round - int(last) if rounds and last else (now - instant(last)).total_seconds() if last else None
    return delta is None or delta < 0 or delta >= n
def warn(why):
    print(why, file=sys.stderr)
def step(node, round, now):
    """處理一回合；now 是 datetime 或 ISO 字串，不自行取時間，測試可直接傳假時間。
    round=None 是人手動 `ls --run`：只看時間（秒型 routine 與 schedule），r 型跳過。回跑了幾件。"""
    now = instant(now)
    stamp = now.isoformat()
    rnd = "" if round is None else str(round)
    ran = 0
    for kind in KINDS:
        path = os.path.join(node, "wf", kind + ".json")
        try:
            snapshot = load(path)
            for item in snapshot["rows"] if snapshot else []:
                try:
                    if not due(item, kind, round, now):
                        continue
                    claimed = []
                    def claim(cur):
                        if cur is None:
                            return None
                        rows = table(cur)["rows"]
                        for row in rows:
                            if isinstance(row, dict) and row.get("name") == item["name"] and due(row, kind, round, now) \
                                    and all(row.get(k, "") == item.get(k, "") for k in ("last_round", "last_time", "claimed")):
                                if kind == "schedule" and row.get("claimed"):
                                    rows.remove(row)
                                    warn("schedule %s 被打斷、不重跑" % row["name"])
                                else:
                                    row.update(last_round=rnd, last_time=stamp, last_code="running") if kind == "routines" else row.update(claimed=stamp)
                                    claimed.append(dict(row))
                                return cur
                        return None
                    edit_json(path, claim, timeout=1)
                    if not claimed:
                        continue
                    row = claimed[0]
                    test_point("routines-after-claim")
                    code, _ = run_target(os.path.abspath(os.path.join(node, row["inst"])), max(1, int(float(row.get("timeout") or "600") * 1000)))
                    def finish(cur):
                        if cur is None:
                            return None
                        rows = table(cur)["rows"]
                        for current in rows:
                            if not isinstance(current, dict) or current.get("name") != row["name"]:
                                continue
                            if kind == "routines" and current.get("last_round") == rnd and current.get("last_time") == stamp:
                                current["last_code"] = str(code)
                                return cur
                            if kind == "schedule" and current.get("claimed") == stamp:
                                rows.remove(current)
                                return cur
                        return None
                    ran += 1
                    where = "" if round is None else " round %s" % round
                    print(("routine %s%s code %s" % (row["name"], where, code)) if kind == "routines" else "schedule %s code %s" % (row["name"], code), flush=True)
                    edit_json(path, finish, timeout=1)
                except (ValueError, KeyError, TypeError) as e:
                    warn("%s 跳過列 %r：%s" % (kind, item, e))
        except (Unknown, OSError) as e:
            warn("%s unknown：%s" % (kind, e))
    return ran
HELP = """把要做的事寫進 node 的清單，到時候自動跑。
  add  加一件：--every 10s（每隔一段時間做）或 --at +5s／ISO 時刻（只做一次）
  ls   看清單；加 --run 先把現在到期的立刻做掉（不必開 daemon）
  rm   刪一件
間隔單位 s/m/h/d；r＝回合＝daemon 每醒一次，只有 daemon 開著才算。"""
class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, message + "\n")
def main(argv=None):
    raw = sys.argv[1:] if argv is None else argv
    if not raw:
        e, last = task_env(), 0
        while True:
            last = wait_tock(e["task"], last)
            step(e["node"], last, dt.datetime.now().astimezone())
    ap = Parser(prog="aos7-routines", description=HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="op", required=True, metavar="{add,ls,rm}")
    tips = {"add": "加一件要做的事", "ls": "看清單（--run 先把到期的做掉）", "rm": "依名字刪一件"}
    for op in ("add", "ls", "rm"):
        p = sub.add_parser(op, help=tips[op], description=tips[op])
        p.add_argument("node", help="node 資料夾（清單放在它的 wf/ 底下）")
        if op != "ls":
            p.add_argument("name", help="這件事的名字（清單內唯一）")
        if op == "ls":
            p.add_argument("--run", action="store_true", help="先把現在到期的立刻做一次（秒型與 schedule；r 型只在 daemon 開著時跑）")
        if op == "add":
            g = p.add_mutually_exclusive_group(required=True)
            g.add_argument("--every", help="每隔多久做一次：正整數加 s/m/h/d，例 10s、1h；r＝daemon 回合，例 3r")
            g.add_argument("--at", help="只做一次的時刻：+5s／+2m 這種相對時間，或 ISO 時刻")
            p.add_argument("inst", metavar="program", help="要跑的東西：可執行檔、inst.json 或資料夾；相對路徑以 node 為準")
            p.add_argument("--timeout", default="600", help="每次最多跑幾秒（預設 600）")
    a = ap.parse_args(raw)
    try:
        now = dt.datetime.now().astimezone()
        paths = {k: os.path.join(os.path.abspath(a.node), "wf", k + ".json") for k in KINDS}
        tables = {k: load(paths[k]) for k in KINDS}
        if a.op == "ls":
            if a.run:
                if not step(os.path.abspath(a.node), None, now):
                    print("（現在沒有到期的事）")
                now = dt.datetime.now().astimezone()
                tables = {k: load(paths[k]) for k in KINDS}
            if not any(t and t["rows"] for t in tables.values()):
                print("（清單是空的）")
            for kind, t in tables.items():
                for row in t["rows"] if t else []:
                    try:
                        due(row, kind, 0, now)
                    except (ValueError, KeyError, TypeError) as e:
                        print("%s bad row %r: %s" % (kind, row, e))
                        continue
                    if kind == "schedule":
                        print("schedule %s  at %s%s" % (row["name"], short(instant(row["at"])), "  running" if row.get("claimed") else ""))
                    else:
                        n, rounds = interval(row["every"])
                        last = row.get("last_round" if rounds else "last_time", "")
                        nxt = ("round 1（daemon 開著才跑）" if rounds else "now") if not last else "round %d" % (int(last) + n) if rounds else short(instant(last) + dt.timedelta(seconds=n))
                        shown = last if rounds or not last else short(instant(last))
                        print("routine %s  every %s  last %s  code %s  next %s" % (row["name"], row["every"], shown or "never", row.get("last_code") or "-", nxt))
            return 0
        if a.op == "rm":
            found = []
            def remove(cur):
                if cur is None:
                    return None
                rows = table(cur)["rows"]
                kept = [r for r in rows if not isinstance(r, dict) or r.get("name") != a.name]
                if len(kept) == len(rows):
                    return None
                found.append(True)
                return dict(cur, rows=kept)
            for path in paths.values():
                edit_json(path, remove, timeout=1)
            if not found:
                warn("清單裡沒有 %s" % a.name)
                return 1
            print("removed %s" % a.name)
            return 0
        kind = "routines" if a.every else "schedule"
        at = (now + dt.timedelta(seconds=interval(a.at[1:])[0])).isoformat() if a.at and a.at.startswith("+") and not a.at.endswith("r") else a.at
        row = dict(name=a.name, inst=a.inst, timeout=a.timeout, **({"every": a.every} if a.every else {"at": instant(at).isoformat()}))
        due(row, kind, 0, now)
        if any(isinstance(r, dict) and r.get("name") == a.name for t in tables.values() if t for r in t["rows"]):
            warn("名字 %s 已經在清單裡；先 rm 再 add" % a.name)
            return 1
        def add(cur):
            cur = empty(kind) if cur is None else table(cur)
            if any(isinstance(r, dict) and r.get("name") == a.name for r in cur["rows"]):
                raise ValueError("name 重複")
            return dict(cur, columns=list(dict.fromkeys(cur.get("columns", empty(kind)["columns"]) + ["timeout"])), rows=cur["rows"] + [dict.fromkeys(empty(kind)["columns"], "") | row])
        def install(cur):
            cur = {"tasks": []} if cur is None else cur
            if not isinstance(cur, dict) or not isinstance(cur.get("tasks"), list):
                raise Unknown("tasks.json 格式不合")
            if any(isinstance(t, dict) and t.get("name") == "routines" for t in cur["tasks"]):
                return None
            return dict(cur, tasks=cur["tasks"] + [dict(name="routines", mode="keep", argv=["python3", ENTRY])])
        edit_json(os.path.join(a.node, ".aos", "tasks.json"), install, timeout=1)
        edit_json(paths[kind], add, timeout=1)
        if not os.path.exists(os.path.join(a.node, a.inst)):
            warn("警告：inst 不存在，仍已登記")
        print("added %s %s %s" % ("routine" if a.every else "schedule", a.name, "every " + a.every if a.every else "at " + short(instant(row["at"]))))
        return 0
    except (Unknown, OSError) as e:
        warn("unknown：%s" % e)
        return 3
    except (ValueError, KeyError, TypeError) as e:
        warn(str(e))
        return 1
