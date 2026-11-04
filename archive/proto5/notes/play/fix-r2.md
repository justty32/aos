# 試玩 r2 修正輪（fix-r2，2026-09-24）

← [play/](README.md)｜來源：[astra](2026-09-24-r2-astra.md)、[Opus](2026-09-24-r2-opus.md) 合併的六條；使用者拍板全做，CLI 形狀照 `thinking/aos-agent.md`

隊形：隊長（Opus）＋兩條 codex：A 線 agent CLI、B 線 kernel check／ls，檔案不重疊。規範與 README 由隊長改，標「（09-24 試玩 r2 補）」。
測試 959 → 1016 條，連跑兩次綠；pgrep 空。README 上手（init＋say --wait 版）照抄全跑：通，約 69 秒。

## 六條

| # | 狀態 | 做了什麼 |
|---|---|---|
| 1 | 已做 | `aos-agent status [--json]`：state、errors、batch 送出／收回數、每道門（連敗暫停附 `touch` 指令）、未收輸入、agent.err 最後一行、K 帳本那筆；info／state 壞了照印。`last` 門關著時警告 |
| 2 | 已做 | `check` 加 `dirs`（K 的 requests／responses／cpus）、`cpus`（daemon 重開後 cpu 不在＝bad，附 boot 指令）；`ls` 尾巴加 `hint`；README 補「daemon 掛了」 |
| 3 | 已做 | `aos-agent continue`：touch 連敗暫停門；沒在暫停印一句、退 0 |
| 4 | 已做 | `aos-agent say [dir] TEXT [--wait]`：原子投到 `input` 第一條；`--wait` 等到被收、idle、有新回話才印；逾時或暫停印 status 退 101 |
| 5 | 已做 | `aos-agent init`：寫死的單一預設家（代號 `default`、date 工具、`input/`、`log/`），info 最後寫、已有就拒絕 |
| 6 | 已做 | 外圈逾時不附舊 llm.err 行、寫明 `info.llm.timeout_ms`；EngineFailed／Timeout 附 endpoint＋代號→真名；stop 沒 `AOS_K` 用 tick.json；`--help` 每子命令一句；`check --agent` 重複＝用法錯；last 退回讀 history；README 第 6 段寫工具；兩份規範開頭「使用者只需要懂的」；標頭改連 rearch README |

沒有跳過的。沒做（寫進 aos-agent.md §13）：`pause`、`tools`／`llms`、`init --template`、check 連 endpoint 探測。

## 隊長裁決

1. **init 的輸入走 `input/` 資料夾**：say 每則取唯一檔名，連投不會撞「上一則還沒收」。
2. **README 的 llm.json 代號改 `default`、拿掉 180000 逾時**：對上 init；原值比外圈 125000 長，外圈會先砍。
3. **只搬「調度者裁決」到檔尾、不重編號**：崩潰恢復各節被大量引用，重編號等於改內容；改在開頭寫明哪些節日常不用讀。
4. **四個新子命令放 aos-agent.md §1.1～§1.4**。
5. **status 的 K 也退回讀 tick.json**，與 stop 一致。
6. **say --wait 遇到連敗暫停提前結束**，不乾等逾時。
7. **ls 的「daemon 沒在跑」提示只在 phase 不是 stopped 時印**；check 帳本沒 `kcpu` 不炸（隊長補修）。
8. **agent.md §3.3 修一句**：工具檔不是 JSON 是 `JsonSyntax`，不是 `ToolInvalid`（astra 卡點 6）。

## 留給之後的

- `aos_kernel.py` 789 行，該拆 CLI 另開一輪。
- 本機只有 Python 3.14，3.12 沒實跑。
