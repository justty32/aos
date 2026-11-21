# test_phase1 - phase 1 of aos-frontend: note, decide, aide-tick, relay ingestion into a temp user zone, answer, match, lights.
# Run through tests/run.sh (unsets every AOS_*). Temp dirs only: temp view home, temp user zone, temp relay mailbox,
# a fixture daemon table (VIEW_LS_FIXTURE); the live daemon, ~/aos-home and ~/.aos are never written.
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
VIEW = os.path.join(os.path.dirname(HERE), "bin", "aos-frontend")
# an integration test against the real aos-user (its zone.py) and aos-post: they live in the installed tools, not in this
# folder. VIEW_TOOLS points at another tools folder; without them (a clean copy) the class is skipped, not failed.
TOOLS = os.environ.get("VIEW_TOOLS") or os.path.expanduser("~/aos-home/ws/tools")
AOS_USER = os.path.join(TOOLS, "aos-user", "aos-user")
MISSING = [x for x, ok in (("aos-user (%s)" % AOS_USER, os.access(AOS_USER, os.X_OK)),
                           ("aos-post on PATH", shutil.which("aos-post"))) if not ok]
KEYS = ("kind", "title", "what", "questions", "done_when", "risk", "urgent", "deadline", "default_if_silent", "dedupe_key")

if any(k.startswith("AOS_") for k in os.environ):
    sys.exit("test_phase1: AOS_* variables are set; run through tests/run.sh")


def canon(body):
    c = {k: body[k] for k in KEYS if k in body}
    return hashlib.sha256(json.dumps(c, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


LETTER = {"kind": "decide", "title": "Pick the map renderer", "what": "Two ways to draw the map.",
          "questions": [{"id": "q1", "question": "SVG or canvas?", "eli5": "SVG is simple. Canvas is fast.",
                         "options": [{"key": "a", "label": "SVG"}, {"key": "b", "label": "canvas"}],
                         "recommend": "a"}],
          "deadline": "2026-12-31"}


@unittest.skipIf(MISSING, "needs the installed tools: missing " + ", ".join(MISSING))
class Phase1(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="view-p1-", dir="/tmp")
        self.home = os.path.join(self.tmp, "view")
        self.zone = os.path.join(self.tmp, "user")
        self.procs = os.path.join(self.tmp, "procs")
        self.leader = os.path.join(self.procs, "ok-t")
        self.aide = os.path.join(self.procs, "ok-t-aide-1")
        for d in (self.leader, self.aide, os.path.join(self.procs, "ok-t-sol-1")):
            os.makedirs(d)
        self.fixture = os.path.join(self.tmp, "ls.json")
        self.rows([("ok-t", "running", "think"), ("ok-t-sol-1", "running", None), ("ok-t-aide-1", "running", None),
                   ("repo-aos", "running", None)])
        self.env = {"PATH": os.environ["PATH"], "HOME": os.environ["HOME"], "LANG": "C.UTF-8",
                    "PYTHONDONTWRITEBYTECODE": "1", "AOS_USER_ZONE": self.zone, "VIEW_LS_FIXTURE": self.fixture, "VIEW_TOOLS": TOOLS}
        self.ok(["aos-post", "init", os.path.join(self.leader, "mailbox")])
        self.ok([VIEW, "--home", self.home, "init"])
        self.ok([AOS_USER, "init"])
        self.team = os.path.join(self.home, "teams", "ok-t")
        os.makedirs(self.team, exist_ok=True)
        self.write(os.path.join(self.team, "aide.json"),
                   {"team": "ok-t", "parent": "repo-aos", "leader": "ok-t", "aide": "ok-t-aide-1", "tags": ["view"]})

    def tearDown(self):
        if self.tmp.startswith("/tmp/view-p1-"):
            shutil.rmtree(self.tmp)

    # helpers
    def rows(self, spec):
        self.write(self.fixture, [{"name": n, "state": st, "phase": st, "ws": self.tmp,
                                   "stack": os.path.join(self.procs, n), "queued": 0, "reason": None,
                                   "auto_restart": False, "queue": 0, "cooldown": None, "busy": busy}
                                  for n, st, busy in spec])

    def load(self, path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def write(self, path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def run_(self, args, stdin=None, env=None):
        e = dict(self.env, **(env or {}))
        return subprocess.run(args, input=stdin, capture_output=True, text=True, env=e, cwd=self.tmp, timeout=60)

    def ok(self, args, stdin=None, env=None):
        p = self.run_(args, stdin, env)
        self.assertEqual(p.returncode, 0, "%s\nstdout: %s\nstderr: %s" % (args, p.stdout, p.stderr))
        return p.stdout

    def view(self, *args, stdin=None, env=None):
        return self.run_([VIEW, "--home", self.home] + list(args), stdin, env)

    def tick(self):
        ev = {"event": "on_clock", "hook": "aide_tick", "stack": self.aide, "clock": "x", "cycle": 60,
              "interval_ms": 1000, "first": False, "last_cycle": 0, "missed": 0}
        # A real hook also has AOS_WS (the aide's workspace, often a shared one): the sender must still be the stack.
        p = self.view("aide-tick", stdin=json.dumps(ev), env={"AOS_WS": self.tmp})
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def letters(self, box, sub="new"):
        out = []
        for d in sorted(glob.glob(os.path.join(box, sub, "*", "letter.json"))):
            with open(d, encoding="utf-8") as f:
                out.append((os.path.basename(os.path.dirname(d)), json.load(f)))
        return out

    def decide(self, letter=LETTER, name="q.json"):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(letter, ensure_ascii=False, indent=2) + "\n")
        p = self.view("decide", "--team", "ok-t", path)
        return p, path

    # tests
    def test_note(self):
        self.assertEqual(self.view("note", "--team", "ok-t", "start", "hello", "world").returncode, 0)
        p = self.view("note", "--on", "ok-t-sol-1", "progress", "default team", env={"AOS_STACK": self.leader + "/"})
        self.assertEqual(p.returncode, 0, p.stderr)
        with open(os.path.join(self.team, "notes.jsonl"), encoding="utf-8") as f:
            ns = [json.loads(x) for x in f]
        self.assertEqual([(n["status"], n["text"], n["on"]) for n in ns],
                         [("start", "hello world", None), ("progress", "default team", "ok-t-sol-1")])
        self.assertTrue(re.match(r"^\d{4}-\d\d-\d\dT", ns[0]["at"]))
        p = self.view("note", "--team", "ok-t", "busy", "x")
        self.assertEqual(p.returncode, 1)
        self.assertIn("aos-frontend: error: StatusBad", p.stderr)
        p = self.view("note", "start", "x", env={"AOS_STACK": os.path.join(self.procs, "nobody")})
        self.assertIn("error: TeamMissing", p.stderr)

    def test_decide(self):
        p, path = self.decide()
        self.assertEqual(p.returncode, 0, p.stderr)
        rid = p.stdout.strip()
        self.assertRegex(rid, r"^ok-t-\d{8}-\d{6}-[0-9a-f]{4}$")
        with open(path, "rb") as a, open(os.path.join(self.team, "outbox", rid + ".json"), "rb") as b:
            self.assertEqual(a.read(), b.read())
        with open(os.path.join(self.team, "sent.jsonl"), encoding="utf-8") as f:
            rec = json.loads(f.readline())
        self.assertEqual((rec["id"], rec["sha256"]), (rid, canon(LETTER)))
        for bad in ("use sk-abcdefghijklmnopqrstuvwx here", "set OPENAI_API_KEY=abc123 first",
                    "header Bearer abcdefghijklmnop", "ghp_" + "a" * 30):
            p, _ = self.decide(dict(LETTER, what=bad), "bad.json")
            self.assertEqual(p.returncode, 1)
            self.assertIn("error: SecretInPayload", p.stderr)
            self.assertNotIn(bad.split()[-1] if "=" not in bad else "abc123", p.stderr)
        p, _ = self.decide(dict(LETTER, questions=[]), "bad2.json")
        self.assertIn("error: SchemaBad", p.stderr)
        self.assertEqual(len(os.listdir(os.path.join(self.team, "outbox"))), 2)  # the one file + sent/

    def test_end_to_end(self):
        self.view("note", "--team", "ok-t", "progress", "drawing the map")
        p, _ = self.decide()
        rid = p.stdout.strip()
        # a plain reply from a team also sits in the relay mailbox and must stay
        self.ok(["aos-post", "send", os.path.join(self.home, "mailbox")],
                stdin=json.dumps({"from": "ok-x", "status": "DONE", "title": "plain reply", "what": "hi"}))
        out = self.tick()
        self.assertIn("passed 1, report sent, beat sent", out)
        self.assertEqual(os.listdir(os.path.join(self.team, "outbox", "sent")), [rid + ".json"])
        ls = [lt for _, lt in self.letters(os.path.join(self.home, "mailbox"))]
        view = [lt for lt in ls if lt["body"].get("zone") == "view/1"]
        self.assertEqual(sorted(lt["body"]["kind"] for lt in view), ["beat", "pass", "report"])
        self.assertEqual(sorted(lt["body"]["seq"] for lt in view), [1, 2, 3])
        for lt in view:
            self.assertEqual(lt["sender"].rstrip("/"), self.aide)
        ps = next(lt["body"] for lt in view if lt["body"]["kind"] == "pass")
        self.assertEqual(ps["payload_sha256"], canon(LETTER))
        self.assertEqual(ps["payload_id"], "ok-t/" + rid)
        self.assertEqual(ps["reply_to_team"], os.path.join(self.leader, "mailbox"))
        self.assertEqual(ps["status"], "NEEDS-USER")
        with open(os.path.join(self.team, "outbox", "sent", rid + ".json"), encoding="utf-8") as f:
            self.assertEqual(ps["payload_text"], f.read())
        rp = next(lt["body"] for lt in view if lt["body"]["kind"] == "report")
        self.assertEqual(rp["summary_by"], "none")
        self.assertEqual(rp["facts"]["leader"], {"name": "ok-t", "state": "running", "busy": "think", "queued": 0})
        self.assertEqual([m["name"] for m in rp["facts"]["members"]], ["ok-t-sol-1"])
        self.assertEqual(rp["facts"]["note"]["text"], "drawing the map")
        self.assertEqual(rp["facts"]["pending_pass"], 0)
        # second tick right away: nothing new
        self.assertIn("passed 0, report -, beat -", self.tick())
        # backend ingestion
        res = json.loads(self.view("ingest").stdout)
        self.assertEqual((res["passed"], res["stored"], res["rejected"]), (1, 2, 0))
        mb = os.path.join(self.home, "mailbox")
        left = [lt["body"].get("title") for _, lt in self.letters(mb) + self.letters(mb, "cur")]
        self.assertEqual(left, ["plain reply"])
        self.assertEqual(len(glob.glob(os.path.join(self.home, "done", "*", "*", "letter.json"))), 3)
        ts = self.load(os.path.join(self.home, "state", "teams", "ok-t.json"))
        self.assertTrue(ts["last_beat"])
        self.assertEqual(ts["report"]["facts"]["note"]["text"], "drawing the map")
        receipt = self.load(os.path.join(self.home, "state", "passed", "ok-t", rid + ".json"))
        zl = self.letters(os.path.join(self.zone, "mailbox"))
        self.assertEqual(len(zl), 1)
        zname, zlt = zl[0]
        self.assertEqual(receipt["zone_letter"], zname)
        self.assertEqual(canon(zlt["body"]), canon(LETTER))  # the zone's question fields = the captain's file
        self.assertEqual(zlt["sender"].rstrip("/"), self.home)
        self.assertEqual(zlt["body"]["from"], "ok-t")
        self.assertEqual(zlt["body"]["origin"], "ok-t/%s sha256:%s via ok-t-aide-1" % (rid, canon(LETTER)))
        self.assertEqual(os.path.normpath(os.path.join(self.zone, "mailbox", zlt["reply_to"])),
                         os.path.join(self.leader, "mailbox"))
        # the user answers in the temp zone; the reply lands in the captain's mailbox
        self.assertIn("answered", self.ok([AOS_USER, "answer", zname, "q1:b*"]))
        replies = glob.glob(os.path.join(self.leader, "mailbox", "new", "*"))
        self.assertEqual(len(replies), 1)
        p = self.view("match", replies[0])
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(p.stdout.startswith("ok: match ok-t/%s" % rid), p.stdout)
        # the same pass letter again = a duplicate, not a second zone letter
        self.ok(["aos-post", "send", "--reply-to", mb, mb], stdin=json.dumps(dict(ps, seq=99)),
                env={"AOS_STACK": self.aide})
        self.assertEqual(json.loads(self.view("ingest").stdout)["duplicate"], 1)
        # a sent.jsonl that disagrees with the zone = PayloadMismatch
        sl = os.path.join(self.team, "sent.jsonl")
        with open(sl, encoding="utf-8") as f:
            recs = [json.loads(x) for x in f]
        recs[0]["sha256"] = "0" * 64
        with open(sl, "w", encoding="utf-8") as f:
            f.write("".join(json.dumps(r) + "\n" for r in recs))
        p = self.view("match", replies[0])
        self.assertEqual(p.returncode, 1)
        self.assertIn("aos-frontend: error: PayloadMismatch", p.stderr)

    def pass_letter(self, letter=LETTER, rid="ok-t-20261114-100000-abcd", sha=None, sender=None):
        text = json.dumps(letter, ensure_ascii=False)
        body = {"zone": "view/1", "kind": "pass", "team": "ok-t", "parent": "repo-aos", "seq": 1, "from": "ok-t-aide-1",
                "to": "view", "status": "NEEDS-USER", "title": "pass", "what": "x", "payload_id": "ok-t/" + rid,
                "payload_text": text, "payload_sha256": sha or canon(letter), "written_by": "ok-t",
                "reply_to_team": os.path.join(self.leader, "mailbox")}
        mb = os.path.join(self.home, "mailbox")
        return self.ok(["aos-post", "send", "--reply-to", mb, mb], stdin=json.dumps(body),
                       env={"AOS_STACK": sender or self.aide}).strip()

    def test_tampered_hash_rejected(self):
        name = self.pass_letter(sha="f" * 64)
        res = json.loads(self.view("ingest").stdout)
        self.assertEqual((res["rejected"], res["passed"]), (1, 0))
        with open(os.path.join(self.home, "rejected", name, "reason.txt"), encoding="utf-8") as f:
            self.assertTrue(f.read().startswith("PayloadHashBad"))
        self.assertEqual(self.letters(os.path.join(self.zone, "mailbox")), [])
        # a payload changed after hashing is caught the same way
        name2 = self.pass_letter(dict(LETTER, title="Changed title"), rid="ok-t-20261114-100001-abcd",
                                 sha=canon(LETTER))
        self.view("ingest")
        self.assertTrue(os.path.isdir(os.path.join(self.home, "rejected", name2)))
        # a letter from someone who is not the team's aide
        name3 = self.pass_letter(rid="ok-t-20261114-100002-abcd", sender=os.path.join(self.procs, "ok-t-sol-1"))
        self.view("ingest")
        with open(os.path.join(self.home, "rejected", name3, "reason.txt"), encoding="utf-8") as f:
            self.assertTrue(f.read().startswith("SenderBad"))

    def test_rate_limit(self):
        for i in range(9):
            self.pass_letter(dict(LETTER, title="Q %d" % i, deadline="2026-12-%02d" % (20 - i)),
                             rid="ok-t-20261114-1000%02d-abcd" % i)
        res = json.loads(self.view("ingest").stdout)
        self.assertEqual((res["passed"], res["waiting"]), (8, 1))
        titles = sorted(lt["body"]["title"] for _, lt in self.letters(os.path.join(self.zone, "mailbox")))
        self.assertNotIn("Q 0", titles)  # the farthest deadline waits
        self.assertEqual(len(self.letters(os.path.join(self.home, "mailbox"), "cur")), 1)

    def test_hook_handler_file(self):
        """The template's handler (aide-def/aide_tick.json) through aos-exec, as hooks.py would run it."""
        fake_home = os.path.join(self.tmp, "aoshome")
        os.makedirs(os.path.join(fake_home, "frontend", "bin"))
        os.symlink(VIEW, os.path.join(fake_home, "frontend", "bin", "aos-frontend"))
        cell = os.path.join(self.aide, "hookeds", "aide_tick") + "/"
        ev = {"event": "on_clock", "hook": "aide_tick", "stack": self.aide, "first": True, "missed": 0}
        handler = os.path.join(os.path.dirname(HERE), "aide-def", "aide_tick.json")
        out = self.ok(["aos-exec", "--stack", cell, handler], stdin=json.dumps(ev),
                      env={"AOS_HOME": fake_home, "AOS_VIEW_HOME": self.home})
        self.assertIn("aide-tick ok-t: passed 0, report sent, beat sent", out)
        hooks = self.load(os.path.join(os.path.dirname(HERE), "aide-def", "hookeds.json"))
        self.assertEqual([n for n in hooks if n != "description"], ["aide_tick"])
        self.assertEqual((hooks["aide_tick"]["event"], hooks["aide_tick"]["every_cycles"]), ("on_clock", 60))
        self.assertEqual(self.load(os.path.join(os.path.dirname(HERE), "aide-def", "llm.json")), {"model": "fake"})

    def snapshot(self):
        p = self.view("snapshot")
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)["nodes"]

    def test_lights(self):
        old = time.time() - 40 * 60
        os.utime(os.path.join(self.team, "aide.json"), (old, old))
        n = self.snapshot()
        self.assertNotIn("ok-t-aide-1", n["ok-t"]["children"])
        self.assertEqual(n["ok-t-aide-1"]["parent_by"], "aide")
        self.assertEqual(n["ok-t"]["aide"]["name"], "ok-t-aide-1")
        self.assertEqual((n["ok-t"]["rollup"]["worst"], n["ok-t"]["rollup"]["why"]), ("red", "aide silent (no beat yet)"))
        self.assertEqual(n["ok-t"]["light"], "green")  # §10: own light unchanged
        # a fresh aide.json = warming up, not red
        os.utime(os.path.join(self.team, "aide.json"))
        self.assertEqual(self.snapshot()["ok-t"]["rollup"]["worst"], "green")
        # beat now, last note 61 min old -> yellow
        self.tick()
        self.view("ingest")
        with open(os.path.join(self.team, "notes.jsonl"), "w", encoding="utf-8") as f:
            at = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() - 61 * 60))
            f.write(json.dumps({"at": at[:-2] + ":" + at[-2:], "status": "progress", "text": "slow", "on": None}) + "\n")
        n = self.snapshot()
        self.assertEqual(n["ok-t"]["aide"]["last_beat"] is not None, True)
        self.assertEqual(n["ok-t"]["note"]["text"], "slow")
        self.assertEqual((n["ok-t"]["rollup"]["worst"], n["ok-t"]["rollup"]["why"]), ("yellow", "no progress 60 min"))
        # a zone letter from the team is waiting -> the 60-min clock pauses
        self.decide()
        self.tick()
        n = self.snapshot()  # snapshot ingests first: the pass reaches the zone
        self.assertEqual(n["ok-t"]["passed"], 1)
        self.assertEqual(n["ok-t"]["rollup"]["worst"], "blue")
        self.assertIsNone(n["ok-t"]["team_light"])
        # beat 36 min ago -> red
        ts = os.path.join(self.home, "state", "teams", "ok-t.json")
        d = self.load(ts)
        d["last_beat"] = time.time() - 36 * 60
        self.write(ts, d)
        self.assertEqual(self.snapshot()["ok-t"]["rollup"]["why"], "aide silent 36 min")
        # everyone stopped -> no heartbeat light
        self.rows([("ok-t", "stopped", None), ("ok-t-sol-1", "stopped", None), ("ok-t-aide-1", "stopped", None)])
        self.assertIsNone(self.snapshot()["ok-t"]["team_light"])


class AideDef(unittest.TestCase):
    """aos-frontend aide-def (11-17 Q3): the agent-fsm template copied, the files of aide-def/ laid over it."""
    AIDE = os.path.join(os.path.dirname(HERE), "aide-def")
    TEMPLATE = os.path.join(os.path.dirname(os.path.dirname(HERE)), "templates", "agent-fsm")

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="view-aidedef-", dir="/tmp")
        self.env = {"PATH": os.environ["PATH"], "HOME": self.tmp, "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_view(self, args, **env):
        return subprocess.run([VIEW, "aide-def"] + args, env=dict(self.env, **env), capture_output=True, text=True, timeout=30)

    @staticmethod
    def files(d):
        return sorted(os.path.relpath(os.path.join(r, f), d) for r, ds, fs in os.walk(d) for f in fs if "__pycache__" not in r)

    def read(self, p):
        with open(p, "rb") as f:
            return f.read()

    def test_template_plus_overlay(self):
        ws = os.path.join(self.tmp, "ws")
        os.makedirs(os.path.join(ws, "defs"))
        r = self.run_view(["defs/t-aide"], AOS_WS=ws, AOS_HOME=os.path.dirname(os.path.dirname(self.TEMPLATE)))
        self.assertEqual(r.returncode, 0, r.stderr)
        dest = os.path.join(ws, "defs", "t-aide")
        self.assertIn("wrote aide definition %s" % dest, r.stdout)
        overlay = [f for f in os.listdir(self.AIDE) if f != "_index.json"]
        self.assertEqual(self.files(dest), sorted(set(self.files(self.TEMPLATE)) | set(overlay)))
        for f in self.files(dest):                                  # every file as it is, _metainfo.json too (user 11-21)
            src = os.path.join(self.AIDE if f in overlay else self.TEMPLATE, f)
            self.assertEqual(self.read(os.path.join(dest, f)), self.read(src), f)
        self.assertEqual(json.loads(self.read(os.path.join(dest, "hookeds.json"))).keys(), {"description", "aide_tick"})
        self.assertFalse([f for f in os.listdir(os.path.join(ws, "defs")) if f.startswith(".")])   # no temp folder left
        again = self.run_view(["defs/t-aide"], AOS_WS=ws, AOS_HOME=os.path.dirname(os.path.dirname(self.TEMPLATE)))
        self.assertEqual(again.returncode, 1)
        self.assertIn("aos-frontend: error: DefExists", again.stderr)

    def test_template_missing(self):
        r = self.run_view([os.path.join(self.tmp, "x")])
        self.assertEqual(r.returncode, 1)
        self.assertIn("aos-frontend: error: TemplateMissing AOS_HOME is not set", r.stderr)
        r = self.run_view(["--template", self.tmp, os.path.join(self.tmp, "x")])
        self.assertIn("aos-frontend: error: TemplateMissing", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "x")))
        r = self.run_view(["--template", self.TEMPLATE, os.path.join(self.tmp, "y")])
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
