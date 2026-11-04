"""同時改 tasks.json：racer.py <誰> <次數> [--lock]，每次讀改寫加一項（from_round 很大，永遠不會起）。"""
import fcntl
import sys
from common import NODE, edit_tasks, os

who, n, lock = sys.argv[1], int(sys.argv[2]), "--lock" in sys.argv
lf = open(os.path.join(NODE, ".aos", "tasks.lock"), "w") if lock else None
for i in range(n):
    if lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
    edit_tasks(lambda ts: ts + [{"name": "r-%s-%d" % (who, i), "argv": ["true"], "from_round": 10 ** 9}])
    if lf:
        fcntl.flock(lf, fcntl.LOCK_UN)
