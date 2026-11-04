"""keep 任務：把自己從 tasks.json 拿掉，再對自己下 kill（D-3：這樣才不會被起回來）。"""
import time
from common import TASK, bump, edit_tasks, fs, os

bump("quitter.count")
edit_tasks(lambda ts: [t for t in ts if t.get("name") != "quitter"])
fs.write_json(os.path.join(TASK, "ctl.json"), {"op": "kill", "by": "self", "why": "不幹了"})
while True:
    time.sleep(1)
