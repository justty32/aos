"""固定回歸矩陣（test_matrix_*.py）共用的小工具：故障注入、SIGKILL 子程序、記錄執行次數的任務、產生獨立 test 方法。

**AOS7_TEST_* 環境變數只給測試用**（`AOS7_TEST_FAULT` 故障注入、`AOS7_TEST_FAULT_HITS` 注入命中紀錄檔、`AOS7_TEST_CRASH`／`AOS7_TEST_RUNNER_CRASH`
在指定點 SIGKILL 自己、`AOS7_TEST_HANG`），正常環境不設；tick 起任務時把它們從任務環境拿掉
（`AOS7_TEST_RUNNER_CRASH` 由 aos7-run 起任務前自己拿掉）。

**每個注入都要證明打中（astra-2 第二節）**：healthy /proc 12 案曾有 9 案注入命中 0 次仍全過——綠燈不代表測到了。
所以 `fault()`／`Fault` 一律同時設 `AOS7_TEST_FAULT_HITS`（lib 的 aos7_fs.inject 真的丟出注入的 OSError 時在那個檔追加
`op<TAB>errno<TAB>path`；子程序 tick／tock／daemon 繼承環境也會記），`fault()` 區塊正常結束時自動斷言「規則裡每個 op
都命中 ≥1 次」；`MatrixCase.run_prog` 帶 AOS7_TEST_FAULT 時也一樣（跑完就斷言）。

這個檔不是測試（檔名不以 test 開頭，unittest discover 不收），只被 test_matrix_*.py import。
"""
import contextlib
import os
import signal
import subprocess
import sys
import tempfile
import time
from unittest import mock

from base import BIN, CoreCase, DaemonCase  # noqa: F401  （DaemonCase 給各檔 re-export）
import aos7_proc
import aos7_task
import aos7_tick
import aos7_tock
from aos7_fs import read_json

ERRNOS = ("EIO", "ESTALE", "EACCES")


def gen(cls, prefix, params, body, doc=None):
    """替 cls 產生一個個獨立的 test 方法：`test_<prefix>_<參數名>`，呼叫 body(self, *參數值)。

    params 是 [(名字片段, (參數…)), …]；名字片段裡的非英數字元換成 `_`。測試數就等於矩陣項數。"""
    for name, args in params:
        safe = "".join(c if c.isalnum() else "_" for c in name).strip("_")

        def t(self, _a=args):
            return body(self, *_a)
        t.__name__ = "test_%s_%s" % (prefix, safe)
        t.__doc__ = "%s［%s］" % (doc or body.__doc__ or prefix, name)
        assert not hasattr(cls, t.__name__), t.__name__
        setattr(cls, t.__name__, t)


def rule_ops(spec):
    """規則字串（`op:glob:ERRNO;…`，分號或換行分隔）裡出現的 op 集合（格式不對的規則略過，跟 aos7_fs.inject 一致）。"""
    out = set()
    for rule in spec.replace("\n", ";").split(";"):
        parts = rule.strip().split(":")
        if len(parts) == 3 and parts[0]:
            out.add(parts[0])
    return out


class Fault:
    """一組故障注入＋它的命中紀錄檔。`env` 是要給程序的環境（AOS7_TEST_FAULT＋AOS7_TEST_FAULT_HITS）。

    rules 是 `op:glob:ERRNO;…`，或 `@/規則檔`（每次注入時從那個檔讀；給跑著的 daemon 中途開關用）。
    ops：要斷言命中的 op；省略時從 rules 解析（`@規則檔` 在建立時讀檔，檔還不在就要明確給 ops，否則 check 時再讀一次）。
    命中紀錄檔放系統暫存（前綴 aos72-test-hits-），close() 刪掉。"""

    def __init__(self, rules, ops=None):
        self.rules = rules
        fd, self.path = tempfile.mkstemp(prefix="aos72-test-hits-", suffix=".tsv")
        os.close(fd)
        self.env = {"AOS7_TEST_FAULT": rules, "AOS7_TEST_FAULT_HITS": self.path}
        self.ops = set(ops) if ops is not None else self._parse()

    def _parse(self):
        if not self.rules.startswith("@"):
            return rule_ops(self.rules)
        try:
            with open(self.rules[1:], encoding="utf-8") as f:
                return rule_ops(f.read())
        except OSError:
            return set()

    def records(self):
        """命中紀錄 [(op, errno 名, 路徑), …]（檔讀不到當沒有）。"""
        try:
            with open(self.path, encoding="utf-8") as f:
                return [tuple(ln.rstrip("\n").split("\t", 2)) for ln in f if ln.strip()]
        except OSError:
            return []

    def hits(self, op=None):
        """命中次數；給 op 只算那個 op。"""
        return sum(1 for r in self.records() if op is None or r[0] == op)

    def check(self, ops=None, where=""):
        """斷言 ops（省略＝建立時的 ops）每個都命中 ≥1 次；沒打中丟 AssertionError，訊息說清楚哪個 op、規則、全部命中。"""
        want = set(ops) if ops is not None else (self.ops or self._parse())
        if not want:
            raise AssertionError("故障注入%s：規則 %r 解析不出任何 op，無法證明有打中" % (where, self.rules))
        recs = self.records()
        miss = sorted(op for op in want if not any(r[0] == op for r in recs))
        if miss:
            seen = {}
            for r in recs:
                seen[r[0]] = seen.get(r[0], 0) + 1
            raise AssertionError("故障注入沒打中%s：op %s 命中 0 次（規則 %r；各 op 命中次數 %r）——這個案例沒測到指定的讀取失敗"
                                 % (where, "、".join(miss), self.rules, seen))

    def close(self):
        try:
            os.remove(self.path)
        except OSError:
            pass


@contextlib.contextmanager
def fault(rules, ops=None, check=True):
    """同程序注入：在 with 區塊裡設 AOS7_TEST_FAULT（`op:glob:ERRNO;…` 或 `@規則檔`）與 AOS7_TEST_FAULT_HITS，yield Fault。

    區塊裡起的子程序（run_prog、start_daemon）繼承環境，命中也記在同一個檔。區塊**正常結束**時（check=True）斷言 ops
    （省略＝規則裡的每個 op）都命中 ≥1 次；區塊裡已經丟例外就不再斷言（不蓋掉原本的失敗）。"""
    f = Fault(rules, ops)
    try:
        with mock.patch.dict(os.environ, f.env):
            yield f
        if check:
            f.check()
    finally:
        f.close()


@contextlib.contextmanager
def env(**kw):
    with mock.patch.dict(os.environ, kw):
        yield


def rec_argv(name, keep=False, short_first=False):
    """每跑一次往 node 的 ran-<name>.txt 加一行 $AOS7_RUN（槽外副作用：數得出到底執行了幾次）。

    keep=True：記完 exec sleep 60（環境帶著 AOS7_*，身分掃描找得到）。
    short_first=True：第一次執行只睡 0.2 秒就結束（給 runner-before-exit 這種要任務先結束的點），之後的執行才長睡。
    最後的命令一律 `exec`：dash（Ubuntu 24.04 的 /bin/sh）不把 -c 的最後一個命令 exec 掉、會 fork 出子程序，同一個 run 就有
    sh＋sleep 兩個活程序，數「同槽活程序」的斷言會誤判雙開。"""
    rec = 'echo $AOS7_RUN >> "$AOS7_NODE/ran-%s.txt"' % name
    if short_first:
        mark = '"$AOS7_NODE/first-done-%s"' % name
        return ["sh", "-c", rec + "; if [ -e %s ]; then exec sleep 60; fi; touch %s; exec sleep 0.2" % (mark, mark)]
    if keep:
        return ["sh", "-c", rec + "; exec sleep 60"]
    return ["sh", "-c", rec]


def dead_pid():
    """一個確定已經不在的 pid（起一個 true、wait 完拿它的 pid）。"""
    p = subprocess.Popen(["true"])
    p.wait()
    return p.pid


def alive(pid):
    return aos7_proc.pid_alive(pid)


class MatrixCase(CoreCase):
    """矩陣共用：子程序 tick／tock（看退出碼）、數執行次數、收集總結、同槽活程序數。"""

    def run_prog(self, name, nid="a", env=None, fault_ops=None):
        """跑 bin/name，回 (退出碼, 最後一行 JSON 或 None, stderr)。不檢查退出碼。

        env 帶 AOS7_TEST_FAULT（又沒自己帶 AOS7_TEST_FAULT_HITS）時自動配一個命中紀錄檔，跑完斷言 fault_ops
        （省略＝規則裡每個 op）都命中 ≥1 次。"""
        env = dict(env or {})
        f = None
        if env.get("AOS7_TEST_FAULT") and "AOS7_TEST_FAULT_HITS" not in env:
            f = Fault(env["AOS7_TEST_FAULT"], fault_ops)
            env.update(f.env)
        try:
            p = subprocess.run([sys.executable, os.path.join(BIN, name), self.root, nid], capture_output=True,
                               text=True, timeout=30, env=dict(os.environ, **env))
            if f:
                f.check(where="（子程序 %s，rc=%r，stderr=%s）" % (name, p.returncode, p.stderr.strip()[-300:]))
        finally:
            if f:
                f.close()
        out = p.stdout.strip().splitlines()
        try:
            j = __import__("json").loads(out[-1]) if out else None
        except ValueError:
            j = None
        return p.returncode, j, p.stderr

    def crash(self, name, point, nid="a", extra=None):
        """子程序跑 name，AOS7_TEST_CRASH=point：要被 SIGKILL（退出碼 -9）。"""
        rc, out, err = self.run_prog(name, nid, dict(extra or {}, AOS7_TEST_CRASH=point))
        self.assertEqual(rc, -signal.SIGKILL, "%s 沒在 %s 被 SIGKILL（rc=%r, out=%r, err=%s）" % (name, point, rc, out, err))
        return rc

    def ran(self, node, name):
        try:
            with open(os.path.join(node, "ran-%s.txt" % name)) as f:
                return f.read().split()
        except OSError:
            return []

    def live_procs(self, node, slot):
        """同槽活程序（不含 aos7-run）：身分掃描 NODE＋TID。"""
        return aos7_proc.env_procs(node, slot, runners=False)

    def assert_le_one(self, node, slot, when):
        ps = self.live_procs(node, slot)
        self.assertLessEqual(len(ps), 1, "%s：槽 %s 同時有 %d 個活程序 %s（雙開）" % (when, slot, len(ps), ps))

    def settle(self, node, slot, timeout=5):
        """槽裡的 run 如果看起來還活著（不是 unsure），等它結束或判得出不在（once 任務很快）；等不到不算失敗，交給後面的判定。"""
        end = time.monotonic() + timeout
        while time.monotonic() < end and os.path.isdir(self.slot(node, slot)):
            v = self.view(node, slot)
            if not (v.state == aos7_task.LIVE and not v.get("unsure") and v.run is not None):
                return
            time.sleep(0.02)

    def kill_runner_and_task(self, node, slot):
        """先 SIGKILL runner（它就寫不了 exit.json）、再 SIGKILL 任務的群組；等兩個都不在。回 (runner pid, 任務 pid)。"""
        b = self.birth(node, slot)
        pj = self.wait_pid(node, slot)
        rp = (b.get("runner") or {}).get("pid")
        if rp:
            try:
                os.kill(rp, signal.SIGKILL)
            except OSError:
                pass
        self.wait_for(lambda: not alive(rp), 5, "runner 收不掉")
        try:
            os.killpg(pj["pgid"], signal.SIGKILL)
        except OSError:
            pass
        self.wait_for(lambda: not alive(pj["pid"]), 5, "任務收不掉")
        return rp, pj["pid"]

    def exit_raw(self, node, slot):
        return read_json(os.path.join(self.slot(node, slot), "exit.json"))

    def ends_of(self, summaries, slot):
        return [e for s in summaries for e in (s.get("ended") or []) if str(e.get("run", "")).startswith(slot + "#")]

    def errors_for(self, summary, slot):
        return [e for e in (summary.get("errors") or []) if e.get("slot") == slot]

    def raw(self, path):
        try:
            with open(path, "rb") as f:
                return f.read()
        except OSError:
            return None


def itick(root, nid="a"):
    return aos7_tick.tick(root, nid)


def itock(root, nid="a", early=None):
    return aos7_tock.tock(root, nid, early)


def wait_until(pred, timeout=5.0, step=0.02):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = pred()
        if v:
            return v
        time.sleep(step)
    return None
