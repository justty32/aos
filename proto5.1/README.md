# proto5.1 — 拿 proto5 的規範去「先做做看」的實驗場

← [INDEX](../wf/INDEX.md)｜母本 [proto5](../proto5/README.md)（規範與程式都從那裡複製過來，2026-09-22 `ace797e`）

proto5 那邊 2026-09-22 做了四份調查，冒出 23 題要使用者拍板（[proto5/notes-brief/README.md](../proto5/notes-brief/README.md)）。
使用者說：決策太多，不如開一個 proto5.1，**照 Claude 的建議先實作看看**，實作時撞到的實際問題與經驗
拿回去當拍板的參考。所以：

- **proto5 不動**（規範與程式維持原樣，等使用者慢慢看）。
- **proto5.1 是實驗場**：codex（gpt-6-astra）照 [proto5 四份總結](../proto5/notes-brief/README.md) 裡的建議實作；
  規範（`spec/`）跟著實作改；撞到的問題、被迫做的決定、跟建議不一樣的地方，全部記在
  [`notes/findings.md`](notes/findings.md)。
- 之後哪些東西要回流到 proto5，由使用者看完 findings 再定。

## 分段

| 段 | 做什麼 | 任務書 | 狀態 |
|---|---|---|---|
| 1 | llm cpu（資料夾＋`aos-llm-cpu` 一次 tick 問一件）、aos-agent 的 `think` 改成丟請求＋`waits` 等結果、兩個逾時關卡（工具 `_timeout_ms` 60 秒、引擎連敗 3 次→`continue.json` 暫停） | [notes/stage1-task.md](notes/stage1-task.md) | 進行中 |
| 2 | tool cpu（跟 llm cpu 同一套請求／結果協議）、工具檔 `_run: "cpu"`、`act` 送出與收回 | 之後 | — |
| 3 | aos-run／aos-daemon／aos-kernel 的 proto5 版（照 daemon／kernel 總結：擋重疊、砍到底、具名代號、沒有 module） | 之後 | — |

```sh
cd proto5.1/lib && python3 -m unittest discover -s test
```
