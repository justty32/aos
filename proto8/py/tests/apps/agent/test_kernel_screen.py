# 驗證 kernel 畫面入口環境與 purge 的回信、關畫面、刪 stack 次序。
import contextlib
import io
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(PROTO / "py"), str(PROTO / "py")]
from aos.apps.agent import common, decl
from aos.apps.agent.ctl import phase, rm


class EntryEnvironment(unittest.TestCase):
    def entry(self, env, kernel):
        agent = common.Agent("ann", {"stack": "/stack/ann", "ws": "/ws"})
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(decl, "via_kernel", return_value=kernel), \
                mock.patch.object(decl, "daemon_path", return_value="/chosen") as path, \
                mock.patch.object(decl.subprocess, "run", return_value=mock.Mock(returncode=0, stderr="")) as run:
            self.assertEqual(decl.run_entry(agent, "/screen", ["watch"]), (0, ""))
            return run.call_args.kwargs["env"], path.call_count

    def test_kernel_preserves_caller_daemon_and_kernel(self):
        original = {"AOS_KERNEL": "/kernel", "AOS_DAEMON": "/caller", "PATH": "/bin"}
        env, calls = self.entry(original, True)
        self.assertEqual(env, original)
        self.assertEqual(calls, 0)
        env, _ = self.entry({"AOS_KERNEL": "/kernel"}, True)
        self.assertNotIn("AOS_DAEMON", env)

    def test_direct_names_daemon_and_removes_kernel(self):
        env, calls = self.entry({"AOS_KERNEL": "/kernel", "AOS_DAEMON": "/old"}, False)
        self.assertEqual(env, {"AOS_DAEMON": "/chosen"})
        self.assertEqual(calls, 1)

    def test_no_kernel_matches_previous_environment(self):
        original = {"AOS_DAEMON": "/old", "PATH": "/bin", "OTHER": "kept"}
        env, _ = self.entry(original, False)
        self.assertEqual(env, dict(original, AOS_DAEMON="/chosen"))


class PurgeScreen(unittest.TestCase):
    def exercise(self, kernel=True, refused=False, definition=True):
        row = {"stack": "/stack/ann", "ws": "/ws"}
        if definition:
            row["def"] = "/definition"
        agent = common.Agent("ann", row)
        events = []

        def wait(*args, **kwargs):
            events.append("reply")
            if refused:
                raise common.Fail("CtlRejected", "request refused")
            return True

        with contextlib.ExitStack() as scope:
            for name, value in (("via_kernel", mock.Mock(return_value=kernel)), ("need_table", mock.Mock()),
                                ("find", mock.Mock(side_effect=lambda name: (events.append("read"), agent)[1])),
                                ("table", mock.Mock(return_value={"ann": row})), ("row_named", mock.Mock(return_value=None)),
                                ("wait_for", mock.Mock(side_effect=lambda *args: events.append("removed"))), ("daemon_path", mock.Mock(return_value="/daemon")),
                                ("covers", mock.Mock(return_value=None)), ("ctl_wait", mock.Mock(side_effect=wait)),
                                ("close_screen_if_any", mock.Mock(side_effect=lambda a: events.append("close")))):
                scope.enter_context(mock.patch.object(rm, name, value))
            scope.enter_context(mock.patch.object(rm.aos_flags, "confirm", return_value=True))
            scope.enter_context(mock.patch.object(rm.shutil, "rmtree", side_effect=lambda *a, **k: events.append("delete")))
            warning = scope.enter_context(mock.patch.object(rm.aos_flags, "warn"))
            scope.enter_context(contextlib.redirect_stdout(io.StringIO()))
            if refused:
                with self.assertRaises(common.Fail):
                    rm.cmd(["--purge", "-y", "ann"])
            else:
                rm.cmd(["--purge", "-y", "ann"])
        return events, warning

    def test_kernel_purge_closes_after_success_before_deletion(self):
        self.assertEqual(self.exercise()[0], ["read", "reply", "close", "removed", "delete"])

    def test_refused_kernel_purge_keeps_screen_and_stack(self):
        self.assertEqual(self.exercise(refused=True)[0], ["read", "reply"])

    def test_missing_definition_warns_then_purges(self):
        events, warning = self.exercise(definition=False)
        self.assertEqual(events, ["read", "reply", "removed", "delete"])
        warning.assert_called_once_with(rm.PROG, "cannot close the screen of ann (the table has no def); close it before rm next time")

    def test_direct_order_is_unchanged(self):
        self.assertEqual(self.exercise(kernel=False)[0], ["read", "close", "reply", "delete"])

    def test_letter_only_rm_and_stop_do_not_close_or_read_table(self):
        with mock.patch.object(rm, "via_kernel", return_value=True), mock.patch.object(rm, "ctl_wait", return_value=True), \
                mock.patch.object(rm, "find", side_effect=AssertionError("unexpected lookup")), \
                mock.patch.object(rm, "close_screen_if_any", side_effect=AssertionError("unexpected close")), \
                contextlib.redirect_stdout(io.StringIO()):
            rm.cmd(["ann"])
        with mock.patch.object(phase, "via_kernel", return_value=True), mock.patch.object(phase, "by_letter", return_value="ann"), \
                mock.patch.object(phase, "need_table", side_effect=AssertionError("unexpected lookup")), \
                mock.patch.object(phase, "close_screen_if_any", side_effect=AssertionError("unexpected close")), \
                contextlib.redirect_stdout(io.StringIO()):
            phase.cmd_stop(["ann"])


if __name__ == "__main__":
    unittest.main()
