← [入口](../2026-10-28-agent-round.md)｜涵蓋：5. stack 裡有什麼、6. 外部指令對內部單位、7. 怎麼落地：做一隻新範本 agent（10-28 晚實作中）｜上一份 [03-4-單位介面](03-4-單位介面.md)｜下一份 [05-已定](05-已定.md)

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
| `aos-hub`（外部 CLI：claude code、codex、pi） | 外部 CLI 跟 aos 接入的接口；**不納入 round**、不另做東西 | agent-ops 決定 14；「黑盒子當 round」已否決 |
| `aos-exec <agent>/round <agent>`（外部接口） | 同步問一題、等答案：先 `queue push` 一題，叫一次 round 認領、跑完一輪、答案在 `out/<題名>`；不需要 agent 常駐 | agent-ops 決定 15；例：claude code 的 tools.json 登記「問 agent-xxx」，背後 push＋round＋讀答案，經 aos-mcp 叫到 |
| loop 的 ctl.json | 外部停、暫停 | 現成（N-06），round 不另做 |

- **外部接口四種並列**：hub、aos-mcp、say／listen 協議、round（決定 14、15）。say／listen 是非同步（要有 agent 開著收信）；round 是同步（叫一次跑完一題）。
- **搶信箱是呼叫者自己的風險**：同一個工作區如果另有 aos-loop 在收信，外面叫的 round 會搶同一個信箱；工具不另加保護（決定 15、C-53），要避開就照 P-18 給各自的工作區或 stack。

<a id="7-怎麼落地做一隻新範本-agent這次不做"></a>

## 7. 怎麼落地：做一隻新範本 agent（10-28 晚實作中）

1. **`lib/endpoint/fake/`、`lib/endpoint/openai/`**：從 agent-dan 的 brain.py 把「問腦」那段抽出來；驗：`echo '{"messages":[…]}' | aos-exec lib/endpoint/fake X` 吐一則 assistant；openai 接 LiteLLM 吐真的、`usage.jsonl` 多一行；拔掉 key 看到 `KeyBad`、指錯埠看到 `BrainFailed`（用 tests/dead_brain.py）。
2. **`lib/agent/queue/`**：從 brain.py 的認領段＋aos-say／listen 抽；驗：push → peek 看得到 → claim 搬到 cur/、current.txt 有 → finish 寫 out/、done/ 有；withdraw 已認領的報錯。
3. **`lib/agent/history/`**：append／read／compact；compact 搬 agent-hal 的三步；驗：塞一份大的 history 跑 compact，`history_archive/` 多一份、新的能被 read。
4. **`lib/agent/act/`**：從 act.py 抽；驗：餵一則有兩個 tool_calls 的 assistant，吐兩則 tool、順序對；`MAX_PARALLEL=2` 結果順序仍對；掛一個 pre_tool 退 10 看到那次不跑。
5. **`lib/agent/round/`**（零件庫、語法糖＝aos-loop 加「這一輪結束就停」，不升成 aos 指令，決定 13）：照 § 2 寫骨架，「從哪接著做」那段要能單獨做一格（給 aos-loop 一格一格跑用，決定 12）；驗：假腦跑完一題退 0、沒題退 10；endpoint 壞掉退 1 且 state／history 不動；掛 `on_error` 印 switch 看到 `endpoint.txt` 換名字再成功。
6. **範本 `demo/agent-nia/`**（人名接 meg、pip…）：照 § 1 擺捷徑與 `.env`；`demo/run.sh` 加一段；驗：WSL 上假腦一題、LiteLLM 一題，`tree -a .stack` 看得到 § 5 的檔。（10-28 晚做了：照第 0 步改成手寫相對路徑的 `parts.json`、不擺捷徑；LiteLLM 那題這台連不上沒跑，見文末 39～41）
7. **aos-ai spawn**：多一種範本（捷徑複製後改絕對）。（10-28 晚做了：複製後把 `parts.json`、`tools.json` 指出範本的相對路徑改成絕對，見文末 42）
8. **測試** `tests/test_round.py`：以上各驗各一案；跑 proto8 全套不退。（10-28 晚做了：範本與 spawn 的案在 `tests/test_nia.py`）
9. **條文**：P-23、P-41 改寫（agent-ops 決定 3；P-41 含「只有 compact 可改寫」）、P-25／C-61 加註（決定 10）、P-20 改「預設」、P-33／C-52 加「round 的參數」一句、N-43 加「分類靠代號」、N-53／C-25 加「一格一次用 aos-loop、一輪用 round，看 `_entry`」（決定 12）；NORMS 待定加這份的代定；code map、demo README、artifact 同步。
10. 黑盒子（claude code）那條：hub 已做，round 不碰（決定 14：aos 歸 aos）。
11. **round 當外部接口**（決定 15）：做一個「問 agent-xxx」的工具（push 一題＋叫一次 round＋印 `out/` 答案），登記進 claude code 用的 tools.json；驗：claude code 經 aos-mcp 問一題拿到答案、agent 不常駐；搶信箱不加保護。（10-28 晚做了：`lib/aos/ask_round`，見文末 43～47；claude -p〔haiku〕經 aos-mcp 問 agent-nia 一題拿到假腦答案）

0. （決定 16，排在第 1 步前）**`proto8/bin/aos-parts`**：add／rm／ls／get／which；驗：註冊的優先、沒註冊走固定名字（捷徑與真資料夾各一）、都沒有退 10、註冊了但路徑壞＝`PartBad`。之後第 5 步 round 叫格一律經 `which`；第 6 步範本改成手寫相對路徑的 `parts.json`（不必擺捷徑）；第 7 步 aos-ai spawn 改成 `aos-parts add`（不複製捷徑）；第 9 步 P-25／C-61 的加註改成「格也走註冊檔，同 aos-tools 的加註；`..` 只在方便用的捷徑」。

每步各一個 commit，每步結尾在 WSL 實跑一次。

<a id="要使用者看的只這一節"></a>
