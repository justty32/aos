"""Test aos-sweeper tasks 1–17 with isolated files, real locks, and owned child processes."""
import datetime
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch


# Imports and CLI runs must not create bytecode files in the shared checkout.
sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "proto8" / "py"))
import aos_sweep
import aos_sweep_proc


BIN = REPO / "proto8" / "cmd" / "aos-sweeper" / "bin" / "aos-sweeper"
NOW = datetime.datetime(2026, 11, 10, 12, 34, 56, 789000,
                        tzinfo=datetime.timezone.utc).timestamp()
STAMP = "2026-11-10T12-34-56.789Z"
ARCHIVE_PATTERN = r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}\.\d{3}Z\.txt\.gz"


def clean_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def start_ticks(pid):
    # Field 22 follows a comm field that can itself contain spaces and ')'.
    text = Path(f"/proc/{pid}/stat").read_text()
    return int(text[text.rindex(")") + 1:].split()[19])


def snapshot(root):
    """Include the root and directories too; exclude access times changed by reads."""
    result = {}
    for path in [root, *sorted(root.rglob("*"))]:
        info = path.lstat()
        kind = stat.S_IFMT(info.st_mode)
        content = None
        if stat.S_ISREG(info.st_mode):
            content = hashlib.sha256(path.read_bytes()).hexdigest()
        elif stat.S_ISLNK(info.st_mode):
            content = os.readlink(path)
        result[str(path.relative_to(root))] = (
            kind, info.st_size, info.st_mtime_ns, content,
            info.st_ino, info.st_nlink, stat.S_IMODE(info.st_mode),
        )
    return result


class SweepTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="aos-sweeper-test-", dir="/tmp")
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name).resolve()
        self.d = self.tmp / "daemon"
        self.d.mkdir()
        self.boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        self.set_table({"a": "procs/a"})
        self.write_state(self.d, os.getpid())
        self.a = self.d / "procs" / "a"
        self.err = self.a / "stderr.txt"
        self.pending = self.d / ".sweeper_pending.json"

    def write_json(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data) + "\n", encoding="utf-8")

    def read_json(self, path):
        with path.open(encoding="utf-8") as stream:
            return json.load(stream)

    def set_table(self, rows, stderr="stderr.txt"):
        for stack in rows.values():
            (self.d / stack).mkdir(parents=True, exist_ok=True)
        self.write_json(self.d / "procs_state.json", {
            "pid": os.getpid(), "procs_stderr": stderr, "procs_loop": "loop.json",
            "procs": {name: {"stack": stack, "phase": "running", "pid": None}
                      for name, stack in rows.items()},
        })

    def write_state(self, cell, pid, ticks=None, boot=None):
        self.write_json(cell / "state.json", {
            "pid": pid,
            "started_at_ticks": start_ticks(pid) if ticks is None else ticks,
            "boot_id": self.boot if boot is None else boot,
        })

    def sweep(self, **opts):
        args = dict(min_bytes=1, retention_days=None, stop_grace_s=300,
                    dry_run=False, wait_s=0, now=NOW)
        args.update(opts)
        return aos_sweep.sweep(str(self.d), "aos-sweeper", **args)

    def purge(self, **opts):
        args = dict(dry_run=False, wait_s=0, now=NOW)
        args.update(opts)
        return aos_sweep.purge(str(self.d), "aos-sweeper", **args)

    def fast_process_checks(self):
        for key, value in (("MIN_AGE_S", 0), ("TERM_WAIT_S", 1)):
            override = patch.object(aos_sweep_proc, key, value)
            override.start()
            self.addCleanup(override.stop)

    def own_process(self, argv, **kwargs):
        proc = subprocess.Popen(argv, cwd=self.tmp, env=clean_env(),
                                start_new_session=True, **kwargs)
        self.addCleanup(self.kill_and_reap, proc)
        return proc

    def kill_and_reap(self, proc):
        try:
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            proc.wait(timeout=5)
        finally:
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream is not None:
                    stream.close()
        self.assertIsNotNone(proc.returncode, "owned child was not reaped")

    def loop(self, relative="procs/orphan", daemon=None, ignore_term=False):
        cell = self.d / relative
        cell.mkdir(parents=True, exist_ok=True)
        env = clean_env()
        env.update(AOS_STACK=str(cell) + "/",
                   AOS_DAEMON=str(self.d if daemon is None else daemon) + "/")
        program = (
            "import signal, sys, time\n"
            f"signal.signal(signal.SIGTERM, signal.{'SIG_IGN' if ignore_term else 'SIG_DFL'})\n"
            "sys.stdout.write('ready\\n'); sys.stdout.flush()\n"
            "time.sleep(600)\n"
        )
        proc = subprocess.Popen([sys.executable, "-c", program], cwd=self.tmp,
                                env=env, start_new_session=True,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL)
        self.addCleanup(self.kill_and_reap, proc)
        self.assertTrue(select.select([proc.stdout], [], [], 5)[0],
                        "child did not become ready")
        self.assertEqual(proc.stdout.readline(), b"ready\n")
        self.assertIsNone(proc.poll())
        self.write_state(cell, proc.pid)
        return cell, proc

    def cli(self, *args):
        proc = self.own_process([sys.executable, str(BIN), *map(str, args)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True)
        stdout, stderr = proc.communicate(timeout=8)
        return subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)

    def archive_files(self, cell=None):
        return sorted((self.a if cell is None else cell).glob("stderr_archives/*.gz"))

    def seed_archives(self, cell):
        adir = cell / "stderr_archives"
        adir.mkdir()
        archive = adir / f"{STAMP}.txt.gz"
        temporary = adir / f".{STAMP}.txt.gz.tmp"
        archive.write_bytes(b"archive payload")
        temporary.write_bytes(b"partial archive")
        return adir, archive, temporary

    def assert_uncontrolled(self, cell, proc):
        self.assertIsNone(proc.poll(), "protected child received a fatal signal")
        self.assertFalse((cell / "ctl.json").exists())
        self.assertFalse(self.pending.exists())

    def assert_archive(self, report, source, content):
        self.assertEqual(len(report["archived"]), 1)
        item = report["archived"][0]
        self.assertEqual(item["file"], str(source))
        self.assertEqual(item["bytes"], len(content))
        archive = Path(item["archive"])
        with gzip.open(archive, "rb") as stream:
            self.assertEqual(stream.read(), content)
        self.assertEqual(source.read_bytes(), b"")
        return archive

    def test_01_min_bytes_below_equal_and_above(self):
        self.set_table({key: f"procs/{key}" for key in ("below", "equal", "above")})
        for name, size in (("below", 3), ("equal", 4), ("above", 5)):
            (self.d / "procs" / name / "stderr.txt").write_bytes(b"x" * size)
        report = self.sweep(min_bytes=4)
        self.assertEqual({row["name"] for row in report["archived"]}, {"equal", "above"})
        for name, size in (("below", 3), ("equal", 4), ("above", 5)):
            with self.subTest(name=name):
                cell = self.d / "procs" / name
                self.assertEqual((cell / "stderr.txt").read_bytes(),
                                 b"x" * size if size < 4 else b"")
                self.assertEqual(len(self.archive_files(cell)), int(size >= 4))
                if size >= 4:
                    with gzip.open(self.archive_files(cell)[0], "rb") as stream:
                        self.assertEqual(stream.read(), b"x" * size)
                else:
                    self.assertFalse((cell / "stderr_archives").exists())

    def test_02_archive_payload_name_truncate_and_report(self):
        content = bytes(range(256)) * 37 + b"last line\n"
        self.err.write_bytes(content)
        report = self.sweep()
        archive = self.assert_archive(report, self.err, content)
        self.assertEqual(archive.parent, self.a / "stderr_archives")
        self.assertRegex(archive.name, "^" + ARCHIVE_PATTERN + "$")
        self.assertEqual(archive.name, STAMP + ".txt.gz")
        self.assertEqual(report["archived"][0]["name"], "a")
        self.assertEqual(self.err.stat().st_size, 0)
        self.assertEqual(report["archives"], {"files": 1, "bytes": archive.stat().st_size})

    def test_03_open_append_fd_continues_at_zero_without_holes(self):
        fd = os.open(self.err, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        self.addCleanup(os.close, fd)
        before, after = b"old content\n" * 200, b"new content\n"
        self.assertEqual(os.write(fd, before), len(before))
        inode = os.fstat(fd).st_ino
        report = self.sweep()
        self.assert_archive(report, self.err, before)
        self.assertEqual(self.err.stat().st_ino, inode)
        self.assertEqual(os.write(fd, after), len(after))
        self.assertEqual(self.err.read_bytes(), after)
        self.assertEqual(self.err.stat().st_size, len(after))
        self.assertNotIn(b"\0", self.err.read_bytes())
        self.assertEqual(os.lseek(fd, 0, os.SEEK_CUR), len(after))

    def test_04_custom_stderr_name_uses_matching_archive_directory(self):
        self.set_table({"a": "procs/a"}, stderr="err.log")
        source = self.a / "err.log"
        source.write_bytes(b"renamed stderr\n")
        archive = self.assert_archive(self.sweep(), source, b"renamed stderr\n")
        self.assertEqual(archive, self.a / "err_archives" / (STAMP + ".log.gz"))
        self.assertFalse((self.a / "stderr_archives").exists())

    def test_05_symlink_stderr_is_left_alone_with_warning(self):
        target = self.tmp / "target.txt"
        target.write_bytes(b"must survive a symlink\n")
        self.err.symlink_to(target)
        before = snapshot(self.a)
        target_before = (target.read_bytes(), target.stat().st_mtime_ns)
        report = self.sweep()
        self.assertEqual(report["archived"], [])
        self.assertEqual(snapshot(self.a), before)
        self.assertEqual((target.read_bytes(), target.stat().st_mtime_ns), target_before)
        self.assertTrue(any(str(self.err) in warning and "symlink" in warning
                            for warning in report["warnings"]))

    def test_05_hardlinked_stderr_is_left_alone_with_warning(self):
        target = self.tmp / "target.txt"
        target.write_bytes(b"must survive a hard link\n")
        os.link(target, self.err)
        self.assertGreater(self.err.stat().st_nlink, 1)
        before = snapshot(self.a)
        target_before = (target.read_bytes(), target.stat().st_mtime_ns)
        report = self.sweep()
        self.assertEqual(report["archived"], [])
        self.assertEqual(snapshot(self.a), before)
        self.assertEqual((target.read_bytes(), target.stat().st_mtime_ns), target_before)
        self.assertTrue(any(str(self.err) in warning and "hard links" in warning
                            for warning in report["warnings"]))

    def retention_fixture(self):
        adir = self.a / "stderr_archives"
        adir.mkdir()
        old = adir / "2026-10-31T12-34-56.789Z.txt.gz"
        recent = adir / "2026-11-09T12-34-56.789Z.txt.gz"
        keep = adir / "keep.txt"
        old.write_bytes(b"ten days old")
        recent.write_bytes(b"one day old")
        keep.write_bytes(b"foreign file")
        # Opposing mtimes prove retention uses the timestamp in the filename.
        os.utime(old, (NOW, NOW))
        os.utime(recent, (NOW - 30 * 86400, NOW - 30 * 86400))
        return old, recent, keep

    def test_06_retention_deletes_only_old_named_archives_and_counts_remaining(self):
        old, recent, keep = self.retention_fixture()
        old_size = old.stat().st_size
        report = self.sweep(retention_days=7)
        self.assertFalse(old.exists())
        self.assertEqual(recent.read_bytes(), b"one day old")
        self.assertEqual(keep.read_bytes(), b"foreign file")
        self.assertEqual(report["expired"], [{"name": "a", "dir": str(old.parent),
                                              "files": 1, "bytes": old_size}])
        self.assertEqual(report["archives"], {"files": 1, "bytes": recent.stat().st_size})

    def test_06_retention_none_preserves_every_archive_and_foreign_file(self):
        old, recent, keep = self.retention_fixture()
        before = snapshot(old.parent)
        report = self.sweep(retention_days=None)
        self.assertEqual(snapshot(old.parent), before)
        self.assertEqual(keep.read_bytes(), b"foreign file")
        self.assertEqual(report["expired"], [])
        self.assertEqual(report["archives"], {
            "files": 2, "bytes": old.stat().st_size + recent.stat().st_size,
        })

    def test_07_parse_retention_accepts_none_and_positive_days(self):
        self.assertIsNone(aos_sweep.parse_retention("none"))
        self.assertEqual(aos_sweep.parse_retention("7"), 7)

    def test_07_parse_retention_rejects_invalid_days(self):
        for value in ("0", "-1", "x", ""):
            with self.subTest(value=value), self.assertRaises(ValueError):
                aos_sweep.parse_retention(value)

    def test_08_purge_removes_archives_and_own_tmp_from_table_and_default_cells(self):
        self.fast_process_checks()
        cell, proc = self.loop("procs/x")
        self.err.write_bytes(b"table stderr stays\n")
        other_err = cell / "stderr.txt"
        other_err.write_bytes(b"off-table stderr stays\n")
        stderr_before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in (self.err, other_err)]
        seeded = [self.seed_archives(c) for c in (self.a, cell)]
        report = self.purge()
        self.assertEqual({row["dir"] for row in report["purged"]},
                         {str(parts[0]) for parts in seeded})
        self.assertTrue(all(row["files"] == 2 for row in report["purged"]))
        self.assertTrue(all(row["bytes"] == len(b"archive payloadpartial archive")
                            for row in report["purged"]))
        for adir, archive, temporary in seeded:
            self.assertFalse(archive.exists())
            self.assertFalse(temporary.exists())
            self.assertFalse(adir.exists())
        self.assertEqual([(p.read_bytes(), p.stat().st_mtime_ns)
                          for p in (self.err, other_err)], stderr_before)
        self.assertFalse(list(self.d.rglob("ctl.json")))
        self.assert_uncontrolled(cell, proc)
        self.assertFalse(report["processes"]["checked"])

    def test_08_purge_preserves_foreign_files_directory_and_warns(self):
        adir, archive, temporary = self.seed_archives(self.a)
        keep = adir / "keep.txt"
        keep.write_bytes(b"belongs to someone else")
        report = self.purge()
        self.assertFalse(archive.exists())
        self.assertFalse(temporary.exists())
        self.assertEqual(list(adir.iterdir()), [keep])
        self.assertEqual(keep.read_bytes(), b"belongs to someone else")
        self.assertEqual(report["purged"][0]["files"], 2)
        self.assertTrue(any(str(adir) in warning and "left alone" in warning
                            for warning in report["warnings"]))
        self.assertFalse(list(self.d.rglob("ctl.json")))

    def test_09_sweep_dry_run_changes_nothing_and_would_archive_expire_stop(self):
        self.fast_process_checks()
        cell, proc = self.loop()
        self.err.write_bytes(b"would archive this\n")
        old, _, _ = self.retention_fixture()
        self.assertFalse((self.d / ".sweeper.lock").exists())
        before = snapshot(self.d)
        report = self.sweep(dry_run=True, retention_days=7)
        self.assertEqual(snapshot(self.d), before)
        self.assertIs(report["dry_run"], True)
        self.assertEqual(len(report["archived"]), 1)
        self.assertEqual(report["archived"][0]["bytes"], len(b"would archive this\n"))
        self.assertEqual(report["expired"][0]["files"], 1)
        self.assertTrue(old.exists())
        self.assertTrue(any("would archive" in line for line in aos_sweep.lines(report)))
        self.assertTrue(any("would write stop" in row["action"]
                            for row in report["processes"]["orphans"]))
        self.assertFalse((self.d / ".sweeper.lock").exists())
        self.assert_uncontrolled(cell, proc)

    def test_09_sweep_dry_run_keeps_existing_pending_lock_and_does_not_signal(self):
        self.fast_process_checks()
        cell, proc = self.loop()
        (self.d / ".sweeper.lock").write_bytes(b"existing lock file")
        self.write_json(cell / "ctl.json", {"cmd": "stop", "seq": 1})
        self.write_json(self.pending, {str(cell): {
            "pid": proc.pid, "ticks": start_ticks(proc.pid), "stop_at": NOW - 500, "seq": 1,
        }})
        self.err.write_bytes(b"would archive\n")
        before = snapshot(self.d)
        report = self.sweep(dry_run=True, stop_grace_s=0)
        self.assertEqual(snapshot(self.d), before)
        self.assertIs(report["dry_run"], True)
        self.assertTrue(report["archived"])
        self.assertTrue(any(row["pid"] == proc.pid and "would signal" in row["action"]
                            for row in report["processes"]["orphans"]))
        self.assertIsNone(proc.poll())

    def test_09_purge_dry_run_changes_nothing_and_would_purge(self):
        self.fast_process_checks()
        cell, proc = self.loop("procs/x")
        self.err.write_bytes(b"stderr stays\n")
        for target in (self.a, cell):
            adir, _, _ = self.seed_archives(target)
            (adir / "keep.txt").write_bytes(b"foreign")
        before = snapshot(self.d)
        report = self.purge(dry_run=True)
        self.assertEqual(snapshot(self.d), before)
        self.assertIs(report["dry_run"], True)
        self.assertEqual(len(report["purged"]), 2)
        self.assertTrue(all(row["files"] == 2 for row in report["purged"]))
        self.assertTrue(any("would purge" in line for line in aos_sweep.lines(report)))
        self.assertFalse((self.d / ".sweeper.lock").exists())
        self.assert_uncontrolled(cell, proc)

    def hold_lock(self):
        stream = (self.d / ".sweeper.lock").open("a+b")
        self.addCleanup(stream.close)
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return stream

    def test_10_sweep_and_purge_raise_busy_without_changes(self):
        self.err.write_bytes(b"not while locked\n")
        self.seed_archives(self.a)
        self.hold_lock()
        before = snapshot(self.d)
        with self.assertRaises(aos_sweep.Busy):
            self.sweep(wait_s=0)
        with self.assertRaises(aos_sweep.Busy):
            self.purge(wait_s=0)
        self.assertEqual(snapshot(self.d), before)

    def test_10_sweep_waits_for_lock_released_by_thread(self):
        self.err.write_bytes(b"after lock release\n")
        stream = self.hold_lock()
        released = threading.Event()

        def release():
            time.sleep(0.3)
            fcntl.flock(stream, fcntl.LOCK_UN)
            released.set()

        thread = threading.Thread(target=release)
        start = time.monotonic()
        thread.start()
        self.addCleanup(thread.join, 5)
        report = self.sweep(wait_s=3)
        self.assertTrue(released.wait(timeout=1))
        self.assertGreaterEqual(time.monotonic() - start, 0.2)
        self.assert_archive(report, self.err, b"after lock release\n")
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())

    def test_10_bin_locked_round_warns_and_exits_zero(self):
        self.err.write_bytes(b"CLI must skip\n")
        self.hold_lock()
        before = snapshot(self.d)
        result = self.cli("--daemon", self.d, "--min-bytes", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("aos-sweeper: warning:", result.stderr)
        self.assertIn("skipped this round", result.stderr)
        self.assertEqual(snapshot(self.d), before)
        self.assertEqual(self.archive_files(), [])

    def test_11_absent_daemon_leaves_live_orphan_but_archives_stderr(self):
        self.fast_process_checks()
        cell, proc = self.loop()
        self.write_state(self.d, os.getpid(), ticks=start_ticks(os.getpid()) + 1)
        self.err.write_bytes(b"archive without a live daemon\n")
        report = self.sweep(stop_grace_s=0)
        self.assertIs(report["processes"]["checked"], False)
        self.assertIn("daemon not running", report["processes"]["note"])
        self.assertEqual(report["processes"]["orphans"], [])
        self.assert_uncontrolled(cell, proc)
        self.assert_archive(report, self.err, b"archive without a live daemon\n")

    def test_12_orphan_stop_grace_then_sigterm_and_pending_removed(self):
        self.fast_process_checks()
        cell, proc = self.loop()
        first = self.sweep()
        self.assertTrue(first["processes"]["checked"])
        self.assertEqual(self.read_json(cell / "ctl.json"), {"cmd": "stop", "seq": 1})
        expected = {str(cell): {"pid": proc.pid, "ticks": start_ticks(proc.pid),
                               "stop_at": NOW, "seq": 1}}
        self.assertEqual(self.read_json(self.pending), expected)
        self.assertIsNone(proc.poll())
        ctl_before = snapshot(cell)
        second = self.sweep(now=NOW + 1, stop_grace_s=300)
        self.assertIsNone(proc.poll())
        self.assertEqual(snapshot(cell), ctl_before)
        self.assertEqual(self.read_json(self.pending), expected)
        self.assertTrue(any("signals after 300 s" in row["action"]
                            for row in second["processes"]["orphans"]))
        third = self.sweep(now=NOW + 2, stop_grace_s=0)
        self.assertEqual(proc.wait(timeout=5), -signal.SIGTERM)
        self.assertTrue(any("sent SIGTERM" in row["action"]
                            for row in third["processes"]["orphans"]))
        self.assertFalse(self.pending.exists())

    def test_12_sigterm_ignoring_orphan_is_sigkilled(self):
        self.fast_process_checks()
        cell, proc = self.loop(ignore_term=True)
        self.sweep()
        self.assertEqual(self.read_json(cell / "ctl.json"), {"cmd": "stop", "seq": 1})
        self.assertIsNone(proc.poll())
        report = self.sweep(now=NOW + 1, stop_grace_s=0)
        self.assertEqual(proc.wait(timeout=5), -signal.SIGKILL)
        self.assertTrue(any("SIGTERM, then SIGKILL" in row["action"]
                            for row in report["processes"]["orphans"]))
        # A kill can race the immediate liveness check; the next round drops it.
        self.sweep(now=NOW + 2, stop_grace_s=0)
        self.assertFalse(self.pending.exists())

    def test_12_stop_sequence_advances_past_ctl_and_state_flux(self):
        self.fast_process_checks()
        cell, proc = self.loop()
        self.write_json(cell / "ctl.json", {"cmd": "pause", "seq": 4})
        self.write_json(cell / "state_flux.json", {"ctl_seq": 9})
        self.sweep()
        self.assertEqual(self.read_json(cell / "ctl.json"), {"cmd": "stop", "seq": 10})
        self.assertEqual(self.read_json(self.pending)[str(cell)]["seq"], 10)
        self.assertIsNone(proc.poll())

    def test_13_table_cell_is_never_stopped(self):
        self.fast_process_checks()
        cell, proc = self.loop("procs/a")
        for now in (NOW, NOW + 301):
            report = self.sweep(now=now, stop_grace_s=0)
            self.assertEqual(report["processes"]["orphans"], [])
            self.assert_uncontrolled(cell, proc)

    def test_13_other_daemon_environment_is_reported_but_not_stopped(self):
        self.fast_process_checks()
        cell, proc = self.loop(daemon=self.tmp / "different_daemon")
        for now in (NOW, NOW + 301):
            report = self.sweep(now=now, stop_grace_s=0)
            self.assert_uncontrolled(cell, proc)
            self.assertTrue(any(row["cell"] == "procs/orphan" and row["pid"] == proc.pid
                                and "not started by this daemon" in row["action"]
                                for row in report["processes"]["orphans"]))

    def test_13_fresh_child_under_default_sixty_seconds_is_only_reported(self):
        self.assertEqual(aos_sweep_proc.MIN_AGE_S, 60)
        cell, proc = self.loop()
        report = self.sweep(stop_grace_s=0)
        self.assert_uncontrolled(cell, proc)
        self.assertTrue(any(row["cell"] == "procs/orphan" and row["pid"] == proc.pid
                            and "younger than 60 s" in row["action"]
                            for row in report["processes"]["orphans"]))

    def test_13_cell_outside_default_procs_is_never_stopped(self):
        self.fast_process_checks()
        cell, proc = self.loop("other/x")
        for now in (NOW, NOW + 301):
            report = self.sweep(now=now, stop_grace_s=0)
            self.assertEqual(report["processes"]["orphans"], [])
            self.assert_uncontrolled(cell, proc)

    def test_14_bad_table_does_not_archive_and_reports_problem(self):
        self.err.write_bytes(b"must survive a bad table\n")
        (self.d / "procs_state.json").write_text("{broken JSON\n")
        before = snapshot(self.a)
        report = self.sweep()
        self.assertNotEqual(report["table"], "ok")
        self.assertIn("StateBad", report["table"])
        self.assertEqual(report["archived"], [])
        self.assertTrue(report["warnings"])
        self.assertEqual(snapshot(self.a), before)

    def test_14_bin_bad_table_warns_and_exits_zero(self):
        self.err.write_bytes(b"must survive a bad CLI table\n")
        (self.d / "procs_state.json").write_text("not JSON")
        before = snapshot(self.a)
        result = self.cli("--daemon", self.d, "--min-bytes", 1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("aos-sweeper: warning:", result.stderr)
        self.assertIn("cannot read the daemon table", result.stderr)
        self.assertEqual(snapshot(self.a), before)

    def test_15_only_own_table_row_is_archived_not_child_daemon_rows(self):
        self.set_table({"kid": "procs/kid"})
        kid = self.d / "procs" / "kid"
        nested = kid / "procs" / "y"
        nested.mkdir(parents=True)
        self.write_json(kid / "procs_state.json", {
            "procs_stderr": "stderr.txt", "procs_loop": "loop.json",
            "procs": {"y": {"stack": "procs/y", "phase": "running", "pid": None}},
        })
        source = kid / "stderr.txt"
        source.write_bytes(b"own row\n")
        (nested / "stderr.txt").write_bytes(b"child daemon's row\n")
        before = snapshot(nested)
        report = self.sweep()
        archive = self.assert_archive(report, source, b"own row\n")
        self.assertEqual(archive.parent, kid / "stderr_archives")
        self.assertEqual(report["archived"][0]["name"], "kid")
        self.assertEqual(snapshot(nested), before)
        self.assertFalse((nested / "stderr_archives").exists())

    def test_15_same_stack_twice_and_daemon_own_stack_are_handled_once_or_skipped(self):
        # Two rows on one stack archive once; a row whose stack is D itself belongs to D's parent.
        self.set_table({"a": "procs/a", "alias": "procs/a", "self": "."})
        self.err.write_bytes(b"shared\n")
        (self.d / "stderr.txt").write_bytes(b"daemon own stderr\n")
        report = self.sweep()
        self.assertEqual([row["name"] for row in report["archived"]], ["a"])
        self.assertEqual(len(self.archive_files()), 1)
        self.assertEqual((self.d / "stderr.txt").read_bytes(), b"daemon own stderr\n")
        self.assertFalse((self.d / "stderr_archives").exists())

    def test_16_bin_help(self):
        result = self.cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage:", result.stdout)

    def test_16_bin_unknown_flag(self):
        result = self.cli("--unknown-test-flag")
        self.assertEqual(result.returncode, 1)
        self.assertIn("aos-sweeper: error: FlagUnknown", result.stderr)

    def test_16_bin_invalid_numeric_arguments(self):
        for flag, value in (("--retention-days", "0"), ("--min-bytes", "abc"),
                            ("--stop-grace-s", "0")):
            with self.subTest(flag=flag):
                result = self.cli("--daemon", self.d, flag, value)
                self.assertEqual(result.returncode, 1)
                self.assertIn("aos-sweeper: error: ArgumentsBad", result.stderr)

    def test_16_bin_missing_daemon_without_aos_environment_or_dot_stack(self):
        self.assertFalse((self.tmp / ".stack").exists())
        self.assertFalse(any(k.startswith("AOS_") for k in clean_env()))
        result = self.cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn("aos-sweeper: error: DaemonMissing", result.stderr)

    def test_16_bin_writes_json_report_and_prints_archive_totals(self):
        self.err.write_bytes(b"CLI report payload\n")
        path = self.d / "report.json"
        result = self.cli("--daemon", self.d, "--min-bytes", "1",
                          "--retention-days", "none", "--stop-grace-s", "300",
                          "--report", path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r"(?m)^archives: 1 file\(s\), \d+ bytes$")
        report = self.read_json(path)
        self.assertEqual(report["daemon"], str(self.d))
        self.assertEqual(report["table"], "ok")
        self.assertIs(report["dry_run"], False)
        self.assert_archive(report, self.err, b"CLI report payload\n")
        self.assertEqual(list(self.d.glob(".report.json.*.tmp")), [])

    def test_16_bin_dry_run_preserves_tree_and_does_not_write_report(self):
        cell, proc = self.loop()
        self.err.write_bytes(b"CLI dry-run payload\n")
        path = self.d / "report.json"
        before = snapshot(self.d)
        result = self.cli("--daemon", self.d, "--min-bytes", 1,
                          "--dry-run", "--report", path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("would archive", result.stdout)
        self.assertEqual(snapshot(self.d), before)
        self.assertFalse(path.exists())
        self.assert_uncontrolled(cell, proc)

    def test_17_moved_state_with_live_matching_pid_but_other_boot_is_only_reported(self):
        self.fast_process_checks()
        cell, proc = self.loop("procs/moved")
        other_boot = "00000000-0000-0000-0000-000000000000"
        self.assertNotEqual(self.boot, other_boot)
        self.write_state(cell, proc.pid, boot=other_boot)
        before = snapshot(cell)
        for now in (NOW, NOW + 301):
            report = self.sweep(now=now, stop_grace_s=0)
            self.assertTrue(report["processes"]["checked"])
            self.assert_uncontrolled(cell, proc)
            self.assertEqual(snapshot(cell), before)
            matches = [row for row in report["processes"]["orphans"]
                       if row["cell"] == "procs/moved"]
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0]["pid"], proc.pid)
            self.assertIn("another boot or another machine", matches[0]["action"])

    def test_17_moved_state_with_nonexistent_pid_and_other_boot_is_silent(self):
        self.fast_process_checks()
        proc = self.own_process([sys.executable, "-c", "pass"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.assertEqual(proc.wait(timeout=5), 0)
        self.assertFalse(Path(f"/proc/{proc.pid}").exists())
        cell = self.d / "procs" / "moved"
        other_boot = "00000000-0000-0000-0000-000000000000"
        self.assertNotEqual(self.boot, other_boot)
        self.write_state(cell, proc.pid, ticks=123, boot=other_boot)
        before = snapshot(cell)
        report = self.sweep(stop_grace_s=0)
        self.assertTrue(report["processes"]["checked"])
        self.assertFalse(any(row["cell"] == "procs/moved"
                             for row in report["processes"]["orphans"]))
        self.assertFalse((cell / "ctl.json").exists())
        self.assertFalse(self.pending.exists())
        self.assertEqual(snapshot(cell), before)


if __name__ == "__main__":
    unittest.main()
