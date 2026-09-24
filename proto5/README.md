# proto5

← [INDEX](../wf/INDEX.md)｜前一輪 [proto4-3](../proto4-3/README.md)（作業系統層）、[proto4-7](../proto4-7/README.md)（簡單 agent）｜使用者的方向草稿在 [`thinking/`](../thinking/)

proto5 從**把規範寫下來**開始：proto4-x 一路長出來的格式與約定，先一份一份寫成文件，
程式再照文件走。文件裡跟現行程式碼對不上的地方，以程式碼為準、回來改文件。

## 規範

| 文件 | 講什麼 | 現況 |
|---|---|---|
| [spec/directives.md](spec/directives.md) | 指示詞機制：`$env`／`$fmt`／`$ref` 取值、`$opt`／`$val` 選項物件、先解再驗、巢狀、循環、錯誤代號。任何 aos 的 JSON 檔都能用；哪個位置認得哪些選項名由宿主規範定 | 2026-09-21 定稿；實作 [`lib/aos_directives.py`](lib/aos_directives.py) |
| [spec/inst-posix.md](spec/inst-posix.md) | inst.json 的 `posix` 呼叫格式第 1 版：七個欄位、各位置的 `$opt` 選項（append／mkdir／inherit／merge／clear）、錯誤代號、執行語意，加上 `_metainfo`（`_type`／`_version`；沒寫＝posix v1）、頂層未知 key 忽略 | 2026-09-21 定稿；實作 [`lib/aos_inst.py`](lib/aos_inst.py)（讀／驗）＋ [`lib/aos_exec.py`](lib/aos_exec.py)（執行）。proto4-3 是凍結的舊版參考 |
| [spec/aos-exec.md](spec/aos-exec.md) | aos-exec 的**命令列**：三種目標（普通檔／`.json`／資料夾）、`--dir-target`／`--timeout-ms`／`--stderr`／`--`、退出碼 2／125／原樣、125 與 2 時 stderr 印什麼。行為照 inst-posix.md 第 6 節 | 命令列走法照 proto4-3 現況整理，使用者還沒逐條拍板 |
| [spec/cpu.md](spec/cpu.md) | cpu 範式（一個家一個主人：`info`／`state`／`requests`／`responses`、JSON-RPC 信封、ack）與 exec cpu：逐件照 aos-exec 跑一次、回音寫 `responses/` | 2026-09-23 定稿；實作 [`lib/aos_home.py`](lib/aos_home.py)＋[`lib/aos_client.py`](lib/aos_client.py)＋[`lib/aos_exec_cpu.py`](lib/aos_exec_cpu.py)（`aos-cpu`） |
| [spec/kernel.md](spec/kernel.md) | kernel：替登記的工作挑空 cpu 派下去、收結果、決定要不要再跑；每次只跑一格 `aos-kernel tick`，格接格排程 | 2026-09-23 定稿；實作 [`lib/aos_kernel.py`](lib/aos_kernel.py)（`aos-kernel`） |
| [spec/daemon.md](spec/daemon.md) | daemon：所有 cpu 的父行程，只管孩子的啟動、重拉、停止；家也照 cpu 範式長 | 2026-09-23 定稿；實作 [`lib/aos_daemon.py`](lib/aos_daemon.py)（`aos-daemon`） |
| [spec/agent.md](spec/agent.md) | 一個 agent 就是一個資料夾：`info.json` 說它是誰、記憶、工具、用哪個 kernel 與模型；`state.json` 記走到哪、輸入從哪來、在等哪些回音 | 2026-09-23 第 2 版草稿、程式未跟（現行 `aos_agent_info.py`／`aos_agent.py` 仍照第 1 版） |
| [spec/aos-agent.md](spec/aos-agent.md) | `aos-agent [dir]`：先看 `waits` 門，門開了走一格（`idle` 收輸入、`think` 問模型、`act` 跑工具）；問跟跑都是往 kernel `add --once` 放單、等回音、ack | 2026-09-23 第 2 版草稿、程式未跟（現行 `aos_agent.py` 仍照第 1 版） |
| [spec/aos-llm-call.md](spec/aos-llm-call.md) | `aos-llm-call AGENT_DIR`：讀 agent 家、組請求、打一次 HTTP、印模型回的 message；取代 aos-llm-ask＋llm cpu | 2026-09-23 草稿、程式未跟 |
| [spec/aos-llm-ask.md](spec/aos-llm-ask.md) | 只剩兩件事：`build_request` 組不含 `model` 的 chat body（人格／記憶／工具檔）、`call(engine, body)` 給 llm cpu 打 HTTP；命令列只印 body | 2026-09-22 從 proto5.1 回流；實作 [`lib/aos_llm_ask.py`](lib/aos_llm_ask.py)。會被 [aos-llm-call.md](spec/aos-llm-call.md) 取代 |
| [spec/llm-cpu.md](spec/llm-cpu.md) | **格式**：llm cpu 的 `models` 表（代號→endpoint／真名／api_key／timeout_ms，cpu 自己解 `$env`）、請求 `{"model","body","result"}`、結果 `message` | 舊架構；實作 [`lib/aos_llm_cpu.py`](lib/aos_llm_cpu.py)（仍在用）。等 agent 重寫落地後刪 |
| [spec/aos-llm-cpu.md](spec/aos-llm-cpu.md) | **程式**：`aos-llm-cpu [dir]` 一次 tick 查代號填真名、同步問一件；退出碼 | 舊架構；實作 [`lib/aos_llm_cpu.py`](lib/aos_llm_cpu.py)（仍在用）。等 agent 重寫落地後刪 |
| [spec/tool-cpu.md](spec/tool-cpu.md) | **格式**：tool cpu 的請求（解好的 inst＋stdin＋timeout_ms）、結果（code／stdout／timed_out）；已知失敗與結果不明（`Reaped`）怎麼分 | 舊架構；實作 [`lib/aos_tool_cpu.py`](lib/aos_tool_cpu.py)（仍在用）。等 agent 重寫落地後刪 |
| [spec/aos-tool-cpu.md](spec/aos-tool-cpu.md) | **程式**：`aos-tool-cpu [dir]` 一次收屍再跑一個工具；退出碼 | 舊架構；實作 [`lib/aos_tool_cpu.py`](lib/aos_tool_cpu.py)（仍在用）。等 agent 重寫落地後刪 |

## 程式

2026-09-23：cpu／daemon／kernel 已依 [cpu.md](spec/cpu.md)、[daemon.md](spec/daemon.md)、
[kernel.md](spec/kernel.md) 重寫。agent 與舊 llm／tool cpu 保留原實作，尚未接上新架構；
新 agent 規範另待實作。實作中的規範歧義與限制記在 [impl-findings.md](notes/2026-09-23-rearch/impl-findings.md)。

| 位置 | 講什麼 | 現況 |
|---|---|---|
| [lib/](lib/README.md) | 十四支標準庫 Python 3.12 模組。底層 directives → inst → exec；新共用 home／client；exec_cpu 執行一次、daemon 管孩子、kernel 用 tick 鏈與帳本排程。六支舊 agent／llm／tool／cpu 模組保留。逐檔 API 與測試表見 lib README | 19 個測試檔、883 條：`cd proto5/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test` |
| [cli/](cli/) | 八個薄入口：`aos-exec`、`aos-cpu`、`aos-daemon`、`aos-kernel`，以及保留的 `aos-llm-ask`、`aos-agent`、`aos-llm-cpu`、`aos-tool-cpu`。`aos-run`／`aos-daemon-ctl` 已移除 | 新架構端到端使用真 daemon＋k／0／llm exec cpu，透過 envs PATH 找假 llm-http，驗 once 輸出、反覆 done_exit 與完整停機；舊 agent 尚未遷移 |

拍板過程的任務書副本在 [notes/2026-09-21-inst-rev-rules.md](notes/2026-09-21-inst-rev-rules.md)（A～L 節）。

## 筆記

- [notes/](notes/)：任務書副本、astra 的調查報告、我的精簡總結（每份都有「要使用者拍板的」清單）。
- [notes-brief/](notes-brief/README.md)：**notes/ 的精簡版**，每份不超過 5000 字；README 尾巴有「今天要使用者拍板的題目總表」，先看這裡。
- [notes/2026-09-22-decisions.md](notes/2026-09-22-decisions.md)：**23 題的拍板紀錄**（2026-09-22），proto5.1 第 4 段與之後的回流都照這份。
- [backlog/](backlog/README.md)：先記著、之後再做的事，一件一個檔。
- [notes/2026-09-22-backflow.md](notes/2026-09-22-backflow.md)：**規範回流紀錄**：哪些從 proto5.1 搬回來、跟舊版差在哪、程式還差什麼。

## 還沒定的

由使用者口述、陸續補進來；我不代替他想（[AGENTS 鐵律 5](../AGENTS.md)）。
