"""keep 任務：第一次起來時只對自己下 kill、不改 tasks.json（對照組，D-3：會被起回來）。"""
import time
from common import TASK, bump, fs, os

if bump("bouncer.count") == 1:
    fs.write_json(os.path.join(TASK, "ctl.json"), {"op": "kill", "by": "self", "why": "試試看"})
while True:
    time.sleep(1)
