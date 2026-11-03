"""封存 2026-11-03：從 proto8/tests/test_llm_kernel.py 切出來的案例（原檔其餘照跑）。只作歷史，不在 unittest discover 範圍、不維護；要拉回去跑得併回原檔（用到原檔開頭的常數與小函數）。"""

class DemoCase(unittest.TestCase):
    def test_demo_llm_kernel(self):
        with tempfile.TemporaryDirectory() as ws:
            for a in "abc":
                Path(ws, a, "new").mkdir(parents=True)
                Path(ws, a, "new", "q1.txt").write_text("%s 問：2+2？\n" % a)
            r = subprocess.run([tool("aos-exec"), str(ROOT / "demo" / "llm-kernel")], cwd=ws, env=env_of(),
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            for a in "abc":
                self.assertEqual(Path(ws, a, "out", "q1.txt").read_text(), "FAKE ANSWER to: %s 問：2+2？\n" % a)
            served = [json.loads(l) for l in Path(ws, ".stack", "procs", "kernel", "served.jsonl").read_text().splitlines()]
            self.assertEqual([s["level"] for s in served], ["high", "normal", "normal"])
            self.assertEqual([s["time_ms"] for s in served], [5000, 800, None])   # 同級：宣告短的（b）先、沒寫的（a）最後
            self.assertEqual([s["code"] for s in served], [0, 0, 0])
            self.assertEqual([s["counter_tokens"] for s in served], [33, 33, 33])   # 假腦編的 usage（字數）經 AOS_KERNEL_REPORT 交回
            used = json.loads(Path(ws, ".stack", "procs", "kernel", "used.json").read_text())
            self.assertEqual((used["window"], used["counter_calls"], used["counter_tokens"]), ("day", 3, 99))


