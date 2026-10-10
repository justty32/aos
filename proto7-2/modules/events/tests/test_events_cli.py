"""事件包按職責分組的測試。"""
from _events_read import *


class TestNewbieCli(Fixtures):
    """第一次跑不靠 daemon：pub 不給 --event-id／--node 也能寫；--help 講清 obs／must。"""
    def run_cli(self, *args):
        return subprocess.run([sys.executable, os.path.join(EVENTS, "aos7-events"), *args],
                              capture_output=True, text=True, timeout=20)

    def test_pub_defaults_without_daemon(self):
        events = os.path.join(self.dir, "n1", "events")
        outs = []
        for _ in range(2):
            p = self.run_cli("pub", "--create", "--events", events, "--kind", "hello", "--payload", '{"msg": "hi"}')
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            outs.append(json.loads(p.stdout))
        self.assertEqual([o["seq"] for o in outs], [1, 2])
        self.assertTrue(all(o["event_id"].startswith("auto/") for o in outs))
        self.assertNotEqual(outs[0]["event_id"], outs[1]["event_id"])
        import aos7_events_store as store
        self.assertEqual(store.load_state(events)["node"], "n1")   # 新建時 node＝上一層資料夾名
        recs = reader.read(events, "obs")["records"]
        self.assertEqual([(r["source"]["node"], r["payload"]) for r in recs], [("n1", {"msg": "hi"})] * 2)
        p = self.run_cli("pub", "--events", events, "--kind", "x", "--payload", "{}", "--event-id", "x/1")
        self.assertNotIn("event_id", json.loads(p.stdout))   # 自己給 id 時輸出格式不變
        p = self.run_cli("read", "--events", events, "--text")
        self.assertIn('1 hello n1 {"msg": "hi"}', p.stdout)

    def test_existing_state_node_wins_and_bad_state_stays_usage(self):
        events = os.path.join(self.dir, "n1", "events")
        import aos7_events_pub as pub
        self.assertTrue(pub.publish(events, "k", "e1", {}, node="other")["ok"])
        p = self.run_cli("pub", "--events", events, "--kind", "k", "--payload", "{}")
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertEqual(reader.read(events, "obs", 2)["records"][0]["source"]["node"], "other")
        with open(os.path.join(events, "state.json"), "w") as f:
            f.write("broken")
        p = self.run_cli("pub", "--events", events, "--kind", "k", "--payload", "{}")
        self.assertEqual((p.returncode, json.loads(p.stdout)["why"]), (2, "usage"))
        fresh = os.path.join(self.dir, "n2", "events")   # 明給壞 source.node 仍是用法錯，不被預設 node 蓋過
        for bad in ('{"node": ""}', '{"node": 0}'):
            p = self.run_cli("pub", "--create", "--events", fresh, "--kind", "k", "--payload", "{}", "--source", bad)
            self.assertEqual(p.returncode, 2, p.stdout)
        self.assertFalse(os.path.exists(fresh))

    def test_auto_id_printed_on_unknown(self):
        events = os.path.join(self.dir, "n1", "events")
        self.assertEqual(self.run_cli("pub", "--create", "--events", events, "--kind", "k", "--payload", "{}").returncode, 0)
        with locked(os.path.join(events, "state.json")):
            p = self.run_cli("pub", "--events", events, "--kind", "k", "--payload", "{}")
        out = json.loads(p.stdout)
        self.assertEqual((p.returncode, out["why"]), (3, "unknown"))
        self.assertTrue(out["event_id"].startswith("auto/"))

    def test_help_explains(self):
        top = self.run_cli("--help").stdout
        self.assertIn("aos7-events pub --help", top)
        pub_help = self.run_cli("pub", "--help").stdout
        for text in ("must＝", "ack", "--event-id", "第一次寫加 --create"):
            self.assertIn(text, pub_help)
        self.assertIn("舊寫法，下一輪移除", self.run_cli("read", "--help").stdout)



class TestErrorCli(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = tmp.name
        self.events = os.path.join(self.root, 'n', 'events')

    def run_cli(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith('AOS7_')}
        return subprocess.run([sys.executable, '-B', os.path.join(EVENTS, 'aos7-events'), *args],
                              env=env, capture_output=True, text=True, timeout=15)

    def failed(self, p, code):
        self.assertEqual(p.returncode, code, p.stdout + p.stderr)
        self.assertEqual(len(p.stderr.splitlines()), 1, p.stderr)
        self.assertTrue(p.stderr.startswith('aos7-events: '), p.stderr)
        self.assertIn('。', p.stderr)
        if code == 3:
            self.assertTrue(p.stderr.startswith('aos7-events: 不確定：'))

    def pub(self, *extra):
        return self.run_cli('pub', '--events', self.events, '--kind', 'hello', '--payload', '{}', *extra)

    def test_create(self):
        p = self.pub()
        self.failed(p, 1)
        self.assertEqual(json.loads(p.stdout), dict(ok=False, seq=None, dup=False, why='no_events'))
        self.assertFalse(os.path.exists(os.path.dirname(self.events)))
        self.assertEqual(self.pub('--create').returncode, 0)
        self.assertTrue(os.path.isfile(os.path.join(self.events, 'state.json')))
        # 已有空夾也可寫，不需 --create。
        os.mkdir(os.path.join(self.root, 'empty'))
        p = self.run_cli('pub', '--events', os.path.join(self.root, 'empty'), '--kind', 'k', '--payload', '{}')
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_ack(self):
        self.failed(self.run_cli('ack', '--events', self.events, '1'), 1)
        self.assertFalse(os.path.exists(os.path.dirname(self.events)))
        os.makedirs(self.events)
        p = self.run_cli('ack', '--events', self.events, '1')
        self.failed(p, 3)
        self.assertEqual(json.loads(p.stdout)['why'], 'unknown')
        self.assertIn('沒有 state.json', p.stderr)
        self.assertEqual(os.listdir(self.events), [])
        self.assertEqual(store.ack(self.events, 1), 0)
        self.assertEqual(os.listdir(self.events), [])
        self.failed(self.run_cli('read', '--events', self.events, '--channel', 'must', '--ack', '1'), 3)
        self.assertEqual(os.listdir(self.events), [])
        self.assertEqual(self.pub('--must').returncode, 0)
        a = self.run_cli('ack', '--events', self.events, '1')
        b = self.run_cli('read', '--events', self.events, '--channel', 'must', '--ack', '1')
        self.assertEqual((a.returncode, b.returncode, a.stderr), (0, 0, ''))
        self.assertEqual(b.stderr, 'aos7-events: read --ack 是舊寫法，下一輪移除。改用 aos7-events ack --events %s 1\n' % self.events)
        self.assertEqual(json.loads(a.stdout), {'acked_upto': 1})
        self.assertEqual(a.stdout, b.stdout)
        with locked(os.path.join(self.events, 'state.json')):
            self.failed(self.run_cli('ack', '--events', self.events, '1'), 3)
            self.failed(self.pub(), 3)

    def test_review_fixes(self):
        """read 拼錯路徑退 1 不像空帳本；state.json 壞連結 ack 退 3；讀不到（非不存在）pub 不誤報沒夾。"""
        p = self.run_cli('read', '--events', self.events, '--text')
        self.failed(p, 1)
        self.assertEqual(p.stdout, '')
        os.makedirs(self.events)
        os.symlink('missing-state', os.path.join(self.events, 'state.json'))
        p = self.run_cli('ack', '--events', self.events, '1')
        self.failed(p, 3)
        os.unlink(os.path.join(self.events, 'state.json'))
        locked_dir = os.path.join(self.root, 'locked')
        os.mkdir(locked_dir, 0o000)
        self.addCleanup(os.chmod, locked_dir, 0o700)
        if os.geteuid() != 0:
            p = self.run_cli('pub', '--events', os.path.join(locked_dir, 'events'), '--node', 'n',
                             '--kind', 'k', '--payload', '{}')
            self.failed(p, 3)

    def test_pub_and_ack_errors(self):
        self.assertEqual(self.pub('--create').returncode, 0)
        for args in (('--payload', '{'), ('--kind', ''), ('--payload', json.dumps('漢' * 30000, ensure_ascii=False))):
            self.failed(self.pub(*args), 2)
        # 讀寫錯的 detail 含換行也只能印一行，證據留在原夾。
        before = sorted(os.listdir(self.events))
        out, err = io.StringIO(), io.StringIO()
        with patch.object(store, 'ack', side_effect=Unknown('讀寫失敗\n細節')), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(cli.ack_main(self.events, 1), 3)
        self.assertEqual(json.loads(out.getvalue())['why'], 'unknown')
        self.assertEqual(len(err.getvalue().splitlines()), 1)
        self.assertTrue(err.getvalue().startswith('aos7-events: 不確定：'))
        self.assertIn('。', err.getvalue())
        self.assertEqual(sorted(os.listdir(self.events)), before)

    def test_help_and_usage(self):
        for flag in ('--help', '-h'):
            p = self.run_cli(flag)
            self.assertEqual((p.returncode, p.stderr), (0, ''))
            self.assertLessEqual(len(p.stdout.splitlines()), 20)
            for word in ('pub', 'read', 'ack', 'aos7-events pub --help'):
                self.assertIn(word, p.stdout)
            self.assertNotIn('--segment-bytes', p.stdout)
        p = self.run_cli('--help-sampler')
        self.assertEqual((p.returncode, p.stderr), (0, ''))
        self.assertIn('--segment-bytes', p.stdout)
        for args in ((), ('--no-such-option',), ('--rounds', '1'),
                     ('ack', '--events', self.events, '--channel', 'obs', '1'),
                     ('ack', '--events', self.events, '-1'), ('ack', '--events', self.events, 'x'),
                     ('pub',), ('read', '--events', self.events, '--cursor', '0'),
                     ('read', '--events', self.events, '--ack', '1')):
            self.failed(self.run_cli(*args), 2)
        self.assertFalse(os.path.exists(os.path.dirname(self.events)))



if __name__ == "__main__":
    unittest.main()
