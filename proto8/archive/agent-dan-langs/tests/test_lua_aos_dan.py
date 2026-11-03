"""封存 2026-11-03：從 proto8/tests/test_lua_aos.py 切出來的案例（原檔其餘照跑）。只作歷史，不在 unittest discover 範圍、不維護；要拉回去跑得併回原檔（用到原檔開頭的常數與小函數）。"""

# 原本是 test_lua_aos.py 裡 build 那個 TestCase 的一個方法
    @unittest.skip("demo/agent-dan 11-02 晚刪了；examples/agent_dan.lua 讀它的 brain.py 等檔、編不出來——留不留等使用者")
    def test_dan_same_as_demo(self):
        same_tree(self, self.build("agent_dan.lua"), ROOT / "demo" / "agent-dan")

