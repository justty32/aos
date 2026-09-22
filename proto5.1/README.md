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
| 2 | 共用 CPU 佇列、tool cpu、工具 `_run: "cpu"`、act 送收；請求對帳只評估 | [notes/stage2-task.md](notes/stage2-task.md) | 做完 |
| 3 | aos-run／aos-daemon／aos-kernel 的 proto5 版（照 daemon／kernel 總結：擋重疊、砍到底、具名代號、沒有 module） | [notes/stage3-task.md](notes/stage3-task.md) | 做完 |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=proto5.1/lib python3 -m unittest discover -s proto5.1/lib/test
```


第 1 段：635 條 Python 測試全綠、C++ ctest 8/8；LM Studio `qwen/qwen3-1.7b` 已真跑 now 工具往返。
第 2 段：686 條 Python 測試全綠、C++ ctest 8/8；LM Studio 與 `sleep 2; date` 的 tool CPU 往返完成。
第 3 段：760 條 Python 測試全綠、C++ ctest 8/8；daemon＋三顆 kernel CPU 的 agent／LLM／tool 往返已真跑通。
完整交付、ls／最後記憶／停止驗證見 [stage3-report](notes/stage3-report.md)，可重跑腳本見 [stage3-demo.py](notes/stage3-demo.py)。
回報與逐次退出碼見 [stage1-report](notes/stage1-report.md)、[stage2-report](notes/stage2-report.md)；實作決定、KISS 限制與對帳評估見 [findings](notes/findings.md)（第 2 段 #18～#26，第 3 段 #27～#35）。

## 規範

| 文件 | 講什麼 | 現況 |
|---|---|---|
| [spec/directives.md](spec/directives.md) | 指示詞機制：env／fmt／ref、opt／val、實體位置與循環 | 沿用母本 |
| [spec/inst-posix.md](spec/inst-posix.md) | posix inst 七欄位、讀驗與執行語意 | 沿用母本 |
| [spec/exec.md](spec/exec.md) | aos-exec 命令列、三種目標、退出碼 | 沿用母本；run_inst 的逾時旗標見 [lib API](lib/README.md) |
| [spec/agent.md](spec/agent.md) | agent 家、info／state、input／waits／errors、tool_cpu | 第 2 段已實作 |
| [spec/aos-agent.md](spec/aos-agent.md) | waits 門、idle／think／act、LLM／工具 CPU 送收、工具限時與連敗暫停 | 第 2 段已實作 |
| [spec/aos-llm-ask.md](spec/aos-llm-ask.md) | 模型請求、工具 _meta／_timeout_ms／_run、engine.cpu、同步 HTTP | 第 2 段已實作 |
| [spec/cpu-queue.md](spec/cpu-queue.md) | 共用 CPU 資料夾、交件／認領／收屍與原子結果 | 第 2 段已實作 |
| [spec/llm-cpu.md](spec/llm-cpu.md) | LLM 的 engine／body payload 與 message 結果 | 第 2 段抽取共用層 |
| [spec/tool-cpu.md](spec/tool-cpu.md) | 已解 inst／stdin／timeout_ms 與工具執行結果 | 第 2 段已實作 |
| [spec/aos-tool-cpu.md](spec/aos-tool-cpu.md) | 一次收屍再執行一個工具請求、退出碼 | 第 2 段已實作 |
| [spec/aos-llm-cpu.md](spec/aos-llm-cpu.md) | 一次問一件的薄層與退出碼；共用佇列另見 cpu-queue | 第 2 段已實作 |
| [spec/aos-run.md](spec/aos-run.md) | 完成後計時、status 事件、第一次 TERM 即終止子程式 | 第 3 段 |
| [spec/daemon-home.md](spec/daemon-home.md) | daemon 家、四個 op、請求回音與最小 state | 第 3 段 |
| [spec/aos-daemon.md](spec/aos-daemon.md) | daemon／ctl、done 先寫、停止與具名錯誤 | 第 3 段 |
| [spec/kernel-home.md](spec/kernel-home.md) | kernel info、CPU／queue／waiting、rm syscall | 第 3 段 |
| [spec/aos-kernel.md](spec/aos-kernel.md) | init／boot／tick／add／rm／ls、排程與防重疊 | 第 3 段 |

逐檔職責、API 與測試表見 [lib/README.md](lib/README.md)，命令列入口在 [cli/](cli/)。

## 程式

| 模組 | 命令列入口 | 做什麼 |
|---|---|---|
| [lib/aos_run.py](lib/aos_run.py) | `cli/aos-run` | 反覆跑一個目標，回報每次開始／完成 |
| [lib/aos_daemon.py](lib/aos_daemon.py) | `cli/aos-daemon`、`cli/aos-daemon-ctl` | 管理 aos-run 的生命週期 |
| [lib/aos_kernel.py](lib/aos_kernel.py) | `cli/aos-kernel` | 把普通 inst 行程排到 CPU；LLM／tool CPU 不需 module |
