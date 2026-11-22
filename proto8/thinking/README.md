# proto8 討論紀錄

← [proto8](../README.md)

一天一份。只留三種內容：使用者原文（照原意整理）、決定（含使用者說「照建議」採納的 AI 建議）、跟 AI 討論後的結論；還沒定的列「未決」。AI 的分析過程、利弊表、被推翻的方案不留（規矩見 [user/03](../../wf/workflows/common/user/03-討論紀錄與規劃.md#討論紀錄只留原文決定結論2026-10-12-夜改)）。

> **10-12 夜使用者定**：thinking 只留「使用者原文整理、決策結果、跟 AI 討論後的結論、未決」，其餘 AI 產出拿掉（「今天 10/12 產出的那些 thinking 也是，留結論」）；整份都是 AI 產出的檔整份刪。

> **改名**：舊紀錄照舊名，連到資料夾的連結改指新路徑。
> 11-06 proto8 按角色重劃夾（[arch-refactor](2026-11/05/arch-refactor/README.md) S5），舊紀錄的路徑照這張換：`bin/<指令>` → `cmd/<指令>/bin/<指令>`（`aos-eca-turn`、`aos-eca-screen` 在 `cmd/aos-eca/bin/`）、`bin/aos_flags.py`、`lib/aos/aos_ws.py`、`lib/agent/cli_session.py` → `py/`、`bin/docs/` → `cmd/docs/`、`extras/agent` → `cmd/aos-agent`、`extras/ai_tools` → `cmd/aos-mcp`、`extras/sandbox` → `cmd/aos-sandbox`、`extras/grow` → `cmd/aos-grow`、`lib/base/judge` → `lib/aos/judge`、`demo/{llm-kernel,daemon-judge,procs-kernel}` → `kernel/`、`demo/{agent-fsm,eca-claude}` → `templates/`、`demo/docs/01、02` → `templates/docs/01、02`、`demo/docs/03～05` → `kernel/docs/01～03`。
> 11-17 proto8 頂層收夾第一步（[proto8-八夾](2026-11/17/proto8-八夾.md)），舊紀錄的路徑照這張換：`schema/` → `lib/schema/`、`notes/` → `docs/notes/`、`user-advice/` → `thinking/user-advice/`（本夾底下，跟月份夾並列）、`feedback/` → repo 根的 `wf/advices/feedback/`；空的 `bin/` 刪掉（裡面的東西 11-06 已照上一段搬走）；`cases/`（measure 的考題 smoke、box-probe）2026-11-17 已刪（使用者「cases裡面的東西應該用不到了？刪掉」），考題格式看 [measure README](../lib/aos/measure/README.md)，兩份考題的內容改由 measure、box_check 的測試自己寫出。這次舊紀錄裡指到這幾個舊位置的連結沒改，點下去是壞的，照這張換著看。
> 11-17 proto8 頂層收夾第二、三步＋路徑規則一（[路徑規則](2026-11/17/路徑規則.md)、[proto8-八夾](2026-11/17/proto8-八夾.md)；頂層剩 `impls cmd lib templates knowledge docs thinking archive` 八夾）：`py/` 的模組攤平進 `lib/` 頂層（`py/aos_flags.py` → `lib/aos_flags.py`、`py/daemon_ctl/` → `lib/daemon_ctl/`，`py/tests/` → `lib/tests/`，`py/README.md` → `lib/docs/04-共用模組.md`）；`kernel/` → `templates/kernel/`；`extras/aos-home/env.sh` → `env.sh`（proto8 頂層），它的測試 → `cmd/aos-tree-start/tests/test_env_sh.py`；`install.sh` → `cmd/install.sh`；`extras/aos-view/` → `cmd/aos-view/`；`extras/fake-mcp-http/` → `lib/tests/fake-mcp-http/`；`extras/kernel-chain-check/` → `templates/kernel/tests/kernel-chain-check/`；`extras/image-move-check/` → `templates/tests/image-move-check/`；`extras/langs/`、`extras/tree-swap/`、`extras/aos-home/`（copy_tree）→ `archive/` 同名夾。舊紀錄的連結同樣沒改，照這張換著看。
> 11-17 下午全景頁改名（使用者「aos-view確實應該是選配的網頁外掛」「那就改名為aos-frontend吧」，放 `proto8/frontend/`、現在就改；頂層變九夾）：指令 `aos-view` → `aos-frontend`；整夾 `cmd/aos-view/` → `frontend/`（執行檔 `cmd/aos-view/aos-view`、後來的 `cmd/aos-view/bin/aos-view` → `frontend/bin/aos-frontend`；`systemd/aos-view.service` → `frontend/systemd/aos-frontend.service`；`ui/v2/`、`aide-def/`、`tests/`、`API.md` 跟著整夾搬、夾內位置不變）。資料夾 `~/.aos/view`、環境變數 `AOS_VIEW_HOME`、`aos-user`、`aos-user-tick` 沒改名。舊紀錄照舊名，照這張換著看。

使用者自己的意見稿（非 AI 產出，原文不動）11-22 整夾搬到 repo 根的 [`wf/user/advice/`](../../wf/user/advice/)（使用者「user advice可以搬進去」）；舊紀錄裡的 `thinking/user-advice/…` 指的就是那裡，連結照「舊紀錄不回頭改」不修。

| 月份 | 份數 | 範圍 |
|---|---|---|
| [2026-11](2026-11/README.md) | 142 | 11-01～11-12：試驗場、procs 合一、aos-post、aos-agent 與 loop／fsm agent、無痛遷移與 kernel／daemon、大重構、知識庫與 json 工具、self 一家與 goal、eca 與外部 MCP、kernel 條文（每天一列見月份表） |
| [2026-10](2026-10/README.md) | 82 | 10-11 重來～10-31：inst／loop／daemon／fsm／agent 的概念與規範、JSON 入口與指示詞、命名、aos-exec 與 `.env`、10-24 的嘗試、介質、aos-tools、eca、parts 收斂（每天一列見月份表） |

按月份分層（使用者「都按照推薦」）：本檔只留月份索引，各月一份表放在該月資料夾的 `README.md`（`2026-10/README.md`），一天一列、連到該日資料夾的 `README.md`，那天的每份一列放在日 README（11-04 使用者「proto8/thinking/2026-10/README.md也太大了，類似的也都拆一拆」）。新增一份討論＝在那天的 README 加一列；那天的第一份順便在月份表加一列。

**存放路徑：月份／日期／子項／分檔**（11-04 使用者「我稍微看了一下proto8，thinking/資料夾太臃腫了，改成以月份/日期/子項/分檔.md來存吧」）：

- 有分檔的子項：`<月>/<日>/<子項>/`，入口是 `README.md`、分檔照 `NN-段名.md` 放進去（例：`2026-10/30/eca/README.md`、`2026-10/30/eca/01-前提.md`）；日期資料夾只寫日。
- 只有一份、沒分檔的子項：直接放日期底下 `<月>/<日>/<子項>.md`（例：`2026-11/03/aos-post.md`）；跟它配套的資料檔並排放（`2026-10/23/naming.csv`）。
- 單檔長大要拆：`<子項>.md` 改成 `<子項>/README.md`＋分檔（[STRUCTURE 拆檔做法](../../wf/STRUCTURE.md#拆檔做法)的同名子資料夾，入口改走資料夾的 README）。
