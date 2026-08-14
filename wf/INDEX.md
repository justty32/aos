# INDEX — aos 專案地圖

整個專案的頂層導航。aos = **一個常駐的 Unix Domain Socket daemon（`aos-daemon`）＋一支很薄的 CLI（`aos`）**。[AGENTS.md](../AGENTS.md) 只放主工作流 + 指向本檔；細節從這裡分流出去。

---

## Repo 佈局

專案根目錄是 `/home/lorkhan/repo/simple_tools/aos`（自己一個 git repo，remote 是 `git@github.com:justty32/aos.git`）。

| 路徑 | 內容 |
|------|------|
| `include/aos/` | 對外公開的標頭（`aos_core` 的 PUBLIC include 目錄）。哪個標頭放什麼 → [code map](workflows/common/code-map.md) |
| `src/` | 實作。`src/core/` 是共用函式庫 `aos_core`，`src/cli/`、`src/daemon/` 是兩個 `main`。詳細分工 → [code map](workflows/common/code-map.md) |
| `tests/` | 三支測試：`protocol_test.cpp`、`streaming_test.cpp`、`e2e.sh`（跑法見 [workflows/testing.md](workflows/testing.md)）|
| `docs/` | 給人讀的程式碼導覽與 C++ 筆記，**由另一個 agent 維護**（入口 [docs/README.md](../docs/README.md)；本工作流只連過去、不動它）|
| `CMakeLists.txt`、`CMakePresets.json`、`vcpkg.json` | 建置設定：CMake 3.25+、Ninja、C++23、vcpkg manifest |
| `README.md` | 給人讀的專案總覽（用法、協定、建置）|
| `bin/`、`build/`、`.cache/` | 產物與建置暫存，已在 `.gitignore` 裡 |
| `.vscode/` | IntelliSense 指到 `build/compile_commands.json` 的設定 |
| `wf/` | **本工作流系統**（就是你現在在讀的這包）。入口見 [WORKFLOWS.md](WORKFLOWS.md) |
| `wf/inbox/` | agent 之間的**信件**收件匣（放信處，保持乾淨；使用方式見 [workflows/inbox/](workflows/inbox/README.md)）|
| `.claude/commands/` | slash 指令（[`/wf-tick`](../.claude/commands/wf-tick.md) 驅動定期心跳）。**必須**放在 repo 根的 `.claude/`，不能收進 `wf/`，否則 Claude Code 讀不到 |

> **非侵入式佈局**：頂層只有 `AGENTS.md`、`CLAUDE.md` 兩個 `.md` 入口（加上原本就有的 `README.md`），工作流的其他東西全在 `wf/` 底下，不弄亂原本的 C++ 專案結構。

## 程式碼在哪 → code map

**改程式之前先讀 [workflows/common/code-map.md](workflows/common/code-map.md)**：哪個檔負責什麼領域、要改某件事該動哪幾個檔、測試在哪，全在那一張圖上。本檔只描述「頂層有哪些資料夾」，不描述檔案層級。

## 工作流

工作流的**選擇與入口**見 **[WORKFLOWS.md](WORKFLOWS.md)** 的派發表（本專案用的是**開發 flavor**）。每個工作流的 durable 知識歸在 `workflows/<該工作流>/` 或單檔 `workflows/<該工作流>.md`（含 `archive/` 封存過時文檔），具體流程在各自入口檔。

[DEV-GUIDE](DEV-GUIDE.md) 是**被動的結構整理參考**（結構整理原則 + 四級成長軌跡）——**只在要重構／整理結構時取用**。always-on 的**鐵律**在 [AGENTS.md](../AGENTS.md)；碰原始碼的**程式碼慣例 + code map 維護鏈**在 [workflows/common/conventions.md](workflows/common/conventions.md)。

## 通用（跨工作流共享）

| 路徑 | 內容 |
|------|------|
| [common/README](workflows/common/README.md) | 跨工作流共通的入口 |
| [common/code-map](workflows/common/code-map.md) | **程式碼結構導航圖**（本 flavor 的導航中樞）|
| [common/conventions](workflows/common/conventions.md) | 程式碼慣例 + code map 維護鏈 |
| [common/gotchas](workflows/common/gotchas.md) | 跨工作流共通踩坑 |

## 活狀態（只列還沒完成的）

三軸：進度＝我手上的、待使用者＝卡在人、信件＝agent 之間收發（像 email）。

| 檔案 | 用途 |
|------|------|
| [SESSION-LOG](SESSION-LOG.md) | 進度 hub → 各工作流 session-log（open-only）|
| [WAIT_USER](WAIT_USER.md) | 待**使用者**親自做/驗證的入口（膨脹後拆 `wait_todo/` 分類檔）|
| [`inbox/`](inbox/)（放信處）+ [workflows/inbox/](workflows/inbox/README.md)（使用方式）| agent 之間的**信件**（像 email，狀態靠位置：`inbox/` 頂層＝未處理、`inbox/done/`＝已處理）|
