"""封存 2026-11-03：從 proto8/tests/test_janet.py 切出來的案例（原檔其餘照跑）。只作歷史，不在 unittest discover 範圍、不維護；要拉回去跑得併回原檔（用到原檔開頭的常數與小函數）。"""

DAN = ROOT / "demo" / "agent-dan"   # 11-02 晚刪了；用到它的兩案 skip


# 原本是 class JanetCompile（test_janet.py）的方法
    def ask_dan(self, prog):
        ws = self.tmp / ("ws-" + Path(prog).name)
        (ws / "new").mkdir(parents=True)
        (ws / "new" / "q1.txt").write_text("現在幾點？\n", encoding="utf-8")
        r = run(EXEC, "--ws", str(ws), str(prog), timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        history = TIME.sub("<時間>", (ws / ".stack" / "history.jsonl").read_text(encoding="utf-8"))
        answer = TIME.sub("<時間>", (ws / "out" / "q1.txt").read_text(encoding="utf-8"))
        trace = [t["state"] for t in fsm_steps(ws / ".stack")]  # 11-03：fsm 不寫 trace.jsonl，跑了哪幾格看 tests/spy_bin 的旁觀者（code＝aos-fsm 的結束碼，分岔接住＝0）
        return files(ws), history, answer, trace, (ws / ".stack" / "state.txt").read_text()

    @unittest.skip("demo/agent-dan 11-02 晚刪了；examples/agent_dan.janet 讀它的檔、編不出來——留不留等使用者")
    def test_agent_dan_same_shape(self):
        """編出來的檔跟手寫的一樣多；JSON 檔內容相同（順序、空白可以不同）；Python 葉子位元組相同。"""
        out = self.compile("agent_dan")
        self.assertEqual(files(out), files(DAN))
        for f in ("fsm.json", "loop.json", "tools.json", "tools/clock/_tooldef.json", "tools/math/_tooldef.json"):
            self.assertEqual(json.loads((out / f).read_text()), json.loads((DAN / f).read_text()), f)
        for f in ("brain.py", "act.py", "system.txt", "tools/math/_entry"):
            self.assertEqual((out / f).read_bytes(), (DAN / f).read_bytes(), f)
        self.assertEqual(json.loads((out / "_entry").read_text()), ["aos-loop", "loop.json"])   # 手寫版是 sh，這裡是 argv 陣列
        self.assertIn("AOS_BRAIN_MODEL=chatgpt-gpt-6-luna-low\n", (out / ".env").read_text())
        self.assertIn("算一個算術式子", (out / "tools/math/_tooldef.json").read_text(encoding="utf-8"))   # 中文不跳脫
        for f in ("idle/_entry", "tools/clock/_entry", "tools/math/_entry"):
            self.assertTrue(os.access(out / f, os.X_OK), f)

    @unittest.skip("demo/agent-dan 11-02 晚刪了；examples/agent_dan.janet 讀它的檔、編不出來——留不留等使用者")
    def test_agent_dan_runs_same(self):
        """假腦（叫 clock 再答）：兩版跑完的工作區、history、答案、走過的格都一樣（時間換掉）。"""
        out = self.compile("agent_dan")
        got, want = self.ask_dan(out), self.ask_dan(DAN)
        self.assertEqual(got, want)
        self.assertIn("FAKE ANSWER to: 現在幾點？（clock said: <時間>）", got[2])

