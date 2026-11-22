# test_v2 - the v2 backend (03 §12.3, §12.8): B1 second port, B2 pulse / rev / ETag, B3 outbox, B4 ui-state,
# B5 batch / correction_of / gone, per-agent board/1, rollup counts. Run through tests/run.sh (unsets every AOS_*).
# One temp `aos-frontend serve` on two free ports; the daemon table is a fixture (VIEW_LS_FIXTURE) and aos-agent is a stub
# on PATH, so the live daemon, ~/aos-home and ~/.aos are never read or written.
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
    sys.exit("test_v2: AOS_* variables are set; run through tests/run.sh")

STUB = """#!/bin/bash
# aos-agent stub for test_v2: say prints a letter name, everything else fails (no state known)
if [ "$1" = say ]; then cat > /dev/null; echo "L-say-$(date +%s%N)"; exit 0; fi
exit 1
"""


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(t))


class V2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="view-v2-", dir="/tmp")
        t = cls.tmp
        cls.home = os.path.join(t, "view")
        cls.procs = os.path.join(t, "procs")
        bindir = os.path.join(t, "bin")
        os.makedirs(bindir)
        with open(os.path.join(bindir, "aos-agent"), "w") as f:
            f.write(STUB)
        os.chmod(os.path.join(bindir, "aos-agent"), 0o755)
        names = [("boss", "running", None), ("boss-a", "running", None), ("boss-a-x", "stopped", "exited with code 1"),
                 ("boss-b", "sleeping", None), ("boss-loner", "running", None)]
        # who is under whom = the subagent records only; boss-loner has a boss- name but nobody's record lists it
        subs = {"boss": ["boss-a", {"name": "boss-b"}], "boss-a": ["boss-a-x"]}
        rows = []
        for n, st, reason in names:
            os.makedirs(os.path.join(cls.procs, n, "mailbox"))
            rows.append({"name": n, "state": st, "phase": st, "ws": t, "stack": os.path.join(cls.procs, n), "queued": 0,
                         "reason": reason, "auto_restart": False, "queue": 0, "cooldown": None, "busy": None,
                         "subagents": subs.get(n, [])})
        cls.fixture = os.path.join(t, "ls.json")
        with open(cls.fixture, "w") as f:
            json.dump(rows, f)
        # board/1 for boss-a (ok-board 06 §7.6 sample, cut down)
        with open(os.path.join(cls.procs, "boss-a", "board.json"), "w") as f:
            json.dump({"format": "board/1", "updated_at": iso(time.time()), "mode": "dnd", "text": "running tests",
                       "waiting_on": [{"who": "user", "what": "pick one", "since_at": iso(time.time() - 600), "junk": 1}],
                       "unknown_key": "dropped"}, f)
        with open(os.path.join(cls.procs, "boss-b", "board.json"), "w") as f:
            json.dump({"format": "board/0", "mode": "here", "updated_at": iso(time.time())}, f)
        # a v2 build
        cls.dist = os.path.join(t, "v2", "dist")
        os.makedirs(os.path.join(cls.dist, "assets"))
        with open(os.path.join(cls.dist, "index.html"), "w") as f:
            f.write("<!doctype html><title>v2</title>")
        with open(os.path.join(cls.dist, "assets", "index-abc123.js"), "w") as f:
            f.write("console.log(1)")
        with open(os.path.join(t, "v2", "VERSION"), "w") as f:
            f.write("view-v2 test")
        cls.env = {"PATH": bindir + ":" + os.environ["PATH"], "HOME": os.environ["HOME"], "LANG": "C.UTF-8",
                   "PYTHONDONTWRITEBYTECODE": "1", "VIEW_LS_FIXTURE": cls.fixture,
                   "AOS_USER_ZONE": os.path.join(t, "user")}
        subprocess.run([VIEW, "--home", cls.home, "init"], env=cls.env, check=True, capture_output=True)
        cls.p1, cls.p2 = free_port(), free_port()
        cfgp = os.path.join(cls.home, "config.json")
        with open(cfgp) as f:
            cfg = json.load(f)
        cfg["ui_ports"] = [{"port": cls.p2, "dir": cls.dist}]
        cfg["externals"] = []
        cfg["poll_s"] = 5
        with open(cfgp, "w") as f:
            json.dump(cfg, f)
        # sent.jsonl: what "the user" sent earlier
        now = time.time()
        sent = [{"at": iso(now - 300), "kind": "mail", "to": "boss", "title": "t1", "text": "w1", "ok": True, "letter": "L-m1"},
                {"at": iso(now - 200), "kind": "say", "to": "boss-a", "text": "hello", "ok": True, "letter": "L-s1", "batch": "b1"},
                {"at": iso(now - 100), "kind": "mail", "to": "gone-team", "title": "t2", "text": "w2", "ok": True, "letter": "L-m2",
                 "correction_of": "Z-1"},
                {"at": iso(now - 8 * 86400), "kind": "mail", "to": "boss", "title": "old", "text": "o", "ok": True, "letter": "L-old"},
                {"at": iso(now - 50), "kind": "answer", "letter": "Z-1", "do": "ok", "args": ["Z-1"], "ok": True, "title": "q"}]
        os.makedirs(os.path.join(cls.home, "state"), exist_ok=True)
        with open(os.path.join(cls.home, "state", "sent.jsonl"), "w") as f:
            for r in sent:
                f.write(json.dumps(r) + "\n")
        # a reply in the relay mailbox to L-m1
        d = os.path.join(cls.home, "mailbox", "new", "R-1")
        os.makedirs(d)
        with open(os.path.join(d, "letter.json"), "w") as f:
            json.dump({"sent_at": iso(now - 250), "in_reply_to": "L-m1", "sender": cls.procs + "/boss",
                       "body": {"from": "boss", "to": "user", "status": "DONE", "title": "done t1", "what": "ok"}}, f)
        cls.srv = subprocess.Popen([VIEW, "--home", cls.home, "--port", str(cls.p1), "serve"], env=cls.env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for _ in range(100):
            try:
                st, h, b = cls.get(cls.p2, "/api/pulse")
                if st == 200 and json.loads(b)["tick"]["at"]:
                    break
            except OSError:
                pass
            time.sleep(0.1)
        st, h, b = cls.get(cls.p1, "/api/session")
        cls.token = json.loads(b)["token"]

    @classmethod
    def tearDownClass(cls):
        cls.srv.terminate()
        try:
            cls.srv.wait(5)
        except subprocess.TimeoutExpired:
            cls.srv.kill()
        if cls.tmp.startswith("/tmp/view-v2-"):
            shutil.rmtree(cls.tmp)

    @classmethod
    def req(cls, port, method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        h = {"Host": "127.0.0.1:%d" % port}
        h.update(headers or {})
        c.request(method, path, body=body, headers=h)
        r = c.getresponse()
        out = (r.status, dict(r.getheaders()), r.read().decode("utf-8", "replace"))
        c.close()
        return out

    @classmethod
    def get(cls, port, path, headers=None):
        return cls.req(port, "GET", path, headers=headers)

    def auth(self, port, extra=None):
        h = {"Content-Type": "application/json", "X-View-Token": self.token, "Cookie": "aosview=" + self.token,
             "Origin": "http://127.0.0.1:%d" % port}
        h.update(extra or {})
        return h

    def j(self, port, path):
        st, h, b = self.get(port, path)
        self.assertEqual(st, 200, b)
        return json.loads(b)

    # B1
    def test_b1_static(self):
        st, h, b = self.get(self.p2, "/")
        self.assertEqual((st, "<title>v2</title>" in b), (200, True))
        self.assertEqual(h["Cache-Control"], "no-store")
        self.assertIn("aosview=", h.get("Set-Cookie", ""))
        self.assertIn("script-src 'self'", h["Content-Security-Policy"])
        self.assertEqual(h["Referrer-Policy"], "same-origin")
        st, h, b = self.get(self.p2, "/assets/index-abc123.js")
        self.assertEqual((st, h["Cache-Control"], h["Content-Type"].split(";")[0]),
                         (200, "max-age=31536000, immutable", "text/javascript"))
        for bad in ("/assets/../index.html", "/assets/%2e%2e/x", "/assets/a/b.js", "/app.js", "/assets/x.exe"):
            self.assertEqual(self.get(self.p2, bad)[0], 404, bad)
        # v1 port still serves v1 (or its fallback), not the v2 build
        st, h, b = self.get(self.p1, "/")
        self.assertNotIn("<title>v2</title>", b)
        # Host of the other port is refused
        self.assertEqual(self.get(self.p2, "/api/pulse", {"Host": "127.0.0.1:%d" % self.p1})[0], 403)
        self.assertEqual(self.j(self.p2, "/api/version")["ui"], "view-v2 test")
        self.assertNotEqual(self.j(self.p1, "/api/version")["ui"], "view-v2 test")

    # B2
    def test_b2_pulse_etag(self):
        p = self.j(self.p2, "/api/pulse")
        self.assertEqual(set(p["rev"]), {"tree", "asks", "relay", "outbox", "board", "answered", "ui_state"})
        self.assertTrue(p["tick"]["ok"])
        for path, kind in (("/api/tree", "tree"), ("/api/asks", "asks"), ("/api/relay", "relay"), ("/api/board", "board"),
                           ("/api/answered", "answered")):
            st, h, b = self.get(self.p2, path)
            self.assertEqual(st, 200)
            self.assertIn("X-Last-Tick", h)
            st2, h2, b2 = self.get(self.p2, path, {"If-None-Match": h["ETag"]})
            self.assertEqual((st2, b2), (304, ""), path)
            self.assertIn("X-Last-Tick", h2)
            self.assertEqual(self.get(self.p2, path, {"If-None-Match": '"nope"'})[0], 200)

    def test_tree_board_rollup(self):
        t = self.j(self.p2, "/api/tree")["tree"]
        n = t["nodes"]
        self.assertEqual(n["boss-a"]["board"]["mode"], "dnd")
        self.assertNotIn("unknown_key", n["boss-a"]["board"])
        self.assertNotIn("junk", n["boss-a"]["board"]["waiting_on"][0])
        self.assertIsNone(n["boss-b"]["board"])           # board/0 = not posted
        self.assertIsNone(n["boss"]["board"])             # no file
        r = n["boss"]["rollup"]
        self.assertEqual(r["counts"]["red"], 1)
        self.assertEqual(r["worst_ids"][0], "boss-a-x")
        self.assertNotIn("_bad", r)
        self.assertNotIn("stack", n["boss"])

    def test_tree_from_subagent_records(self):
        t = self.j(self.p2, "/api/tree")["tree"]
        n = t["nodes"]
        self.assertEqual(sorted(n["boss"]["children"]), ["boss-a", "boss-b"])
        self.assertEqual((n["boss-a-x"]["parent"], n["boss-a-x"]["parent_by"]), ("boss-a", "subagent"))
        self.assertEqual((n["boss-loner"]["parent"], n["boss-loner"]["parent_by"]), (None, None))  # no record = top level
        self.assertIn("boss-loner", t["roots"])
        with open(os.path.join(self.home, "config.json")) as f:
            self.assertEqual(sorted(json.load(f)), ["externals", "poll_s", "ui_ports"])   # init writes no parent keys

    # B3
    def test_b3_outbox(self):
        o = self.j(self.p2, "/api/outbox")
        by = {x["letter"]: x for x in o["items"]}
        self.assertNotIn("L-old", by)                     # older than 7 days
        self.assertEqual(by["L-m1"]["delivery"], "replied")
        self.assertEqual(by["L-m1"]["reply"]["status"], "DONE")
        self.assertEqual(by["L-s1"]["batch"], "b1")
        self.assertEqual(by["L-s1"]["delivery"], "unknown")   # stub aos-agent: state not known
        self.assertTrue(by["L-m2"]["gone"])
        self.assertEqual(by["L-m2"]["correction_of"], "Z-1")
        st, h, b = self.get(self.p2, "/api/outbox")
        self.assertEqual(self.get(self.p2, "/api/outbox", {"If-None-Match": h["ETag"]})[0], 304)
        a = self.j(self.p2, "/api/answered")["answered"]
        self.assertEqual(a[0]["corrections"], ["L-m2"])

    # B4
    def test_b4_ui_state(self):
        path = "/api/ui-state?key=seen"
        self.assertEqual(self.req(self.p2, "PUT", path, json.dumps({"a": 1}), {"Content-Type": "application/json"})[0], 403)
        self.assertEqual(self.req(self.p2, "PUT", path, json.dumps({"a": 1}),
                                  self.auth(self.p2, {"Origin": "http://127.0.0.1:%d" % self.p1}))[0], 403)
        self.assertEqual(self.req(self.p2, "PUT", "/api/ui-state?key=evil", "{}", self.auth(self.p2))[0], 400)
        self.assertEqual(self.req(self.p2, "PUT", path, json.dumps(["x"]), self.auth(self.p2))[0], 400)
        now = time.time()
        st, h, b = self.req(self.p2, "PUT", path, json.dumps({"a": now, "b": now - 20 * 86400}), self.auth(self.p2))
        self.assertEqual(st, 200, b)
        self.assertEqual(json.loads(b)["value"], {"a": now})          # 14-day prune
        rev1 = json.loads(b)["rev"]
        # another window marks c; a with an older time keeps the newer one
        st, h, b = self.req(self.p2, "PUT", path, json.dumps({"c": now, "a": now - 5}), self.auth(self.p2))
        v = json.loads(b)
        self.assertEqual((v["value"], v["rev"]), ({"a": now, "c": now}, rev1 + 1))
        st, h, b = self.req(self.p2, "PUT", path, json.dumps({"a": None}), self.auth(self.p2))
        self.assertEqual(json.loads(b)["value"], {"c": now})
        self.assertEqual(self.j(self.p2, path)["value"], {"c": now})
        st, h, b = self.req(self.p2, "PUT", "/api/ui-state?key=prefs", json.dumps({"stage": "wall"}), self.auth(self.p2))
        self.assertEqual(json.loads(b)["value"], {"stage": "wall"})
        # the same API on the v1 port
        self.assertEqual(self.j(self.p1, "/api/ui-state?key=prefs")["value"], {"stage": "wall"})

    # B5
    def test_b5_say_letter_and_gone(self):
        st, h, b = self.req(self.p2, "POST", "/api/say", json.dumps({"name": "boss", "text": "hi", "batch": "b9",
                                                                      "correction_of": "bad id with spaces"}), self.auth(self.p2))
        r = json.loads(b)
        self.assertEqual(st, 200, b)
        self.assertTrue(r["letter"].startswith("L-say-"))
        with open(os.path.join(self.home, "state", "sent.jsonl")) as f:
            last = json.loads(f.readlines()[-1])
        self.assertEqual(last["batch"], "b9")
        self.assertNotIn("correction_of", last)           # not well-formed: dropped
        t = self.j(self.p2, "/api/thread?name=gone-team")
        self.assertEqual((t["gone"], t["turn"], t["letters"][0]["letter"]), (True, None, "L-m2"))
        self.assertEqual(self.get(self.p2, "/api/thread?name=never-was")[0], 404)
        self.assertEqual(self.get(self.p2, "/api/thread?name=..%2Fx")[0], 404)


class NoBuild(unittest.TestCase):
    """ui/v2/dist is not in git (11-17): a ui dir without index.html = one warning on stderr, the first port still serves."""

    def test_missing_dist_warns(self):
        tmp = tempfile.mkdtemp(prefix="view-v2-nobuild-", dir="/tmp")
        try:
            home, dist = os.path.join(tmp, "view"), os.path.join(tmp, "v2", "dist")
            env = {"PATH": os.environ["PATH"], "HOME": os.environ["HOME"], "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
                   "VIEW_LS_FIXTURE": os.path.join(tmp, "ls.json"), "AOS_USER_ZONE": os.path.join(tmp, "user")}
            with open(env["VIEW_LS_FIXTURE"], "w") as f:
                f.write("[]")
            subprocess.run([VIEW, "--home", home, "init"], env=env, check=True, capture_output=True)
            p1, p2 = free_port(), free_port()
            cfgp = os.path.join(home, "config.json")
            with open(cfgp) as f:
                cfg = json.load(f)
            cfg.update(ui_ports=[{"port": p2, "dir": dist}], externals=[], poll_s=5)
            with open(cfgp, "w") as f:
                json.dump(cfg, f)
            srv = subprocess.Popen([VIEW, "--home", home, "--port", str(p1), "serve"], env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            try:
                line = srv.stderr.readline()
                for _ in range(100):
                    try:
                        if V2.get(p1, "/api/session")[0] == 200:
                            break
                    except OSError:
                        time.sleep(0.1)
                self.assertEqual(line.strip(), "aos-frontend: warning: port %d not opened: %s has no index.html (the page is not "
                                 "built; build it first: see %s)" % (p2, dist, os.path.join(tmp, "v2", "README.md")))
                self.assertEqual(V2.get(p1, "/api/session")[0], 200)
                with self.assertRaises(OSError):
                    V2.get(p2, "/api/session")
            finally:
                srv.terminate()
                try:
                    srv.wait(5)
                except subprocess.TimeoutExpired:
                    srv.kill()
                srv.stderr.close()
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
