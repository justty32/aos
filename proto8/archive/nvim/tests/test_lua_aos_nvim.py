"""封存 2026-11-03：從 proto8/tests/test_lua_aos.py 切出來的案例（原檔其餘照跑）。只作歷史，不在 unittest discover 範圍、不維護；要拉回去跑得併回原檔（用到原檔開頭的常數與小函數）。"""

NVIM_DIR = ROOT / "extras" / "editors" / "nvim"


@unittest.skip("demo/agent-dan 11-02 晚刪了；smoke.lua 編 examples/agent_dan.lua（讀 agent-dan 的檔）、編不出來——留不留等使用者")
@unittest.skipUnless(shutil.which("nvim"), "沒有 nvim")
class TestNvim(unittest.TestCase):
    def test_headless_smoke(self):
        """editors/nvim/tests/smoke.lua：在 nvim --clean --headless 裡把外掛的指令都走一遍。"""
        r = subprocess.run(["nvim", "--clean", "--headless", "-l", str(NVIM_DIR / "tests" / "smoke.lua")],
                           capture_output=True, text=True, env=env(), timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("smoke: 全部通過", r.stdout + r.stderr)


