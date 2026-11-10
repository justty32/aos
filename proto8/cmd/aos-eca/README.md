# aos-eca — 外部 coding agent（claude／codex）的兩支指令

← [cmd](../README.md)｜範本：[templates/eca-claude](../../templates/docs/01-eca-claude.md)

- `bin/aos-eca-turn`：答一輪——從 stack 的 queue 認領一批、交給 CLI 就收信、回答接進 history。說明在 [cmd/docs/01](../docs/01-逐支說明.md#逐支說明)。
  **history 被改過＝下一輪開新 claude 對話**（11-10 self-family ⑩）：靠小格的 `.history_sum` 認出來，帶改過的紀錄過去；畫面開著不換。細節同上。
  **turn 死了外部 CLI 跟著收**（11-10 坑-52，Linux）：非互動起的 claude／codex 設了 `PR_SET_PDEATHSIG`＝SIGTERM，aos-eca-turn 被 `kill -9`／OOM（或它的 aos-loop 被殺、經 aos-inst 的 PDEATHSIG 連帶）時 CLI 收 SIGTERM，不留孤兒跟下一輪的 `--resume` 寫同一段對話；tmux 畫面裡的 CLI 不在此列（`cli_session.parent_death_term`）。
- `bin/aos-eca-screen`：eca 的 screen 子介面身體（open／close／watch），人經 `aos-agent` 叫。說明在 [cmd/docs/05](../docs/05-aos-llm與eca入口.md)。
