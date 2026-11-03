← [入口](../2026-10-28-agent-round.md)｜涵蓋：5. stack 裡有什麼、6. 外部指令對內部單位｜上一份 [03-4-單位介面](03-4-單位介面.md)｜下一份 [05-已定](05-已定.md)

## 5. stack 裡有什麼

| 檔 | 誰寫 | 內容 |
|---|---|---|
| `current.txt` | queue claim | 認領中的題名，一行一題（插話多題） |
| `history.jsonl` | history append／compact | 對話（P-41） |
| `history_archive/<UTC>.jsonl` | history compact | 壓掉的原文整份 |
| `compact/` | compact 格 | 壓到一半的半成品（`run/`）與每次的報告（`<run>/report.json`、`log.jsonl`；實作時代定 25） |
| `endpoint.txt` | round（switch）、外面的人 | 目前用的 endpoint 名；沒有＝default |
| `usage.jsonl` | endpoint | 每次問腦的 usage |
| `live.jsonl` | queue emit、endpoint 串流 | 中間輸出；只接不重寫 |
| `trace.jsonl` | loop、round | 每次、每格一行 |
| `<工具名>/` | aos-tools call | 工具的小格（P-17） |

都在 `$AOS_STACK`（預設 `$AOS_WS/.stack/`，N-57）；定義資料夾不被寫（P-15）。沒有別的狀態檔：round 從哪接著做看 `cur/` 跟 history 就夠。

## 6. 外部指令對內部單位

| 外面打的 | 對到 | 備註 |
|---|---|---|
| `aos-say` | `queue push` | 現成，不改 |
| `aos-listen` | `queue pop`；`--follow` 讀 `live.jsonl` | 現成；follow 改讀 live.jsonl |
| `aos-tools add／rm／ls／get／call` | `tools.json`；act 用 `call` | 現成 |
| （未來）`aos-endpoint ls／set／get` | `ls endpoint/`、`endpoint.txt` | 先不做，手打就行 |
| `aos-hub`（外部 CLI：claude code、codex、pi） | 外部 CLI 跟 aos 接入的接口；**不納入 round**、不另做東西 | agent-ops 決定 14 |
| `aos-exec <agent>/round <agent>`（外部接口） | 同步問一題、等答案：先 `queue push` 一題，叫一次 round 認領、跑完一輪、答案在 `out/<題名>`；不需要 agent 常駐 | agent-ops 決定 15；例：claude code 的 tools.json 登記「問 agent-xxx」，背後 push＋round＋讀答案，經 aos-mcp 叫到 |
| loop 的 ctl.json | 外部停、暫停 | 現成（N-06），round 不另做 |

- **外部接口四種並列**：hub、aos-mcp、say／listen 協議、round（決定 14、15）。say／listen 是非同步（要有 agent 開著收信）；round 是同步（叫一次跑完一題）。
- **搶信箱是呼叫者自己的風險**：同一個工作區如果另有 aos-loop 在收信，外面叫的 round 會搶同一個信箱；工具不另加保護（決定 15、C-53），要避開就照 P-18 給各自的工作區或 stack。
