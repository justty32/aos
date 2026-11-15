#!/usr/bin/env python3
# demo_v2 - a fixture company for looking at the v2 page by hand or with headless Chrome (not a unit test).
# Everything lives in a new /tmp/view-demo-* folder: fixture daemon table (VIEW_LS_FIXTURE), stub aos-agent on PATH,
# fixture letters for the user (VIEW_ASKS_FIXTURE), stub aos-user (VIEW_TOOLS), temp view home.
# The live daemon, ~/aos-home and ~/.aos are never read or written.
# Run through tests/run.sh-like env (no AOS_*):  env -u ... python3 tests/demo_v2.py [PORT1 PORT2]
# Prints "READY <tmp> <p1> <p2>" and keeps serving until killed.
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VIEW = os.path.join(os.path.dirname(HERE), "aos-view")
DIST = os.path.join(os.path.dirname(HERE), "ui", "v2", "dist")

if any(k.startswith("AOS_") for k in os.environ):
    sys.exit("demo_v2: AOS_* variables are set; unset them first")

STUB = r"""#!/bin/bash
# aos-agent stub: say prints a letter name; ctl state / history answer with small fixed JSON; the rest fails
case "$1" in
  say) cat > /dev/null; echo "L-say-$(date +%s%N)"; exit 0;;
  ctl) echo '{"state":{"state":"running","phase":"idle","queued":0,"pid":4242},"resources":{"memory_mb":120,"up_s":3600},"who":{"workspace":"/tmp/ws"},"mailbox":{"waiting":0,"letters":[]}}'; exit 0;;
  history) echo '[{"line":1,"role":"user","text":"開始工作","tools":[]},{"line":2,"role":"assistant","text":"好，先讀規則。","tools":["Read"]}]'; exit 0;;
esac
exit 1
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
    t = tempfile.mkdtemp(prefix="view-demo-", dir="/tmp")
    home, procs, zone, bindir = (os.path.join(t, x) for x in ("view", "procs", "user", "bin"))
    os.makedirs(bindir)
    with open(os.path.join(bindir, "aos-agent"), "w") as f:
        f.write(STUB)
    os.chmod(os.path.join(bindir, "aos-agent"), 0o755)
    now = time.time()
    spec = [("repo-aos", "running", None, None), ("ok-view", "running", "think", None), ("ok-view-sol-1", "running", None, None),
            ("ok-board", "running", None, None), ("ok-board-sol-1", "stopped", None, "exited with code 1"),
            ("ok-board-sol-2", "running", None, None), ("ok-release", "sleeping", None, None),
            ("xiaosi", "running", None, None), ("ok-view-sol-2", "running", None, None), ("ok-view-astra-1", "running", None, None),
            ("ok-board-sol-3", "stopped", None, "RunFailed: timeout after 600000 ms")]
    # claude cells with a live stream: (last event, age s). ok-view: a long quiet turn = yellow, not red
    live = {"ok-view": ("assistant", 40 * 60), "ok-view-sol-2": ("assistant", 30), "repo-aos": ("result", 120),
            "xiaosi": ("result", 600), "ok-board": ("result", 60)}
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
        rows.append({"name": n, "state": st, "phase": st, "ws": t, "stack": os.path.join(procs, n), "queued": 1 if busy else 0,
                     "reason": reason, "auto_restart": False, "queue": 0, "cooldown": None, "busy": busy})
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
    env = {"PATH": bindir + ":" + os.environ["PATH"], "HOME": os.environ["HOME"], "LANG": "C.UTF-8",
           "PYTHONDONTWRITEBYTECODE": "1", "VIEW_LS_FIXTURE": os.path.join(t, "ls.json"), "AOS_USER_ZONE": zone,
           "VIEW_TOOLS": tools, "VIEW_ASKS_FIXTURE": asks}
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
    subprocess.run([VIEW, "--home", home, "note", "--team", "ok-view", "progress", "v2", "前端在寫"], env=env, capture_output=True)
    qs = [{"id": "q1", "question": "SVG 還是 canvas？", "eli5": "SVG 簡單，canvas 快。",
           "options": [{"key": "a", "label": "SVG", "consequence": "改起來快"}, {"key": "b", "label": "canvas"}], "recommend": "a", "why": "格子不多"},
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
        for r in [{"at": iso(now - 3000), "kind": "mail", "to": "ok-board", "title": "board/1 進度？", "text": "寫到哪了", "ok": True, "letter": "L-m1"},
                  {"at": iso(now - 900), "kind": "say", "to": "ok-release", "text": "先等我", "ok": True, "letter": "L-s1"}]:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    d = os.path.join(home, "mailbox", "new", "R-1")
    os.makedirs(d)
    with open(os.path.join(d, "letter.json"), "w") as f:
        json.dump({"sent_at": iso(now - 600), "in_reply_to": "L-m1", "sender": procs + "/ok-board",
                   "body": {"from": "ok-board", "to": "user", "status": "PROGRESS", "title": "board/1 寫到 §7", "what": "還差 U1–U7。"}}, f, ensure_ascii=False)
    srv = subprocess.Popen([VIEW, "--home", home, "--port", str(p1), "serve"], env=env)
    print("READY", t, p1, p2, "pid", srv.pid, flush=True)
    try:
        srv.wait()
    except KeyboardInterrupt:
        srv.terminate()


if __name__ == "__main__":
    main()
