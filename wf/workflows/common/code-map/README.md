# code map 各分冊導覽

← [code map 總圖](../code-map.md)（頂層結構圖、單向相依鐵律、快速索引都在那裡）

這個資料夾是 code map 的逐檔表格部分，**按小專案分冊**。要找「某個檔負責什麼」，先看下表選一冊。

**新增或刪除原始碼檔案時**：檔案在哪個小專案底下，就去那一冊的表格加／減那一列（`common/`、`app/`、建置設定檔一律進 `build.md`）。這是 AGENTS.md「改了程式碼就要同步 code map」那條鐵律的落點。

## 全部分冊與各核心小專案的逐檔表格入口

| 分冊 | 涵蓋 | 什麼時候會想看 |
|------|------|---------------|
| [core/exec/README.md](../../../../core/exec/README.md) | `core/exec/`：整批 POSIX 行程的啟動、等待、中斷、逾時、輸出與時間 | 要改 `start_all`／`wait_all`／`interrupt_running`、行程群組、PATH／env 準備或暫存檔收拾 |
| [core/wire/README.md](../../../../core/wire/README.md) | `core/wire/`：指令、結果與 loop state 三種協定的 C++ struct／JSON 邊界 | 要改協定欄位的解析、序列化、預設值或錯誤回報 |
| [core/loop/README.md](../../../../core/loop/README.md) | `core/loop/`：`.aos/` 版面、投遞、匯聚、state 與一回合的推進順序 | 要改資料夾回合機、`aos run`／`aos deliver` 或它對 exec／wire 的接法 |
| [core/tool/README.md](../../../../core/tool/README.md) | `core/tool/`：世界層工具登記表、探測與 agent 通訊錄；逐檔表格見 [tool.md](tool.md) | 要改 `.aos/tools/`／`.aos/contacts.json`、`aos tool`／`aos contact` 或工具自述探測 |
| [core/llm/README.md](../../../../core/llm/README.md) | `core/llm/`：OpenAI 相容 chat completions client；逐檔表格見 [llm.md](llm.md) | 要改 endpoint／model／request／response、環境變數或 `aos llm` CLI |
| [core/agent/README.md](../../../../core/agent/README.md) | `core/agent/`：回合 agent、工具往返與可選 LLM CPU；逐檔表格見 [agent.md](agent.md)，常查的東西見 [agent-lookup.md](agent-lookup.md) | 要改 agent 版面、step、工具呼叫、跨世界 say 或 lmstudio／pi engine |
| [core/tick/README.md](../../../../core/tick/README.md) | `core/tick/`：heartbeat 兩張清單的格式、到期規則、`aos tick` 一次心跳與四個登記子命令 | 要改到期判定、`routines.json`／`schedule.json` 的欄位、`log.md` 格式或 `aos routine`／`aos schedule` 的 CLI |
| [build.md](build.md) | `common/`、`app/` 的逐檔表格，以及根 CMakeLists／`cmake/`／vcpkg／presets 等建置設定 | 要改建置骨架、子命令登記機制、相依放哪一層，或新增一個小專案 |
| [proto8.md](proto8.md) | `proto8/`（現役主線）：impls、bin、lib、extras、demo、tests 每個檔一列，照資料夾分檔 | 要改 proto8 |
| [proto7-2.md](proto7-2.md) | `proto7-2/` 逐檔表的位置（INDEX、tests/README） | 要改 proto7-2 |
| [proto6/src/py/README.md](../../../../proto6/src/py/README.md) | `proto6/src/py/` Python 3.9 POC：從 proto5 複製的 inst／aos-exec，加 `aos-tick`（`lib/aos_tick*.py`） | 要改 proto6 的 inst／aos-exec 或 tick 核心 |
| [proto5/README.md](../../../../proto5/README.md) | `proto5/` Python 3.12 原型；逐模組一句見 [proto5-lib.md](proto5-lib.md)，API 細節見 [lib/README.md](../../../../proto5/lib/README.md)；命令列薄殼在 `proto5/cli/` | 要改 proto5 的指示詞、inst／exec、daemon 池、kernel、agent、aos-team |
| [proto5.1/README.md](../../../../proto5.1/README.md) | `proto5.1/` 實驗場：proto5 的複本加 cpu 佇列、llm／tool cpu、run、daemon、kernel 的實作與 `notes/findings.md` | 要看「建議實作起來撞到什麼」、或要把 proto5.1 的東西回流 proto5 |
| [proto4-5/README.md](../../../../proto4-5/README.md) | `proto4-5/` LLM 排程原型：`llm_cpu_request.py`、`llm_cpu_manage.py` | 要改請求對帳或原型的 `aos-kernel llm ls／rm` |
| [proto4-3/docs/files.md](../../../../proto4-3/docs/files.md) | `proto4-3/` 作業系統層原型的逐檔表 | 要改 aos-exec／aos-run／aos-daemon／aos-kernel 原型 |
