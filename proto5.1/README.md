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
| 1 | llm cpu（資料夾＋`aos-llm-cpu` 一次 tick 問一件）、aos-agent 的 `think` 改成丟請求＋`waits` 等結果、兩個逾時關卡（工具 `_timeout_ms` 60 秒、引擎連敗 3 次→`continue.json` 暫停） | [notes/stage1-task.md](notes/stage1-task.md) | 做完 |
| 2 | tool cpu（跟 llm cpu 同一套請求／結果協議）、工具檔 `_run: "cpu"`、`act` 送出與收回 | 之後 | — |
| 3 | aos-run／aos-daemon／aos-kernel 的 proto5 版（照 daemon／kernel 總結：擋重疊、砍到底、具名代號、沒有 module） | 之後 | — |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=proto5.1/lib python3 -m unittest discover -s proto5.1/lib/test
```


第 1 段：635 條 Python 測試全綠、C++ ctest 8/8；LM Studio `qwen/qwen3-1.7b` 已真跑 now 工具往返。
回報與逐次退出碼見 [stage1-report](notes/stage1-report.md)；實作決定與已知限制見 [findings](notes/findings.md)。

## 規範

| 文件 | 講什麼 | 現況 |
|---|---|---|
| [spec/directives.md](spec/directives.md) | 指示詞機制：env／fmt／ref、opt／val、實體位置與循環 | 沿用母本 |
| [spec/inst-posix.md](spec/inst-posix.md) | posix inst 七欄位、讀驗與執行語意 | 沿用母本 |
| [spec/exec.md](spec/exec.md) | aos-exec 命令列、三種目標、退出碼 | 沿用母本；run_inst 的逾時旗標見 [lib API](lib/README.md) |
| [spec/agent.md](spec/agent.md) | agent 家、info／state、input／waits／errors | 第 1 段已實作 |
| [spec/aos-agent.md](spec/aos-agent.md) | waits 門、idle／think／act、CPU 送收、工具限時與連敗暫停 | 第 1 段已實作 |
| [spec/aos-llm-ask.md](spec/aos-llm-ask.md) | 模型請求、工具 _meta／_timeout_ms、engine.cpu、同步 HTTP | 第 1 段已實作 |
| [spec/llm-cpu.md](spec/llm-cpu.md) | CPU 資料夾與請求／結果格式 | 第 1 段已實作 |
| [spec/aos-llm-cpu.md](spec/aos-llm-cpu.md) | 一次收屍再問一件、認領、短鎖、退出碼 | 第 1 段已實作 |

逐檔職責、API 與測試表見 [lib/README.md](lib/README.md)，命令列入口在 [cli/](cli/)。
