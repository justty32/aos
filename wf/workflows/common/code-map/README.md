# code map 各分冊導覽

← [code map 總圖](../code-map.md)（頂層結構圖、單向相依鐵律、快速索引都在那裡）

這個資料夾是 code map 的逐檔表格部分，**按小專案分冊**。要找「某個檔負責什麼」，先看下表選一冊。

| 檔案 | 裡面有什麼 | 什麼時候會想看 |
|------|-----------|---------------|
| [inst.md](inst.md) | `core/inst/` 這一冊的**入口**：小專案總述、「新增一個 instruction 欄位」的維護鏈，以及指向 [`inst/`](inst/README.md) 底下 library／capi／cli／tests 四份逐檔表格的路由 | 要改 instruction 結構、format／resolve／handoff／exec、C ABI 或 `aos init`／`aos exec` CLI |
| [tooljson.md](tooljson.md) | `core/tooljson/` 的公開 API、內部邊界、spec／registry／exec_type／args／text／fingerprint、CLI 與測試逐檔表格 | 要改 tool spec 驗證、`_type` registry、argv 展開或 `aos tooljson` CLI |
| [llms.md](llms.md) | `core/llms/` 的公開 API、內部邊界、content／params／transport／SSE／caps／Reply／Bot／presets、CLI 與測試逐檔表格 | 要改 LLM client、串流、toolset、presets 或 `aos llms` CLI |
| [build.md](build.md) | `common/`、`app/` 的逐檔表格，以及根 CMakeLists／`cmake/`／vcpkg／presets 等建置設定 | 要改建置骨架、子命令登記機制、相依放哪一層，或新增一個小專案 |

**新增或刪除原始碼檔案時**：檔案在哪個小專案底下，就去那一冊的表格加／減那一列（`common/`、`app/`、建置設定檔一律進 `build.md`）。這是 AGENTS.md「改了程式碼就要同步 code map」那條鐵律的落點。

## 全部分冊與各核心小專案的逐檔表格入口

> 2026-09-25 從 [code-map 總圖](../code-map.md)「逐檔表格在哪」整張搬來（總圖超過 8 KB，導航表往下一層放）；上面那張是早期四冊的簡表，這張是完整版。

| 分冊 | 涵蓋 | 什麼時候會想看 |
|------|------|---------------|
| [code-map/inst.md](inst.md) | `core/inst/`：公開標頭、五個核心分層、C ABI 包裝層、CLI 層、測試，以及「新增一個 instruction 欄位」的維護鏈（逐檔表格再按層拆在 [`code-map/inst/`](inst/README.md) 底下的 library／capi／cli／tests 四份） | **`core/inst` 已刪 2026-08-30，本冊為歷史存檔** |
| [code-map/tooljson.md](tooljson.md) | `core/tooljson/`：公開 API、內部邊界、spec／registry／exec_type／args／text／fingerprint、CLI、測試 | **`core/tooljson` 已刪 2026-08-30，本冊為歷史存檔** |
| [code-map/llms.md](llms.md) | `core/llms/`：公開 API、內部邊界、content／params／transport／SSE／caps／Reply／Bot／presets、CLI、測試 | **`core/llms` 已刪 2026-08-30，本冊為歷史存檔** |
| [core/exec/README.md](../../../../core/exec/README.md) | `core/exec/`：整批 POSIX 行程的啟動、等待、中斷、逾時、輸出與時間 | 要改 `start_all`／`wait_all`／`interrupt_running`、行程群組、PATH／env 準備或暫存檔收拾 |
| [core/wire/README.md](../../../../core/wire/README.md) | `core/wire/`：指令、結果與 loop state 三種協定的 C++ struct／JSON 邊界 | 要改協定欄位的解析、序列化、預設值或錯誤回報 |
| [core/loop/README.md](../../../../core/loop/README.md) | `core/loop/`：`.aos/` 版面、投遞、匯聚、state 與一回合的推進順序 | 要改資料夾回合機、`aos run`／`aos deliver` 或它對 exec／wire 的接法 |
| [core/tool/README.md](../../../../core/tool/README.md) | `core/tool/`：世界層工具登記表、探測與 agent 通訊錄；逐檔表格見 [code-map/tool.md](tool.md) | 要改 `.aos/tools/`／`.aos/contacts.json`、`aos tool`／`aos contact` 或工具自述探測 |
| [core/llm/README.md](../../../../core/llm/README.md) | `core/llm/`：OpenAI 相容 chat completions client；逐檔表格見 [code-map/llm.md](llm.md) | 要改 endpoint／model／request／response、環境變數或 `aos llm` CLI |
| [core/agent/README.md](../../../../core/agent/README.md) | `core/agent/`：回合 agent、工具往返與可選 LLM CPU；逐檔表格見 [code-map/agent.md](agent.md) | 要改 agent 版面、step、工具呼叫、跨世界 say 或 lmstudio／pi engine |
| [core/tick/README.md](../../../../core/tick/README.md) | `core/tick/`：heartbeat 兩張清單的格式、到期規則、`aos tick` 一次心跳與四個登記子命令 | 要改到期判定、`routines.json`／`schedule.json` 的欄位、`log.md` 格式或 `aos routine`／`aos schedule` 的 CLI |
| [proto4-3/docs/files.md](../../../../proto4-3/docs/files.md) | `proto4-3/` 作業系統層原型的逐檔表；inst 指示詞、run 訊號狀態與 daemon lifecycle 已各自拆檔 | 要改 aos-exec／aos-run／aos-daemon／aos-kernel 原型 |
| [proto5/README.md](../../../../proto5/README.md) | `proto5/` Python 3.12 原型（09-24 起 daemon／kernel 是 proto5-2 納入的池式版本）；逐模組一句見 [proto5/lib 模組](proto5-lib.md)，API 細節見 [lib/README.md](../../../../proto5/lib/README.md)；命令列薄殼在 `proto5/cli/`（aos（`aos up`／`aos down`）／aos-exec／aos-cpu／aos-daemon／aos-kernel／aos-agent／aos-jail／aos-llm／aos-directives／aos-json／aos-team），三支主人指令的家一律 `--target` | 要改 proto5 的指示詞、inst／exec、JSON-RPC 家與交件、cpu 執行、daemon 池、kernel 池表／sqlite 帳本／tick（09-24 one-boot 起由 daemon 開）、`aos up`／`down`，或 agent 家讀驗、aos-llm call、aos-agent 各子命令、aos-team 團隊分派 |
| [proto5.1/README.md](../../../../proto5.1/README.md) | `proto5.1/` 實驗場：proto5 的複本，照 23 題建議先實作——`lib/` 多了 `aos_cpu.py`（共用佇列）、`aos_llm_cpu.py`、`aos_tool_cpu.py`、`aos_run.py`、`aos_daemon.py`、`aos_kernel.py`；`spec/` 多了 cpu-queue／llm-cpu／tool-cpu／aos-*-cpu／aos-run／daemon-home／aos-daemon／kernel-home／aos-kernel；`notes/findings.md`（35 條）與 `findings-brief.md` | 要看「建議實作起來撞到什麼」、或要把 proto5.1 的東西回流 proto5 |
| [proto4-5/README.md](../../../../proto4-5/README.md) | `proto4-5/` LLM 排程原型；`llm_cpu_request.py` 管請求 ID／位置／指紋，`llm_cpu_manage.py` 直接查／刪 `K/llm/` 的 queued、running、done | 要改請求對帳或原型的 `aos-kernel llm ls／rm` |
| [code-map/build.md](build.md) | `common/`、`app/` 的逐檔表格，以及根 CMakeLists／`cmake/`／vcpkg／presets 等建置設定 | 要改建置骨架、子命令登記機制、相依放哪一層，或新增一個小專案 |
| [code-map/proto5-lib.md](proto5-lib.md) | proto5/lib 模組逐模組一句（2026-09-25 從本檔拆出） | 要改對應模組、找某個檔負責什麼 |
| [code-map/tool.md](tool.md) | core/tool 逐檔表格（2026-09-25 從本檔拆出） | 要改對應模組、找某個檔負責什麼 |
| [code-map/llm.md](llm.md) | core/llm 與 core/agent 總述、core/llm 逐檔表格（2026-09-25 從本檔拆出） | 要改對應模組、找某個檔負責什麼 |
| [code-map/agent.md](agent.md) | core/agent 逐檔表格與分層、agents/<name>/ 版面（2026-09-25 從本檔拆出） | 要改對應模組、找某個檔負責什麼 |
| [code-map/agent-lookup.md](agent-lookup.md) | core/llm／core/agent 常查的東西在哪、agent 的可選 LLM CPU（2026-09-25 從本檔拆出） | 要改對應模組、找某個檔負責什麼 |
