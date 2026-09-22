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
| [spec/agent.md](spec/agent.md) | 什麼是 agent 資料夾：`info.json`（`_metainfo`＝`llm_agent`；`engine` 只有 `cpu`／`model` 代號／`params`）＋`state.json`（`state` 三格、`input`、`waits` 等待表與五個選項、`errors`）；共用錯誤代號 | **2026-09-22 回流 proto5.1 版**；proto5 程式仍是舊版（engine 帶 endpoint） |
| [spec/aos-agent.md](spec/aos-agent.md) | `aos-agent [dir]`：先判 `waits` 門，門開了走一格；`think` 把請求交 llm cpu、`act` 同步工具自己跑、`_run: cpu` 的交 tool cpu，都用 `waits` 等結果檔；連敗 3 次用 consume 的 `continue.json` 暫停；結果不明看 `code`；退出碼 0／101／1／2 | **回流 proto5.1 版**；proto5 程式仍是舊版（同步問、同步跑） |
| [spec/aos-llm-ask.md](spec/aos-llm-ask.md) | 只剩兩件事：`build_request` 組不含 `model` 的 chat body（人格／記憶／工具檔）、`call(engine, body)` 給 llm cpu 打 HTTP；命令列只印 body | **回流 proto5.1 版**；proto5 程式仍會同步問 |
| [spec/cpu-queue.md](spec/cpu-queue.md) | **格式**：cpu 資料夾共用的長相（`info.json`＋`requests/`→`running/`→`done/`、`bad/`）、請求檔共同欄位 `result`、結果檔 `{"ok":true,…}`／`{"ok":false,"code","msg"}`、`.queue.lock` 短鎖、認領、收屍 | 回流；proto5 沒有實作 |
| [spec/aos-cpu.md](spec/aos-cpu.md) | **程式**：共用層 `load`／`submit`／`tick(execute)`；壞單隔離到 `bad/`、結果寫不進去也搬 done | 回流；proto5 沒有實作 |
| [spec/llm-cpu.md](spec/llm-cpu.md) | **格式**：llm cpu 的 `models` 表（代號→endpoint／真名／api_key／timeout_ms，cpu 自己解 `$env`）、請求 `{"model","body","result"}`、結果 `message` | 回流；proto5 沒有實作 |
| [spec/aos-llm-cpu.md](spec/aos-llm-cpu.md) | **程式**：`aos-llm-cpu [dir]` 一次 tick 查代號填真名、同步問一件；退出碼 | 回流；proto5 沒有實作 |
| [spec/tool-cpu.md](spec/tool-cpu.md) | **格式**：tool cpu 的請求（解好的 inst＋stdin＋timeout_ms）、結果（code／stdout／timed_out）；已知失敗與結果不明（`Reaped`）怎麼分 | 回流；proto5 沒有實作 |
| [spec/aos-tool-cpu.md](spec/aos-tool-cpu.md) | **程式**：`aos-tool-cpu [dir]` 一次收屍再跑一個工具；退出碼 | 回流；proto5 沒有實作 |
| [spec/run-home.md](spec/run-home.md) | **格式**：runner 家的 `run.json`（busy／target／last_target／runs／last_exit／held…，寫入順序是 kernel 擋重疊的前提）與 `ctl.json`（stop／hold） | 回流；proto5 沒有實作 |
| [spec/aos-run.md](spec/aos-run.md) | **程式**：`aos-run [TARGET] --interval-ms --timeout-ms --max-runs --stop-exit --home --kill-tree`；父程序離開就自停、hold 睡 50 ms、兩次訊號、`--kill-tree` 預設不開 | 回流；proto5 沒有實作 |
| [spec/daemon-home.md](spec/daemon-home.md) | **格式**：daemon 家（`info.json` 身分、`requests/`＋`done/`、`runners/<名>/`、`state.json` 的 entry 含 `home`）、三個 op add／remove／stop、失敗回音 ok／code／msg | 回流；proto5 沒有實作 |
| [spec/aos-daemon.md](spec/aos-daemon.md) | **程式**：`aos-daemon`／`aos-daemon-ctl add／rm／ls／stop`；done 先寫再刪原單、舊 runner 還活就拒起、5＋5 秒停機階梯、具名錯誤 | 回流；proto5 沒有實作 |
| [spec/kernel-home.md](spec/kernel-home.md) | **格式**：`K/`（`info.json` 含 `daemon` 家與 `kill_tree`、`idle.json`、`procs/`＋`done/`＋`bad/`、`cpus/<n>.json` 是 symlink、`state.json` 的 cpus／queue／waiting）、rm syscall | 回流；proto5 沒有實作 |
| [spec/aos-kernel.md](spec/aos-kernel.md) | **程式**：`aos-kernel init／boot／tick／add／rm／ls`；先換槽再看各 cpu 的 run.json 擋重疊、`last_target` 對帳、100／101／bad_after | 回流；proto5 沒有實作 |

## 程式

> 2026-09-22 起規範走在程式前面：上表「回流」的規範在 proto5.1 有能跑的實作（802 條測試），proto5 這邊的程式**還沒**跟上。什麼時候把程式也搬回來由使用者定。

| 位置 | 講什麼 | 現況 |
|---|---|---|
| [lib/](lib/README.md) | 六支模組，一層疊一層：`aos_directives.py`（指示詞機制的純函式庫，不知道 inst 是什麼）→ `aos_inst.py`（inst.json 的讀、驗、解，回執行者能直接用的 dict）→ `aos_exec.py`（執行者：`run_target()` 回 `(code, kind)`＋命令列 `main()`）；另一條線 `aos_agent_info.py`（agent 資料夾的讀、驗：`info.json` 解指示詞、其他檔原樣、工具表合併；不碰 `state.json`）→ `aos_llm_ask.py`（`build_request()`／`ask()`＋命令列 `main()`）；最後 `aos_agent.py` 以 `load_obj()`／`run_inst()` 接起兩條線、先看 waits 再走一格；`cd proto5/lib && python3 -m unittest discover -s test` | 571 條測試全綠（directives 101、inst 139、exec 89、agent_info 88、llm_ask 53、agent 101） |
| [cli/aos-exec](cli/aos-exec) | 命令列入口，薄薄一層（`sys.path` 加 `../lib` 再叫 `aos_exec.main()`）。用法見 [spec/aos-exec.md](spec/aos-exec.md) | 能跑；命令列形狀還沒拍板 |
| [cli/aos-llm-ask](cli/aos-llm-ask) | 命令列入口，同樣薄薄一層（叫 `aos_llm_ask.main()`）。用法見 [spec/aos-llm-ask.md](spec/aos-llm-ask.md)：`aos-llm-ask [dir] [--dry-run]`，stdout 一行 JSON，退出碼 0／1／2／3 | 能跑；對 LM Studio（`qwen/qwen3-1.7b`）真打過一次，模型會回 `tool_calls` |
| [cli/aos-agent](cli/aos-agent) | 命令列薄入口（叫 `aos_agent.main()`）：`aos-agent [dir]`，先判 waits、再走 idle／think／act 一格；退出碼 0／101／1／2。API 與寫檔順序見 [lib README](lib/README.md) | 能跑；LM Studio（`qwen/qwen3-1.7b`）真跑過收輸入 → 問模型 → now 工具 → 回話 → 101 |

拍板過程的任務書副本在 [notes/2026-09-21-inst-rev-rules.md](notes/2026-09-21-inst-rev-rules.md)（A～L 節）。

## 筆記

- [notes/](notes/)：任務書副本、astra 的調查報告、我的精簡總結（每份都有「要使用者拍板的」清單）。
- [notes-brief/](notes-brief/README.md)：**notes/ 的精簡版**，每份不超過 5000 字；README 尾巴有「今天要使用者拍板的題目總表」，先看這裡。
- [notes/2026-09-22-decisions.md](notes/2026-09-22-decisions.md)：**23 題的拍板紀錄**（2026-09-22），proto5.1 第 4 段與之後的回流都照這份。
- [backlog/](backlog/README.md)：先記著、之後再做的事，一件一個檔。
- [notes/2026-09-22-backflow.md](notes/2026-09-22-backflow.md)：**規範回流紀錄**：哪些從 proto5.1 搬回來、跟舊版差在哪、程式還差什麼。

## 還沒定的

由使用者口述、陸續補進來；我不代替他想（[AGENTS 鐵律 5](../AGENTS.md)）。
