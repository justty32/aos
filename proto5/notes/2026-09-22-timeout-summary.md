# 逾時：精簡總結與待拍板（2026-09-22）

astra 唯讀調查了 proto2／4-3／4-5／4-6／4-7 與 proto5 現況（原報告 341 行，在 scratchpad `codex/timeout-report.md`；
這份是我的精簡版與建議，決策由使用者做）。

## 1. proto5 現在哪裡有限時、哪裡沒有

| 環節 | 現況 |
|---|---|
| aos-exec 子程式 | 有，`--timeout-ms`／`run_target(timeout_ms)`，**預設 0＝不限**；到了 TERM 整個 group → 2 秒 → KILL |
| aos-llm-ask 的 HTTP | 有，`engine.timeout_ms` 預設 120 秒——但那是 **socket 逾時**（每次讀寫卡住多久），不是整次呼叫的總上限；慢慢滴回來的回應可以超過 120 秒 |
| aos-agent `idle`／`think`／`act` 各格 | **沒有**整格限時 |
| 工具（`act` 裡一個 call） | **沒有**（`_meta` 沒地方寫；aos-agent 呼叫 `run_inst` 時 `timeout_ms=0`） |
| `waits` 門 | **沒有**期限；每次檢查沒到就退 101，可以永遠等 |
| 引擎失敗重試 | **沒有**上限、沒有間隔；每次退 0，外面再叫就再問 |
| 整個「走一格」 | **沒有**；命令列也沒旗標 |

兩個容易誤會的：exec 的 143／137 只是「子程式被 TERM／KILL」的碼，不能單憑它斷定是逾時（回傳沒有 `timed_out` 欄位）；
工具是另開 session 跑的，**外面砍掉 aos-agent 不會連工具一起死**（agent 沒轉送訊號）。

## 2. 歷代怎麼做（一行一代）

- **proto2**：工具 60 秒、HTTP 300 秒、主線等 LLM 1800 格、連敗 5 次→`stuck`；坑：格數當秒數用、放棄等不撤舊單、互等死結、idle 掉話。
- **proto4-3**：limit 在 aos-run／exec（每格 `timeout_ms`＋整體 `time-limit-ms`，預設都 0）；kernel **沒有** elapsed watchdog，只數非零退出 `bad_after=10`；101 不算壞。
- **proto4-5**：HTTP 300 秒、worker 從派工起算 T＋5 秒（只 TERM 不 KILL）、**排隊沒期限**、`--wait` 到時只是不等了、不撤單。
- **proto4-6**：`wait_for` 沒上限，只記 checks。
- **proto4-7**：每工具 60 秒、輸出 8000 字、等模型 600 次檢查、errors≥5→`stuck`（成功沒清帳，實際是同題累積 5 錯）。

使用者自己在 proto2 筆記寫過的方向：「每一步盡可能短小，不然影響 fps」「跑很久的操作另開一個時鐘去處理」「預期很快卻卡很久，通常就乖乖阻塞」。

## 3. 四個不同的問題，一個 timeout 管不完

1. **一次工作跑太久**（工具卡住）→ 誰量：exec；到了：砍、回一則 `tool` 失敗訊息。
2. **等結果等太久**（`waits`）→ 誰量：加那條等待的人；到了：不能假裝到了。
3. **連續失敗太多**（引擎一直 3）→ 誰量：agent；到了：停下來等人。
4. **整格卡死**（agent 自己讀寫卡住）→ 誰量：只能是**外面另一個進程**（run／kernel），agent 自己量抓不到「永遠不返回」。

## 4. 我的建議：最精簡的一組（先做三個，其他等 kernel／llm cpu）

| 關卡 | 建議 | 放哪 | 先後 |
|---|---|---|---|
| 每個 tool call | 預設 60 秒，可覆寫 | 工具元素多一個 `_timeout_ms`（`_` 開頭本來就不會送給模型；`_meta` 保持是純 inst） | **先做** |
| 引擎連敗 | 連 3 次失敗就停，成功清零 | `state.json` 加一格 `errors`（程式寫、字面整數）；到 3 → **用現有的暫停機制**：往 `waits` 加一條 `continue.json`、`errors` 歸零、stderr 講一句；人 touch 就繼續。不加新狀態 | **先做**（但破了「aos-agent 只劃不加」這條，要你點頭） |
| HTTP | 維持 120 秒 | 規範講清楚它是 socket 逾時 | 只改文件 |
| 整格硬上限 | 300 秒起跳、可覆寫 | 外面的 run／kernel 量與砍，kernel 記一筆、停排、**不自動重跑**（`act` 跑到一半被砍會重複執行工具） | 跟 kernel 一起做 |
| `waits` 期限 | **先不加**預設期限 | 人工 pause 要能永遠等；有 owner 的非同步工作由 owner 給有限終態 | 之後要再加 `until` |
| llm cpu 排隊／worker | 排隊 300 秒、worker 150 秒 | llm cpu 自己管；agent 不再另猜 | 跟 llm cpu 一起做 |

先不做：通用 inst 加 timeout（推翻已定分工）、每條 waits 自動套期限、被砍的 act 自動重放、用格數當秒數、「多久沒進展」自動判失敗。

## 5. 要你拍板的

1. 工具預算放哪：**A** `_timeout_ms`（工具元素旁）／B `_meta.timeout_ms`（inst 會忽略、只有 agent 讀）／C 通用 inst 欄位。建議 A。
2. 工具預設幾秒：**A** 60／B 120／C 不限。建議 A。
3. 引擎連敗幾次停、停了怎麼恢復：**A** 3 次→加 `continue.json` 等人 touch／B 5 次／C 一直試。建議 A；恢復＝touch（不要新 input 就自動恢復，會被無關輸入重置）。
4. 整格硬上限誰管：**A** 外面的 run／kernel（等 kernel 落地）／B kernel 每 tick 查 elapsed／C agent 自己量（抓不到卡死）。建議 A，現在先不做。
5. `waits` 這輪加不加 `until`：**A** 不加／B 加可選 `until`、過期＝那條劃掉並記一則失敗給模型（不假裝到了）。建議 A。
