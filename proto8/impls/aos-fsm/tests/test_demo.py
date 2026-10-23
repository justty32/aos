#!/usr/bin/env python3
"""test_demo.py：整合測試——proto8/demo 的 agent-bob、agent-ann 在 impls 線跑，結果要跟 proto8/bin 線一樣（ctest 會跑）。只用標準庫。

    python3 tests/test_demo.py

照 proto8/demo/run.sh 的做法：每隻 agent 一個暫存工作區（tempfile，結束就清掉）、放一題 new/q1.txt、cd 進去 `aos-exec <agent>`。
impls 線：PATH 最前面放 impls 的 aos-exec、aos-loop、aos-fsm 的 bin/（不放 proto8/bin）；bin 線：PATH 最前面放 proto8/bin。
兩條線各跑一次，比：結束碼、stderr、工作區裡（含 .stack/ stack 整棵樹）有哪些檔、每個檔的內容。
會變的東西先抹掉：trace.jsonl 每行的 at、elapsed_ms；stamp 印的「# <UTC 時間>」那行。腦一律用假腦（清掉 AOS_BRAIN_*）。
要先建好 impls 的三支（aos-exec、aos-loop、aos-fsm 各自 cmake --build）。
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

IMPLS = Path(__file__).resolve().parent.parent.parent
PROTO = IMPLS.parent
DEMO = PROTO / "demo"
IMPLS_BINS = [IMPLS / "aos-exec" / "bin", IMPLS / "aos-loop" / "bin", IMPLS / "aos-fsm" / "bin"]
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
            d["at"] = "AT"
            d["elapsed_ms"] = "MS"
            out.append(d)
        return out
    return re.sub(r"^# \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$", "# TIME", text, flags=re.M)


def run_line(agent, bins):
    """一條線跑一隻 agent，回 (結束碼, stderr, {相對路徑: 抹掉後的內容})。"""
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    env["PATH"] = os.pathsep.join([str(b) for b in bins] + path_without(PY_BIN, *IMPLS_BINS))
    exe = str(bins[0] / "aos-exec")
    with tempfile.TemporaryDirectory() as ws:
        Path(ws, "new").mkdir()
        Path(ws, "new", "q1.txt").write_text("1+1 等於多少？\n")
        r = subprocess.run([exe, str(DEMO / agent)], cwd=ws, env=env, capture_output=True, text=True, timeout=120)
        files = {}
        for p in sorted(Path(ws).rglob("*")):
            if p.is_file():
                rel = str(p.relative_to(ws))
                files[rel] = normalize(rel, p.read_text())
        return r.returncode, r.stderr, files


def main():
    for b in IMPLS_BINS:
        name = b.parent.name
        if not (b / name).exists():
            print("失敗：%s 還沒建（%s）" % (name, b / name))
            sys.exit(1)
    for agent in ("agent-bob", "agent-ann"):
        impls = run_line(agent, IMPLS_BINS)
        py = run_line(agent, [PY_BIN])
        check(agent + " 結束碼／stderr（impls）", impls[:2], (0, ""))
        check(agent + " 跟 bin 線一樣：結束碼、stderr", impls[:2], py[:2])
        check(agent + " 跟 bin 線一樣：有哪些檔", sorted(impls[2]), sorted(py[2]))
        for rel in sorted(set(impls[2]) & set(py[2])):
            check(agent + " 跟 bin 線一樣：" + rel, impls[2][rel], py[2][rel])
        check(agent + " 答案寫出來了", "out/q1.txt" in impls[2] and "done/q1.txt" in impls[2], True)
        print("%s：impls 線結束碼 %d、%d 個檔（含 stack），跟 bin 線一樣" % (agent, impls[0], len(impls[2])))
    print("2 隻 agent、%d 個失敗" % failures)
    sys.exit(1 if failures else 0)


main()
