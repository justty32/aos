# 探針 namespace：Plan 9 式命名空間＋服務卡

← [probes](../README.md)｜出處：[astra 調查報告二 §14 實驗一](../../notes/research/2026-10-03-other-os-borrow.md)（§1.1、§1.3 的服務卡與請求格式）

全離線：服務是 mock（`mock_model.py`），不打任何模型。約 1.5 秒。

- **同一份任務程式**：`reviewer.py`，proj-a、proj-b 的 tasks.json 寫的是同一個 argv。它只認自己任務資料夾的 `mnt/mail`（收工作信）、`mnt/model`（模型服務）、`mnt/context`（checkpoint、結果、流水），可選 `mnt/model-prev`（舊服務，只收尾、不送新件）。
- **服務**：`services/model-a`、`model-a2`、`model-b`（介面 `llm-submit.v1`）、`model-x`（`llm-submit.v2`），各是一個 node，tick 起的 keep 任務。每次起來 `instance_epoch` +1，寫服務卡 `clients/reviewer/service.json`。它讀 `requests/`、寫 `receipts/`。副作用記在 node 的 `executed.jsonl`，不跟著程序一起丟；重起後先照這份帳補回條。
- reviewer 先把請求記進 `context/checkpoint.json` 再送件。重起後在途的請求**不重送**：只有請求檔不見時，才補寫同一個 request_id。送去的服務現在看不到（掛載換了）就記成 unknown，status 寫得出原因。

## 步驟與結果（19 個 check 全綠；4 份並行各跑一次也全綠）

| 步 | 做法 | 結果 |
|---|---|---|
| 1 | A 兩件、B 六件 | 都經 `mnt/model` 拿到結果，歸到各自的 context |
| 2 | model-a 執行完 a-job3、寫回條前卡住，探針用 pid.json 的 pgid SIGKILL；卡住期間 a-job4 在舊 epoch 送出 | keep 約 50 ms 重起，epoch 從 model-a-1 換成 model-a-2。a-job3 照 executed 帳補回條（`recovered`），沒有第二次副作用；a-job4 由新 epoch 執行一次。reviewer 每個 request_id 只送一次 |
| 3 | model-a 停著不處理（hold）時 a-job5 在途；改 proj-a 的 tasks.json，`model` → model-a2，再 `restart` `"reload": true` | 回條 ok，`diff` 列出 mounts 舊→新。新 reviewer 讀到舊 checkpoint，看不到 model-a，把 a-job5 報成 unknown，沒有重送到 model-a2；新工作 a-job6 走 model-a2 |
| 4 | 再 reload 一次，多掛 `model-prev` → model-a，放開 hold | a-job5 經 `mnt/model-prev` 收尾，全空間只執行一次 |
| 5 | mounts 換到 model-x（v2） | reviewer 寫可讀的拒絕（「服務介面是 'llm-submit.v2'，我只會 llm-submit.v1；不送件」），一件都沒送。另外直接丟一個 v0 請求給 model-b：回條是 `rejected`，說得出哪裡不合，沒執行 |
| 6 | 總核對 | 各服務的 executed 帳只有自己客戶的工作；全空間每個 request_id 只執行一次；proj-a、proj-b 一共跑了 5 個 reviewer 任務（A 換了四代），都是同一支程式。寫入紀錄（`AOS7_AUDIT`）：10 個任務、約 480 筆寫入，0 筆超出 node 與掛載點 |

報告 §14 第 4 步「同名 `lint.json` 來源衝突、namespace manifest」沒做（使用者這次給的步驟沒列）。

## 盲讀清單（不做 LLM 盲讀，只記回答要讀哪些檔）

路徑相對空間根，探針會檢查這些檔都在。五題總共 8 個檔、約 4.3 KB：

| 題 | 要讀的檔 |
|---|---|
| 在哪送件 | `services/model-a2/clients/reviewer/service.json`（`submit`、`receipt`） |
| 誰付錢 | 同上（`charging: caller_context`）＋請求檔的 `charge_context` |
| 是否已完成 | `…/receipts/<request_id>.json` 的 `state`（`settled`／`rejected`） |
| 故障後能否重送 | 服務卡的 `dedup`、`instance_epoch`；`proj-a/context/checkpoint.json`（在途）；回條的 `recovered`、`executed_epoch` |
| 現在接的是哪個服務（原題「哪份工具生效」；union 沒做，改問這個） | 現任 reviewer 的 `birth.json` `mounts`；reload 的 `ctl-done.json` `result.diff` |

任務只要讀 `mnt/` 底下三四個檔就答得出來，不必翻整棵 `.aos`。

## 逼出的 daemon／tick 需求

- **首次裝配、服務重起、換 epoch、整份換掛載：現有基底足夠**。用的是 keep、mounts、`restart reload`（回條帶 diff）、pid.json。
- **N-78（對應報告 E-03，可以）活任務換服務時，舊目標上的在途請求**：reload 換掉整份 mounts，就是「重起時換一版命名空間」。舊服務上還沒回的請求，新任務就看不到了。現在的收尾辦法是 kernel 自己約定多掛一個 `model-prev`。做得到，但有兩個代價：
  - 何時能拿掉 `model-prev`，只有讀任務的 checkpoint 才知道。
  - 拿掉要再 reload（kill）一次，因為 spec 寫明「卸掛不做」。

  本探針用了兩次 reload、4 個控制步。tick 不知道「這個掛載點上還有在途請求」。
