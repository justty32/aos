← [把「exec 只當純 CPU、其餘全外放成 argv」真的做出來，去打研討會的三個主張](../argv-split.md)（分檔 27/29）｜所在：下一輪的資料包 ＞ 2. repo 裡已經有答案的｜[上一份](26-給-p4分母丙的可交付門檻租約影.md)｜[下一份](28-3-兄弟專案裡可以抄的.md)

#### 給「deliver 的規格形式（argv 還是 stdin）」

- **這題已經被打了兩輪，有結論**：`wf/workflows/hackathon/records/deliver-contract.md`〈第 1 輪紀錄／4. 題目那三個數字／數字一：四種 CLI 的 caller temp／歧義／必填參數〉（四案 (a)–(d) 的 12 格對照表）與〈第 2 輪評分與意見／如果現在就得拍板〉——選 **(d') `aos deliver WORLD (-f FILE | -)`**，契約是先完整驗證 CLI grammar 才碰 stdin、相對 FILE 以 caller cwd 解、一次成功呼叫使整批恰好成為一個 ready delivery。第一版**不公開冪等 key**。
- **另一份更早的介面草稿**：`wf/workflows/experiments/t5-agent-loop/subcommand-specs.md`〈`aos deliver [WORLD] [-f FILE|-]`〉。
- **規格側那條「沒有實作」的自陳**：`docs/aos-folder.md`〈十二／仍然開著的〉——「**投遞那一步沒有實作。** ……整套協定的安全性就靠這一步，現在它是口頭約定」；階段側在 `docs/roadmap/stages.md`〈T2 — 取件與投遞協定〉標題後面那句「**已完成，但投遞那一步只有協定沒有 API**」。
- **四位都自己補了一次這一步，已被記成一條**：`wf/workflows/hackathon/records/agent-loop.md`〈規格級的發現／十一、「投遞那一步沒有實作」這條開著的規格項，四位都自己補了一次〉。

#### 給「這場的名詞與前人系統」

- `wf/workflows/workshop/BACKGROUND.md`〈分檔導航〉與〈名詞索引〉是入口。每個詞的格式固定是「白話／嚴格／**在 aos 裡具體是什麼**／為什麼會冒出這個詞」，第三塊會直接寫「已存在／提案，目前不存在／不是 aos 的公開名詞」。
- 這一場用得到的四份：`background/execution-and-turns/turn-boundary.md`（world、`.runi`、彙整／取件／釋放、孤兒與 `setpgid`、running marker 與租約）、`background/delivery-contract.md`（Publish、Deliver、correlation ID、receipt、no-replace／`renameat2`、consumer acknowledgment、TOCTOU）、`background/reliability.md`（idempotency key、ledger、`unknown`、two-phase commit、**visibility atomicity 與 power-loss durability**、terminal projection）、`background/process-control.md`（control plane、capability、proc-table、join／barrier、handle 與 generation）。
- 短路與 `"needs"`、tick、cursor 三個詞在 `background/execution-and-turns/wake-and-progress.md`。
- **研討會本身的三好六壞與 15 條轉交提案原文**：`wf/workflows/workshop/records/exec-as-pure-cpu.md`〈這個體系的好與壞〉與〈轉交提案〉（分〈一、要改 `docs/aos-folder.md` 的〉／〈二、碰到已知未拍板選擇的〉／〈三、不改規格、但要在動手前先有的〉三段）。〈這場沒有誰在場〉那一節記了「**沒有任何一位主張整包外放，也沒有任何一位主張什麼都不拆**，這個共識強得可疑」。

#### 給「找程式碼要看哪裡」

- `wf/workflows/common/code-map/inst.md`〈逐檔表格在哪：core/inst 分冊的四份〉→ `code-map/inst/library.md`（`include/aos/` 公開標頭與 inst／format／resolve／handoff／exec 五層逐檔表，含改 exec 的注意事項）、`code-map/inst/cli.md`、`code-map/inst/capi.md`、`code-map/inst/tests.md`。
- 建置與相依的已知坑在 `wf/workflows/common/gotchas.md`〈建置與相依〉（`PRIVATE` 相依會變成使用者義務、漏標 `AOS_API` 只在連結期爆等）。

---
