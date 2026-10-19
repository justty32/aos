# act 格：把 plan（在 stack）當答案寫進 $AOS_WS/out/<題名>，題目從 inbox/ 搬到 done/。
import os, shutil, sys
stack, ws = os.environ.get("AOS_STACK"), os.environ.get("AOS_WS", ".")
if not stack:
    sys.exit("agent-ann: 沒設定 AOS_STACK")
name = open(os.path.join(stack, "current"), encoding="utf-8").read().strip()
os.makedirs(os.path.join(ws, "out"), exist_ok=True)
os.makedirs(os.path.join(ws, "done"), exist_ok=True)
shutil.copy(os.path.join(stack, "plan"), os.path.join(ws, "out", name))
shutil.move(os.path.join(ws, "inbox", name), os.path.join(ws, "done", name))
