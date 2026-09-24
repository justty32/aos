# 試玩 r1 修正輪（fix-r1，2026-09-24）

← [play/](README.md)｜來源：[astra](2026-09-24-r1-astra.md)、[Opus](2026-09-24-r1-opus.md) 的「改了會更順的清單」；使用者拍板 A＋B 組全做

隊形：Opus 隊長＋兩條 codex（gpt-6-astra）線：A 線 kernel CLI、B 線 aos-agent，檔案不重疊。規範與 README 由隊長改，每處標「（09-24 試玩 r1 補）」。
測試 900 → 959 條，全套連跑兩次綠；結束時 pgrep 空。

## 十條各做了什麼

| # | 狀態 | 做了什麼 |
|---|---|---|
| 1 | 已做 | README 加「十分鐘上手」五段（PATH＋daemon → init／check／boot → once／反覆 → 最小 agent＋`last` → 停機），明寫「once 回音不含 stdout」「CLI 成功≠工作成功」。隊長抽出程式碼區塊用 zsh 照跑：全通、約 34 秒。 |
| 2 | 已做 | daemon.md §6.1 寫 PATH 前提；新 `aos-kernel check K [--agent DIR] [--daemon D]`（`aos_kernel_check.py`）：info、daemon、五支 CLI 在 daemon 的 PATH（讀 `/proc/<pid>/environ`）、池、llm 設定與模型代號；`--agent` 查 agent。 |
| 3 | 已做 | `init --env NAME:KEY=VALUE`（可重複、字面字串）。 |
| 4 | 已做 | `aos-kernel stop` 等到停好印 `stopped`（`--wait-ms`、`--no-wait`）；init／agent start／stop 各印一行。 |
| 5 | 已做 | 問模型失敗附 llm.err 絕對路徑＋最後一行；kind=aos 指 cpu.log；工具 126／127 補 argv[0]；`ToolInvalid` 帶檔與元素位置；`ls` 的 bad 附「看 <路徑>」；touch 提示給完整路徑。 |
| 6 | 已做 | 選刪：daemon.md 拿掉 `daemon.log`，改寫「stderr 自己重導」。 |
| 7 | 已做 | 併入 1。 |
| 8 | 已做 | `aos-agent stop` 不讀 info，只讀 `tick.json` 比對 `AOS_K`；aos-agent.md §11 改。 |
| 9 | 已做 | `aos-agent last [dir] [--json]`（`aos_agent_last.py`），不要 `AOS_K`。 |
| 10 | 已做 | 封存名改 `<來源資料夾>/done/<原檔名>.<消費 id>.done`；舊式 dst 照原樣處理；agent.md、aos-agent.md 跟上。 |

沒有跳過的。

## 隊長裁決（實作層級）

1. **done/ 放在來源檔自己的資料夾底下**：rename 不跨檔案系統、不同資料夾同名不撞；慣例輸入在 agent 家，日常就是 `agent/done/`。
2. **daemon.log 選刪不選寫**：不改 daemon 行為，重導交給啟動的人。
3. **kernel stop 鏈沒在跑就不放單**、印 `not running`（放了下次 boot 一開機就停）。
4. **agent stop 仍要 `AOS_K`**（§1 的用法錯規則不動），tick.json 只用來擋「綁在別的 K」。
5. **check 加 `--daemon D`**（任務書沒列）：boot 前 info 還沒有 `daemon`，照抄上手時誤報「沒在跑」才補。
6. `--json` 只給 `last`，給別的子命令＝用法錯 2。

## 留給之後的

- `aos_kernel.py` 已 775 行（門檻 300），stop 等停好又加了約 50 行；該拆 CLI 另開一輪。
- 報告裡沒列進十條的（continue 指令、狀態查詢、規範重排、kernel cpu 殘格）這輪沒做。
- 測試輸出會夾著 `started／stopped agent-bob`（行程內叫 CLI），不影響結果。
