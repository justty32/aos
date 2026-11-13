# Check daemon_ctl.state_path: ask AOS_KERNEL for the table file with a query letter (a fake kernel answers), KernelFailed when nobody answers, and reading a table by its file path.
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(PROTO / "py"), str(PROTO / "lib")]
import daemon_ctl as dc  # noqa: E402
sp = importlib.import_module("daemon_ctl.state_path")   # the module: once wired, the package attribute state_path is the function

BINS = ":".join(str(p) for p in sorted((PROTO / "impls").glob("*/bin")))


class FakeKernel(threading.Thread):
    """A mailbox reader standing in for a kernel: takes each letter in BOX/new and answers it with answer(body) (None = no reply)."""

    def __init__(self, box, answer):
        super().__init__(daemon=True)
        self.box, self.answer, self.seen, self.stop = Path(box), answer, [], threading.Event()

    def run(self):
        while not self.stop.is_set():
            for name in sorted(os.listdir(self.box / "new")):
                cur = self.box / "cur" / name
                try:
                    os.rename(self.box / "new" / name, cur)
                except OSError:
                    continue
                letter = json.loads((cur / "letter.json").read_text())
                self.seen.append(letter["body"])
                reply = self.answer(letter["body"])
                if reply is not None and letter.get("reply_to"):
                    subprocess.run(["aos-post", "send", "--in-reply-to", name, os.path.join(self.box, letter["reply_to"])],
                                   input=json.dumps(reply), text=True, stdout=subprocess.DEVNULL, check=True)
                shutil.rmtree(cur)
            time.sleep(0.02)

    def close(self):
        self.stop.set()
        self.join(5)


class StatePath(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="state-path-")))
        self.saved, self.cwd = dict(os.environ), os.getcwd()
        for key in [k for k in os.environ if k.startswith("AOS_")]:
            del os.environ[key]
        os.environ["PATH"] = BINS + ":" + os.environ["PATH"]
        self.box = self.tmp / "station" / "requests"
        subprocess.run(["aos-post", "init", str(self.box)], check=True, stdout=subprocess.DEVNULL)
        self.d = self.tmp / "d"                       # a daemon folder with its own table: must NOT be read on the kernel route
        self.d.mkdir()
        (self.d / "procs_state.json").write_text(json.dumps({"procs": {"direct": {"phase": "running", "stack": "procs/direct"}}}))
        self.table = self.tmp / "given" / "trimmed.json"   # the table the kernel points at; not named procs_state.json
        self.table.parent.mkdir()
        self.table.write_text(json.dumps({"procs": {"ann": {"phase": "running", "stack": "procs/ann", "ws": "/abs/ws",
                                                            "exec": "defs/ann#/loop", "def": None}}}))
        self.kernel = None
        sp._asked.clear()

    def tearDown(self):
        if self.kernel:
            self.kernel.close()
        os.chdir(self.cwd)
        os.environ.clear()
        os.environ.update(self.saved)
        sp._asked.clear()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def serve(self, answer):
        self.kernel = FakeKernel(self.box, answer)
        self.kernel.start()

    def waiting(self):
        return sorted(os.listdir(self.box / "new"))

    def test_no_kernel_is_the_daemon_folder(self):
        os.environ["AOS_DAEMON"] = str(self.d)
        got = sp.state_path()
        self.assertEqual(got, str(self.d / "procs_state.json"))
        self.assertIsInstance(got, sp.TableFile)
        self.assertEqual(self.waiting(), [])

    def test_no_kernel_no_daemon_is_DaemonMissing(self):
        os.chdir(self.tmp)
        with self.assertRaises(dc.Fail) as e:
            sp.state_path()
        self.assertEqual(e.exception.code, "DaemonMissing")

    def test_daemon_flag_sends_no_letter(self):
        os.environ["AOS_KERNEL"] = str(self.box)
        self.assertEqual(sp.state_path(str(self.d)), str(self.d / "procs_state.json"))
        self.assertEqual(self.waiting(), [])
        self.assertFalse((self.box / "reply").exists())

    def test_kernel_answers_and_is_asked_once(self):
        os.environ.update(AOS_KERNEL=str(self.box), AOS_DAEMON=str(self.d))
        self.serve(lambda body: {"applied": True, "procs_state_path": str(self.table)})
        got = sp.state_path()
        self.assertEqual(got, str(self.table))
        self.assertIsInstance(got, sp.TableFile)
        self.assertEqual(sp.state_path(), got)
        self.assertEqual(self.kernel.seen, [{"procs_state_path": True}])
        self.assertEqual(list(sp.rows_at(got)), ["ann"])              # the kernel's table, not AOS_DAEMON's

    def test_no_reply_is_KernelFailed_and_AOS_DAEMON_is_not_read(self):
        os.environ.update(AOS_KERNEL=str(self.box), AOS_DAEMON=str(self.d))
        started = time.monotonic()
        with self.assertRaises(dc.Fail) as e:
            sp.state_path(timeout_s=0.4)
        self.assertEqual(e.exception.code, "KernelFailed")
        self.assertIn("no reply from AOS_KERNEL=%s within 0.4 s" % self.box, str(e.exception))
        self.assertGreaterEqual(time.monotonic() - started, 0.4)
        self.assertEqual(self.waiting(), [])                          # the unanswered query was withdrawn

    def test_default_wait_is_three_seconds(self):
        self.assertEqual(sp.QUERY_S, 3)

    def test_refusal_code_goes_into_the_error(self):
        os.environ["AOS_KERNEL"] = str(self.box)
        self.serve(lambda body: {"applied": False, "error": {"code": "BodyBad", "msg": "procs_state_path must be true"}})
        with self.assertRaises(dc.Fail) as e:
            sp.state_path()
        self.assertEqual(e.exception.code, "KernelFailed")
        self.assertIn("BodyBad procs_state_path must be true", str(e.exception))

    def test_null_path_is_StateMissing(self):
        os.environ["AOS_KERNEL"] = str(self.box)
        self.serve(lambda body: {"applied": True, "procs_state_path": None})
        with self.assertRaises(dc.Fail) as e:
            sp.state_path()
        self.assertEqual(e.exception.code, "StateMissing")

    def test_reply_without_the_key_is_KernelFailed(self):
        os.environ["AOS_KERNEL"] = str(self.box)
        self.serve(lambda body: {"applied": True})                    # e.g. a daemon too old to know the query
        with self.assertRaises(dc.Fail) as e:
            sp.state_path()
        self.assertEqual(e.exception.code, "KernelFailed")
        self.assertIn("does not carry procs_state_path", str(e.exception))

    def test_relative_path_in_the_reply_is_StateBad(self):
        os.environ["AOS_KERNEL"] = str(self.box)
        self.serve(lambda body: {"applied": True, "procs_state_path": "procs_state.json"})
        with self.assertRaises(dc.Fail) as e:
            sp.state_path()
        self.assertEqual(e.exception.code, "StateBad")

    def test_kernel_that_is_no_mailbox_is_MailboxMissing(self):
        os.environ["AOS_KERNEL"] = str(self.tmp / "nowhere")
        with self.assertRaises(dc.Fail) as e:
            sp.state_path()
        self.assertEqual(e.exception.code, "MailboxMissing")

    def test_reply_box_of_a_shell_is_under_the_kernel(self):
        os.environ["AOS_KERNEL"] = str(self.box)
        self.assertEqual(sp.kernel_reply_box(), str(self.box / "reply"))
        self.assertTrue((self.box / "reply" / "new").is_dir())

    def test_reply_box_of_a_proc_is_in_its_stack(self):
        stack = self.tmp / "me"
        stack.mkdir()
        os.environ.update(AOS_KERNEL=str(self.box), AOS_STACK=str(stack))
        self.assertEqual(sp.kernel_reply_box(), str(stack / "daemon_reply"))
        self.assertFalse((self.box / "reply").exists())

    def test_rows_count_from_the_folder_of_the_table_file(self):
        row = sp.rows_at(str(self.table))["ann"]
        base = str(self.table.parent)
        self.assertEqual(row["stack"], base + "/procs/ann")
        self.assertEqual(row["ws"], "/abs/ws")
        self.assertEqual(row["exec"], base + "/defs/ann#/loop")
        self.assertIsNone(row["def"])

    def test_split_table_parts_count_from_the_same_folder(self):
        (self.table.parent / "part0.json").write_text(json.dumps({"bob": {"phase": "stopped", "stack": "procs/bob"}}))
        self.table.write_text(json.dumps({"procs": {"$ref": ["part0.json"]}}))
        self.assertEqual(sp.rows_at(str(self.table))["bob"]["stack"], str(self.table.parent / "procs" / "bob"))

    def test_missing_and_broken_table_files(self):
        with self.assertRaises(dc.Fail) as e:
            sp.state_at(str(self.tmp / "gone.json"))
        self.assertEqual(e.exception.code, "StateMissing")
        self.table.write_text("{not json")
        with self.assertRaises(dc.Fail) as e:
            sp.state_at(str(self.table))
        self.assertEqual(e.exception.code, "StateBad")

    def test_same_rows_as_the_folder_reader_for_a_daemon_table(self):
        self.assertEqual(sp.state_at(str(self.d / "procs_state.json")), dc.state(str(self.d)))

    def test_names_come_from_the_table_file(self):
        self.table.write_text(json.dumps({"procs": {}, "procs_loop": "body.json", "procs_requests": None}))
        names = sp.names_at(str(self.table))
        self.assertEqual((names["procs_loop"], names["procs_requests"], names["procs_stderr"]), ("body.json", None, "stderr.txt"))


if __name__ == "__main__":
    unittest.main()
