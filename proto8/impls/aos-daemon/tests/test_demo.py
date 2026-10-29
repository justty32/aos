#!/usr/bin/env python3
"""test_demo.py：整合測試——proto8/demo/daemon（一個 daemon 同時管 bob、ann 兩個子 loop）在 impls 線跑，
結果要跟 proto8/bin 線一樣（ctest 會跑）。只用標準庫。

    python3 tests/test_demo.py

照 proto8/demo/run.sh 的 daemon 那段：暫存工作區、bob/new、ann/new 各放一題、cd 進去 `aos-exec <demo/daemon>`。
impls 線：PATH 最前面放 impls 的 aos-exec、aos-loop、aos-fsm、aos-daemon 的 bin/（不放 proto8/bin）；bin 線：PATH 最前面放 proto8/bin。
兩條線各跑一次，比：結束碼、stderr、工作區裡（含 .stack/ stack 整棵樹）有哪些檔、每個檔的內容。
會變的東西先抹掉：trace.jsonl 每行的 started_at、elapsed_ms；state.json 的 pid、started_at_ticks、boot_id、recorded_at（含 loops 每列的 pid、started_at_ticks）；
stamp 印的「# <UTC 時間>」那行。要先建好 impls 的四支。
10-23 起 proto8/bin 的 Python 版 aos-exec／aos-loop／aos-fsm／aos-daemon 刪了（使用者「python版本可以刪掉了。aos-exec/loop/daemon都用C++」，fsm 也改 C++）：
不再跟 bin 線比，只跑 impls 線、看結束碼 0、stderr 空、答案寫出來了。
10-29 加 proto8/demo/daemon-2（信箱模式；run_daemon2）：要多建 impls 的 aos-post，aos-tick 用 proto8/bin 的。
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

IMPLS = Path(__file__).resolve().parent.parent.parent
PROTO = IMPLS.parent
DEMO = PROTO / "demo"
IMPLS_BINS = [IMPLS / "aos-exec" / "bin", IMPLS / "aos-loop" / "bin", IMPLS / "aos-fsm" / "bin", IMPLS / "aos-daemon" / "bin"]
PY_BIN = PROTO / "bin"
failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print("失敗 %s：\n  得到 %r\n  應該 %r" % (name, got, want))


def path_without(*drop):
    drop = {os.path.realpath(d) for d in drop}
    return [p for p in os.environ.get("PATH", "").split(os.pathsep) if p and os.path.realpath(p) not in drop]


def normalize(rel, text):
    if rel.endswith("trace.jsonl"):
        out = []
        for line in text.splitlines():
            d = json.loads(line)
            d["started_at"] = "AT"
            d["elapsed_ms"] = "MS"
            out.append(d)
        return out
    if rel.endswith("state.json"):
        d = json.loads(text)
        for k in ("pid", "started_at_ticks", "boot_id", "recorded_at"):
            d[k] = k.upper()
        for r in d.get("loops", {}).values():
            r["pid"] = r["started_at_ticks"] = "X"
        return d
    return re.sub(r"^# \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$", "# TIME", text, flags=re.M)


def run_line(agent, bins):
    """一條線跑一次 daemon demo，回 (結束碼, stderr, {相對路徑: 抹掉後的內容})。"""
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    env["PATH"] = os.pathsep.join([str(b) for b in bins] + path_without(PY_BIN, *IMPLS_BINS))
    exe = str(bins[0] / "aos-exec")
    with tempfile.TemporaryDirectory() as ws:
        for a in ("bob", "ann"):
            Path(ws, a, "new").mkdir(parents=True)
            Path(ws, a, "new", "q1.txt").write_text("2+2 等於多少？\n")
        r = subprocess.run([exe, str(DEMO / agent)], cwd=ws, env=env, capture_output=True, text=True, timeout=120)
        files = {}
        for p in sorted(Path(ws).rglob("*")):
            if p.is_file():
                rel = str(p.relative_to(ws))
                files[rel] = normalize(rel, p.read_text())
        return r.returncode, r.stderr, files


def run_daemon2():
    """proto8/demo/daemon-2（信箱模式，10-29）：照 run.sh 那段——`aos-exec demo/daemon-2 --max 25` 放背景跑，
    信箱建好後人寄一封加 tock（帶 --reply-to），等 daemon 收工。PATH 多 aos-post 與 proto8/bin（aos-tick）。"""
    bins = IMPLS_BINS + [IMPLS / "aos-post" / "bin", PY_BIN]
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    env["PATH"] = os.pathsep.join([str(b) for b in bins] + path_without(*bins))
    post = str(IMPLS / "aos-post" / "bin" / "aos-post")
    with tempfile.TemporaryDirectory() as t:
        ws = Path(t)
        subprocess.run([post, "init", str(ws / "inbox")], env=env, check=True)
        p = subprocess.Popen([str(IMPLS_BINS[0] / "aos-exec"), str(DEMO / "daemon-2"), "--max", "25"], cwd=str(ws), env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        box = ws / ".stack" / "loops_mailbox"
        end = time.monotonic() + 10
        while not (box / "new").is_dir() and time.monotonic() < end:
            time.sleep(0.05)
        body = {"loops_added": {"tock": {"exec": {"argv": ["aos-tick", {"$env": "AOS_STACK", "$path": "tock.txt"}]},
                                         "interval_ms": 500}}}
        s = subprocess.run([post, "send", "--reply-to", str(ws / "inbox"), str(box)], input=json.dumps(body), env=env,
                           capture_output=True, text=True)
        out, err = p.communicate(timeout=60)
        check("daemon-2 結束碼／stderr", (p.returncode, err, s.returncode), (0, "", 0))
        ls = json.loads((ws / ".stack" / "loops_state.json").read_text())
        check("daemon-2 名單", {n: r["phase"] for n, r in ls["loops"].items()}, {"sam": "done", "tick": "stopped", "tock": "stopped"})
        check("daemon-2 letter_warning", ls["letter_warning"], None)
        check("daemon-2 信都收完", [x.name for x in box.iterdir() if any((box / x.name).iterdir())], [])
        ticks = [int((ws / ".stack" / n / (n + ".txt")).read_text()) for n in ("tick", "tock")]
        check("daemon-2 tick、tock 都走了", all(n > 0 for n in ticks), True)
        replies = list((ws / "inbox" / "new").iterdir())
        r = json.loads((replies[0] / "letter.json").read_text()) if len(replies) == 1 else {}
        check("daemon-2 回信", (r.get("in_reply_to"), r.get("body")), (s.stdout.strip(), {"applied": True}))
        print("daemon-2：結束碼 %d、tick %d、tock %d" % (p.returncode, ticks[0], ticks[1]))


def main():
    for b in IMPLS_BINS + [IMPLS / "aos-post" / "bin"]:
        name = b.parent.name
        if not (b / name).exists():
            print("失敗：%s 還沒建（%s）" % (name, b / name))
            sys.exit(1)
    for agent in ("daemon",):
        impls = run_line(agent, IMPLS_BINS)
        check(agent + " 結束碼／stderr（impls）", impls[:2], (0, ""))
        check(agent + " 答案寫出來了", all(a + "/out/q1.txt" in impls[2] for a in ("bob", "ann")), True)
        print("%s：impls 線結束碼 %d、%d 個檔（含 stack）" % (agent, impls[0], len(impls[2])))
    run_daemon2()
    print("daemon demo、%d 個失敗" % failures)
    sys.exit(1 if failures else 0)


main()
