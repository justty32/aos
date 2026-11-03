← [把「exec 只當純 CPU、其餘全外放成 argv」真的做出來，去打研討會的三個主張](../argv-split.md)（分檔 27/29）｜所在：下一輪的資料包 ＞ 2. repo 裡已經有答案的｜[上一份](26-給-p4分母丙的可交付門檻租約影.md)｜[下一份](28-3-兄弟專案裡可以抄的.md)

#### 給「deliver 的規格形式（argv 還是 stdin）」

- 已有結論：`wf/workflows/hackathon/records/deliver-contract.md`〈第 1 輪紀錄／4. 題目那三個數字／數字一：四種 CLI 的 caller temp／歧義／必填參數〉與〈第 2 輪評分與意見／如果現在就得拍板〉——選 **(d') `aos deliver WORLD (-f FILE | -)`**：先完整驗證 CLI grammar 才碰 stdin、相對 FILE 以 caller cwd 解、一次成功呼叫使整批恰好成為一個 ready delivery；第一版不公開冪等 key。
- 介面草稿：`wf/workflows/experiments/t5-agent-loop/subcommand-specs.md`〈`aos deliver [WORLD] [-f FILE|-]`〉。
- 「沒有實作」的自陳：`docs/aos-folder.md`〈十二／仍然開著的〉「**投遞那一步沒有實作。** ……整套協定的安全性就靠這一步，現在它是口頭約定」；`docs/roadmap/stages.md`〈T2 — 取件與投遞協定〉「**已完成，但投遞那一步只有協定沒有 API**」。
- 四位都自己補過這一步：`wf/workflows/hackathon/records/agent-loop.md`〈規格級的發現／十一、「投遞那一步沒有實作」這條開著的規格項，四位都自己補了一次〉。

#### 給「這場的名詞與前人系統」

- 入口：`wf/workflows/workshop/BACKGROUND.md`〈分檔導航〉〈名詞索引〉（每詞第三塊寫「已存在／提案，目前不存在／不是 aos 的公開名詞」）。
- 這場用得到的：`background/execution-and-turns/turn-boundary.md`（world、`.runi`、彙整／取件／釋放、孤兒與 `setpgid`、running marker 與租約）、`background/delivery-contract.md`（Publish、Deliver、receipt、no-replace／`renameat2`、consumer acknowledgment、TOCTOU）、`background/reliability.md`（idempotency key、ledger、visibility atomicity 與 power-loss durability）、`background/process-control.md`（control plane、capability、proc-table）；短路與 `"needs"`、tick、cursor 在 `background/execution-and-turns/wake-and-progress.md`。
- 研討會的三好六壞與 15 條轉交提案原文：`wf/workflows/workshop/records/exec-as-pure-cpu.md`〈這個體系的好與壞〉〈轉交提案〉；〈這場沒有誰在場〉記了「**沒有任何一位主張整包外放，也沒有任何一位主張什麼都不拆**，這個共識強得可疑」。

#### 給「找程式碼要看哪裡」

- `wf/workflows/common/code-map/inst.md`〈逐檔表格在哪：core/inst 分冊的四份〉→ `code-map/inst/library.md`、`cli.md`、`capi.md`、`tests.md`。
- 建置與相依的坑：`wf/workflows/common/gotchas.md`〈建置與相依〉。
