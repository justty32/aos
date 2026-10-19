# idle 格：inbox 有題目就結束碼 0（往下走），沒有就 10（請 loop 停）。
import os, sys
ws = os.environ.get("AOS_WS", ".")
try:
    names = os.listdir(os.path.join(ws, "inbox"))
except OSError:
    names = []
sys.exit(0 if names else 10)
