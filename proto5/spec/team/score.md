← [team](README.md)｜評分表：[axes.md §4](../../notes/2026-09-24-tool-era/axes.md#4-評分表怎麼量幾分)

# 六軸彙整：`aos-team score`

把六軸表（axes.md §4 的**團隊欄**）能自動量的部分填好。**只讀**：不叫模型、不寫任何檔。
程式：[`lib/aos_team_score.py`](../../lib/aos_team_score.py)。第一波第 5 隊（收尾隊），2026-09-24 第 1 版。

```
aos-team score [--task t-0001] [--runs FILE] [--json] [--target 團隊資料夾]
```

## 範圍

- 沒給 `--task`：整支團隊，從頭到現在。事件與用量**全部**算。
- 給了：那張單加它的審查子單（`t-0001.r1`、`.r2`…）。事件、用量、信**只算時間窗裡的**：起點到那張單結束；還沒結束＝到現在。
  時間窗只看時間，**同一段時間別的單的事件也會算進來**（紀錄裡沒寫「這一批是為哪張單」）；要乾淨的數字就一次只跑一件事。

## 讀哪些檔

| 檔 | 拿來算 |
|---|---|
| 名冊 `team.json` | 成員名單、誰是領隊（`template: lead`）。讀不到或壞了＝退 1 |
| 每個成員家的 `log/events.jsonl`（連輪換舊檔 `events.1.jsonl`…，[events.md](../agent/events.md)） | think 次數、等模型、跑工具；照 `ev`＋`id` 去重（`id` 是 null 的不去重） |
| 每個成員家的 `log/usage.jsonl`（連舊檔） | token（`usage.total_tokens`）；一行一次 HTTP，不去重 |
| `team/post/sent/*.json`（[post.md](post.md)） | 人的信與申請的時間（起點）、信件數、退件數 |
| `team/tasks/*.json`（[tasks.md](tasks.md)） | 狀態、rev、attempt、history（終點與時間怎麼花）、驗收結果 |

- 被 `aos-team rm` 拿掉的成員（不在名冊）不算。
- 壞掉的行（不是 JSON、不是物件、`at` 讀不懂）與讀不到的檔：**跳過**，最後印「跳過 N 行、M 個檔」（`--json` 在 `skipped`）。不會 Traceback。

## 六軸

分數 1～5，**不加總**。量不到＝`null`（表上印 `—`）。

| 軸 | 量什麼 | 分數 |
|---|---|---|
| **L** LLM 參與 | `think_end` 事件數（**含失敗的**），按成員分列、領隊標出來 | 0～1→5、2～5→4、6～15→3、16～40→2、>40→1。「模型做的步數」這版不算（`model_steps: null`） |
| **S** 穩定 | 沒給 `--runs`：只看這次成不成（單子 done＝成；failed／cancelled＝沒成；其他＝還沒結束）。整支團隊＝所有頂層單都 done 才算成、有一張 failed／cancelled 就算沒成 | **跑不到 10 次不給分**，只寫「x/y 次過」。給 `--runs` 且 ≥ 10 筆：全過→4（5 分要崩潰恢復測試，團隊層這裡不給）、≥80%→3、≥50%→2、其他→1 |
| **R** 資源 | token 總量，按成員分列。端點沒回用量的那幾次另外數（`no_usage`），不算進總量 | <20k→5、<60k→4、<150k→3、<400k→2、其他→1。有 think 卻一行用量都沒有＝`null`。cpu 秒、記憶體寫 `null`（另用 `/usr/bin/time -v` 量），「三個數取最低」時不算量不到的 |
| **F** 快 | 牆上時間＝起點到終點（下兩節） | <1 分→5、<3→4、<10→3、<30→2、其他→1。沒終點（還沒結束）＝`null` |
| **H** 人易懂 | — | 留空，印「給人填」 |
| **B** 邊界 | — | 同上 |

### 起點

axes.md 說團隊的快從「人 `ask` 那一刻」算，不從收件封存檔名算。這版照資料這樣找：

1. 單子是**人開的**（`opened_by: human`：門房命中 `handoff`、人寄的開單申請）＝那份申請的投遞紀錄（`kind: request`、`id` 等於單子的 `request`）的 `at`。
2. 單子是**領隊開的**＝人寄給這位領隊的 `REQUEST` 信（投遞紀錄 `from: human`）裡，落在「這位領隊**上一張頂層單**開單之後、這張開單之前」的**最後一封**的 `at`。門房沒命中時，人那句話就是這樣一封信（[route.md](route.md)）。
   紀錄裡沒有「這張單是因為哪封信開的」，所以這是推定；那段時間人寄了好幾封，取最後一封（最可能是觸發開單的那句）。
3. 都找不到＝單子的 `created_at`（沒有就用 history 的 `opened`）。
4. 沒給 `--task`：最早一封人信與最早開單，取早的。

輸出的 `start_from` 寫用了哪一種。

### 終點

單子進到 done／failed／cancelled 的那筆 history 的 `at`（被 `reassign` 拉回來又結束的，取最後一次）。
沒給 `--task`：所有頂層單（沒有 `parent`）都結束了才有終點＝最晚結束的那一張；有一張沒結束＝沒終點。

### 時間花在哪

各自加總，單位秒；**會重疊**（兩個成員同時想、驗收時別的單在跑），所以加起來可以超過牆上時間。

| 鍵 | 算法 |
|---|---|
| `model_s` 等模型 | `think_end` 的 `ms` 加總（沒記 `ms` 的次數在 `think_ms_missing`） |
| `tools_s` 跑工具 | `act_end` 每個 `calls[].ms` 加總（沒送出去的 `ms: null` 不算） |
| `pickup_s` 等收件 | 範圍裡每張單停在 `sent`（派工信投進 input、還沒被收走）的時間 |
| `verify_s` 等驗收 | 停在 `verifying` 的時間 |
| `human_s` 等人 | 停在 `waiting_user` 的時間 |
| `other_s` 排隊與郵差 | 牆上時間減掉上面五個，不到 0 算 0；沒牆上時間＝`null` |

停在某狀態的一段＝history 進到那個狀態，到下一筆「狀態換了」的 history；還停著＝算到終點（沒終點不算）。

## 另外印的

- **單子**：一張一行：單號、狀態、負責人、rev、第幾/最多幾次、Done when 幾條、最後一次驗收＋最後一次審查共驗了幾條、過幾條（驗收結果看 `verify[-1].results`，審查看 `review[-1].items`；每條 `pass`，沒有就看 `result == "pass"`）。
- **信**：時間窗裡的信（投遞紀錄 `kind: letter`，看 `at`，沒有就 `recorded_at`），按寄件人數；退件另數。郵差自己生的信寄件人是 `post`。例外：郵差寄的終局通知（`from: post`、`DONE`／`FAILED`、回這張單或它的子單）常記在單子結束之後一點點，一律算進來。

## `--runs FILE`

給穩定軸用：同一個驗收例子從同一個初始狀態跑了好幾次，每次的成敗。兩種寫法都收：

```json
[{"ok": true, "note": "第 1 次"}, {"ok": false}, true]
```

或一行一筆（jsonl）。每筆是物件（看 `ok`，其他鍵不看）或直接 `true`／`false`。`ok` 不是布林、行不是 JSON＝跳過並計入「跳過 N 行」。檔不在＝`NotFound` 退 1。

## 人看的輸出

第一行一句話總結（範圍、成不成、問模型幾次、token、牆上時間），接著六軸表（軸｜分｜依據），再來「時間花在哪」、單子、信、跳過幾行。

## `--json`

印一個物件，鍵固定：

```text
{"scope": "task"|"team", "task": 單號或 null, "summary": 那一句話,
 "axes": {
   "L": {"score", "think", "failed", "by_member": {名: 次數}, "model_steps": null, "why"},
   "S": {"score", "this_run": "ok"|"fail"|"unfinished"|"none", "runs": {"ok", "total"} 或 null, "why"},
   "R": {"score", "tokens", "by_member": {名: token}, "calls", "no_usage", "cpu_s": null, "mem_mb": null, "why"},
   "F": {"score", "wall_s", "start", "end", "start_from", "think_ms_missing",
         "parts": {"model_s", "tools_s", "pickup_s", "verify_s", "human_s", "other_s"}, "why"},
   "H": {"score": null, "why": "給人填"}, "B": {"score": null, "why": "給人填"}},
 "tasks": [{"id", "status", "assignee", "rev", "attempt", "max_attempts",
            "done_when": {"total", "checked", "passed"}, "opened_at", "ended_at"}],
 "letters": {"total", "by_sender": {寄件人: 封數}, "rejected"},
 "skipped": {"lines", "files"}}
```

時間是 ISO 8601（帶時區）；`why` 是給人看的白話。

## 退出碼

0＝印出來了（資料再少也是 0）；1＝團隊資料夾不在（`NotFound`）、名冊壞、`--task` 那張單不在、`--runs` 的檔讀不到，stderr 一行 `aos-team: <代號>: <白話>`；2＝用法錯（例如 `--task` 不像 `t-0001`）。
