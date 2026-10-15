# INDEX — aos 專案地圖

整個專案的頂層導航。aos = **一個 monorepo：一支執行檔 `aos`，靠子命令把陸續長出來的各個小專案掛上去**（小專案清單見 [core/README](../core/README.md)）。[AGENTS.md](../AGENTS.md) 只放主工作流 + 指向本檔；細節從這裡分流出去。

---

## Repo 佈局

佈局表與說明（每個頂層路徑放什麼、`proto*/` 各代原型、非侵入式佈局）在 [INDEX/01-repo-layout.md](INDEX/01-repo-layout.md)（2026-10-13 tidy：本檔超過 8 KB，整段逐字下放）。

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
| [session_logs/](session_logs/README.md) | SESSION-LOG 搬出的舊條目（按月份全文＋索引；月份檔膨脹再按日拆進 `<月>/`，如 `2026-09/`）|
| [WAIT_USER.md](WAIT_USER.md) | 等使用者親自做 / 驗證 / 拍板的事（只列 open）|
| [HANDOFF.md](HANDOFF.md) | compact 交接：compact 前頂層寫、compact 後 hook 自動讀回最新一條 |

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
| [WAIT_USER](WAIT_USER.md) | 待**使用者**親自做/驗證的入口（10-12 舊帳全清）|
| [`inbox/`](inbox/)（放信處）+ [workflows/inbox/](workflows/inbox/README.md)（使用方式）| agent 之間的**信件**（像 email，狀態靠位置：`inbox/` 頂層＝未處理、`inbox/done/`＝已處理）|
