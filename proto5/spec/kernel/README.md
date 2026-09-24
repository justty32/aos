← [spec 總導航](../README.md)

# kernel：排程一格一格跑

← [proto5 README](../../README.md)｜範式：[cpu.md](../cpu/README.md)｜跑一次：[aos-exec.md](../aos-exec/README.md)｜下層：[daemon](../daemon/README.md)

> 第 1 版，2026-09-23 定稿，2026-09-24 fix-r4 改命令列、fix-r5 改日常輸出、advice-r1 改 ls 的長相與 `--json`、check 的 `--agent` 搬到 `aos-agent check`；
> **2026-09-24 proto5-2 池式納入**：cpu 表改池表、帳本第 2 版、每格只碰有事的 cpu、跟 daemon 只講 `scale`、`cpu add／rm／ls`、ls 按池與 `--json` 第 2 版。
> **2026-09-24 one-boot**：kernel cpu、tick 鏈、開機交接拿掉，改由 daemon 替 kernel 開 tick、同時只准一格（`K/.tick.lock`）；帳本從 `K/state.json` 換成 `K/ledger.sqlite`（第 3 版）；boot 改成「寫帳本＋向 daemon 登記」；開機停機用 `aos up`／`aos down`；`ls --json` 第 3 版；新增 `aos-kernel proc`。
> 已實作（[`aos_kernel.py`](../../lib/aos_kernel.py)，入口 `aos-kernel`）。沿革在 [history.md](history.md)。

一句話：**kernel 替登記好的工作（行程）挑一顆空著的 cpu 派下去、收回執行結果、決定要不要再跑。**
它不是長命行程：每次只跑一格 `aos-kernel tick`，做完自己的事就退出。
一格由 daemon 開：時間到（`tick_ms`），或 `K/requests/` 來了新單，就開一格；**同時只准一格**（daemon 只開一格，kernel 自己再拿 `K/.tick.lock`）。
cpu 按**池**管：info 只寫「池 P 要幾顆、帶什麼環境」，kernel 把號碼整份宣告給 daemon，daemon 自己補、重拉、收。
工作與 syscall 走資料夾（往 cpu 的 `requests/` 放、從 `responses/` 收、放 `ack`），cpu 回完音往 kernel 家丟一張通知；
kernel 跟 daemon 講話也走 daemon 家的資料夾。**`K/ledger.sqlite` 是唯一的帳本**：派工跟出貨都是先記帳再動檔。

---

## 9. 已拍板的前提（使用者定的，不重問）

kernel 一格一格跑、每格做完就退（怎麼開一格見下面 one-boot 那段）；rm 正在跑的行程後同名 add 拒絕到它跑完；stop 分 stopping／stopped 兩段，在途與 once 的回音收完才停；
kind=aos 併進一般失敗、沒有獨立 aos 計數；兩個 kernel 共用 daemon 而池名撞了＝`NameTaken` 大聲失敗。

**2026-09-24 使用者定的池式六點**：(a) cpu 表改池表（池名、daemon 家、daemon 那邊的池名、要幾顆、envs；種類由池 envs 定）→ [§1.1](info.md)；
(b) 宣告式：kernel 只說「P 要 N 顆」，daemon 補、重拉（節流）、收；kernel 不記 pid、只看摘要 → [§3.1](pools.md)、[daemon §4](../daemon/loop.md)；
(c) daemon 按池管、可帶多池、指令全帶 `--pool`、孩子表不整份重寫、階梯批次 → [daemon](../daemon/README.md)；
(d) `cpu add／rm／ls` 就是改池數字、看池摘要，下一格生效不用 boot → [cli-cpu](cli-cpu.md)；
(e) `init --config` 只剩 kernel 參數＋池定義，cpu 可空 → [cli](cli.md)；
(f) 每格 O(有事的 cpu)：回音丟通知檔、派工不掃每顆 → [§3](tick.md)、[cpu §6.4](../cpu/notify.md)（帳本仍整份讀寫，[§11](scale.md)）。
同日九題（Q1～Q9）由調度者代定、使用者未反對，落點寫在各節（標「09-24 Qn」）。

**2026-09-24 P 審查（daemon-split-review）後使用者改的**（[審查報告](../../notes/2026-09-24-daemon-split-review/README.md)、[one-boot 報告](../../notes/2026-09-24-one-boot/README.md)）：
- 原本「kernel 可以是 exec（tick 鏈）：在 kernel cpu 上一格接一格」→ 改成「**daemon 定時或有新單時開一格 `aos-kernel tick`，同時只准一格**」。
  kernel cpu、kernel 池、開機交接都拿掉（[§3](tick.md)、[§7](no-overlap.md)、[daemon §10](../daemon/ticks.md)）。
- 原本「kernel 的家照 cpu 範式、帳本是 `state.json`」→ **只對帳本放寬**：帳本是 sqlite 檔 `K/ledger.sqlite`（[§1.2](ledger.md)）；
  `requests/`、`responses/`、`pools/`、cpu 的家都還是檔案。
- 開機、停機各一條指令：`aos up`、`aos down`（[daemon §11](../daemon/up.md)）；`aos-daemon`／`aos-kernel` 的子命令留給 debug。

## 8. 這份沒管的

適用範圍同範式 §8（同一台 POSIX 機器）。daemon 的 method 完整形狀、daemon 自己怎麼停（[daemon](../daemon/README.md)）。
agent 那份要接的：怎麼用 `add --once` 問模型／跑工具、輸入檔跟答案檔放哪、誰清——kernel 只交執行結果，不交內容。
`aos-llm call` 這支程式（[aos-llm.md](../aos-llm/README.md)）。

## 各節

原文裡「檔尾〈沿革〉」「檔尾〈實作補記〉」「見下」這類方位詞是拆檔前的位置，拆後照下表找對應檔。

| 檔 | 內容 |
|---|---|
| [terms.md](terms.md) | §0 名詞：行程、tick、tick 鎖、帳本、池、宣告、巡檢等白話解釋 |
| [home.md](home.md) | §1 家的目錄圖、池模板、cpu 的家怎麼建、家不刪 |
| [info.md](info.md) | §1.1 `info.json` 池表：欄位、成員編號 `count`＋`skip`、改了什麼時候生效、讀驗邊界 |
| [ledger.md](ledger.md) | §1.2 `K/ledger.sqlite` 帳本第 3 版：表、舊格判法；一格最多存三次（提交點 A／B／C；叫醒後再派多一次 D） |
| [ledger-keys.md](ledger-keys.md) | §1.2（續）帳本讀進記憶體後的例子與每個鍵的意思（one-boot 拆出） |
| [names.md](names.md) | §1.3 kernel 自己取的檔名 |
| [syscall.md](syscall.md) | §2 syscall：`K/requests/` 認的 method 與 params |
| [tick.md](tick.md) | §3 一格 tick 做什麼：拿鎖、收單與通知、收回音、池、派工、出貨的順序 |
| [pools.md](pools.md) | §3.1 池怎麼增減：幾組號碼、每格步驟、先做完再收、崩在哪都接得上 |
| [echo.md](echo.md) | §4 回音怎麼判 |
| [daemon-link.md](daemon-link.md) | §5 跟 daemon 講話：`scale` 與 `tick` 登記、偷看摘要、崩潰窗口、保證外 |
| [cli.md](cli.md) | §6 命令列：用法總表、`--target` 找家的順序、`init`、`proc`（查一筆行程，one-boot 新增） |
| [boot.md](boot.md) | §6（續）boot 五步與崩潰表、daemon 重開之後、每天開機（`aos up`）、停機 |
| [cli-cpu.md](cli-cpu.md) | §6（續）`cpu add／rm／ls` |
| [cli-ops.md](cli-ops.md) | §6（續）add、ack、halt、check、退出碼 |
| [cli-ls.md](cli-ls.md) | §6（續）ls 的長相、`--pool`／`--procs`／`-v` |
| [cli-ls-json.md](cli-ls-json.md) | §6（續）ls `--json` 第 3 版：為什麼升版、欄位表（one-boot 拆出） |
| [health.md](health.md) | §6（續）ls 第一行 health 的判定 |
| [no-overlap.md](no-overlap.md) | §7 為什麼這樣就不會兩格重疊 |
| [choices.md](choices.md) | §10 我自己選的（等使用者確認） |
| [scale.md](scale.md) | §11 規模：上萬顆時保證什麼、還剩哪些 O(N)、保證外 |
| [impl-notes.md](impl-notes.md) | 實作補記：實作審查與實作決定回寫的句子總表 |
| [history.md](history.md) | 沿革：輪次、審查與實作紀錄 |
