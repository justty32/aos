← [INDEX](../INDEX.md)｜所在段落：Repo 佈局

## Repo 佈局

本專案自己一個 git repo，remote 是 `git@github.com:justty32/aos.git`。**在兩台機器上開發**，checkout 路徑不同（家裡 Linux／WSL、公司 Windows），所以**文件裡一律用 repo 相對路徑，不要寫死絕對路徑**。「從 repo 根目錄」指的是有 `CMakeLists.txt` 的那一層。

| 路徑 | 內容 |
|------|------|
| `CMakeLists.txt` | 根建置檔：`option()`、`find_package`、`add_subdirectory(...)`、`install`／`export`。**只能從這裡 configure**，子專案不可單獨 configure |
| `CMakePresets.json` | 建置 preset：`default`／`release`／`merged`；個人路徑放 `CMakeUserPresets.json`（已 `.gitignore`）|
| `vcpkg.json` | root manifest，有 `builtin-baseline`；測試相依放 `"tests"` feature |
| `cmake/` | 共用 CMake 函式（`aos_add_subproject()` 等）與 `find_package(aos CONFIG)` 的匯出設定 |
| `common/` | `aos::common`，header-only，目前只有 `<aos/export.h>` |
| `app/` | 唯一的執行檔 `aos`，靠子命令分派（如 `aos init`／`aos exec`）|
| `core/` | **核心小專案**（aos 的基本組成，一定會建）：`exec`／`wire`／`loop`／`llm`／`agent`／`tick`（另有 `tool/`），各自一個 `aos::<name>` lib，清單在 [core/README](../../core/README.md)。內部分工 → [code map](../workflows/common/code-map.md) |
| `modules/` | **擴充小專案**（可選，`-DAOS_BUILD_MODULES=OFF` 整批不建）。目前是空的。新增小專案 → [add-subproject](../workflows/add-subproject.md) |
| `docs/` | **整體文件**（給使用者與新加入的人）：總覽、建置、使用、新增小專案，以及最新的 [`aos-core-guide.md`](../../docs/aos-core-guide.md)（目前的子命令與建置實況）。入口是 [docs/README.md](../../docs/README.md)。**`.aos` 版面與回合模型的規格不在 `docs/`**，`core/` 程式的唯一真源是 [PROTOCOL](../workflows/dispatch/proto/PROTOCOL.md)；現行主線 proto7-2 照 [proto7-2/spec.md](../../proto7-2/spec.md)（上一代 proto6 照 [proto6/spec](../../proto6/spec/README.md)）（[workflows/spec/](../workflows/spec/README.md) 是 09-05 的舊規格，只當歷史）；階段表在 `roadmap`。個別小專案自己的細節在它們的 `docs/`，例如 `core/inst/docs/` |
| `proto*/` | **原型區**（任意語言、跟 `core/` 切開、不進 CMake）：**[`proto8/`](../../proto8/README.md) 是 10-11 新開的重新思考（lib：指示詞、inst、loop、daemon；討論紀錄在它的 [thinking/](../../proto8/thinking/README.md)）**，[`proto8-1/`](../../proto8-1/README.md) 是在 aos_inst 之上的 tasks 小程式（aos-seq、aos-par、aos-if、aos-not）與時鐘 aos-tick；到 10-10 為止的主線是 [`proto7-2/`](../../proto7-2/README.md)（10-04 起，照使用者建議重做 daemon／tick，之後長出 kernel、agent、`packs/` 工具包與選單包；Python 純標準庫，導覽在它的 [INDEX](../../proto7-2/INDEX.md)）；[`proto7/`](../../proto7/README.md) 是 10-03 新開的 aos 時空架構（[核心 spec](../../proto7/spec/core.md)，proto7-2 照它做）；[`proto7-1/`](../../proto7-1/README.md) 是照核心 spec 一路做到 kernel／agent 的 Python 試做，重點是[遇到的問題](../../proto7-1/notes/problems.md)；[`proto6/`](../../proto6/README.md) 是到 10-03 為止的主線（Linux agent 新方向；規格 `spec/`、Python POC `src/py/`、各段狀態 `plan/`，分工見 roadmap）；上一代可執行原型是 [`proto5/`](../../proto5/README.md)（規範先行：`spec/` 規範、`lib/` Python 實作、`cli/` 六支指令 daemon→kernel→cpu＋agent，`notes/` 見 [notes 索引](../../proto5/notes/README.md)；09-24 已納入池式的 [`proto5-2/`](../../proto5-2/README.md)，那邊只剩規範草稿與筆記當歷史）；[`proto5.1/`](../../proto5.1/README.md) 是 09-22 的實驗場、只當紀錄；更早的 [`proto4-3/`](../../proto4-3/README.md) 作業系統層（2026-09-21 凍結當參考）、[`proto4-4/`](../../proto4-4/README.md) 逐步 lisp、[`proto4-5/`](../../proto4-5/README.md) LLM 兩層、[`proto4-6/`](../../proto4-6/README.md) 逐步 JSON／Python／Lua、[`proto4-7/`](../../proto4-7/README.md) 簡單 agent；[`playground/`](../../playground/README.md) 是給人玩的遊樂場，設計筆記在 [`proto4/notes/`](../../proto4/notes/)，其餘舊版留著參考 |
| `wf/` | **本工作流系統**（就是你現在在讀的這包）。入口見 [WORKFLOWS.md](../WORKFLOWS.md)；共享區 [workflows/common/](../workflows/common/README.md) |
| `wf/inbox/` | agent 之間的**信件**收件匣：頂層＝未處理、`done/`＝已處理（放信處，保持乾淨；使用方式見 [workflows/inbox/](../workflows/inbox/README.md)）|
| `wf/tools/` | kernel 工具：`wf-lint.sh`（檢查壞連結／錨點／超標檔／條列／殘留）、`tabledb.py`（資料檔 CRUD／連結）、`find_big_lists.py`、`fix_moved_links.py`、`check_anchors.py`；inbox 腳本：`inbox_send.sh`／`inbox_read.sh`（單一收件匣），`inbox_mail.sh`／`inbox_poll.sh`／`inbox_team.sh`／`notify_watch.sh`（五通道升級後才用）；`compact_reload.sh`（compact 後 SessionStart hook 印 user.md＋[HANDOFF](../HANDOFF.md) 最新一條）。資料檔契約見 [common/data-files](../workflows/common/data-files.md) |
| `wf/salvage/` | **`roadmap-run` 打撈包**（2026-08-29）：那條分支跑完 M0→M2 後被凍結、系統要重新架構，這裡是抽出來的教訓與已驗證結論——七篇，給「從零重寫這套系統的人」讀。入口見 [salvage/README](../salvage/README.md) |
| `.claude/commands/` | slash 指令（[`/wf-tick`](../../.claude/commands/wf-tick.md) 驅動定期心跳、[`/wf-lint`](../../.claude/commands/wf-lint.md) 跑文檔檢查）；`.claude/settings.json` 掛 SessionStart（`compact`）hook 跑 `wf/tools/compact_reload.sh`。**必須**放在 repo 根的 `.claude/`，不能收進 `wf/`，否則 Claude Code 讀不到 |
| `reference/` | **移植用的原始碼**，不建置、不安裝（C++ 重寫時對照用），見 [reference/README](../../reference/README.md) |
| `thinking/` | **使用者自己的想法草稿**（下一輪 CLI：`aos-agent`／`aos-inst`／`aos-user`／`aos-tools`），是他的方向、不是定案；討論脈絡在 [proto4/notes §25](../../proto4/notes/24-agent.md) |
| `README.md` | 給人讀的專案總覽 |

> **非侵入式佈局**：頂層只有 `AGENTS.md`、`CLAUDE.md` 兩個 `.md` 入口（加上原本就有的 `README.md`），工作流的其他東西全在 `wf/` 底下，不弄亂原本的 C++ 專案結構。
>
> **之後會照同一個模子長出更多小專案**（例如 `llm/`、`tooljson/`……），各自跟 `core/inst/` 一樣有自己的 `include/`、`src/`、`tests/`、`docs/`，依「拿掉它 aos 還成不成立」放進 `core/` 或 `modules/`，透過同一套 CMake 註冊函式把子命令掛上 `app/`。
