# run.py - run 格：跑「現在這一版」的函數，結果寫進 $AOS_STACK/versions/<版>/runs.jsonl（判定是 judge 格的事）
# 第一次（還沒有任何版本）先把工作區的 target/（或 target.json）拍成 v000；工作區那份原版之後永遠不動。
# 判準是例子＝每組在函數的暫時複本上 aos-exec 一次；判準是檢查程式＝aos-exec 它一次（函數複本的路徑在 IMPROVE_TARGET）。
import json, os, shutil
import common
from common import VERSIONS, stack, ws

current = (common.read(os.path.join(stack, "current.txt")) or "").strip()
if not current:
    if common.target_name(ws) is None:
        common.die("TargetMissing", "工作區沒有 target/ 也沒有 target.json")
    common.write(os.path.join(stack, "started_at.txt"), common.now() + "\n")
    v0 = os.path.join(VERSIONS, "v000")
    if os.path.exists(v0):                                   # 上次拍到一半就斷了：重拍
        shutil.rmtree(v0)
    common.copy_target(ws, v0)
    common.write(os.path.join(v0, "version.json"), json.dumps(
        {"version": "v000", "from": None, "hash": common.tree_hash(v0), "same_as": None, "ignored": [],
         "created_at": common.now()}, ensure_ascii=False) + "\n")
    current = "v000"
    common.write(os.path.join(stack, "current.txt"), current + "\n")

vdir = os.path.join(VERSIONS, current)
if not os.path.exists(os.path.join(vdir, "version.json")):
    common.die("StackBad", "current.txt 指的 %s 不是拍好的版本" % current)
kind, crit = common.criteria()
results = []
if kind == "cases":
    for i, c in enumerate(crit, 1):
        r = common.run_target(vdir, c.get("args", []), c.get("stdin", ""), c.get("timeout_ms", 10000))
        results.append(dict(r, case=i))
else:
    results.append(common.run_target(vdir, [], "", 300000, exec_target=crit))

try:
    os.remove(os.path.join(vdir, "verdict.json"))         # 重跑＝重判
except FileNotFoundError:
    pass
common.write(os.path.join(vdir, "runs.jsonl"), "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in results))
