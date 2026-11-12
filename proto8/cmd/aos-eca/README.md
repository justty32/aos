# aos-eca — 外部 coding agent（claude／codex）的兩支指令

← [cmd](../README.md)｜範本：[templates/eca-claude](../../templates/docs/01-eca-claude.md)

- `bin/aos-eca-turn`：答一輪——從 stack 的 queue 認領一批、交給 CLI 就收信、回答接進 history。說明在 [cmd/docs/01](../docs/01-逐支說明.md#逐支說明)。
  **history 被改過＝下一輪開新 claude 對話**（11-10 self-family ⑩）：靠小格的 `.history_sum` 認出來，帶改過的紀錄過去；畫面開著不換。細節同上。
  **turn 死了外部 CLI 跟著收**（11-10 坑-52，Linux）：非互動起的 claude／codex 設了 `PR_SET_PDEATHSIG`＝SIGTERM，aos-eca-turn 被 `kill -9`／OOM（或它的 aos-loop 被殺、經 aos-inst 的 PDEATHSIG 連帶）時 CLI 收 SIGTERM，不留孤兒跟下一輪的 `--resume` 寫同一段對話；tmux 畫面裡的 CLI 不在此列（`cli_session.parent_death_term`）。
  **hook（eca 縮水版）**（11-10 晚 [hook 圖紙 § 6](../../thinking/2026-11/10/self-family/hook/01-圖紙.md#6-eca-縮水版)）：定義的 interfaces.json 宣告 `hooks` 時，這支跑 `before_queue`／`after_queue`／`brain_failed`／`tool_added`，`before_tool`／`after_tool` 在 aos-mcp；有哪些、沒有哪些見 [templates/docs/01](../../templates/docs/01-eca-claude.md)。
  **slash 指令**（11-12 [eca-slash](../../thinking/2026-11/12/eca-slash.md)，⑭）：`aos-agent say／chat` 送一封剛好是 `/clear`、`/compact`、`/status`、`/usage`、`/exit` 的信＝aos 這層做（claude -p 認得的 `/compact`、`/usage` 交給 claude），回一則 `[aos] slash: …`，listen 照拿；`/clear` 連 history 一起清、claude 的 `/compact` 把 history 換成它的摘要（原文都搬到 `history_removed.jsonl`）；畫面開著時這兩個打進畫面。`/goal …`（以它開頭就算，含 `/goal clear`）是 CLI 自己的 goal：畫面開著打進去、沒開交給 claude（codex 回一句請開畫面），跟 aos 的 goal.json 不同步。畫面上打的由畫面 hook 跟上（`cli_session.follow_session`／`clear_history`／`compact_history`；codex 換到剛開的 thread＝清、同一段 thread 被壓過＝history 換成它壓縮後留下的對話）。
- `bin/aos-eca-screen`：eca 的 screen 子介面身體（open／close／watch），人經 `aos-agent` 叫。說明在 [cmd/docs/05](../docs/05-aos-llm與eca入口.md)。
