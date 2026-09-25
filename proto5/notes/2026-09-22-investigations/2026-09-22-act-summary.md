# `act` 怎麼跑工具：精簡總結與待拍板（2026-09-22）

astra 唯讀調查了 proto2／3／4-2～4-7 與 proto5 現況（原報告 339 行：`2026-09-22-act-report-astra.md`）。
這份是我的精簡版與建議；決策由使用者做。跟 [逾時總結](2026-09-22-timeout-summary.md) 一起看。

## 1. 先把三件事拆開

「丟給另一個 cpu／開 thread／async」其實是三個獨立的問題，別混成一題：

| 問題 | 選項 |
|---|---|
| 工具**在哪裡跑** | agent 自己開子進程（現狀）／另一顆 cpu 的 worker |
| agent **要不要占著這顆 cpu 等** | 留在這次呼叫裡等（現狀）／存檔、退 101、下次再接 |
| 模型**收到什麼** | 真正的工具結果（`tool` 訊息）／先收一張「已接單」收據、完成後另來一則 `user` |

OpenAI 的 tool_calls 契約只要求「每個 call 都要有一則同 id 的 `tool` 訊息接在後面」，**沒有要求同步跑**；
結果晚點補齊也合法。所以規範 §5 的 async（收據＋結果走 `input`）和「丟給 tool cpu、結果仍當 tool 訊息」是**兩種不同的東西**，可以共用同一個背景執行器。

## 2. 歷代事實（一行一代）

- **proto2**：普通工具同步在 `act` 串行跑完；長工作走 `jobs.run_long`＝立刻回收據當 tool 訊息、跑完 hook 注入一則 user（就是 §5 的 async）；`think`／`branch` 也是收據制。教訓：丟出去之後「結果到→叫醒→繼續」那條路要完整，光背景跑只解一半。
- **proto3 系**：記憶體原型，LLM 用 request id＋wait-for，`act` 沒有真工具。
- **proto4-2／4-3**：cpu＝一支常駐 `aos-run`，一次只等一個 child；quantum 是「完成幾次」不是秒數；**kernel 沒用 daemon 的 running 欄位擋換人，同一行程有機會被兩顆 cpu 重疊執行**（靜態推論）——這跟 agent「同一資料夾不要同時跑兩份」的前提衝突，kernel 規範要處理。
- **proto4-5**：llm 排程器派**背景 worker 子進程**、自己馬上返回，所以 kernel tick 短；不是 module 機制自動非阻塞。
- **proto4-6**：`wait_for` 宣告等檔、退 101、檔到了同一次呼叫繼續下一格；沒有等待逾時。
- **proto4-7**：`act` 同步串行、每工具 60 秒、輸出截 8000 字；LLM 才有 ask／wait 分格。
- **proto5 現在**：`act` 同步串行、不限時、不截輸出；自癒只救「記憶寫了、state 沒寫」，救不了「工具做了、記憶沒寫」（會整批重跑，副作用重複）。

## 3. 五個選項一句話

| 選項 | 一句話 | 我的看法 |
|---|---|---|
| **A** 現狀：一格同步跑完 | 最少狀態；整批時間相加、占住 cpu、任一支不回就整批卡 | **預設留著**，加每工具逾時（逾時總結第 1 題） |
| **B** 丟給 tool cpu、結果仍當 tool 訊息 | `act` 寫請求、往 `waits` 加結果檔、退 101；門開了照順序接 tool 訊息→think | **要做的那個**，跟 llm cpu 同一套「請求檔／結果檔／waits」 |
| **C** agent 內 thread／pool | 只能縮短「整批相加」變「最慢那支」，**不會讓出 cpu**（aos-run 還在等這次 agent 退出）；要跨格活就變成 B | **不做** |
| **D** async 工具：收據＋結果走 `input` | 模型可以先回話；改變對話語意、要 job id、`input` 只在 idle 收會延後 | 之後給明確標成 async 的長工作（服務、跑很久的 job） |
| **E** 工具檔上標籤混用 | 每個工具選 A／B／D | 最終形態，但第一版只要 A＋B 兩種 |

**阻塞是不是常態**：歷代普通工具就是同步等，這是常態；不是常態的是「長工作占住負責排程的那一格」——proto2 的 run_long、4-5 的 llm worker 都是把長的搬出去。沒有任何一代定過「一格最多阻塞幾毫秒」。

## 4. 我的建議（最精簡）

1. **`act` 預設仍是 A**：短工具（ls、cat、算數）走同步，加每工具 60 秒逾時。
2. **B 跟 llm cpu 一起設計成同一個協議**：「提交一個工作、稍後拿結果」——請求檔（id＋payload）、`queued/running/done`、結果檔；llm cpu 的 payload 是 engine＋body、tool cpu 的是 inst＋arguments＋agent 資料夾；`waits` 等結果檔。**`think` 送 llm 請求跟 `act` 送工具請求是同一個動作**，只是 payload 不同、收回時一個接 assistant、一個接 tool。
3. **aos-agent 要能自己往 `waits` 加條目**（think 送出、act 送出、連敗暫停都要）——推翻現在「只劃不加」那句。
4. **同一則 assistant 的多個 call 串行**；並行等有需要再說。
5. **worker 死了、結果不明**：回一則「結果不明」的 tool 訊息給模型，不自動重試（副作用可能已發生）。
6. 工具檔怎麼標：`_run: "sync"`（預設）｜`"cpu"`；`"async"` 之後再加。`_` 開頭本來就不會送給模型。
7. 送去 tool cpu 的是**解好的 inst**（在 agent 這邊用 `load_obj` 解完、`$env`／路徑以 agent 為中心），不是原始 `_meta`，不然 worker 會讀到自己的環境。
8. kernel 規範要保證**同一個行程不會同時在兩顆 cpu 上跑**（舊 kernel 有重疊窗口）。

## 5. 要你拍板的

1. 慢工具沒回來時模型等不等：**A** 等真結果（B 方案）／B 先收據（D 方案）。建議 A 為主，D 留給明確標 async 的。
2. 預設模式：**A** 同步、工具檔標 `_run: "cpu"` 才丟出去／B 一律丟 tool cpu。建議 A。
3. tool cpu 與 llm cpu：**A** 共用同一套請求／結果／waits 協議（payload 不同）／B 各做各的。建議 A。
4. aos-agent 可不可以自己加 `waits`：**A** 可以／B 不行（那 B 方案就得另存 pending）。建議 A。
5. 多個 call：**A** 串行／B 並行。建議 A。
6. 結果不明：**A** 回「結果不明」tool 訊息、不重試／B 自動重試。建議 A。
