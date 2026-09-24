← [spec 總導航](../README.md)

# kernel：排程也是一格一格的 aos-exec

← [proto5 README](../../README.md)｜範式：[cpu.md](../cpu/README.md)｜跑一次：[aos-exec.md](../aos-exec/README.md)｜下層：[daemon](../daemon/README.md)

> 第 1 版，2026-09-23 定稿，2026-09-24 fix-r4 改命令列、fix-r5 改日常輸出（boot 印一行、check `--probe`、ls 的恢復中與 agent 暫停）、advice-r1 改 ls 的長相與 `--json`、check 的 `--agent` 搬到 `aos-agent check`；已實作（[`aos_kernel.py`](../../lib/aos_kernel.py)，入口 `aos-kernel`）。輪次、審查與實作沿革在檔尾〈沿革〉（09-24 試玩 r3 搬）。

一句話：**kernel 替登記好的工作（行程）挑一顆空著的 cpu 派下去、收回執行結果、決定要不要再跑。**
它不是長命行程：每次只跑一格 `aos-kernel tick`，格的開頭先把下一格放進一顆專用 exec cpu 的 `requests/`，
再做自己的事、然後退出（像尾遞迴：不等下一格跑完，排上去就走），排程就這樣一格接一格。
工作與 syscall 走資料夾（往 cpu 的 `requests/` 放、從 `responses/` 收、放 `ack`），父子生死走 pipe，
兩者共用 JSON-RPC 信封。kernel 跟 daemon 講話也走 daemon 家的資料夾。
**`K/state.json` 是唯一的帳本**：每個決定都是一次原子寫；派工跟四類出貨都是先記帳再動檔，只有接鏈反過來。

---

## 9. 已拍板的前提（使用者定的，不重問）

kernel 可以是 exec（tick 鏈）；`spawn` 有 `restart:true`，kernel cpu 死了靠它；rm 正在跑的行程後同名
add 拒絕到它跑完；stop 分 stopping／stopped 兩段，在途與 once 的回音收完才停；kind=aos 併進一般失敗、
沒有獨立 aos 計數；兩個 kernel 共用 daemon 而 cpu 同名＝`NameTaken` 大聲失敗。

## 8. 這份沒管的

適用範圍同範式 §8（同一台 POSIX 機器）。daemon 的 method 完整形狀、`restart`、daemon 自己怎麼停（[daemon](../daemon/README.md)）。
agent 那份要接的：怎麼用 `add --once` 問模型／跑工具、輸入檔跟答案檔放哪、誰清——kernel 只交執行結果，不交內容。
`aos-llm call` 這支程式（[aos-llm.md](../aos-llm/README.md)）。實作時值得順手做一支小函式庫（取名、放單、等回音、ack 包成一個呼叫），不然每個交件者都要自己寫這五步。

## 各節

原文裡「檔尾〈沿革〉」「檔尾〈實作補記〉」「見下」這類方位詞是拆檔前的位置，拆後照下表找對應檔（`history.md`、`impl-notes.md`、`rulings.md` 等）。

| 檔 | 內容 |
|---|---|
| [terms.md](terms.md) | §0 名詞：行程、tick、鏈、帳本、kernel cpu 等白話解釋 |
| [home.md](home.md) | §1 家的目錄圖；§1.1 `info.json`（cpus、pool、envs、tick_ms 等設定） |
| [ledger.md](ledger.md) | §1.2 `state.json` 帳本的欄位；§1.3 kernel 自己取的檔名 |
| [syscall.md](syscall.md) | §2 syscall：`K/requests/` 認的 method 與 params |
| [tick.md](tick.md) | §3 一格 tick 做什麼：接鏈、收單、派工、出貨的順序 |
| [echo.md](echo.md) | §4 回音怎麼判 |
| [daemon-link.md](daemon-link.md) | §5 跟 daemon 講話 |
| [cli.md](cli.md) | §6 命令列：用法總表、`--target` 找家的順序、`init --config` |
| [boot.md](boot.md) | §6（續）boot 的五步：交接、拉起來、放第 1 格；何時要重 boot |
| [cli-ops.md](cli-ops.md) | §6（續）add、自動 ack、halt、check、ls（health 行）、ack、退出碼 |
| [cli-ls.md](cli-ls.md) | §6（續）ls 的對齊表、`-v`、`--json` 的穩定欄位（09-24 advice-r1） |
| [no-overlap.md](no-overlap.md) | §7 為什麼這樣就不會兩格重疊 |
| [choices.md](choices.md) | §10 我自己選的（等使用者確認） |
| [impl-notes.md](impl-notes.md) | 實作補記（2026-09-24）：實作審查回寫的句子總表 |
| [history.md](history.md) | 沿革：輪次、審查與實作紀錄 |
