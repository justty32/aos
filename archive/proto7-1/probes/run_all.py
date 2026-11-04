#!/usr/bin/env python3
"""跑全部探針：每個 `probes/<名字>/probe.py` 一個子程序，最後檢查沒有殘留程序與暫存資料夾。

    python3 proto7-1/probes/run_all.py [名字 ...]
"""
import glob
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import probelib  # noqa: E402


def main(argv):
    names = argv or sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(HERE, "*", "probe.py")))
    results = []
    for n in names:
        t0 = time.monotonic()
        p = subprocess.Popen([sys.executable, os.path.join(HERE, n, "probe.py")], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
        try:
            out, err = p.communicate(timeout=600)
        except BaseException as e:
            # 逾時或 Ctrl-C：先 SIGTERM（探針的 Space 會收自己的 daemon 與任務），等不到才 SIGKILL（N-55）
            p.terminate()
            try:
                out, err = p.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                p.kill()
                out, err = p.communicate()
            if not isinstance(e, subprocess.TimeoutExpired):
                raise
        sys.stdout.write(out)
        if p.returncode:
            sys.stdout.write(err[-2000:])
        results.append((n, p.returncode, time.monotonic() - t0))
    prefix = os.path.join(os.path.realpath(tempfile.gettempdir()), probelib.PREFIX)
    left_procs = probelib.our_procs(prefix) + probelib.daemon_procs(prefix)
    left_dirs = glob.glob(prefix + "*")
    print("\n== 總結")
    for n, rc, dt in results:
        print("  [%s] %s（%.1f 秒）" % ("OK" if rc == 0 else "NG rc=%d" % rc, n, dt))
    print("  [%s] 沒有殘留程序 %s" % ("OK" if not left_procs else "NG", left_procs or ""))
    print("  [%s] 沒有殘留暫存 %s" % ("OK" if not left_dirs else "NG", left_dirs or ""))
    return 0 if all(rc == 0 for _, rc, _ in results) and not left_procs and not left_dirs else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
