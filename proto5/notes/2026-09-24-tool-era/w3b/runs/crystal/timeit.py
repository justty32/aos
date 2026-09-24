"""這台沒有 /usr/bin/time：python3 timeit.py 時間檔 -- 指令…；stdout 照原樣，時間檔寫 {"wall_s", "cpu_s", "rc"}。"""
import json
import resource
import subprocess
import sys
import time

out, cmd = sys.argv[1], sys.argv[3:]
t0 = time.monotonic()
rc = subprocess.run(cmd).returncode
wall = time.monotonic() - t0
ru = resource.getrusage(resource.RUSAGE_CHILDREN)
json.dump({'wall_s': round(wall, 3), 'cpu_s': round(ru.ru_utime + ru.ru_stime, 3), 'maxrss_kb': ru.ru_maxrss, 'rc': rc},
          open(out, 'w'))
sys.exit(rc)
