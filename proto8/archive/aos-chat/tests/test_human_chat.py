"""封存 2026-11-03：從 proto8/tests/test_human.py 切出來的案例（原檔其餘照跑）。只作歷史，不在 unittest discover 範圍、不維護；要拉回去跑得併回原檔（用到原檔開頭的常數與小函數）。"""

CHAT = str(HUMAN / "aos-chat")


class ChatTest(Base):
    def test_two_questions_keep_history(self):
        r = run(CHAT, "--ws", str(self.ws), self.agent, input="你好\n/status\n第二句\n//斜線開頭\n/bogus\n")   # /status 11-03 拿掉＝沒有這個指令
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(len(lines), 3, r.stdout)              # stdout 只有三個回答
        self.assertTrue(lines[0].startswith("FAKE ANSWER to: 你好"))
        self.assertTrue(lines[1].startswith("FAKE ANSWER to: 第二句"))
        self.assertTrue(lines[2].startswith("FAKE ANSWER to: /斜線開頭"))
        self.assertEqual(r.stderr.count("沒有這個指令"), 2)       # /status、/bogus
        self.assertEqual([m["content"] for m in self.history() if m["role"] == "user"], ["你好", "第二句", "/斜線開頭"])
        self.assertEqual(self.queue("new") + self.queue("cur"), [])

    def test_agent_fails_then_run_resumes(self):
        bad = self.nia(Path(self._tmp.name) / "bad", brain=DEAD)
        r = run(CHAT, "--ws", str(self.ws), bad, input="壞腦那題\n")
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertIn("endpoint: BrainFailed", r.stderr)       # agent 的錯誤一行原樣看得到
        self.assertIn("agent 停了（agent 結束碼 1）", r.stderr)
        self.assertIn("queue 裡還有 1 封沒答", r.stderr)
        r = run(CHAT, "--ws", str(self.ws), self.agent, input="/run\n")   # 新開一個 chat（假腦）：認得還沒答的那封，/run 接著做
        self.assertIn("queue 裡已經有 1 封還沒答", r.stderr)
        self.assertTrue(r.stdout.startswith("FAKE ANSWER to: 壞腦那題"), r.stdout + r.stderr)

    def test_old_protocol_agent_hint(self):
        """chat 替你跑舊協議的 agent：跑完信還在 new/，提醒可能是舊協議（10-30 晚真腦實測發現 2）。"""
        r = run(CHAT, "--ws", str(self.ws), DAN, input="你好\n")
        self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)
        self.assertIn("agent 跑完了，但 queue 裡還有 1 封沒答", r.stderr)
        self.assertIn("舊協議", r.stderr)

    def test_without_agent_waits_for_other_runner(self):
        p = subprocess.Popen([CHAT, "--ws", str(self.ws)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, env=env())
        p.stdin.write("別人跑\n")
        p.stdin.flush()
        deadline = time.time() + 10
        while not self.queue("new"):
            self.assertLess(time.time(), deadline)
            time.sleep(0.1)
        time.sleep(1.5)
        self.assertEqual(self.go().returncode, 0)
        out, err = p.communicate("", timeout=30)
        self.assertEqual(p.returncode, 0, err)
        self.assertTrue(out.startswith("FAKE ANSWER to: 別人跑"), out + err)
        self.assertIn("目前沒有程式在跑這隻 agent", err)

    def test_agent_missing(self):
        r = run(CHAT, "--ws", str(self.ws), str(self.ws / "nope"), input="")
        self.assertRegex(r.stderr, r"^aos-chat: AgentMissing ")
        r = run(CHAT, "--ws", str(self.ws), "--trace", input="")      # 11-03 拿掉
        self.assertRegex(r.stderr, r"^aos-chat: FlagUnknown ")


