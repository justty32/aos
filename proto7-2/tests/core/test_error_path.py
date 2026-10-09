"""〔error-path〕錯誤路徑一致性（notes/blueprint-errors.md）；清單與欄位見 ../error_path.json。"""
import contextlib
import fcntl
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOP = str(Path(__file__).resolve().parents[2])

def problems(row, top):
    out, exempt = [], row.get("exempt", {})
    entry = os.path.join(top, row["entry"])
    cmd = [sys.executable, entry] if entry.endswith(".py") else [entry]

    def run(tag, c):
        tmp = os.path.realpath(tempfile.mkdtemp(prefix="aos72-test-errpath-"))
        modes, p = [], None
        expand = lambda v: v.replace("{tmp}", tmp)

        def path(v):  # 只准在暫存夾內
            d = Path(os.path.realpath(os.path.join(tmp, expand(v))))
            if not d.is_relative_to(tmp):
                raise ValueError(v + " 逃出暫存夾")
            return d
        snap = lambda: sorted((d, f, os.lstat(os.path.join(d, f)).st_mtime_ns)
                              for d, ds, fs in os.walk(tmp) for f in ds + fs)
        try:
            env = {k: v for k, v in os.environ.items() if not k.startswith("AOS")}
            env.update({k: expand(v) for k, v in c.get("env", {}).items()})
            for key, val in c.get("files", {}).items():
                d = path(key)
                (d if key[-1] == "/" else d.parent).mkdir(parents=True, exist_ok=True)
                if key[-1] != "/":
                    d.write_text(val if isinstance(val, str) else json.dumps(val))
            for key, mode in c.get("chmod", {}).items():
                d = path(key)
                modes.append((d, d.stat().st_mode))
                d.chmod(int(mode, 8))
            with contextlib.ExitStack() as st:
                for key in c.get("lock", []):  # 非阻塞，不卡死
                    fcntl.flock(st.enter_context(path(key).open("a+")), fcntl.LOCK_EX | fcntl.LOCK_NB)
                before = snap()
                p = subprocess.Popen(cmd + [expand(a) for a in c["argv"]], cwd=tmp, env=env,
                                     stdin=-3, stdout=-1, stderr=-1, text=True, start_new_session=True)
                o, e = p.communicate(timeout=20)
                r = (p.returncode, o, e)
            if tag == "bad" and snap() != before:
                out.append("bad: 動了檔案")
            return r
        except (OSError, ValueError, subprocess.TimeoutExpired) as e:
            out.append(f"{tag}: 失敗：{e}")
        finally:
            if p:  # 連孫程序一起收，再刪暫存夾
                with contextlib.suppress(OSError):
                    os.killpg(p.pid, 9)
                p.communicate()
            for d, mode in reversed(modes):
                with contextlib.suppress(OSError):
                    d.chmod(mode)
            shutil.rmtree(tmp, ignore_errors=True)

    def check(tag, c, want, head):
        r = run(tag, c)
        if r is None:
            return None
        rc, so, se = r
        if rc != want:
            out.append(f"{tag}: 退出碼 {rc}，預期 {want}")
        if tag == "help":
            if not so.strip() or se or len(so.splitlines()) > 30:
                out.append("help: stdout 要有且 ≤30 行、stderr 要空")
            return r
        lines = [s for s in se.splitlines() if s.strip() and s[0] != "{"]  # JSON 行不算
        if len(lines) != 1:
            out.append(f"{tag}: 人話應一行，實際 {len(lines)} 行")
        elif head is not None and not (lines[0].startswith(head) and lines[0][len(head):].strip()):
            out.append(f"{tag}: 應以「{head}」開頭且有內容")
        else:
            return lines[0][len(head or ""):]

    name = row["name"] + ": "
    if "help" not in exempt:
        check("help", {"argv": row.get("help", ["--help"])}, 0, None)
    bad = row.get("bad", ["--no-such-option"])
    fmt = "format" not in exempt
    body = check("bad", bad if isinstance(bad, dict) else {"argv": bad}, row.get("bad_code", 2),
                 name if fmt else None)
    if fmt and body is not None:
        what, _, how = body.partition("。")
        if not what.strip() or not how.strip():
            out.append("bad: 要「發生什麼。怎麼辦」兩句")
    if "unsure" not in exempt:
        if row.get("unsure") is None:
            out.append("unsure: 沒自報不確定案")
        else:
            check("unsure", row["unsure"], 3, name + "不確定：")
    return out

class TestErrorPath(unittest.TestCase):
    """〔error-path〕逐包檢查。"""

with open(os.path.join(TOP, "tests", "error_path.json"), encoding="utf-8") as fh:
    ROWS = json.load(fh)["rows"]
SKIPPED = [r["pack"] for r in ROWS if r.get("skip")]
if SKIPPED:
    print("error_path: skip %d 列：%s" % (len(SKIPPED), "、".join(SKIPPED)), file=sys.stderr)

def make_test(row):
    def test(self):
        issues = problems(row, TOP)
        self.assertEqual([], issues, "\n".join(issues))
    return unittest.skip(row["skip"])(test) if row.get("skip") else test

for n, row in enumerate(ROWS, 1):
    setattr(TestErrorPath, "test_%02d_%s" % (n, row["name"].replace("-", "_")), make_test(row))

FAKE = '''import fcntl, os, stat, sys
mode = VARIANT
if "--help" in sys.argv:
    print("aos7-fake\\n用法說明")
    if mode == "help_err":
        print("x", file=sys.stderr)
    sys.exit(0)
if "--unsure" in sys.argv:
    if mode == "lock":
        dst = os.environ["FIX"]
        assert open(dst).read() + open("d/v.json").read() == "原樣[1]"
        assert [stat.S_IMODE(os.stat(f).st_mode) for f in ("d/v.json", "e")] == [0o400, 0]
        with open(dst) as fh:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                sys.exit(0)
            except BlockingIOError:
                pass
    tail = {"unsure_prefix": "鎖忙", "unsure_empty": "不確定："}.get(mode, "不確定：鎖忙。再跑")
    print("aos7-fake: " + tail, file=sys.stderr)
    sys.exit(1 if mode == "unsure_code" else 3)
if mode == "bad_touch":
    open("touched", "w").close()
msg = {"bad_prefix": "aos7-fakx: 錯。例：-h", "bad_period": "aos7-fake: 錯，例：-h",
       "bad_what": "aos7-fake: 。例：-h"}.get(mode, "aos7-fake: 錯。例：-h")
print(msg, file=sys.stderr)
if mode == "bad_lines":
    print("usage: aos7-fake [--help]", file=sys.stderr)
sys.exit(1 if mode == "bad_code" else 2)
'''

class TestErrorPathSelf(unittest.TestCase):
    """〔error-path〕檢查器自測：假入口逐項弄壞要抓得到。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aos72-test-errpath-"))
        self.addCleanup(shutil.rmtree, self.tmp)

    def row(self, mode="good"):
        entry = self.tmp / (mode + ".py")
        entry.write_text(FAKE.replace("VARIANT", repr(mode)))
        return {"name": "aos7-fake", "entry": str(entry), "unsure": {"argv": ["--unsure"]}}

    def test_good(self):
        self.assertEqual([], problems(self.row(), TOP))

    def test_variants(self):
        for mode in ("help_err", "bad_code", "bad_lines", "bad_prefix", "bad_period", "bad_what",
                     "bad_touch", "unsure_code", "unsure_prefix", "unsure_empty", "no_unsure"):
            with self.subTest(mode=mode):
                row = self.row(mode)
                if mode == "no_unsure":
                    row["unsure"] = None
                self.assertTrue(problems(row, TOP))

    def test_fixtures_and_lock(self):
        row = self.row("lock")
        u = row["unsure"] = {"argv": ["--unsure"], "env": {"FIX": "{tmp}/d/held"},
                             "files": {"{tmp}/d/held": "原樣", "d/v.json": [1], "e/": ""},
                             "chmod": {"{tmp}/d/v.json": "0o400", "e": "0o000"}, "lock": ["d/held"]}
        self.assertEqual([], problems(row, TOP))
        u["lock"] = []
        self.assertTrue(problems(row, TOP))
        for bad in ({"lock": ["d/held", "{tmp}/d/held"]}, {"lock": ["d/held", "../aos72-test-errpath-esc"]}):
            with self.subTest(bad=bad):
                self.assertTrue(problems(dict(row, unsure=dict(u, **bad)), TOP))

if __name__ == "__main__":
    unittest.main()
