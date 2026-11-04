# proto8 討論紀錄

← [proto8](../README.md)

一天一份。只留三種內容：使用者原文（照原意整理）、決定（含使用者說「照建議」採納的 AI 建議）、跟 AI 討論後的結論；還沒定的列「未決」。AI 的分析過程、利弊表、被推翻的方案不留（規矩見 [user/03](../../wf/workflows/common/user/03-討論紀錄與規劃.md#討論紀錄只留原文決定結論2026-10-12-夜改)）。

> **10-12 夜使用者定**：thinking 只留「使用者原文整理、決策結果、跟 AI 討論後的結論、未決」，其餘 AI 產出拿掉（「今天 10/12 產出的那些 thinking 也是，留結論」）；整份都是 AI 產出的檔整份刪。

> **10-30 改名**：aos-kernel-llm 改名 aos-llm-kernel（`demo/kernel-llm/` → `demo/llm-kernel/`、標頭 `aos/kernel_llm.hpp` → `aos/llm_kernel.hpp`、`tests/test_kernel_llm.py` → `tests/test_llm_kernel.py`；[map-review 第 9 點](2026-10/30/map-review/01-使用者原文.md#決定10-30)）；aos-gate 改名 aos-llm-send（[第 11 點](2026-10/30/map-review/01-使用者原文.md#決定10-30)）。舊紀錄照舊名。

> **10-30 夜改名**：aos-hub 改做 aos-eca-hub（`extras/cli_hub/` → `extras/eca_hub/`、`bin/aos-hub` → `bin/aos-eca-hub`；`aos-hub-kernel` 與 `AOS_HUB` 退場，`aos-hub` 這個名字留給以後；[eca](2026-10/30/eca/09-方向題.md#決定10-30) 衝突 2、4，[map-review 第 5 點](2026-10/30/map-review/01-使用者原文.md#決定10-30)）。舊紀錄照舊名。

> **11-03 改名**（同日再改名 aos-eca：`extras/eca_ctl/` → `extras/eca/`、`bin/aos-eca`、`tests/test_eca_cmd.py`，使用者「好像也不用aos-eca-ctl，改成aos-eca就好。」，[eca 16](2026-10/30/eca/16-11-03-改名-aos-eca-ctl.md#11-03-再改名aos-eca-ctl--aos-eca)）：aos-eca-hub 改名 aos-eca-ctl（`extras/eca_hub/` → `extras/eca_ctl/`、`bin/aos-eca-hub` → `bin/aos-eca-ctl`、`tests/test_eca_hub.py` → `tests/test_eca_ctl.py`；使用者 11-03「aos-eca-hub應該改名為aos-eca-ctl」，[eca 16](2026-10/30/eca/16-11-03-改名-aos-eca-ctl.md)）。舊紀錄照舊名，連到資料夾的連結改指新路徑。

| 月份 | 份數 | 範圍 |
|---|---|---|
| [2026-11](2026-11/README.md) | 20 | 11-01～11-04：試驗場 bob／cathy、daemon 的環境變數與窗、常駐 bob、晚 loop 窗檔名改 `ctl.json`／`state.json`；procs、ctl 改下指令、stack 不放工作區、trace 拿掉、aos-agent 通用介面、eca 接 aos 工具、aos-post 重新定位；eca 開場白檔、loop／fsm agent、aos-post 信箱要不要改成一個資料夾（每天一列見月份表，每份一列見各日 README） |
| [2026-10](2026-10/README.md) | 82 | 10-11 重來～10-31：inst／loop／daemon／fsm／agent 的概念、JSON 入口與指示詞、kernel、命名、aos-exec 與 `.env`、10-24 的各種嘗試、介質與 aos-hub、aos-tools、playground 與 agent-bob、agent-lifecycle、eca、aos-round、aos-var 收回與 parts 收斂（每天一列見月份表，每份一列見各日 README） |

按月份分層（使用者「都按照推薦」）：本檔只留月份索引，各月一份表放在該月資料夾的 `README.md`（`2026-10/README.md`），一天一列、連到該日資料夾的 `README.md`，那天的每份一列放在日 README（11-04 使用者「proto8/thinking/2026-10/README.md也太大了，類似的也都拆一拆」）。新增一份討論＝在那天的 README 加一列；那天的第一份順便在月份表加一列。

**存放路徑：月份／日期／子項／分檔**（11-04 使用者「我稍微看了一下proto8，thinking/資料夾太臃腫了，改成以月份/日期/子項/分檔.md來存吧」）：

- 有分檔的子項：`<月>/<日>/<子項>/`，入口是 `README.md`、分檔照 `NN-段名.md` 放進去（例：`2026-10/30/eca/README.md`、`2026-10/30/eca/01-前提.md`）；日期資料夾只寫日。
- 只有一份、沒分檔的子項：直接放日期底下 `<月>/<日>/<子項>.md`（例：`2026-11/03/aos-post.md`）；跟它配套的資料檔並排放（`2026-10/23/naming.csv`）。
- 單檔長大要拆：`<子項>.md` 改成 `<子項>/README.md`＋分檔（[STRUCTURE 拆檔做法](../../wf/STRUCTURE.md#拆檔做法)的同名子資料夾，入口改走資料夾的 README）。
