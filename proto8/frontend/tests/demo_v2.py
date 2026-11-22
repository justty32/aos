#!/usr/bin/env python3
# demo_v2 - a fixture company for looking at the v2 page by hand or with headless Chrome (not a unit test).
# Everything lives in a new scratch/view-demo-* folder: fixture daemon table (VIEW_LS_FIXTURE), stub aos-agent on PATH,
# fixture letters for the user (VIEW_ASKS_FIXTURE), stub aos-user (VIEW_TOOLS), temp view home.
# The live daemon and ~/aos-home are never read or written.
# Run through the task clean.sh wrapper (no AOS_*): python3 tests/demo_v2.py [PORT1 PORT2]
# VIEW_DEMO_SLASH_DELAY=SECONDS (default 0): a slash sent from the page is answered only after that long (to see the queued state).
# VIEW_DEMO_PEEK_DELAY=SECONDS (default 2): `aos-agent peek` (/status, /usage) answers after that long, never touching history.
# VIEW_DEMO_TMP=DIR (default ~/.aos/scratch/ok-pano-1116): where the new view-demo-* folder goes.
# Prints "READY <tmp> <p1> <p2>" and keeps serving until killed.
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VIEW = os.path.join(os.path.dirname(HERE), "bin", "aos-frontend")
DIST = os.path.join(os.path.dirname(HERE), "ui", "v2", "dist")

if any(k.startswith("AOS_") for k in os.environ):
    sys.exit("demo_v2: AOS_* variables are set; unset them first")
if not os.path.isfile(os.path.join(DIST, "index.html")):   # dist/ is not in git (11-17): build it first
    sys.exit("demo_v2: %s has no index.html; build the v2 page first (see ui/v2/README.md)" % DIST)

STUB = r"""#!/usr/bin/env python3
# The fixture agent records bare stdin and serves per-agent state and history without a daemon.
import json
import os
from pathlib import Path
import sys
import time

root = Path(os.environ["VIEW_DEMO_ROOT"])
args = sys.argv[1:]
name = args[args.index("-t") + 1] if "-t" in args else "unknown"
history = root / ("history-" + name + ".json")
pending = root / ("pending-" + name + ".json")
DELAY = float(os.environ.get("VIEW_DEMO_SLASH_DELAY", "0"))   # seconds a slash waits "for the turn to end" before it is answered


def settle():
    # answer the slash letters whose delay is over: a user row with aos.letter, then the answer with aos.answer_to
    rows = json.loads(history.read_text()) if history.exists() else []
    waiting = json.loads(pending.read_text()) if pending.exists() else []
    due = [p for p in waiting if p["due"] <= time.time()]
    for p in due:
        command = p["text"].split()[0]
        content = "[aos] slash: " + command + ": typed into the open screen; it printed:\n"
        content += "\n".join("Context row %02d: tokens, workspace, tools and the current plan." % i for i in range(35))
        rows.append({"line": len(rows) + 1, "message": {"role": "user", "content": p["text"], "aos": {"letter": p["letter"]}}})
        rows.append({"line": len(rows) + 1, "message": {"role": "assistant", "content": content, "aos": {"answer_to": [p["letter"]]}}})
    if due:
        history.write_text(json.dumps(rows))
        pending.write_text(json.dumps([p for p in waiting if p not in due]))
    return rows


if args[0] == "say":
    text = sys.stdin.read()
    with (root / "said.jsonl").open("a") as f:
        f.write(json.dumps({"name": name, "text": text}) + "\n")
    letter = "L-say-" + str(time.time_ns())
    if text.startswith("/"):
        waiting = json.loads(pending.read_text()) if pending.exists() else []
        waiting.append({"letter": letter, "text": text, "due": time.time() + DELAY})
        pending.write_text(json.dumps(waiting))
        settle()
    print(letter)
elif args[0] == "peek":
    # read-only: logged with how=peek, answered on stdout, history and pending untouched
    text = args[-1]
    with (root / "said.jsonl").open("a") as f:
        f.write(json.dumps({"name": name, "text": text, "how": "peek"}) + "\n")
    time.sleep(float(os.environ.get("VIEW_DEMO_PEEK_DELAY", "2")))
    print(text + " for " + name + " (peek, not queued):")
    print("\n".join("Peek row %02d: model, session, limits." % i for i in range(12)))
elif args[0] == "ctl":
    hist_rows = settle()
    rows = json.loads((root / "ls.json").read_text())
    row = next(r for r in rows if r["name"] == name)
    print(json.dumps({"state": {"state": row["state"], "phase": "idle", "queued": row["queued"],
                                "last_answer": "好。" if name == "ok-green-sol-1" else "Context preview (upstream shortened)"},
                      "resources": {"pid": 4242, "memory_bytes": 125829120}, "time": {"up_seconds": 3600},
                      "who": {"workspace": str(root)}, "mailbox": {"waiting": row["queued"], "letters": []},
                      "history": {"messages": len(hist_rows)}}))
elif args[0] == "history":
    print(json.dumps(settle()))
else:
    sys.exit(1)
"""


USER_STUB = r"""#!/bin/bash
# aos-user stub: answer / reply / ok say done; nothing is written anywhere
echo "ok: $1 $2"; exit 0
"""


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(t))


def main():
    p1 = int(sys.argv[1]) if len(sys.argv) > 1 else 18767
    p2 = int(sys.argv[2]) if len(sys.argv) > 2 else 18768
    t = tempfile.mkdtemp(prefix="view-demo-", dir=os.environ.get("VIEW_DEMO_TMP") or os.path.expanduser("~/.aos/scratch/ok-pano-1116"))
    home, procs, zone, bindir = (os.path.join(t, x) for x in ("view", "procs", "user", "bin"))
    os.makedirs(bindir)
    with open(os.path.join(bindir, "aos-agent"), "w") as f:
        f.write(STUB)
    os.chmod(os.path.join(bindir, "aos-agent"), 0o755)
    now = time.time()
    long_text = "\n".join("第 %02d 行：目前計畫、使用量、工具與工作區的詳細內容，保留換行方便展開閱讀。" % i for i in range(55))
    spec = [("repo-aos", "running", None, None), ("ok-view", "running", "think", None), ("ok-view-sol-1", "running", None, None),
            ("ok-board", "running", None, None), ("ok-board-sol-1", "stopped", None, "exited with code 1: " + "failure detail; " * 50 + "sk-demo_fake_key_1234567890 final error detail"),
            ("ok-board-sol-2", "running", None, None), ("ok-release", "sleeping", None, None),
            ("xiaosi", "running", None, None), ("ok-view-sol-2", "running", None, None), ("ok-view-astra-1", "running", None, None),
            ("ok-board-sol-3", "stopped", None, "RunFailed: timeout after 600000 ms"),
            ("ok-green", "running", None, None), ("ok-green-sol-1", "running", None, None),
            ("ok-errors", "running", None, None), ("ok-errors-sol-1", "stopped", None, "exited with code 1"),
            ("ok-board-room", "running", None, None), ("ok-board-room-sol-1", "running", None, None),
            ("ok-green-member-with-a-very-long-name-for-the-map-and-inspector", "running", None, None),
            ("ok-cooling", "stopped", None, None)]
    # claude cells with a live stream: (last event, age s). ok-view: a long quiet turn = yellow, not red
    live = {"ok-view": ("assistant", 40 * 60), "ok-view-sol-2": ("assistant", 30), "repo-aos": ("result", 120),
            "xiaosi": ("result", 600), "ok-board": ("result", 60)}
    # who is under whom: the subagent records (the page reads nothing else)
    subs = {"repo-aos": ["ok-view", "ok-board", "ok-release", "xiaosi", "ok-green", "ok-errors", "ok-cooling"],
            "ok-view": ["ok-view-sol-2", "ok-view-astra-1"],
            "ok-board": ["ok-board-sol-1", "ok-board-sol-2", "ok-board-sol-3", "ok-board-room"],
            "ok-board-room": ["ok-board-room-sol-1"],
            "ok-green": ["ok-green-sol-1", "ok-green-member-with-a-very-long-name-for-the-map-and-inspector"],
            "ok-errors": ["ok-errors-sol-1"]}
    rows = []
    for n, st, busy, reason in spec:
        os.makedirs(os.path.join(procs, n))
        subprocess.run(["aos-post", "init", os.path.join(procs, n, "mailbox")], check=True, capture_output=True)
        if n in live:
            os.makedirs(os.path.join(procs, n, "claude"))
            lp = os.path.join(procs, n, "claude", "live.jsonl")
            with open(lp, "w") as f:
                f.write(json.dumps({"type": "system"}) + "\n" + json.dumps({"type": live[n][0]}) + "\n")
            os.utime(lp, (now - live[n][1], now - live[n][1]))
        rows.append({"name": n, "state": st, "phase": st, "ws": t, "stack": os.path.join(procs, n), "queued": 2 if n == "ok-view-sol-2" else 0,
                     "reason": reason, "auto_restart": False, "queue": 0,
                     "cooldown": {"failures": 4, "reason": "cooldown reason; " * 60, "until": now + 600} if n == "ok-cooling" else None,
                     "busy": busy, "subagents": subs.get(n, [])})
        history = [{"line": i + 1, "message": {"role": "user" if i % 2 == 0 else "assistant",
                    "content": "Demo history row %02d" % (i + 1)}} for i in range(29)]
        history.append({"line": 30, "message": {"role": "assistant", "content": "[aos] slash: /context: screen output:\n" + long_text}})
        if n == "ok-green-sol-1":
            history[-1]["message"]["content"] = "好。"
        with open(os.path.join(t, "history-" + n + ".json"), "w") as f:
            json.dump(history, f)
    with open(os.path.join(t, "ls.json"), "w") as f:
        json.dump(rows, f)
    with open(os.path.join(procs, "ok-board", "board.json"), "w") as f:
        json.dump({"format": "board/1", "updated_at": iso(now - 120), "mode": "dnd", "text": "在寫 board/1 規格，急事才找",
                   "doing": "06 §7 定稿", "waiting_on": [{"who": "user", "what": "U4：使用者布告欄要不要也改 board/1", "since_at": iso(now - 1800)}]}, f)
    with open(os.path.join(procs, "ok-view-sol-1", "board.json"), "w") as f:
        json.dump({"format": "board/1", "updated_at": iso(now - 30 * 3600), "mode": "busy", "text": "舊的公告（過期）"}, f)
    tools = os.path.join(t, "tools")
    os.makedirs(os.path.join(tools, "aos-user"))
    with open(os.path.join(tools, "aos-user", "aos-user"), "w") as f:
        f.write(USER_STUB)
    os.chmod(os.path.join(tools, "aos-user", "aos-user"), 0o755)
    asks = os.path.join(t, "asks.json")
    slash_fixture = os.path.join(t, "slash.json")
    commands = [{"name": name, "args": args, "confirm": confirm, "how": how, "cli": ["claude", "codex"]}
                for name, args, confirm, how in (("compact", "optional", False, "turn"), ("status", "none", False, "peek"),
                    ("usage", "none", False, "peek"), ("goal", "optional", False, "turn"), ("clear", "none", True, "turn"),
                    ("exit", "none", True, "turn"))]
    commands.append({"name": "context", "args": "none", "confirm": False, "how": "screen", "cli": ["claude"]})
    with open(slash_fixture, "w") as f:
        json.dump(commands, f)
    env = {"PATH": bindir + ":" + os.environ["PATH"], "HOME": os.environ["HOME"], "LANG": "C.UTF-8",
           "PYTHONDONTWRITEBYTECODE": "1", "VIEW_LS_FIXTURE": os.path.join(t, "ls.json"), "AOS_USER_ZONE": zone,
           "VIEW_TOOLS": tools, "VIEW_ASKS_FIXTURE": asks, "VIEW_SLASH_FIXTURE": slash_fixture, "VIEW_DEMO_ROOT": t,
           "VIEW_DEMO_SLASH_DELAY": os.environ.get("VIEW_DEMO_SLASH_DELAY", "0"),
           "VIEW_DEMO_PEEK_DELAY": os.environ.get("VIEW_DEMO_PEEK_DELAY", "2")}
    subprocess.run([VIEW, "--home", home, "init"], env=env, check=True, capture_output=True)
    cfgp = os.path.join(home, "config.json")
    with open(cfgp) as f:
        cfg = json.load(f)
    cfg["ui_ports"] = [{"port": p2, "dir": DIST}]
    cfg["externals"] = []
    cfg["poll_s"] = 5
    with open(cfgp, "w") as f:
        json.dump(cfg, f)
    # a team with an aide, a note and a decision letter
    team = os.path.join(home, "teams", "ok-view")
    os.makedirs(team, exist_ok=True)
    with open(os.path.join(team, "aide.json"), "w") as f:
        json.dump({"team": "ok-view", "parent": "repo-aos", "leader": "ok-view", "aide": "ok-view-sol-1", "tags": ["view"]}, f)
    subprocess.run([VIEW, "--home", home, "note", "--team", "ok-view", "--on", "v2", "progress", long_text[:1800]],
                   env=env, check=True, capture_output=True)
    qs = [{"id": "q1", "question": "SVG 還是 canvas？", "eli5": "SVG 簡單，canvas 快。",
           "options": [{"key": "a", "label": "SVG", "consequence": "改起來快"}, {"key": "b", "label": "canvas"}, {"key": "c", "label": "HTML", "consequence": "直接排版"}], "recommend": "a", "why": "格子不多"},
          {"id": "q2", "question": "要不要動畫？", "eli5": "動畫好看但比較吃電。", "options": [{"key": "a", "label": "要"}, {"key": "b", "label": "不要"}], "recommend": "b"},
          {"id": "q3", "question": "名牌多寬？", "eli5": "寬一點名字不會被截。", "options": [{"key": "a", "label": "116"}, {"key": "b", "label": "96"}], "recommend": "a"}]
    letters = [{"letter": "Z-1", "kind": "decide", "from": "ok-view", "title": "地圖要用 SVG 還是 canvas", "what": "v2.1 的地圖兩種畫法。\n第二行說明。",
                "questions": qs, "urgent": False, "risk": "normal", "deadline": "2026-12-31", "decide": None, "sent_at": now - 1200, "same": 1, "unseen": True},
               {"letter": "Z-2", "kind": "decide", "from": "ok-board", "title": "board/1 要不要收 U4", "what": "布告欄格式。",
                "questions": qs[:1], "urgent": True, "risk": "irreversible", "deadline": None, "decide": None, "sent_at": now - 300, "same": 1, "unseen": True},
               {"letter": "Z-3", "kind": "fyi", "from": "xiaosi", "title": "今天的摘要", "what": "沒事。", "questions": [], "urgent": False,
                "risk": "normal", "deadline": None, "decide": None, "sent_at": now - 60, "same": 1, "unseen": True}]
    with open(asks, "w") as f:
        json.dump(letters, f, ensure_ascii=False)
    # what "the user" sent earlier, and one reply in the relay mailbox
    os.makedirs(os.path.join(home, "state"), exist_ok=True)
    with open(os.path.join(home, "state", "sent.jsonl"), "w") as f:
        for r in [{"at": iso(now - 3000), "kind": "mail", "to": "ok-board", "title": "board/1 進度？", "text": long_text, "ok": True, "letter": "L-m1"},
                  {"at": iso(now - 900), "kind": "say", "to": "ok-release", "text": "先等我", "ok": True, "letter": "L-s1"}]:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    d = os.path.join(home, "mailbox", "new", "R-1")
    os.makedirs(d)
    with open(os.path.join(d, "letter.json"), "w") as f:
        json.dump({"sent_at": iso(now - 600), "in_reply_to": "L-m1", "sender": procs + "/ok-board",
                   "body": {"from": "ok-board", "to": "user", "status": "PROGRESS", "title": "board/1 寫到 §7", "what": "還差 U1–U7。"}}, f, ensure_ascii=False)
    # Three reports with full bodies, not just headings, for the inspector's expandable list.
    for i in range(3):
        d = os.path.join(home, "mailbox", "new", "R-report-%d" % i)
        os.makedirs(d)
        with open(os.path.join(d, "letter.json"), "w") as f:
            json.dump({"sent_at": iso(now - 30 - i), "sender": procs + "/ok-board",
                       "body": {"from": "ok-board", "to": "user", "status": "PROGRESS",
                                "title": "進度報告 %d" % (i + 1), "what": long_text}}, f, ensure_ascii=False)
    srv = subprocess.Popen([VIEW, "--home", home, "--port", str(p1), "serve"], env=env)
    print("READY", t, p1, p2, "pid", srv.pid, flush=True)
    try:
        srv.wait()
    except KeyboardInterrupt:
        srv.terminate()


if __name__ == "__main__":
    main()
