"""測試鉤子（只給測試）：核心 `aos7_fs.inject`／`test_point` 在環境變數 `AOS7_TEST_HOOKS` 指到這個檔時才載入它。

tests/base.py 在 import 時設好 `AOS7_TEST_HOOKS`，所以測試起的 daemon、tick、tock、aos7-run 都繼承到；
aos7-run 交給任務的環境拿掉所有 `AOS7_TEST_*`。規則都由環境變數給（正常環境沒有這些變數）：

- `AOS7_TEST_FAULT`：故障注入。分號（或換行）分隔的 `op:glob:ERRNO`（例 `proc-stat:*:EIO;open:*/round.json:ESTALE`），
  glob 用 fnmatch 比完整路徑；值是 `@/路徑` 時每次從那個檔讀規則（檔不在＝沒有注入；給跑著的 daemon 中途開關用）。
  op：proc-list、proc-stat、proc-environ、proc-cmdline、open（讀檔入口 fact）、listdir（列槽）、stat（daemon 看 node）、
  node-open（tick／tock 開 node）。
- `AOS7_TEST_FAULT_HITS`：注入真的命中時，在這個檔追加一行 `op<TAB>errno<TAB>path`（astra-2 矩陣盲點：每個案例都要證明
  故障確實打中 ≥1 次，不能只靠綠燈）。用檔案不用記憶體計數：子程序命中的也算得到。寫不進去就算了。
- `AOS7_TEST_CRASH`：逗號分隔的測試點名，跑到就 SIGKILL 自己（模擬 kill -9 打在那一步）。
- `AOS7_TEST_RUNNER_CRASH`：同上，給 aos7-run 的點（runner-before-pid、runner-before-exit）。
- `AOS7_TEST_HANG`：跑到這些點就長睡（模擬卡住）。
"""
import errno
import fnmatch
import os
import re
import signal
import time


def inject(op, path):
    """環境 `AOS7_TEST_FAULT` 有符合 op 與 path 的規則就丟那個 errno 的 OSError（並記命中）。"""
    spec = os.environ.get("AOS7_TEST_FAULT")
    if not spec:
        return
    if spec.startswith("@"):
        try:
            with open(spec[1:], encoding="utf-8") as f:
                spec = f.read()
        except OSError:
            return
    for rule in re.split(r"[;\n]", spec):
        parts = rule.strip().split(":")
        if len(parts) != 3 or parts[0] != op or not fnmatch.fnmatchcase(str(path), parts[1]):
            continue
        code = getattr(errno, parts[2].strip(), None)
        if isinstance(code, int):
            _record_hit(op, path, parts[2].strip())
            raise OSError(code, "%s（AOS7_TEST_FAULT 注入）" % os.strerror(code), str(path))


def _record_hit(op, path, name):
    """注入命中時在 `AOS7_TEST_FAULT_HITS` 指的檔追加一行 `op<TAB>errno<TAB>path`；寫不進去不影響被測程式。"""
    hits = os.environ.get("AOS7_TEST_FAULT_HITS")
    if not hits:
        return
    try:
        with open(hits, "a", encoding="utf-8") as f:
            f.write("%s\t%s\t%s\n" % (op, name, path))
    except OSError:
        pass


def _listed(var, name):
    v = os.environ.get(var)
    return bool(v) and name in v.split(",")


def test_point(name):
    """`AOS7_TEST_CRASH`／`AOS7_TEST_RUNNER_CRASH` 列到 name 就 SIGKILL 自己；`AOS7_TEST_HANG` 列到就長睡。"""
    if _listed("AOS7_TEST_CRASH", name) or _listed("AOS7_TEST_RUNNER_CRASH", name):
        os.kill(os.getpid(), signal.SIGKILL)
    if _listed("AOS7_TEST_HANG", name):
        time.sleep(10 ** 6)
