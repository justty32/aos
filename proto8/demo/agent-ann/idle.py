# idle 格：cur/ 或 new/ 有題目就結束碼 0（往下走），沒有就 10（請 loop 停）。
import os, sys
ws = os.environ.get("AOS_WS", ".")
names = []
for d in ("cur", "new"):      # 認領了沒做完的也算還有題目
    try:
        names += [n for n in os.listdir(os.path.join(ws, d)) if not n.startswith(".")]   # . 開頭＝寫到一半的暫存檔（N-05），不算
    except OSError:
        pass
sys.exit(0 if names else 10)
