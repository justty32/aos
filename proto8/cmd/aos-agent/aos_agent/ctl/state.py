# aos_agent/ctl/state.py - 顯示單隻 agent 的狀態：總覽（每類一行）或點菜（某幾類的細節）；只給數字與事實、不給建議（11-10 self-family self_state）。
import aos_ws
import json
import os
import subprocess
import sys
import time
from .. import common
from ..common import bad_args, Fail, parse, target
from ..decl import agent_decl, def_of, show_limits
from .. import declared_files
from ..hints import label, queued


PARTS = ("who", "state", "tools", "llm", "hooks", "history", "mailbox", "children", "resources", "time")
HELP = """aos-agent ctl state - show one agent's state (status = the same)

usage: aos-agent [--daemon D] ctl state [--target NAME] [-j] [PART... | all]

parts:
  who        name, definition, workspace, stack
  state      daemon phase, reason, queued letters, latest answer
  tools      its tools (aos-agent tools ls), with its own changes
  llm        its brain settings (aos-agent llm ls)
  hooks      its hooks (aos-agent hook ls)
  history    how many messages and bytes; the last ones (aos-agent history ls)
  mailbox    letters waiting in its mailbox (aos-mailbox peek)
  children   agents it started with agents_children, and its quota
  resources  limits on the daemon table; memory, cpu time and processes in use
  time       now, and how long it has been up

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT)
  -j, --json          print one JSON object {PART: {...}}
  -h, --help          show this help

No PART = the overview: one line per part. PART... = those parts in detail; all = every part.
Numbers and facts only. A part that cannot be read prints "not available (why)"
(JSON: {"available": false, "reason": ...}); the other parts still show.
exit codes: 0 shown; 1 error (TargetMissing, InstanceMissing, ArgumentsBad...).
more: proto8/cmd/aos-agent/README.md
"""


class Missing(Exception):
    """這一類拿不到：印 not available＋原因，不整支失敗。"""


BIN = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bin", "aos-agent"))


def agent_cmd(a, args):
    """轉叫自己的子命令（同一個 daemon、同一隻）；退非 0＝Missing（最後一行錯誤行當原因）。"""
    argv = [sys.executable, BIN] + (["--daemon", common.TOP["daemon"]] if common.TOP.get("daemon") else []) + args[:1] + ["--target", a.name] + args[1:]
    return run(argv)


def run(argv, env=None):
    try:
        p = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Missing("%s did not run: %s" % (os.path.basename(argv[1] if argv[0] == sys.executable else argv[0]), e))
    if p.returncode != 0:
        err = [l for l in p.stderr.splitlines() if ": error: " in l]
        raise Missing(err[-1].split(": error: ", 1)[1] if err else "exit %d" % p.returncode)
    return p.stdout


def last_answer(a):
    got = aos_ws.answers(a.stack)
    if not got:
        return None
    s = got[-1].strip().replace("\n", " ")
    return s[:60] + ("…" if len(s) > 60 else "")


# ---- 各類：回 (一行總覽, 細節文字, JSON 物件) ----

def part_who(a):
    try:
        d = def_of(a)
    except Fail:
        d = None
    j = {"name": a.name, "def": d, "ws": a.row.get("ws"), "stack": a.stack}
    return ("%s (def %s, ws %s, stack %s)" % (a.name, d or "-", j["ws"] or "-", a.stack),
            "\n".join("%-6s %s" % (k, v or "-") for k, v in j.items()), j)


def part_state(a):
    q = queued(a)
    ans = last_answer(a)
    j = {"state": label(a), "phase": a.phase, "reason": a.reason or None, "queued": q, "last_answer": ans}
    warn = aos_ws.read(os.path.join(a.stack, "mailbox_warning.txt"))
    if warn and warn.strip():
        j["badmail"] = warn.strip().splitlines()[-1]
    one = "%s (daemon phase %s); %s queued; last answer %s" % (j["state"], a.phase, "-" if q is None else q, json.dumps(ans, ensure_ascii=False) if ans else "(none yet)")
    if j["reason"]:
        one += "; reason %s" % j["reason"]
    rows = ["state   %s (daemon phase %s)" % (j["state"], a.phase)] + (["reason  %s" % j["reason"]] if j["reason"] else []) + \
           ["queue   %s" % ("-" if q is None else "%d queued" % q), "answer  %s" % (ans or "(none yet)")] + \
           (["badmail %s" % j["badmail"]] if "badmail" in j else [])
    return one, "\n".join(rows), j


def part_tools(a):
    rows = json.loads(agent_cmd(a, ["tools", "ls", "--json"]) or "[]")
    names = [r.get("name") for r in rows if isinstance(r, dict)]
    own = overlay_count(a)
    j = {"count": len(names), "names": names, "own": own}
    one = "%d tools (%s)" % (len(names), ", ".join(map(str, names)) or "none") + ("; %s" % own if own else "; no own changes")
    return one, agent_cmd(a, ["tools", "ls"]).rstrip("\n") + ("\n" + own if own else ""), j


def part_llm(a):
    rows = json.loads(agent_cmd(a, ["llm", "ls", "--json"]) or "[]")
    kv = {r["key"]: r.get("value") for r in rows if isinstance(r, dict) and "key" in r}
    changed = [r["key"] for r in rows if isinstance(r, dict) and r.get("from") not in (None, "definition")]
    j = {"settings": kv, "changed": changed}
    one = (" ".join("%s=%s" % (k, v) for k, v in kv.items()) or "no settings") + ("; changed by it: %s" % ", ".join(changed) if changed else "")
    return one, agent_cmd(a, ["llm", "ls", "-l"]).rstrip("\n"), j


def part_hooks(a):
    rows = json.loads(agent_cmd(a, ["hook", "ls", "--json"]) or "[]")
    j = {"count": len(rows), "hooks": [{"name": r.get("name"), "on": r.get("on"), "from": r.get("from")} for r in rows if isinstance(r, dict)]}
    one = "%d hooks" % len(rows) + (" (%s)" % ", ".join("%s on %s" % (h["name"], h["event"]) for h in j["hooks"]) if rows else "")
    return one, agent_cmd(a, ["hook", "ls"]).rstrip("\n") or "(no hooks)", j


def part_history(a):
    rows = json.loads(agent_cmd(a, ["history", "ls", "--json"]) or "[]")
    roles = {}
    for r in rows:
        role = (r.get("message") or {}).get("role", "?") if isinstance(r.get("message"), dict) else "?"
        roles[role] = roles.get(role, 0) + 1
    path = history_path(a)
    size = os.path.getsize(path) if path and os.path.isfile(path) else 0
    removed = os.path.join(os.path.dirname(path), os.path.splitext(os.path.basename(path))[0] + "_removed.jsonl") if path else None
    kept = sum(1 for _ in open(removed, encoding="utf-8")) if removed and os.path.isfile(removed) else 0
    j = {"messages": len(rows), "bytes": size, "roles": roles, "removed_kept": kept, "file": path}
    one = "%d messages, %d bytes (%s)" % (len(rows), size, ", ".join("%s %d" % kv for kv in sorted(roles.items())) or "empty") + \
          ("; %d removed messages kept" % kept if kept else "")
    tail = "\n".join(l if len(l) <= 200 else l[:200] + "…" for l in
                     agent_cmd(a, ["history", "ls", "%d-" % max(1, len(rows) - 4)]).splitlines()) if rows else "(empty)"   # 一行最多 200 字，全文用 history ls
    return one, "%s\nlast %d:\n%s" % (one, min(5, len(rows)), tail), j


def history_path(a):
    from ..history import history_file
    try:
        return history_file(a)
    except Fail:
        return None


def part_mailbox(a):
    try:
        out = run(["aos-mailbox", "-s", a.stack, "peek", "--json"])
    except Missing as e:
        raise Missing(str(e) if "No such file" not in str(e) else "aos-mailbox is not on PATH")
    rows = json.loads(out or "[]")
    j = {"waiting": len(rows), "letters": rows}
    one = "%d letters waiting" % len(rows) + (" (oldest: %s from %s)" % (rows[0].get("title"), rows[0].get("from")) if rows else "")
    detail = "\n".join("\t".join(str(r.get(k, "?")) for k in ("letter", "from", "status", "title")) for r in rows) or "(no letters)"
    return one, detail, j


def part_children(a):
    book = os.path.join(a.stack, "tools", "agents_children", "children.json")   # agents_children 的帳（它自己的小格）
    try:
        with open(book, encoding="utf-8") as f:
            kids = json.load(f)
    except FileNotFoundError:
        kids = []
    except (OSError, ValueError) as e:
        raise Missing("cannot read %s: %s" % (book, e))
    cfg = {}
    for d in (a.row.get("def"), a.stack):
        try:
            with open(os.path.join(d, "children.json"), encoding="utf-8") as f:
                v = json.load(f)
            if isinstance(v, dict):
                cfg.update(v)
        except (OSError, ValueError, TypeError):
            pass
    most = cfg.get("max_children", 4)
    tab = common.table()
    out = []
    for k in kids if isinstance(kids, list) else []:
        if not isinstance(k, dict):
            continue
        n = k.get("name")
        r = tab.get(n)
        out.append({"name": n, "phase": (r or {}).get("phase") or ("queued" if k.get("queued_letter") else "gone")})
    j = {"count": len(out), "max_children": most, "children": out}
    one = "%d/%s children" % (len(out), most) + (" (%s)" % ", ".join("%s %s" % (c["name"], c["phase"]) for c in out) if out else "")
    return one, "\n".join("%s\t%s" % (c["name"], c["phase"]) for c in out) or "(no children)", j


def tree(pid):
    """pid 與它所有子孫（讀 /proc/*/stat 的 ppid）。"""
    kids = {}
    for p in os.listdir("/proc"):
        if p.isdigit():
            try:
                with open("/proc/%s/stat" % p) as f:
                    ppid = int(f.read().rsplit(")", 1)[1].split()[1])
                kids.setdefault(ppid, []).append(int(p))
            except (OSError, ValueError, IndexError):
                pass
    out, todo = [], [pid]
    while todo:
        p = todo.pop()
        out.append(p)
        todo += kids.get(p, [])
    return out


def proc_use(pids):
    rss, cpu, tick, page = 0, 0.0, os.sysconf("SC_CLK_TCK"), os.sysconf("SC_PAGE_SIZE")
    n = 0
    for p in pids:
        try:
            with open("/proc/%d/stat" % p) as f:
                s = f.read().rsplit(")", 1)[1].split()
            with open("/proc/%d/statm" % p) as f:
                rss += int(f.read().split()[1]) * page
            cpu += (int(s[11]) + int(s[12])) / tick
            n += 1
        except (OSError, ValueError, IndexError):
            pass
    return rss, cpu, n


def part_resources(a):
    lim = a.row.get("limits")
    pid = a.row.get("pid")
    j = {"limits": lim or None, "pid": pid}
    if isinstance(pid, int) and os.path.isdir("/proc/%d" % pid):
        rss, cpu, n = proc_use(tree(pid))
        j.update(memory_bytes=rss, cpu_seconds=round(cpu, 2), processes=n)
        use = "memory %.1f MiB, cpu %.1f s, %d processes" % (rss / 1048576, cpu, n)
    else:
        use = "no running process"
    one = "limits %s; %s" % (show_limits(lim) if lim else "none", use)
    return one, one, j


def part_time(a):
    now = time.time()
    j = {"now": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now)), "up_seconds": None}
    ticks, pid = a.row.get("started_at_ticks"), a.row.get("pid")
    if isinstance(ticks, int) and isinstance(pid, int) and os.path.isdir("/proc/%d" % pid):
        try:
            with open("/proc/uptime") as f:
                j["up_seconds"] = int(float(f.read().split()[0]) - ticks / os.sysconf("SC_CLK_TCK"))
        except (OSError, ValueError):
            pass
    up = j["up_seconds"]
    one = "now %s; %s" % (j["now"], "up %dh%02dm%02ds" % (up // 3600, up // 60 % 60, up % 60) if up is not None else "not running")
    return one, one, j


FN = {p: globals()["part_" + p] for p in PARTS}


def cmd(argv):
    opts, rest = parse(argv, {"--target": "target"}, {"--json": "json"}, help=HELP, short=("-t", "-j"))
    if "all" in rest:
        rest = [p for p in rest if p != "all"] + list(PARTS)
    bad = [p for p in rest if p not in PARTS]
    if bad:
        raise bad_args(HELP, "unknown part %s (parts: %s, all)" % (bad[0], " ".join(PARTS)))
    a = target(opts)
    picked = list(dict.fromkeys(rest)) or list(PARTS)
    got = {}
    for p in picked:
        try:
            got[p] = FN[p](a)
        except (Missing, Fail) as e:
            why = str(e) if isinstance(e, Missing) else "%s %s" % (e.code, e)
            got[p] = ("not available (%s)" % why, "not available (%s)" % why, {"available": False, "reason": why})
        except (ValueError, OSError, TypeError, AttributeError) as e:
            got[p] = ("not available (%s)" % e, "not available (%s)" % e, {"available": False, "reason": str(e)})
    if opts.get("json"):
        print(json.dumps({p: got[p][2] for p in picked}, ensure_ascii=False))
    elif rest:
        print("\n\n".join("== %s\n%s" % (p, got[p][1]) for p in picked))
    else:
        print("\n".join("%-9s %s" % (p, got[p][0]) for p in picked))


def overlay_count(a):
    """這隻自己那份 tools（stack 裡、$override 定義那份）加了幾個、拿掉幾個、疊在誰上面；沒有＝None。"""
    try:
        folder, decl = agent_decl(a)
        rel = declared_files(folder).get("tools")
    except (Fail, ValueError):
        return None
    if rel is None:
        return None
    p = os.path.join(a.stack, rel)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            o = json.load(f)
        tools = o.get("tools") or {}                 # 11-10 aos-tools-cli 步 4：{"$override": 底檔, "tools": {加的…, "不要的": null}}（null 那格不算工具）
        if not isinstance(tools, dict):
            raise TypeError("tools is not an object")
        add = sorted(n for n, e in tools.items() if e is not None)
        rm = sorted(n for n, e in tools.items() if e is None)
        base = o.get("$override")
        over = " over %s" % json.dumps(base, ensure_ascii=False) if base is not None else ""
        return "own: %d listed, %d set to null (%s)%s" % (len(add), len(rm), ", ".join(["+" + n for n in add] + ["null:" + n for n in rm]) or "empty", over)
    except (OSError, ValueError, AttributeError, TypeError) as e:
        return "own tools file unreadable: %s (%s)" % (p, e)
