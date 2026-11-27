"""A small client for a proto9 aos-daemon started without init: start it, write its ctl, read procs/<name>/ facts, wait for a proc to die, stop it."""

import json
import os
import re
import select
import signal
import subprocess
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DAEMON_BIN = os.path.join(REPO, "proto9", "cpp", "aos-daemon", "build", "bin", "aos-daemon")


def read(p):
    try:
        with open(p, errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def write(p, text, mode=None):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(text)
    if mode is not None:
        os.chmod(p, mode)


def wait_for(cond, timeout, step=0.1):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(step)
    return cond()


class DaemonError(Exception):
    pass


class Daemon:
    """One aos-daemon with no init; everything is driven from outside through /proc/<PID>/cwd/ctl."""

    def __init__(self, run_dir, binary=DAEMON_BIN):
        self.run_dir, self.binary = run_dir, binary
        self.p = self.pid = self.root = None
        self.err_path = os.path.join(run_dir, "logs", "daemon.err")

    def start(self):
        dj = os.path.join(self.run_dir, "daemon.json")
        write(dj, "{}\n")  # no "init": the daemon starts nothing by itself
        os.makedirs(os.path.dirname(self.err_path), exist_ok=True)
        with open(self.err_path, "w") as err:
            self.p = subprocess.Popen([self.binary, dj], stdout=subprocess.PIPE, stderr=err,
                                      stdin=subprocess.DEVNULL, cwd="/")
        end, buf = time.monotonic() + 15, b""
        while time.monotonic() < end and b"\n" not in buf:
            r, _, _ = select.select([self.p.stdout], [], [], 0.1)
            if r:
                c = os.read(self.p.stdout.fileno(), 4096)
                if not c:
                    break
                buf += c
        line = buf.decode(errors="replace").split("\n")[0]
        m = re.fullmatch(r"export AOS_DAEMON=/proc/(\d+)/cwd", line)
        if not m:
            self.stop()
            raise DaemonError("aos-daemon did not start (%r): %s" % (line, read(self.err_path).strip()[-500:]))
        self.pid = m.group(1)
        self.root = "/proc/%s/cwd" % self.pid

    def status(self):
        return read(self.root + "/status")

    def status_field(self, key):
        m = re.search(r"^%s: (.*)$" % re.escape(key), self.status(), re.M)
        return m.group(1) if m else None

    def warnings(self):
        """What the daemon warns about: landlock_warning in status, and warning lines on its stderr."""
        out = ["status: " + l for l in self.status().splitlines() if l.startswith("landlock_warning")]
        out += [l for l in read(self.err_path).splitlines() if "warning" in l.lower()]
        return out

    def ctl(self, line):
        """Write one ctl line; returns None when done, or the error (errno text and aos_ctl_error)."""
        # check the pid first: /proc/<PID>/cwd goes stale once the daemon is gone (aos-daemon README)
        if not re.search(r"^pid_host: %s$" % self.pid, self.status(), re.M):
            raise DaemonError("aos-daemon %s is gone" % self.pid)
        try:
            fd = os.open(self.root + "/ctl", os.O_WRONLY)
            try:
                os.write(fd, (line + "\n").encode())
            finally:
                os.close(fd)
            return None
        except OSError as e:
            return "%s: %s" % (e.strerror, self.status_field("aos_ctl_error") or "")

    def fact(self, name, f):
        return read("%s/procs/%s/%s" % (self.root, name, f))

    def start_proc(self, config, config_path):
        write(config_path, json.dumps(config, indent=1) + "\n")
        err = self.ctl("start " + config_path)
        if err:
            raise DaemonError("start %s: %s" % (config["name"], err))

    def alive(self, name):
        return self.fact(name, "state") == "alive\n"

    def wait_dead(self, name, timeout):
        """Wait for the proc to end; past the timeout kill its whole cgroup. True if it ended by itself."""
        ok = wait_for(lambda: self.fact(name, "state") == "dead\n", timeout, 0.25)
        if not ok:
            self.ctl("kill %s KILL" % name)
            wait_for(lambda: self.fact(name, "state") == "dead\n", 10)
        return ok

    def stop(self):
        """SIGTERM: with no init the daemon SIGKILLs everything under it and exits."""
        if self.p and self.p.poll() is None:
            self.p.send_signal(signal.SIGTERM)
            try:
                self.p.wait(20)
            except subprocess.TimeoutExpired:
                self.p.kill()
                self.p.wait(5)
        if self.p and self.p.stdout:
            self.p.stdout.close()
