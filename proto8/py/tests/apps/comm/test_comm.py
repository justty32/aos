"""Test aos-comm board set/clear/wait/show/ls and check against hand-written boards and a hand-written daemon table (real aos-agent)."""
import datetime
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[4]
BIN = PROTO / "bin" / "aos-comm"
SAMPLES = PROTO / "py" / "schema" / "comm" / "1" / "samples"
UTC = datetime.timezone.utc


def iso(dt):
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + "%03d+00:00" % (dt.microsecond // 1000)


def ago(**kw):
    return iso(datetime.datetime.now(UTC) - datetime.timedelta(**kw))


def ahead(**kw):
    return iso(datetime.datetime.now(UTC) + datetime.timedelta(**kw))


def has_jsonschema():
    try:
        import jsonschema  # noqa: F401
    except ImportError:
        return False
    return True


class Comm(unittest.TestCase):
    def setUp(self):
        # 暫存夾不刪（使用者 11-14 不刪規則）：放在 $TMPDIR 底下，帶 aos-comm- 字頭
        self.tmp = Path(tempfile.mkdtemp(prefix="aos-comm-"))
        self.home = self.tmp / "home"
        self.home.mkdir()
        for n in ("me", "bob", "carol", "zone"):
            (self.tmp / n).mkdir()
        (self.tmp / "me" / "mailbox").mkdir()
        self.daemon = self.tmp / "d"
        self.daemon.mkdir()
        self.table({"bob": "running", "carol": "sleeping"})
        path = "%s:%s:%s" % (PROTO / "bin", PROTO / "bin", os.environ["PATH"])
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.env.update(HOME=str(self.home), PATH=path, PYTHONDONTWRITEBYTECODE="1", AOS_USER_ZONE=str(self.tmp / "zone"))

    def table(self, phases, daemon=None, stacks=None):
        procs = {n: {"stack": (stacks or {}).get(n, "../" + n), "phase": p} for n, p in phases.items()}
        (daemon or self.daemon).joinpath("procs_state.json").write_text(json.dumps({"procs": procs}))

    def run_c(self, *args, env=None):
        return subprocess.run([sys.executable, str(BIN)] + list(args), stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, env=env or self.env, cwd=str(self.tmp), timeout=60)

    def ok(self, *args, code=0, **kw):
        r = self.run_c(*args, **kw)
        self.assertEqual(r.returncode, code, (args, r.stdout, r.stderr))
        return r.stdout

    def fails(self, code, *args):
        r = self.run_c(*args)
        self.assertEqual(r.returncode, 1, (args, r.stdout, r.stderr))
        self.assertTrue(r.stderr.startswith("aos-comm: error: %s " % code), (args, r.stderr))
        return r

    def board(self, who="me"):
        return json.loads((self.tmp / who / "board.json").read_text())

    def put(self, who, **fields):
        b = dict({"format": "board/1", "updated_at": ago(minutes=1), "mode": "here"}, **fields)
        (self.tmp / who / "board.json").write_text(json.dumps(b))

    def show(self, *args):
        return json.loads(self.ok("-d", "d", "board", "show", "-j", *args))

    # ---- 寫 --------------------------------------------------------------------------

    def test_set_seq_by_and_defaults(self):
        b = json.loads(self.ok("-s", "me", "board", "set", "dnd", "writing", "the", "report", "--doing", "report", "-j"))
        self.assertEqual((b["format"], b["seq"], b["by"], b["mode"], b["text"], b["doing"]),
                         ("board/1", 1, "self", "dnd", "writing the report", "report"))
        left = datetime.datetime.fromisoformat(b["expires_at"]) - datetime.datetime.fromisoformat(b["updated_at"])
        self.assertEqual(left, datetime.timedelta(hours=2))                           # dnd 沒給到期＝2h
        b = json.loads(self.ok("-s", "me", "board", "set", "away", "--by", "user", "--back", "8h", "-j"))
        self.assertEqual((b["seq"], b["by"], "text" in b, "doing" in b), (2, "user", False, False))   # 整張換掉
        left = datetime.datetime.fromisoformat(b["expires_at"]) - datetime.datetime.fromisoformat(b["updated_at"])
        self.assertEqual(left, datetime.timedelta(hours=12))                          # away＝12h
        self.assertEqual(datetime.datetime.fromisoformat(b["back_at"]) - datetime.datetime.fromisoformat(b["updated_at"]),
                         datetime.timedelta(hours=8))
        b = json.loads(self.ok("-s", "me", "board", "set", "busy", "--for", "30m", "-j"))
        self.assertEqual(datetime.datetime.fromisoformat(b["expires_at"]) - datetime.datetime.fromisoformat(b["updated_at"]),
                         datetime.timedelta(minutes=30))
        b = json.loads(self.ok("-s", "me", "board", "set", "here", "-j"))
        self.assertNotIn("expires_at", b)                                             # here／busy 沒預設到期
        self.assertEqual(self.board(), b)
        self.assertFalse(list((self.tmp / "me").glob("board.json.tmp.*")))            # 暫存檔都改名掉了

    def test_set_keeps_waiting_on_and_unknown_keys(self):
        self.ok("-s", "me", "board", "wait", "user", "approve", "the", "plan", "--level", "urgent", "--ref", "L1")
        b = self.board()
        b["ext"] = {"view": 1}
        b["later_key"] = "x"
        (self.tmp / "me" / "board.json").write_text(json.dumps(b))
        b = json.loads(self.ok("-s", "me", "board", "set", "busy", "still", "-j"))
        self.assertEqual([(w["who"], w["what"], w["level"], w["ref"]) for w in b["waiting_on"]],
                         [("user", "approve the plan", "urgent", "L1")])
        self.assertEqual((b["ext"], b["later_key"], b["seq"]), ({"view": 1}, "x", 2))
        b = json.loads(self.ok("-s", "me", "board", "clear", "-j"))
        self.assertEqual((b["mode"], "waiting_on" in b, "text" in b, b["later_key"], b["seq"]), ("here", False, False, "x", 3))

    def test_wait_add_and_done(self):
        self.ok("-s", "me", "board", "wait", "bob", "the numbers")
        self.ok("-s", "me", "board", "wait", "user", "a decision")
        self.ok("-s", "me", "board", "wait", "bob", "the review")
        b = json.loads(self.ok("-s", "me", "board", "wait", "--done", "bob", "-j"))
        self.assertEqual([w["who"] for w in b["waiting_on"]], ["user"])
        self.assertEqual(self.ok("-s", "me", "board", "wait", "--done", "bob", code=10), "")   # 沒東西拿＝退 10、不寫
        self.assertEqual(self.board()["seq"], 4)
        for i in range(19):                                                           # user 那筆＋19＝20 筆，滿了
            self.ok("-s", "me", "board", "wait", "w%d" % i, "x")
        self.fails("BoardFull", "-s", "me", "board", "wait", "one", "more")
        self.assertEqual(len(self.board()["waiting_on"]), 20)

    def test_concurrent_writers_use_flock(self):
        lock = self.tmp / "me" / "comm" / "board.lock"
        self.ok("-s", "me", "board", "set", "busy")
        self.assertTrue(lock.is_file())
        fd = os.open(str(lock), os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX)                                                # 我拿著鎖：寫的人要等
        p = subprocess.Popen([sys.executable, str(BIN), "-s", "me", "board", "wait", "bob", "x"], stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.env, cwd=str(self.tmp))
        time.sleep(1.0)
        self.assertIsNone(p.poll())
        self.assertEqual(self.board()["seq"], 1)
        os.close(fd)
        p.communicate(timeout=60)
        self.assertEqual((p.returncode, self.board()["seq"]), (0, 2))
        ps = [subprocess.Popen([sys.executable, str(BIN), "-s", "me", "board", "wait", "p%d" % i, "x"], stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.env, cwd=str(self.tmp))
              for i in range(8)]
        for q in ps:
            q.communicate(timeout=60)
            self.assertEqual(q.returncode, 0)
        b = self.board()
        self.assertEqual(b["seq"], 10)                                                # 一筆都沒丟
        self.assertEqual(sorted(w["who"] for w in b["waiting_on"]), ["bob"] + ["p%d" % i for i in range(8)])

    def test_agent_root_from_tool_folder(self):
        (self.tmp / "me" / "tools" / "board_set").mkdir(parents=True)
        env = dict(self.env, AOS_STACK=str(self.tmp / "me" / "tools" / "board_set"))
        self.ok("board", "set", "busy", "via", "tool", env=env)
        self.assertEqual(self.board()["text"], "via tool")                            # 寫在 <root>/board.json
        self.assertFalse((self.tmp / "me" / "tools" / "board_set" / "board.json").exists())
        (self.tmp / "bob" / "tools" / "t").mkdir(parents=True)                       # bob 沒 mailbox/：不認回
        self.ok("board", "set", "busy", env=dict(self.env, AOS_STACK=str(self.tmp / "bob" / "tools" / "t")))
        self.assertTrue((self.tmp / "bob" / "tools" / "t" / "board.json").is_file())
        self.ok("board", "set", "away", env=dict(env, AOS_STACK=str(self.tmp / "carol")))
        self.assertEqual(self.board("carol")["mode"], "away")
        self.ok("-s", "bob", "board", "set", "dnd", env=env)                          # --stack 優先
        self.assertEqual(self.board("bob")["mode"], "dnd")
        self.fails("StackMissing", "board", "set", "busy")
        self.fails("StackMissing", "-s", "nowhere", "board", "set", "busy")

    def test_agent_root_before_its_mailbox_exists(self):
        # 11-24（eca-aos-sol-3 報告 §4 第 4 點）：真的 lazy 工具小格——agent 的 stack 有 daemon 建的 stderr.txt，mailbox/ 與 tools/board_set/
        # 都還沒建；board set 要寫進 <root>/board.json，不是 StackMissing、也不在小格裡建一份
        dev = self.tmp / "dev"
        dev.mkdir()
        (dev / "stderr.txt").write_text("")
        cell = dev / "tools" / "board_set"
        self.ok("board", "set", "busy", "before", "mail", env=dict(self.env, AOS_STACK=str(cell)))
        self.assertEqual(self.board("dev")["text"], "before mail")
        self.assertFalse(cell.exists())
        self.assertFalse((dev / "mailbox").exists())

    def test_refusals(self):
        for args, code in ((["board", "set", "nap"], "ArgumentsBad"),
                           (["board", "set"], "ArgumentsBad"),
                           (["board", "set", "busy", "--back", "soon"], "ArgumentsBad"),
                           (["board", "set", "busy", "--accept", "loud"], "ArgumentsBad"),
                           (["board", "set", "busy", "--by", "bot"], "ArgumentsBad"),
                           (["board", "wait", "bob", "x", "--level", "asap"], "ArgumentsBad"),
                           (["board", "fly"], "CommandUnknown"),
                           (["fly"], "CommandUnknown")):
            self.fails(code, "-s", "me", *args)
        self.fails("ArgumentsBad", "-s", "me", "board", "set", "busy", "x" * 1001)
        self.assertFalse((self.tmp / "me" / "board.json").exists())                  # 被拒的都沒寫

    # ---- 讀：06 §7.3 四步 ----------------------------------------------------------------

    def test_missing_file_is_no_board(self):
        r = json.loads(self.ok("-s", "me", "board", "show", "-j"))
        self.assertEqual((r["posted"], r["board"], r["mode"], r["stale"]), (False, None, "here", False))
        self.assertIn("posted: no board", self.ok("-s", "me", "board", "show"))

    def test_bad_file_is_no_board(self):
        (self.tmp / "me" / "board.json").write_text("{not json")
        r = self.run_c("-s", "me", "board", "show", "-j")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("unreadable", r.stderr)
        self.assertEqual(json.loads(r.stdout)["posted"], False)
        self.put("me", format="board/2", mode="dnd")                                  # format 不對＝沒貼
        r = json.loads(self.ok("-s", "me", "board", "show", "-j"))
        self.assertEqual((r["posted"], r["mode"]), (False, "here"))
        (self.tmp / "me" / "board.json").write_text("{not json")                       # 寫的人不被壞檔擋住
        b = json.loads(self.ok("-s", "me", "board", "set", "busy", "-j"))
        self.assertEqual(b["seq"], 1)

    def test_stale_counts_as_here_for_every_mode(self):
        self.put("me", updated_at=ago(hours=25), mode="here", text="old")            # here 也會過期（05 A7）
        r = json.loads(self.ok("-s", "me", "board", "show", "-j"))
        self.assertEqual((r["stale"], r["mode"]), (True, "here"))
        self.put("me", updated_at=ago(hours=25), mode="dnd", text="old",
                 waiting_on=[{"who": "user", "what": "x", "since_at": ago(hours=25)}])
        r = json.loads(self.ok("-s", "me", "board", "show", "-j"))
        self.assertEqual((r["stale"], r["mode"], r["waiting_on"], r["board"]["text"]), (True, "here", [], "old"))
        out = self.ok("-s", "me", "board", "show")
        self.assertIn("notes: stale", out)
        self.assertIn("[stale, does not count]", out)
        self.put("me", updated_at=ago(minutes=10), expires_at=ago(minutes=1), mode="dnd")   # 過了 expires_at
        self.assertEqual(json.loads(self.ok("-s", "me", "board", "show", "-j"))["mode"], "here")
        self.put("me", updated_at=ago(hours=30), expires_at=ahead(hours=1), mode="dnd")     # expires_at 優先於 24h
        r = json.loads(self.ok("-s", "me", "board", "show", "-j"))
        self.assertEqual((r["stale"], r["mode"]), (False, "dnd"))

    def test_overdue(self):
        self.put("me", mode="away", back_at=ago(minutes=5), back_text="soon")
        r = json.loads(self.ok("-s", "me", "board", "show", "-j"))
        self.assertEqual((r["overdue"], r["mode"]), (True, "away"))
        self.put("me", mode="away", back_at=ahead(minutes=5))
        self.assertFalse(json.loads(self.ok("-s", "me", "board", "show", "-j"))["overdue"])

    def test_clock_odd(self):
        self.put("me", updated_at=ahead(hours=1), mode="dnd")                        # 比現在晚超過 5 分鐘＝當成現在
        r = json.loads(self.ok("-s", "me", "board", "show", "-j"))
        self.assertEqual((r["clock_odd"], r["stale"], r["mode"]), (True, False, "dnd"))
        self.put("me", updated_at=ahead(days=3), mode="dnd")                         # 不會因為「未來」而永不過期，也不算過期
        r = json.loads(self.ok("-s", "me", "board", "show", "-j"))
        self.assertEqual((r["clock_odd"], r["stale"]), (True, False))
        self.put("me", updated_at=ahead(minutes=2), mode="dnd")                       # 5 分鐘內不算怪
        self.assertFalse(json.loads(self.ok("-s", "me", "board", "show", "-j"))["clock_odd"])

    def test_sleeping_counts_as_away_and_live_is_merged(self):
        self.put("bob", mode="dnd")
        self.put("carol", mode="busy", waiting_on=[{"who": "user", "what": "x", "since_at": ago(minutes=1)}])
        r = self.show("bob")
        self.assertEqual((r["mode"], r["asleep"], r["live"]["phase"]), ("dnd", False, "running"))
        r = self.show("carol")
        self.assertEqual((r["mode"], r["asleep"], r["live"]["phase"]), ("away", True, "sleeping"))
        self.table({"bob": "stopped", "carol": "running"})
        self.assertEqual(self.show("bob")["mode"], "away")
        self.assertEqual(self.show("carol")["mode"], "busy")
        self.fails("InstanceMissing", "-d", "d", "board", "show", "nobody")
        r = json.loads(self.ok("-s", "me", "board", "show", "-j"))                   # 查不到 daemon 表＝不併、不報錯
        self.assertIsNone(r["live"])

    def test_user_board(self):
        (self.tmp / "zone" / "board.json").write_text(json.dumps(
            {"format": "board/1", "updated_at": ago(minutes=1), "mode": "away", "by": "user", "text": "asleep"}))
        r = json.loads(self.ok("board", "show", "user", "-j"))
        self.assertEqual((r["who"], r["mode"], r["board"]["text"], r["stack"]), ("user", "away", "asleep", str(self.tmp / "zone")))

    # ---- ls --------------------------------------------------------------------------

    def test_ls_counts_and_only(self):
        self.put("bob", mode="dnd", doing="tests", waiting_on=[{"who": "user", "what": "ok?", "since_at": ago(minutes=1)}])
        lines = self.ok("-d", "d", "board", "ls").splitlines()
        self.assertEqual(lines[0], "bob\tdnd\ttests\tuser\t-")
        self.assertEqual(lines[1], "carol\taway (no board, asleep)\t-\t-\t-")
        self.assertEqual(lines[-1], "2 procs: 1 dnd, 1 away, 1 waiting, 1 waiting on user")
        self.assertEqual([l.split("\t")[0] for l in self.ok("-d", "d", "board", "ls", "--only", "waiting-user").splitlines()[:-1]],
                         ["bob"])
        r = json.loads(self.ok("-d", "d", "board", "ls", "-j"))
        self.assertEqual((r["count"]["procs"], r["truncated"], [x["who"] for x in r["rows"]]), (2, False, ["bob", "carol"]))

    def test_ls_deep_walks_daemon_rows(self):
        sub = self.tmp / "sub"
        sub.mkdir()
        (self.tmp / "dave").mkdir()
        self.table({"dave": "running", "loop": "running"}, daemon=sub, stacks={"loop": str(self.daemon)})   # loop 繞回頂層
        self.table({"bob": "running", "sub": "running"})
        self.put("dave", mode="busy")
        self.assertEqual([l.split("\t")[0] for l in self.ok("-d", "d", "board", "ls").splitlines()[:-1]], ["bob", "sub"])
        names = [l.split("\t")[0] for l in self.ok("-d", "d", "board", "ls", "--deep").splitlines()[:-1]]
        self.assertEqual(names, ["bob", "sub", "sub/dave", "sub/loop"])                # loop 列出來，但不再往下走
        r = json.loads(self.ok("-d", "d", "board", "ls", "--deep", "-j"))
        self.assertEqual([(x["who"], x["mode"]) for x in r["rows"]][2], ("sub/dave", "busy"))

    # ---- check -----------------------------------------------------------------------

    def test_check_samples(self):
        engines = ["--builtin"] + ([""] if has_jsonschema() else [])
        names = sorted(p.name for p in SAMPLES.glob("*.json"))
        for schema in ("board", "letter-comm", "channel", "channel-members"):
            mine = [n for n in names if n.startswith(schema + "-ok") or n.startswith(schema + "-bad")]
            self.assertTrue(any("-ok" in n for n in mine) and any("-bad" in n for n in mine), (schema, mine))
            for n in mine:
                for e in engines:
                    args = ["check", str(SAMPLES / n), "--schema", schema] + ([e] if e else [])
                    r = self.run_c(*args)
                    want = 0 if "-ok" in n else 1
                    self.assertEqual(r.returncode, want, (args, r.stdout, r.stderr))
                    if want:
                        self.assertIn("aos-comm: error: CheckFailed ", r.stderr)

    def test_check_finds_schema_by_format_and_letter(self):
        self.ok("-s", "me", "board", "set", "busy", "x")
        self.assertIn("ok ", self.ok("check", "me/board.json"))
        self.assertIn("ok ", self.ok("check", str(SAMPLES / "channel-ok.json")))
        letter = self.tmp / "letter1"
        letter.mkdir()
        env = {"sender": "/x", "sent_at": ago(minutes=1), "body": {"from": "a", "comm": {"v": 1, "level": "urgent"}}}
        (letter / "letter.json").write_text(json.dumps(env))
        r = self.run_c("check", str(letter), "-j")
        self.assertEqual(r.returncode, 1)
        out = json.loads(r.stdout)
        self.assertEqual((out["schema"], out["ok"]), ("comm/1/letter-comm", False))
        env["body"].pop("comm")
        (letter / "letter.json").write_text(json.dumps(env))
        self.assertIn("a normal letter", self.ok("check", str(letter)))
        self.fails("FileMissing", "check", "nope.json")
        (self.tmp / "x.json").write_text("{}")
        self.fails("ArgumentsBad", "check", "x.json")


if __name__ == "__main__":
    unittest.main()
