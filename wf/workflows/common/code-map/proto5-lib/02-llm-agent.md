← [proto5/lib 模組](../proto5-lib.md)（分檔 2/3）｜[上一份](01-exec-daemon-kernel.md)｜[下一份](03-team.md)

| 模組 | 職責 |
|------|------|
| `aos_llm_call` | `aos-llm call`：問模型一次 |
| `aos_llm_ask` | （第三波 W3-2）不需要 agent 家的「多問一次模型」：工具的 `--describe-with-llm`／`--summarize`／`--suggest-with-llm` 共用；temperature 0、從回話抽 JSON |
| `aos_agent` | agent 的 tick 三格、批次派工、kernel 排程登記 |
| `aos_agent_cli` | `aos-agent` 各子命令的 argparse 與分派 |
| `aos_agent_home` | agent 家的內容讀驗與 `aos-llm call` 的六格 loader |
| `aos_agent_info` | agent 的 info 設定與 state 讀驗、寫回 |
| `aos_agent_batch` | 批次建立、inst 產生（含 aos-jail 包裝）、交件、結清 |
| `aos_agent_inputs` | waits 門與輸入消費的恢復流程 |
| `aos_agent_results` | 模型與工具結果判定、失敗分類 |
| `aos_agent_runtime` | 持久化、恢復清理、tick 鎖、測試掛鉤 |
| `aos_agent_init` | `aos-agent init` |
| `aos_agent_say` | `aos-agent say` |
| `aos_agent_listen` | `aos-agent listen` |
| `aos_agent_listen_render` | listen 的印法 |
| `aos_agent_talk` | `aos-agent talk` 來回對話 |
| `aos_agent_status` | `aos-agent status` |
| `aos_agent_pause` | `aos-agent pause`／`continue` |
| `aos_agent_check` | `aos-agent check`（kernel 檢查＋agent 家、工具、權限牆） |
| `aos_agent_tools` | `aos-agent tools add` |
| `aos_agent_tools_edit` | `aos-agent tools ls／rm／alias／unalias` 與共用 info 編輯 |
| `aos_agent_tools_dev` | `aos-agent tools new／test／wrap-py`：造工具（骨架、照描述自動跑案例、Python 函式包成工具包），不需要 agent 家；wrap-py 的 `--describe-with-llm`（只寫提案檔）／`--describe`（照人看過的提案產包）（第三波 W3-2） |
| `aos_agent_tools_wrapcli` | （第三波 W3-2）`aos-agent tools wrap-cli CMD`：argparse 腳本靜態讀、其他指令解 `--help` 文字 → 工具包（`run` 把 JSON 組成 argv、不經 shell）；`--describe-with-llm` 只寫提案、`--spec` 照人看過的參數表產包 |
| `aos_agent_access` | 權限牆（access.json）讀驗與快照 |
| `aos_agent_access_cli` | `aos-agent access ls／set／rm／cwd／net` |
| `aos_agent_events` | 事件紀錄：`log/events.jsonl` 追加與去重讀取，`aos-llm call` 的 `log/usage.jsonl` |
| `aos_agent_context` | 送給模型的東西多大：`aos-agent context` 與 `talk /context` 共用的字數／token 粗估 |
| `aos_agent_compact` | 機械壓縮記憶：`aos-agent compact`、tick idle 自動壓縮、compact 申請、`history --archive`；`--summarize`（第三波 W3-2，只給人用）：模型濃縮封存摘要，機械檢查不過退回機械版 |
| `aos_agent_notes` | `aos-agent notes ls／show`：讀 `tools/notes/` 寫的 `wf-table/1` 筆記檔 |
| `aos_agent_persona` | `aos-agent persona show／set／append`：人格是信任資料，讀寫 `prompts/system.json`，不叫模型不進牢 |
| `aos_jail` | `aos-jail`：組 bwrap 參數並 exec |
| `aos_json_cli` | `aos-json`：人用的 JSON Pointer 改檔（get／set／del／append／merge），`--check-directives` 先驗才寫 |
