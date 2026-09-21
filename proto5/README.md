# proto5

← [INDEX](../wf/INDEX.md)｜前一輪 [proto4-3](../proto4-3/README.md)（作業系統層）、[proto4-7](../proto4-7/README.md)（簡單 agent）｜使用者的方向草稿在 [`thinking/`](../thinking/)

proto5 從**把規範寫下來**開始：proto4-x 一路長出來的格式與約定，先一份一份寫成文件，
程式再照文件走。文件裡跟現行程式碼對不上的地方，以程式碼為準、回來改文件。

## 規範

| 文件 | 講什麼 | 現況 |
|---|---|---|
| [spec/directives.md](spec/directives.md) | 指示詞機制：`$env`／`$fmt`／`$ref` 取值、`$opt`／`$val` 選項物件、先解再驗、巢狀、循環、錯誤代號。任何 aos 的 JSON 檔都能用；哪個位置認得哪些選項名由宿主規範定 | 2026-09-21 定稿；實作 [`lib/aos_directives.py`](lib/aos_directives.py) |
| [spec/inst-posix.md](spec/inst-posix.md) | inst.json 的 `posix` 呼叫格式第 1 版：七個欄位、各位置的 `$opt` 選項（append／mkdir／inherit／merge／clear）、錯誤代號、執行語意，加上 `_metainfo`（`_type`／`_version`；沒寫＝posix v1）、頂層未知 key 忽略 | 2026-09-21 定稿；實作 [`lib/aos_inst.py`](lib/aos_inst.py)（讀／驗）＋ [`lib/aos_exec.py`](lib/aos_exec.py)（執行）。proto4-3 是凍結的舊版參考 |
| [spec/exec.md](spec/exec.md) | aos-exec 的**命令列**：三種目標（普通檔／`.json`／資料夾）、`--dir-target`／`--timeout-ms`／`--stderr`／`--`、退出碼 2／125／原樣、125 與 2 時 stderr 印什麼。行為照 inst-posix.md 第 6 節 | 命令列走法照 proto4-3 現況整理，使用者還沒逐條拍板 |
| [spec/agent.md](spec/agent.md) | 什麼是 agent 資料夾：`info.json`（人寫，`_metainfo`＝`llm_agent`，每格解指示詞）＋`state.json`（agent 寫，只有 `state`）、誰寫誰、指示詞解不解、共用錯誤代號；`info.json` 其他欄位由用它的程式定 | **草稿**，跟使用者一步步改中；最精簡標準 |
| [spec/aos-agent.md](spec/aos-agent.md) | `aos-agent [dir]`：先看 `waits` 這道門（動態等待表、`exists`／`mtime`／`consume`／`any`／`all`），門開了走一格（`idle` 收 `input`、`think` 問、`act` 跑完所有工具接 `tool` 訊息）；三格狀態、退出碼 0／101／1／2；非同步工具之後再做 | **草稿**；程式還沒寫 |
| [spec/aos-llm-ask.md](spec/aos-llm-ask.md) | `aos-llm-ask [dir]` 把 agent 資料夾問模型一次：`info.json` 的 `system`／`history`／`tools`／`engine` 四格與它們指到的檔（人格、記憶、工具檔＝OpenAI tools 陣列＋`_meta`）長什麼樣、組請求、`--dry-run` 只印請求、輸出 `choices[0].message`、退出碼 0／1／2／3；`state.json` 不看，不寫任何檔 | **草稿**；實作 [`lib/aos_llm_ask.py`](lib/aos_llm_ask.py)（讀驗在 [`lib/aos_agent_info.py`](lib/aos_agent_info.py)），入口 [`cli/aos-llm-ask`](cli/aos-llm-ask) |

## 程式

| 位置 | 講什麼 | 現況 |
|---|---|---|
| [lib/](lib/README.md) | 五支模組，一層疊一層：`aos_directives.py`（指示詞機制的純函式庫，不知道 inst 是什麼）→ `aos_inst.py`（inst.json 的讀、驗、解，回執行者能直接用的 dict）→ `aos_exec.py`（執行者：`run_target()` 回 `(code, kind)`＋命令列 `main()`）；另一條線 `aos_agent_info.py`（agent 資料夾的讀、驗：`info.json` 解指示詞、其他檔原樣、工具表合併；不碰 `state.json`）→ `aos_llm_ask.py`（`build_request()`／`ask()`＋命令列 `main()`）；`cd proto5/lib && python3 -m unittest discover -s test` | 470 條測試全綠（directives 101、inst 139、exec 89、agent_info 88、llm_ask 53） |
| [cli/aos-exec](cli/aos-exec) | 命令列入口，薄薄一層（`sys.path` 加 `../lib` 再叫 `aos_exec.main()`）。用法見 [spec/exec.md](spec/exec.md) | 能跑；命令列形狀還沒拍板 |
| [cli/aos-llm-ask](cli/aos-llm-ask) | 命令列入口，同樣薄薄一層（叫 `aos_llm_ask.main()`）。用法見 [spec/aos-llm-ask.md](spec/aos-llm-ask.md)：`aos-llm-ask [dir] [--dry-run]`，stdout 一行 JSON，退出碼 0／1／2／3 | 能跑；對 LM Studio（`qwen/qwen3-1.7b`）真打過一次，模型會回 `tool_calls` |

拍板過程的任務書副本在 [notes/2026-09-21-inst-rev-rules.md](notes/2026-09-21-inst-rev-rules.md)（A～L 節）。

## 還沒定的

由使用者口述、陸續補進來；我不代替他想（[AGENTS 鐵律 5](../AGENTS.md)）。
