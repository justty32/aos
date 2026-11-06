pyfix 與 check_inbox 兩個 lib 工具，2026-11-06 從 proto8/lib 封存到這裡（索引見 [archive/README](../README.md)）。

- `pyfix/`：原 `proto8/lib/agent/pyfix`，把改 Python 的事交給子 agent（`pyfix/agent/`，工具是 base 的 ls、read、write、edit、bash）。
- `check_inbox/`：原 `proto8/lib/aos/check_inbox`，看自己信箱還沒處理的（只看不拿）。
- `agent_tool.py`：封存當下 `proto8/lib/agent/agent_tool.py` 的全文副本；pyfix 要它的 `run_agent`、`fresh_cell`。lib 那份現在只剩 claude、codex 用的 `ask_cli`。
- 為什麼封存：沒有範本、knowledge、試驗場掛它們；授權是 arch-refactor 方向題 6（[thinking](../../thinking/2026-11/05/arch-refactor/README.md)）。
- 要拉回來時注意：`pyfix/agent/tools/` 底下五條捷徑是相對路徑（`../../../../base/<名>`），原本指 `lib/base`，搬進 archive 後已斷；放回 `lib/agent/` 才會通，`agent_tool.py` 也要用這份副本換回 `run_agent`、`fresh_cell`。
