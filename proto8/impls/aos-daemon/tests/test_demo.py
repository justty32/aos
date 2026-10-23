#!/usr/bin/env python3
"""test_demo.py：整合測試——proto8/demo/daemon（一個 daemon 同時管 bob、ann 兩個子 loop）在 impls 線跑，
結果要跟 proto8/bin 線一樣（ctest 會跑）。只用標準庫。

    python3 tests/test_demo.py

照 proto8/demo/run.sh 的 daemon 那段：暫存工作區、bob/new、ann/new 各放一題、cd 進去 `aos-exec <demo/daemon>`。
impls 線：PATH 最前面放 impls 的 aos-exec、aos-loop、aos-fsm、aos-daemon 的 bin/（不放 proto8/bin）；bin 線：PATH 最前面放 proto8/bin。
兩條線各跑一次，比：結束碼、stderr、工作區裡（含 .stack/ stack 整棵樹）有哪些檔、每個檔的內容。
會變的東西先抹掉：trace.jsonl 每行的 at、elapsed_ms；state.json 的 pid、start_ticks、boot_id、at（含 loops 每列的 pid、start_ticks）；
stamp 印的「# <UTC 時間>」那行。要先建好 impls 的四支。
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
            d["at"] = "AT"
            d["elapsed_ms"] = "MS"
            out.append(d)
        return out
    if rel.endswith("state.json"):
        d = json.loads(text)
        for k in ("pid", "start_ticks", "boot_id", "at"):
            d[k] = k.upper()
        for r in d.get("loops", {}).values():
            r["pid"] = r["start_ticks"] = "X"
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


def main():
    for b in IMPLS_BINS:
        name = b.parent.name
        if not (b / name).exists():
            print("失敗：%s 還沒建（%s）" % (name, b / name))
            sys.exit(1)
    for agent in ("daemon",):
        impls = run_line(agent, IMPLS_BINS)
        py = run_line(agent, [PY_BIN])
        check(agent + " 結束碼／stderr（impls）", impls[:2], (0, ""))
        check(agent + " 跟 bin 線一樣：結束碼、stderr", impls[:2], py[:2])
        check(agent + " 跟 bin 線一樣：有哪些檔", sorted(impls[2]), sorted(py[2]))
        for rel in sorted(set(impls[2]) & set(py[2])):
            check(agent + " 跟 bin 線一樣：" + rel, impls[2][rel], py[2][rel])
        check(agent + " 答案寫出來了", all(a + "/out/q1.txt" in impls[2] for a in ("bob", "ann")), True)
        print("%s：impls 線結束碼 %d、%d 個檔（含 stack），跟 bin 線一樣" % (agent, impls[0], len(impls[2])))
    print("daemon demo、%d 個失敗" % failures)
    sys.exit(1 if failures else 0)


main()
