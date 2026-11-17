# test_compact_quiet - the compact button's API (/api/compact: a bare "/compact", alone) and the quiet-turn light
# (a long turn is yellow "quiet", a timeout stop is yellow, only a real crash is red). Run through tests/run.sh.
# Fixture daemon table (VIEW_LS_FIXTURE), stub aos-agent on PATH that records what it was given; temp dirs only.
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
VIEW = os.path.join(os.path.dirname(HERE), "bin", "aos-frontend")

if any(k.startswith("AOS_") for k in os.environ):
    sys.exit("test_compact_quiet: AOS_* variables are set; run through tests/run.sh")

STUB = """#!/bin/bash
# aos-agent stub: say writes its argv and stdin to $STUB_LOG and prints a letter name; the rest fails
if [ "$1" = say ]; then printf '%s\\n' "$*" >> "$STUB_LOG"; cat >> "$STUB_LOG"; printf '\\n--end--\\n' >> "$STUB_LOG"; echo "L-say-1"; exit 0; fi
exit 1
"""


def dead_pid():
    p = subprocess.Popen(["true"])
    p.wait()
    return p.pid


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class CompactQuiet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="view-cq-", dir="/tmp")
        t = cls.tmp
        cls.home = os.path.join(t, "view")
        procs = os.path.join(t, "procs")
        bindir = os.path.join(t, "bin")
        os.makedirs(bindir)
        with open(os.path.join(bindir, "aos-agent"), "w") as f:
            f.write(STUB)
        os.chmod(os.path.join(bindir, "aos-agent"), 0o755)
        cls.log = os.path.join(t, "stub.log")
        now = time.time()
        # name, state, queued, reason, live stream: None = no claude cell, else (last event type, age in s)
        spec = [("c-idle", "running", 0, None, ("result", 30)),
                ("c-quiet", "running", 0, None, ("assistant", 30 * 60)),
                ("c-fresh", "running", 1, None, ("assistant", 20)),
                ("c-queued", "running", 2, None, ("result", 30)),
                ("plain", "running", 0, None, None),
                ("c-timeout", "stopped", 0, "RunFailed: timeout after 600000 ms", ("assistant", 700)),
                ("c-crash", "stopped", 0, "exited with code 1", ("assistant", 700)),
                ("q-mark", "running", 0, None, ("result", 30)),
                ("q-stale", "running", 0, None, ("result", 30)),
                ("q-stuck", "running", 0, None, None)]
        rows = []
        for n, st, q, reason, live in spec:
            stack = os.path.join(procs, n)
            os.makedirs(os.path.join(stack, "mailbox"))
            if live:
                os.makedirs(os.path.join(stack, "claude"))
                p = os.path.join(stack, "claude", "live.jsonl")
                with open(p, "w") as f:
                    f.write(json.dumps({"type": "system"}) + "\n" + json.dumps({"type": live[0]}) + "\n")
                os.utime(p, (now - live[1], now - live[1]))
            # the shared quiet mark (timeout-1115, lib/agent/quiet.py): a live pid counts, a dead one is ignored
            if n in ("q-mark", "q-stale"):
                pid = os.getpid() if n == "q-mark" else dead_pid()
                with open(os.path.join(stack, "quiet.json"), "w") as f:
                    json.dump({"quiet": True, "what": "cli_turn", "since": "2026-11-15T08:00:00Z",
                               "at": "2026-11-15T08:12:30Z", "quiet_s": 750, "pid": pid}, f)
            rows.append({"name": n, "state": st, "phase": "stuck" if n == "q-stuck" else st, "ws": t, "stack": stack, "queued": q, "reason": reason,
                         "auto_restart": False, "queue": 0, "cooldown": None, "busy": None})
        cls.fixture = os.path.join(t, "ls.json")
        with open(cls.fixture, "w") as f:
            json.dump(rows, f)
        cls.env = {"PATH": bindir + ":" + os.environ["PATH"], "HOME": os.environ["HOME"], "LANG": "C.UTF-8",
                   "PYTHONDONTWRITEBYTECODE": "1", "VIEW_LS_FIXTURE": cls.fixture, "STUB_LOG": cls.log,
                   "AOS_USER_ZONE": os.path.join(t, "user")}
        subprocess.run([VIEW, "--home", cls.home, "init"], env=cls.env, check=True, capture_output=True)
        cfgp = os.path.join(cls.home, "config.json")
        with open(cfgp) as f:
            cfg = json.load(f)
        cfg["externals"] = []
        cfg["poll_s"] = 5
        with open(cfgp, "w") as f:
            json.dump(cfg, f)
        cls.port = free_port()
        cls.srv = subprocess.Popen([VIEW, "--home", cls.home, "--port", str(cls.port), "serve"], env=cls.env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for _ in range(100):
            try:
                st, b = cls.req("GET", "/api/pulse")
                if st == 200 and json.loads(b)["tick"]["at"]:
                    break
            except OSError:
                pass
            time.sleep(0.1)
        cls.token = json.loads(cls.req("GET", "/api/session")[1])["token"]

    @classmethod
    def tearDownClass(cls):
        cls.srv.terminate()
        try:
            cls.srv.wait(5)
        except subprocess.TimeoutExpired:
            cls.srv.kill()
        if cls.tmp.startswith("/tmp/view-cq-"):
            shutil.rmtree(cls.tmp)

    @classmethod
    def req(cls, method, path, body=None, auth=False):
        c = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=10)
        h = {"Host": "127.0.0.1:%d" % cls.port}
        if auth:
            h.update({"Content-Type": "application/json", "X-View-Token": cls.token, "Cookie": "aosview=" + cls.token,
                      "Origin": "http://127.0.0.1:%d" % cls.port})
        c.request(method, path, body=body, headers=h)
        r = c.getresponse()
        out = (r.status, r.read().decode("utf-8", "replace"))
        c.close()
        return out

    def compact(self, name):
        st, b = self.req("POST", "/api/compact", json.dumps({"name": name}), auth=True)
        return st, json.loads(b)

    def test_lights(self):
        n = json.loads(self.req("GET", "/api/tree")[1])["tree"]["nodes"]
        self.assertEqual(n["c-idle"]["light"], "green")
        self.assertEqual(n["c-quiet"]["light"], "yellow")
        self.assertIn("quiet for 30 min (not crashed)", n["c-quiet"]["why"])
        self.assertEqual(n["c-fresh"]["light"], "green")
        self.assertTrue(n["c-fresh"]["why"].startswith("in a turn"))
        self.assertEqual(n["c-timeout"]["light"], "yellow")
        self.assertIn("timeout", n["c-timeout"]["why"])
        self.assertEqual(n["c-crash"]["light"], "red")
        self.assertIsNone(n["plain"]["live"])
        self.assertTrue(n["c-quiet"]["live"]["in_turn"])
        self.assertEqual(n["q-mark"]["light"], "yellow")                       # quiet.json wins over the live stream
        self.assertIn("long quiet, not dead: waiting on a CLI turn, quiet for 12 min", n["q-mark"]["why"])
        self.assertEqual((n["q-stale"]["light"], n["q-stale"]["quiet"]), ("green", None))   # writer gone: ignored
        self.assertEqual(n["q-stuck"]["light"], "yellow")                      # daemon "stuck" = slow, not red

    def test_compact(self):
        st, r = self.compact("c-idle")
        self.assertEqual(st, 200, r)
        with open(self.log) as f:
            got = f.read()
        argv, body = got.split("\n", 1)
        self.assertEqual(argv, "say -t c-idle --from user-via-page -")
        self.assertEqual(body, "/compact\n--end--\n")             # no prefix, no tail
        with open(os.path.join(self.home, "state", "sent.jsonl")) as f:
            last = json.loads(f.readlines()[-1])
        self.assertEqual((last["kind"], last["to"], last["text"]), ("compact", "c-idle", "/compact"))
        # refused: letters waiting (they would be batched with it), no CLI cell, not running, not on the table
        for name in ("c-queued", "plain", "c-crash", "nobody"):
            st, r = self.compact(name)
            self.assertEqual((st, r["ok"]), (400, False), name)
        st, r = self.compact("c-quiet")
        self.assertEqual(st, 200)
        self.assertIn("這一輪結束才會壓", r["message"])

    def test_version_names_the_app(self):
        v = json.loads(self.req("GET", "/api/version")[1])
        self.assertEqual(v["app"], os.path.basename(VIEW))


if __name__ == "__main__":
    unittest.main()
