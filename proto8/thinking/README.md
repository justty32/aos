# proto8 討論紀錄

← [proto8](../README.md)

一天一份。只留三種內容：使用者原文（照原意整理）、決定（含使用者說「照建議」採納的 AI 建議）、跟 AI 討論後的結論；還沒定的列「未決」。AI 的分析過程、利弊表、被推翻的方案不留（規矩見 [user/03](../../wf/workflows/common/user/03-討論紀錄與規劃.md#討論紀錄只留原文決定結論2026-10-12-夜改)）。

> **10-12 夜使用者定**：thinking 只留「使用者原文整理、決策結果、跟 AI 討論後的結論、未決」，其餘 AI 產出拿掉（「今天 10/12 產出的那些 thinking 也是，留結論」）；整份都是 AI 產出的檔整份刪。

> **改名**：舊名 → 現名見 [NORMS 附錄3 舊名對照](../docs/NORMS/附錄3-舊名對照.md)。舊紀錄照舊名，連到資料夾的連結改指新路徑。
> 11-06 proto8 按角色重劃夾（[arch-refactor](2026-11/05/arch-refactor/README.md) S5），舊紀錄的路徑照這張換：`bin/<指令>` → `cmd/<指令>/bin/<指令>`（`aos-eca-turn`、`aos-eca-screen` 在 `cmd/aos-eca/bin/`）、`bin/aos_flags.py`、`lib/aos/aos_ws.py`、`lib/agent/cli_session.py` → `py/`、`bin/docs/` → `cmd/docs/`、`extras/agent` → `cmd/aos-agent`、`extras/ai_tools` → `cmd/aos-mcp`、`extras/sandbox` → `cmd/aos-sandbox`、`extras/grow` → `cmd/aos-grow`、`lib/base/judge` → `lib/aos/judge`、`demo/{llm-kernel,daemon-judge,procs-kernel}` → `kernel/`、`demo/{agent-fsm,eca-claude}` → `templates/`、`demo/docs/01、02` → `templates/docs/01、02`、`demo/docs/03～05` → `kernel/docs/01～03`。

| 月份 | 份數 | 範圍 |
|---|---|---|
| [2026-11](2026-11/README.md) | 142 | 11-01～11-12：試驗場、procs 合一、aos-post、aos-agent 與 loop／fsm agent、無痛遷移與 kernel／daemon、大重構、知識庫與 json 工具、self 一家與 goal、eca 與外部 MCP、kernel 條文（每天一列見月份表） |
| [2026-10](2026-10/README.md) | 82 | 10-11 重來～10-31：inst／loop／daemon／fsm／agent 的概念與規範、JSON 入口與指示詞、命名、aos-exec 與 `.env`、10-24 的嘗試、介質、aos-tools、eca、parts 收斂（每天一列見月份表） |

按月份分層（使用者「都按照推薦」）：本檔只留月份索引，各月一份表放在該月資料夾的 `README.md`（`2026-10/README.md`），一天一列、連到該日資料夾的 `README.md`，那天的每份一列放在日 README（11-04 使用者「proto8/thinking/2026-10/README.md也太大了，類似的也都拆一拆」）。新增一份討論＝在那天的 README 加一列；那天的第一份順便在月份表加一列。

**存放路徑：月份／日期／子項／分檔**（11-04 使用者「我稍微看了一下proto8，thinking/資料夾太臃腫了，改成以月份/日期/子項/分檔.md來存吧」）：

- 有分檔的子項：`<月>/<日>/<子項>/`，入口是 `README.md`、分檔照 `NN-段名.md` 放進去（例：`2026-10/30/eca/README.md`、`2026-10/30/eca/01-前提.md`）；日期資料夾只寫日。
- 只有一份、沒分檔的子項：直接放日期底下 `<月>/<日>/<子項>.md`（例：`2026-11/03/aos-post.md`）；跟它配套的資料檔並排放（`2026-10/23/naming.csv`）。
- 單檔長大要拆：`<子項>.md` 改成 `<子項>/README.md`＋分檔（[STRUCTURE 拆檔做法](../../wf/STRUCTURE.md#拆檔做法)的同名子資料夾，入口改走資料夾的 README）。
