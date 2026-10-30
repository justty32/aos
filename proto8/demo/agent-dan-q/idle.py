# idle.py - idle 格：$AOS_STACK/queue/ 的 cur/ 或 new/ 有信就結束碼 0（往下走），沒有就 10（請 loop 停＝射後不理）
# 10-30（eca 第 8 步）：agent-dan 搬到 queue 的版本；舊的 agent-dan 看的是 $AOS_WS/cur/、new/。. 開頭的名字不算信（N-05）。
import os, sys

box = os.path.join(os.environ.get("AOS_STACK") or ".", "queue")
for stage in ("cur", "new"):                      # 認領了沒做完的也算
    try:
        if any(not n.startswith(".") for n in os.listdir(os.path.join(box, stage))):
            sys.exit(0)
    except (FileNotFoundError, NotADirectoryError):
        pass
sys.exit(10)
