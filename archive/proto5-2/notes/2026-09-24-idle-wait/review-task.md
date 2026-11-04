# astra 唯讀審查任務書：等模型的 agent 不空轉（提案）

你是唯讀審查者。**不要改任何檔**，只輸出報告（繁體中文、白話）。

## 要審的東西

- `proto5-2/notes/2026-09-24-idle-wait/README.md`（提案本體）
- `proto5-2/notes/2026-09-24-idle-wait/measure.md`（實驗數字與換算）
- `proto5-2/notes/2026-09-24-idle-wait/exp/*.py`（實驗腳本）

## 對照的規範與程式

- proto5 kernel：`proto5/spec/kernel/tick.md`（一格的步驟順序）、`echo.md`（回音判定）、`syscall.md`、`ledger.md`；
  程式 `proto5/lib/aos_kernel_engine.py`（`collect`／`dispatch`／`step`）、`aos_kernel_ledger.py`（`save`、`flush_outboxes`、`_add`）、`aos_kernel_info.py`（`classify`）。
- proto5 agent：`proto5/spec/aos-agent/tick.md`、`collect.md`、`send.md`、`register.md`、`gate.md`、`idle.md`；程式 `proto5/lib/aos_agent.py`、`aos_agent_batch.py`。
- proto5-2：`proto5-2/spec/kernel-tick.md`、`kernel-ledger.md`（`ready`／`delayed`、舊格規則）、`cpu-notify.md`、`scale.md`。

## 請特別看三件事

1. **漏喚醒的時序**（README §4）：方案 (b) 說「喚醒在出貨放好回音檔之後才生效＋`woken` 旗標」就不會漏。
   請照 proto5 kernel 一格的真實步驟順序（收單、收回音、派工、出貨、崩潰重跑）和 agent tick 的步驟（門、收回、ack、結清）逐一找反例：
   有沒有哪種交錯會讓 agent 停車後再也等不到喚醒（除了靠 `park_ms` 保底）？崩在任何兩步之間呢？`rm`／`stop` 後同名重 add 呢？act 批多個工具呢？
   agent 收回音、ack、清檔（sweep）的步驟會不會讓喚醒失效？proto5-2 的 `ready`／`delayed`＋舊格規則下同樣成立嗎？
2. **數字有沒有算錯**：measure.md 的表、第 E 節的公式與五列換算、README §1 的結論（「一次空轉＝帳本存三次」「56 ms」「一到兩分鐘」「14 顆核」等）。
   特別核對：proto5 kernel 每次收回音／出 ack／派工真的各存一次整份帳本嗎？once 行程（think 單）也各有幾次？實驗 B 的 CPU 歸屬方法（/proc cutime）有沒有漏算或重算？
3. **方案有沒有跟 proto5-2 池式打架**：(b) 的停車＝進 `delayed`、喚醒＝推新的一筆進 `ready` 靠舊格規則丟舊的，這樣寫行不行？
   跟 cpu-notify、巡檢、`recent` 有沒有衝突？(a) 的喚醒員投 `add --once` 會不會撞 agent 的 `AlreadyExists`、ack 誰負責？

其他看到的問題也歡迎（方案表有沒有對某方案不公平、漏了更簡單的做法、「kernel 估 20～30 行」合不合理）。

## 輸出格式

每條：編號、〔必修〕或〔建議〕、位置（檔:行）、現象、依據（規範或程式的檔:行）、建議改法。最後一段總評三五句。
