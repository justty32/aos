# step 包 spec（第一版）

← [step 包](README.md)｜[核心 spec](../../spec.md)

寫的是規則；理由在[第六輪綜合](../../../proto7/notes/thinking/2026-10-04-r6-synthesis.md) §3 與 [astra 原報告](../../../proto7/notes/thinking/2026-10-04-r6-astra.md) §六。路徑未特別說明時都相對 node（任務的 cwd），全部在槽外。

## 1. 工作資料夾

`<node>/jobs/<job>/`（直譯器 argv 給的路徑；名字不限，下稱 `${job}`）：

| 檔 | 誰寫 | 內容 |
|---|---|---|
| `steps.json` | 人／作者 | 步驟表（§2）。工作進行中不改 |
| `frame.json` | 直譯器（人手指令經同一把 `frame.json.lock`） | 框架（§3） |
| `results/<step>/<attempt>.json` | 包裝程式 | 結果檔（§4），到 `close` 才清 |
| `error.json` | 直譯器 | 最近一筆錯誤 `{"kind","where","why","at","round"}`，覆寫 |
| `out/`、其他 | 子工作 | 產物；本包不刪 |

## 2. 步驟表

```json
{"job": "csv", "start": "convert", "options": {"wake": false, "restart_on_end": false},
 "steps": {
  "convert": {"run": ["python3", "${job}/convert.py", "${job}/data.csv", "${out}/data.json", "${request}"],
              "finite": true, "idempotent": true, "expect": ["${out}/data.json"], "ok": "stats", "fail": "failed"},
  "stats":   {"run": ["python3", "${job}/stats.py", "${out}/data.json", "${req:convert}", "${out}/report.json"],
              "finite": true, "idempotent": true, "ok": "done"},
  "done":    {"end": "ok"},
  "failed":  {"end": "failed"}}}
```

- 步名、`job`：英數與 `_`，最多 32 字。每步恰好一個種類鍵：
  - **`run`**（字串陣列）：派一個子工作。欄：`ok`（必填）、`fail`、`finite`、`idempotent`（預設 false）、`patience`、`on_timeout`、`on_unknown`、`wake`、`receipt`（條件）、`expect`（產物路徑陣列）。
  - **`wait`**（條件）：每回合看一次，成立走 `then`。欄：`patience`、`on_timeout`（`unknown`／`fail`）、`fail`。
  - **`count`**（非負整數 N）：框架裡這步的計數 +1，≤N 走 `then`，否則走 `exhausted`。
  - **`end`**（字串）：工作結束，狀態寫進框架。
- **條件**只准四種：`{"exists": 路徑}`、`{"glob": 樣式}`（至少一個符合）、`{"result.ok": 步名}`（該步最近採用的結果 `ok`）、`{"num": 路徑, "key": "a.b", "op": "<|<=|==|!=|>=|>", "value": 數字}`（JSON 檔裡一個數字比一次）。不開運算式。
- **展開**（只在 argv、`expect`、條件路徑裡）：`${job}`、`${out}`＝`${job}/out`、`${step}`、`${request}`、`${attempt}`、`${result}`（這次嘗試的結果檔）、`${req:<步>}`（該步最近採用結果的 request id）。展開不了＝那一步停（`halt`）。
- **選項**（`options`）：`wake`（false）、`restart_on_end`（false）、`on_timeout`（`unknown`）、`on_unknown`（`stop`）。可在步內用同名欄逐步覆蓋的只有 `wake`（`run` 步）、`on_timeout`（`run`／`wait`）、`on_unknown`（`run`）；`restart_on_end` 是工作級，只能寫在 `options`。檢查器對**套預設後的有效值**查限制：全域 `on_timeout: kill` 時，每個 `wait` 步都要在步內改回 `unknown`／`fail`。
- 欄位型別：`start`、跳轉目標（`ok`／`fail`／`then`／`exhausted`）、`result.ok` 的步名、`num` 的 `op` 都要是字串；不對的話檢查器只報型別錯、不做圖檢查。

## 3. 框架與識別

```json
{"v": 1, "job": "csv", "inst": "9f3a1c2b", "table": "<steps.json sha1 前 12>", "pc": "stats", "phase": "running",
 "counts": {}, "visits": {"convert": 1, "stats": 1}, "accepted": {"convert": {"request", "attempt", "ok", "run"}},
 "pending": {"step": "stats", "request": "9f3a1c2b-stats-1", "attempt": "9f3a1c2b-stats-1-a1", "n": 1,
             "task": "step-csv-stats", "result": "jobs/csv/results/stats/9f3a1c2b-stats-1-a1.json",
             "state": "intent|queued", "intent_round": 7, "since": 7, "resends": 0},
 "tries": {"9f3a1c2b-convert-1": 1, "9f3a1c2b-stats-1": 1}, "since": 7,
 "halt": null, "end": null, "seen": 8, "tock": 8, "rev": 12, "at": "..."}
```

- `tries`：每個 request 派過幾個 attempt；`since`：走到現在這步的回合（`wait` 的耐性起點；新工作＝建框架那圈的回合，那時回合不知道就在第一次知道時補上）；`seen`／`tock`：最近一圈看到的本地回合與叫醒它的 tock（啟動那圈 `tock` 是 null）；`rev`：寫入次數，人手指令改過框架時直譯器那一圈放棄寫入、下一圈重讀。

- **識別**：`job`（表上的名）；`inst`（這一次工作，隨機）；`step_id`；`request`＝`<inst>-<step>-<第幾次走到這步>`，跨重送保持；`attempt`＝`<request>-a<k>`，每次派工一個；核心的 `slot#run` 由包裝程式從環境取，寫進結果，不預猜。
- 子工作 once 項：`name`＝`step-<job>-<step>`（同一步固定一個槽），`x.step`＝`{job, inst, step, request, attempt}`（`x` 每包一個 key）。
- `phase`：`running`／`halted`／`ended`。`halt`＝`{"kind","why","round","at"}`，kind 為 `unknown`／`timeout`／`failed`／`version`／`expand`。
- 每次框架寫入是一個完整的轉移（拿 `frame.json.lock` 讀—改—寫，原子 rename）；推進 `pc` 與更新計數在同一次寫入。

## 4. 結果檔

包裝程式 `aos7-step-result --result P --job J --inst I --step S --request R --attempt A [--expect 路徑]... -- 命令...`：

```json
{"job","inst","step","request","attempt","run": "step-csv-convert#12","slot","code": 0,"ok": true,
 "artifacts": {"jobs/csv/out/data.json": "<sha256>"},"missing": [],"at"}
```

- `ok`＝退出碼 0 且 `expect` 的產物都在。先跑完命令、算完雜湊，最後一個動作才 rename 結果檔；P 已存在＝不覆寫、退出碼 2。
- 被 kill（整個程序群組）＝沒有結果檔。結果檔內容的識別欄和框架的 `pending` 不符＝當壞結果（`halt` unknown）。

## 5. 直譯器每一圈（啟動時一次，之後每個 tock 一次）

1. 讀 `steps.json`（讀不到、壞、檢查器有錯→記 `error.json`，不動）。讀 `frame.json`：不存在＝新工作（新 `inst`、`pc`＝`start`）；讀不到、壞、缺欄＝**不前進、記錯、等人**，不從結果檔反推。`table` 跟現在的表不同＝`halt` version。
2. `phase: ended`：`restart_on_end` 時先 close（清 `results/`）再開新 `inst`；否則立刻退出 0。
3. `halted`：只更新 `seen`，不前進（遲到的結果照樣留在 `results/`，`resume` 後採用）。
4. 照 `pc` 前進，一圈內可走多步，但**最多登記一個 once**：
   - `run` 沒有 `pending`：有 `receipt` 且成立→當 ok、不派。否則**先存意圖**（`pending.state=intent`、`intent_round`＝現在的回合），再拿表鎖加 once 項（表上已有同 attempt 的不加），再寫 `state=queued`。表鎖拿不到、表讀不到或壞＝**拒寫**：撤掉 `pending`、記 `error.json`，下一圈重來（attempt 號照加）。`wake: true` 時再寫 daemon 的 wake。
   - `run` 有 `pending`：照順序看證據——結果檔（識別相符）→採用、推進；表上有同 attempt 項→還沒起，等；槽 `birth.json` 的 `x.step.attempt` 相符→有 `exit.json` 就重讀一次結果檔，仍沒有＝**unknown**；沒結束就等。都沒有：`intent` 且現在回合 ≤ `intent_round`+1（once 槽最早在加項後第三個 tock 才刪）＝確定沒加上→補加；其餘＝**unknown**。
     - 「第三個 tock」不是核心直接承諾的數字，是本包從核心兩條保證推出的：(a) once 項從表上拿掉時，該槽 `birth.json` 已寫好（[核心 spec](../../spec.md) §4.4）；(b) 已結束的槽最早在**報結束的下一個 tock** 才刪（核心 spec §5.1）。所以加項後到第三個 tock 之前，「表上有」或「槽裡有」至少一邊看得到這個 attempt。
   - `wait`：條件成立走 `then`；不成立看耐性。`count`、`end` 見 §2。
5. **耐性**：`patience` 是本 node 的回合數，起點 `since` 寫在框架；`現在回合 − since > patience` 才算到期。pause 時沒有回合，耐性不走。到期照 `on_timeout`：`unknown`（停，`halt.kind=timeout`）、`fail`（走 `fail`）、`kill`（只給 `run`：對槽寫帶 run 的 kill，再停住——`halt.kind=timeout`，處理同 unknown，等人 `resume`；不抹掉之後到的結果）。
6. **unknown**：`on_unknown: stop`（預設）＝`halt` unknown，等人。`resend` 只准冪等步（檢查器與執行時都擋），同一 request 新 attempt，最多一次，之後仍 unknown 就停。有 `receipt` 的先查，成立就當 ok。
7. 結果 `ok: false`：走 `fail`；沒寫 `fail`＝`halt` failed。
8. 每圈結束寫 `seen`＝這圈看到的回合。

## 6. 檢查器（`aos7-step check`）

回 `[{"level": "error"|"warn", "step", "rule", "why"}]`，有 error 退出碼 1。直譯器啟動時也跑，有 error 不開工。

- **結構**：先驗欄位型別（§2，不對就只報型別、不做圖檢查，不拋例外）；`start`／所有跳轉目標存在；每步恰一個種類鍵；不認得的欄；argv、條件、名字格式；`on_timeout: kill` 只給 `run`（查套全域預設後的有效值）；`on_timeout: fail` 要有 `fail`；走不到的步（warn）。
- **R1 等結束只等有限工作**：`run` 步要 `finite: true` 或有 `patience`。
- **R2 重試要冪等或先查回條**：`run` 步在跳轉圈裡（自己走得回自己），或 `on_unknown: resend`，就要 `idempotent: true`；圈裡的步改用 `receipt` 也可以（`resend` 不行）。
- **R3 時間值標線**：v1 只有本地回合。`patience` 要是非負整數（＝本 node 回合）；寫成秒、毫秒、期限、`{"clock": …}` 的一律錯。

## 7. 明確不管（誤用，不處理）

人手改 `frame.json`／`results/`（例如手改框架刪掉 `pc`，直譯器會 KeyError——誤用，不處理）、工作進行中改 `steps.json`（偵測到就停）、兩個直譯器跑同一個工作資料夾、同一個 node 上兩個工作用同一個 `job` 名（子工作槽 `step-<job>-<step>` 會撞）、子工作自己改程序群組逃過 kill、不拿表鎖改 tasks.json。
