"""step 任務包測試。"""
from _step import *  # noqa: F403

class TestStepDaemon(StepCase):
    """〔step〕真的 daemon：兩個範例走通、pause 時耐性不走、重複跑檔案數不長、wake 選項。"""

    def test_csv_end_to_end(self):
        """CSV→JSON→報表：兩步各一個核心 run（不同槽），第二步只讀第一步已採用的 request，結果檔各一份。"""
        node = self.mknode("a", interval_ms=50)
        self.set_tasks(node, [self.install(node, "csv", example="csv")])
        self.start_daemon(register=["a"])
        self.wait_for(lambda: self.frame(node, "csv").get("phase") == "ended", 20, "csv 沒跑完")
        fr = self.frame(node, "csv")
        self.assertEqual(fr["end"], "ok", fr)
        acc = fr["accepted"]
        self.assertTrue(acc["convert"]["run"].startswith("step-csv-convert#"), acc)
        self.assertTrue(acc["stats"]["run"].startswith("step-csv-stats#"), acc)
        rep = read_json(self.jd(node, "csv", "out", "report.json"))
        self.assertEqual(rep["from"], acc["convert"]["request"])
        self.assertEqual(rep["rows"], 5)
        self.assertEqual(rep["by_dept"]["eng"], {"n": 2, "sum": 200.0, "avg": 100.0})
        self.assertEqual(len(self.results(node, "csv", "convert")), 1)
        self.assertEqual(len(self.results(node, "csv", "stats")), 1)
        res = read_json(self.jd(node, "csv", "results", "convert", self.results(node, "csv", "convert")[0]))
        self.assertEqual(res["run"], acc["convert"]["run"])
        self.assertIn("jobs/csv/out/data.json", res["artifacts"])
        self.assertEqual(self.step_items(node), [])
        done = os.path.join(self.root, ".aosd", "ctl-done")
        self.assertEqual([n for n in os.listdir(done) if ".wake." in n], [])     # wake 預設 false
        st = self.step_cli(node, "status", "jobs/csv")
        self.assertEqual(json.loads(st.stdout)["end"], "ok", st.stderr)

    def test_backup_end_to_end(self):
        """備份四步走通：rotate 一次、通知帶 request；dump 失敗兩次後成功（count 計數 2）。"""
        node = self.mknode("a", interval_ms=50)
        item = self.install(node, "backup", example="backup")
        jd = self.jd(node, "backup")
        with open(os.path.join(jd, "dump.sh")) as f:
            body = f.read()
        with open(os.path.join(jd, "dump.sh"), "w") as f:     # 前兩次故意失敗
            f.write('n=$(cat "$1/../tries" 2>/dev/null || echo 0); echo $((n+1)) > "$1/../tries"\n'
                    '[ "$n" -ge 2 ] || exit 1\n' + body)
        self.set_tasks(node, [item])
        self.start_daemon(register=["a"])
        self.wait_for(lambda: self.frame(node, "backup").get("phase") == "ended", 30, "backup 沒跑完")
        fr = self.frame(node, "backup")
        self.assertEqual(fr["end"], "ok", fr)
        self.assertEqual(fr["counts"], {"retry_dump": 2})
        self.assertEqual(len(self.results(node, "backup", "dump")), 3)
        with open(os.path.join(jd, "archive", "rotations.log")) as f:
            self.assertEqual(f.read().split(), ["rotated"])
        with open(os.path.join(jd, "out", "notify.txt")) as f:
            self.assertIn(fr["accepted"]["notify"]["request"], f.read())

    def test_pause_freezes_patience(self):
        """wait 步耐性 10 回合；pause node 1.5 秒（≈15 個 interval）：框架不動、不逾時；resume 後條件成立照常結束。"""
        node = self.mknode("a", interval_ms=100)
        t = {"job": "pz", "start": "a", "steps": {
            "a": {"run": child("pz-a"), "finite": True, "ok": "w"},
            "w": {"wait": {"exists": "${job}/ack"}, "patience": 10, "then": "done"},
            "done": {"end": "ok"}}}
        self.set_tasks(node, [self.install(node, "pz", t)])
        self.start_daemon(register=["a"])
        self.wait_for(lambda: self.frame(node, "pz").get("pc") == "w"
                      and self.frame(node, "pz")["seen"] > self.frame(node, "pz")["since"], 15, "沒走到 w")
        self.prog("aos7-ctl", "daemon", self.root, "pause", "a", "--owner", "t")
        self.wait_for(lambda: self.nstat().get("phase") == "paused", 10, "沒 pause")
        time.sleep(0.3)                                          # 最後一個 tock 的那一圈寫完
        before, rnd = self.frame(node, "pz"), self.node_round()
        time.sleep(1.5)
        after = self.frame(node, "pz")
        self.assertEqual((after["rev"], after["seen"], after["phase"], after["halt"]),
                         (before["rev"], before["seen"], "running", None))
        self.assertEqual(self.node_round(), rnd)
        self.prog("aos7-ctl", "daemon", self.root, "resume", "a", "--owner", "t")
        open(self.jd(node, "pz", "ack"), "w").close()
        self.wait_for(lambda: self.frame(node, "pz").get("phase") == "ended", 10, "resume 後沒結束")
        self.assertEqual(self.frame(node, "pz")["end"], "ok")

    def test_file_count_bounded(self):
        """restart_on_end：同一個工作跑 6 次，結案時清結果，工作資料夾檔數與槽數不隨次數長。"""
        node = self.mknode("a", interval_ms=20)
        self.set_tasks(node, [self.install(node, "csv", example="csv", restart_on_end=True)])
        self.start_daemon(register=["a"])
        seen = {}

        def files():
            return sum(len(fs) for _, _, fs in os.walk(self.jd(node, "csv")))

        def sample():
            fr = self.frame(node, "csv")
            if fr.get("phase") == "ended" and fr["inst"] not in seen:
                n, slots = files(), os.listdir(os.path.join(node, ".aos", "tasks"))
                if self.frame(node, "csv").get("rev") == fr["rev"]:     # 數的時候沒換人
                    seen[fr["inst"]] = (n, len(slots))
            return len(seen) >= 6
        self.wait_for(sample, 60, "沒跑滿 6 次")
        counts = [v[0] for v in seen.values()]
        self.assertEqual(len(set(counts[1:])), 1, seen)
        self.assertTrue(all(v[1] <= 3 for v in seen.values()), seen)   # 直譯器＋兩個 once 槽

    def test_wake_option(self):
        """wake: true：登記完 once 就寫 daemon 的 wake（回條 ok）；預設不寫。"""
        node = self.mknode("a", interval_ms=300)
        self.set_tasks(node, [self.install(node, "wk", probe_table("wk"), wake=True)])
        self.start_daemon(register=["a"])
        self.wait_for(lambda: self.frame(node, "wk").get("phase") == "ended", 20, "沒跑完")
        done = os.path.join(self.root, ".aosd", "ctl-done")
        rs = [read_json(os.path.join(done, n)) for n in os.listdir(done) if ".wake." in n]
        self.assertTrue(rs and all(r["result"]["ok"] for r in rs), rs)
        self.assertTrue(any(r["by"] == "a:step-wk" for r in rs), rs)


if __name__ == "__main__":
    unittest.main()
