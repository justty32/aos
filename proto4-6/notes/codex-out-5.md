完成，未 commit、未 push，也未開 agent／連真網路。

- 修改 15 檔：兩個 README、四支執行器、三語言 aos 模組、共用 `step_common.py` 與相關測試。
- `wait_for` 四支行為一致；`llm_submit` 已加入 Python／Lua／Janet。
- 新增 21 條測試／檢查，含 Python 假 LLM＋手動 kernel tick 端到端。
- proto4-4：`38 條通過 ✓`、`12 條通過 ✓`、`45 條通過 ✓`。
- proto4-6：65 tests，最後一行 `OK`。
- 根層驗證：ctest 8/8，`100% tests passed`。
- 自行決定：Janet 沿用分散狀態佈局，新增 `.aos-step/state` JDN 保存 `last/history/waiting`。
- 坑：不帶 `--wait` 仍會等 kernel 回 syscall 確認；測試因此在提交行程執行中手動 tick。
- README 179 行；範圍檢查與 `git diff --check` 均通過，沒有未完成項。