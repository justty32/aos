from _matrix_faults import *  # noqa: F403


class TestMountUnknown(MatrixCase):
    """〔core〕A4-01（spec §0、§4.5）：加掛請求或 birth.json 讀不到＝那一件不知道——請求留著、不寫回條、不改 birth，
    round.json 的 mounts 記一筆 unknown；故障解除後下一個 tick 照常掛上。"""
    def _setup(self):
        node = self.mknode("a", [keep_item("job")])
        self.itick()
        self.wait_pid(node, "job")
        self.itock()
        sd = self.slot(node, "job")
        write_json(os.path.join(sd, "mount-req", "data.json"), {"name": "data", "path": "data", "why": "t"})
        return node, sd, self.birth(node, "job")

    def _held_then_served(self, node, sd, before):
        self.assertTrue(os.path.exists(os.path.join(sd, "mount-req", "data.json")), "讀不到時把請求刪了")
        self.assertFalse(os.path.exists(os.path.join(sd, "mount-done", "data.json")), "讀不到時寫了回條")
        self.assertEqual(self.birth(node, "job"), before, "讀不到時改了 birth")
        self.assertTrue([m for m in self.round_json(node)["mounts"] if m.get("unknown")], self.round_json(node)["mounts"])
        self.itock()
        self.itick()
        self.assertTrue(read_json(os.path.join(sd, "mount-done", "data.json"))["result"]["ok"])
        b = self.birth(node, "job")
        self.assertEqual((b["run"], b["mounts"]["data"].get("dyn")), (1, True), b)
        self.assertTrue(os.path.islink(os.path.join(sd, "mnt", "data")))

    def test_request_unreadable_kept(self):
        node, sd, before = self._setup()
        with fault("open:*/mount-req/data.json:EIO"):
            self.itick()
        self._held_then_served(node, sd, before)

    def test_birth_unreadable_while_serving(self):
        node, sd, before = self._setup()
        real = aos7_mount.fact

        def fact(path, *a, **kw):   # 只讓加掛重讀 birth 那一下讀不到（槽判定照常）
            if str(path).endswith("/birth.json"):
                with fault("open:*/birth.json:EIO"):
                    return real(path, *a, **kw)
            return real(path, *a, **kw)
        with mock.patch.object(aos7_mount, "fact", side_effect=fact):
            self.itick()
        self._held_then_served(node, sd, before)


class TestDaemonStatUnknown(MatrixCase):
    """〔core〕"""
    def _stat(self, e):
        """daemon 看已登記 node 的 stat 讀不到：時間線保留、不進 missing、不起 reaper，last_error 帶 errno 類型。"""
        node = self.mknode("a")
        d = aos7_daemon.Daemon(self.root)
        self.addCleanup(os.close, d.rfd)
        d.registry = {"a": {}}
        st = os.lstat(node)
        tl = aos7_daemon_timeline.Timeline(d, "a", (st.st_dev, st.st_ino))   # 不 start：只看 check_nodes 怎麼對待它
        d.timelines["a"] = tl
        with fault("stat:%s:%s" % (node, e)):
            d.check_nodes()
        self.assertIs(d.timelines.get("a"), tl, "看不到 node 就丟掉時間線")
        self.assertNotIn("a", d.missing)
        self.assertNotIn("a", d.reapers)
        self.assertFalse(tl.gone)
        le = tl.last_error or {}
        err = le.get("why", "")
        # 契約（隊長 10-04）：errno 類型放在 last_error 的 kind（errno 名）；err 文字裡帶也算
        self.assertTrue(le.get("kind") == e or e in err or "Errno %d" % getattr(errno, e) in err,
                        "last_error 沒有 errno 類型：%r" % tl.last_error)


gen(TestDaemonStatUnknown, "node_stat", [(e, (e,)) for e in ERRNOS], TestDaemonStatUnknown._stat)


class TestDaemonStatRuleFile(DaemonCase):
    """〔core〕"""
    def test_real_daemon_node_stat_rule_file(self):
        """真 daemon、`AOS7_TEST_FAULT=@規則檔` 中途開關：命中紀錄檔經環境傳給 daemon，證明 stat 注入真的打中；
        看不到 node 時不進 missing、任務不被收、last_error 帶 errno 類型；拿掉規則檔後回合照常前進。"""
        node = self.mknode("a", [keep_item()], interval_ms=150)
        rules = os.path.join(self.root, "fault-rules.txt")
        f = Fault("@" + rules, ops={"stat"})
        self.addCleanup(f.close)
        self.start_daemon(env=f.env, register=["a"])
        pid = self.wait_pid(node, "k")["pid"]
        self.wait_round(2)
        self.assertEqual(f.hits(), 0, "規則檔還沒寫就有命中：%r" % f.records())
        with open(rules, "w") as fh:
            fh.write("stat:%s:EIO\n" % node)
        self.wait_for(lambda: f.hits("stat") >= 2, 5, "daemon 沒有打中 stat 注入（命中 %r）" % f.records())
        self.wait_for(lambda: (self.nstat().get("last_error") or {}).get("kind") == "EIO", 5,
                      "last_error 沒有 errno 類型：%r" % self.nstat())
        self.assertNotEqual(self.nstat().get("phase"), "missing", "看不到 node 就進 missing：%r" % self.nstat())
        self.assertTrue(alive(pid), "看不到 node 就把任務收了")
        f.check(where="（真 daemon、@規則檔）")
        os.remove(rules)
        n = f.hits("stat")
        r = self.node_round()
        self.wait_round(r + 2)
        self.assertEqual(f.hits("stat"), n, "拿掉規則檔後還在命中")
        self.assertTrue(alive(pid))
        self.assertEqual(self.wait_pid(node, "k")["pid"], pid)


if __name__ == "__main__":
    unittest.main()
