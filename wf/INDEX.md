# INDEX — aos 專案地圖

整個專案的頂層導航。aos = **一個 monorepo：一支執行檔 `aos`，靠子命令把陸續長出來的各個小專案掛上去**（第一個小專案是 `core/inst/`）。[AGENTS.md](../AGENTS.md) 只放主工作流 + 指向本檔；細節從這裡分流出去。

---

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
| `core/` | **核心小專案**（aos 的基本組成，一定會建）。目前只有 `inst/`：lib `aos::inst`（`libaos_inst.so`）＋ `inst` 子命令。內部分工 → [code map](workflows/common/code-map.md) |
| `modules/` | **擴充小專案**（可選，`-DAOS_BUILD_MODULES=OFF` 整批不建）。目前是空的。新增小專案 → [add-subproject](workflows/add-subproject.md) |
| `docs/` | **整體文件**（給使用者與新加入的人）：總覽、建置、使用、新增小專案，以及最新的 [`aos-core-guide.md`](../docs/aos-core-guide.md)（目前的子命令與建置實況）。入口是 [docs/README.md](../docs/README.md)。**`.aos` 版面與回合模型的規格不在 `docs/`**，唯一真源是 [PROTOCOL](workflows/dispatch/proto/PROTOCOL.md)；階段表在 [`roadmap`](workflows/roadmap.md)。個別小專案自己的細節在它們的 `docs/`，例如 `core/inst/docs/` |
| `wf/` | **本工作流系統**（就是你現在在讀的這包）。入口見 [WORKFLOWS.md](WORKFLOWS.md)；共享區 [workflows/common/](workflows/common/README.md) |
| `wf/inbox/` | agent 之間的**信件**收件匣：頂層＝未處理、`done/`＝已處理（放信處，保持乾淨；使用方式見 [workflows/inbox/](workflows/inbox/README.md)）|
| `wf/tools/` | kernel 工具：`wf-lint.sh`（檢查壞連結／錨點／超標檔／條列／殘留）、`tabledb.py`（資料檔 CRUD／連結）、`find_big_lists.py`、`fix_moved_links.py`、`check_anchors.py`；inbox 腳本：`inbox_send.sh`／`inbox_read.sh`（單一收件匣），`inbox_mail.sh`／`inbox_poll.sh`／`inbox_team.sh`／`notify_watch.sh`（五通道升級後才用）。資料檔契約見 [common/data-files](workflows/common/data-files.md) |
| `wf/salvage/` | **`roadmap-run` 打撈包**（2026-08-29）：那條分支跑完 M0→M2 後被凍結、系統要重新架構，這裡是抽出來的教訓與已驗證結論——七篇，給「從零重寫這套系統的人」讀。入口見 [salvage/README](salvage/README.md) |
| `.claude/commands/` | slash 指令（[`/wf-tick`](../.claude/commands/wf-tick.md) 驅動定期心跳、[`/wf-lint`](../.claude/commands/wf-lint.md) 跑文檔檢查）。**必須**放在 repo 根的 `.claude/`，不能收進 `wf/`，否則 Claude Code 讀不到 |
| `README.md` | 給人讀的專案總覽 |

> **非侵入式佈局**：頂層只有 `AGENTS.md`、`CLAUDE.md` 兩個 `.md` 入口（加上原本就有的 `README.md`），工作流的其他東西全在 `wf/` 底下，不弄亂原本的 C++ 專案結構。
>
> **之後會照同一個模子長出更多小專案**（例如 `llm/`、`tooljson/`……），各自跟 `core/inst/` 一樣有自己的 `include/`、`src/`、`tests/`、`docs/`，依「拿掉它 aos 還成不成立」放進 `core/` 或 `modules/`，透過同一套 CMake 註冊函式把子命令掛上 `app/`。

## 程式碼在哪 → code map

**改程式之前先讀 [workflows/common/code-map.md](workflows/common/code-map.md)**：哪個檔負責什麼領域、要改某件事該動哪幾個檔、測試在哪，全在那一張圖上。本檔只描述「頂層有哪些資料夾」，不描述檔案層級。

## 工作流

工作流的**選擇與入口**見 **[WORKFLOWS.md](WORKFLOWS.md)** 的派發表（本專案合了 **dev、heartbeat、multi-agent** 三個 flavor）。每個工作流的 durable 知識歸在 `workflows/<該工作流>/` 或單檔 `workflows/<該工作流>.md`（含 `archive/` 封存過時文檔），具體流程在各自入口檔。

[STRUCTURE](STRUCTURE.md) 是**被動的結構整理參考**（分層原則、膨脹即拆、四級成長、archive 規則）——**只在要重構／整理結構時取用**。always-on 的**鐵律**在 [AGENTS.md](../AGENTS.md)；碰原始碼的**程式碼慣例 + code map 維護鏈**在 [workflows/common/conventions.md](workflows/common/conventions.md)。

## 頂層文件（`wf/` 這一層）

| 檔案 | 角色 |
|------|------|
| [WORKFLOWS.md](WORKFLOWS.md) | 派發器：意圖 → 工作流入口 |
| [STRUCTURE.md](STRUCTURE.md) | 結構整理參考（被動）|
| [SESSION-LOG.md](SESSION-LOG.md) | 我的 open 進度（hub）|
| [WAIT_USER.md](WAIT_USER.md) | 等使用者親自做 / 驗證 / 拍板的事 |

## 通用（跨工作流共享）

| 路徑 | 內容 |
|------|------|
| [common/README](workflows/common/README.md) | 跨工作流共通的入口 |
| [common/code-map](workflows/common/code-map.md) | **程式碼結構導航圖**（本 flavor 的導航中樞）＋ 真相層優先序 |
| [common/conventions](workflows/common/conventions.md) | 程式碼慣例 + code map 維護鏈 |
| [common/gotchas](workflows/common/gotchas.md) | 跨工作流共通踩坑 |
| [common/user](workflows/common/user.md) | 使用者偏好、確認邊界、時區 |
| [common/data-files](workflows/common/data-files.md) | 資料檔契約 `wf-table/1`（>1 KB 同質記錄表抽 `.json`／`.csv`）|
| [tidy/](workflows/tidy/README.md) | 文件層整理：封存／分類／合併小檔／抽資料檔／拆大檔 |
| [digest/](workflows/digest/README.md) | **精簡版**：把已寫完的紀錄濃縮成使用者本人讀得動的短文（只讀不產）|

## 活狀態（只列還沒完成的）

三軸：進度＝我手上的、待使用者＝卡在人、信件＝agent 之間收發（像 email）。

| 檔案 | 用途 |
|------|------|
| [SESSION-LOG](SESSION-LOG.md) | 進度 hub → 各工作流 session-log（open-only）|
| [WAIT_USER](WAIT_USER.md) | 待**使用者**親自做/驗證的入口（膨脹後拆 `wait-user/` 分類檔）|
| [`inbox/`](inbox/)（放信處）+ [workflows/inbox/](workflows/inbox/README.md)（使用方式）| agent 之間的**信件**（像 email，狀態靠位置：`inbox/` 頂層＝未處理、`inbox/done/`＝已處理）|
