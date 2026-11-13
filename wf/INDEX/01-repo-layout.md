← [INDEX](../INDEX.md)｜所在段落：Repo 佈局

## Repo 佈局

本專案自己一個 git repo，remote 是 `git@github.com:justty32/aos.git`。**在兩台機器上開發**，checkout 路徑不同（家裡 Linux／WSL、公司 Windows），所以**文件裡一律用 repo 相對路徑，不要寫死絕對路徑**。「從 repo 根目錄」指的是有 `AGENTS.md` 的那一層（根上沒有 CMake）。

| 路徑 | 內容 |
|------|------|
| `proto8/` | **現役本體**（第八版原型；使用者 11-05「我們在proto8內……畢竟是prototype-8」）：C／C++ 的基礎層與標準庫在 `proto8/impls/`（各專案獨立 CMake，建法見 [testing「proto8」](../workflows/testing.md#proto8)），Python／sh 的指令在 `proto8/cmd/`（共用模組 `proto8/py/`）、腦叫的工具在 `proto8/lib/`、掛在 daemon 上的管理元件在 `proto8/kernel/`、agent 範本在 `proto8/templates/`；概念 CONCEPTS、規範 NORMS、慣例 CONVENTION 在 `proto8/docs/`，討論紀錄在它的 [thinking/](../../proto8/thinking/README.md)，使用者自己的意見稿在 `proto8/user-advice/`（含 09 月的草稿）。各夾一覽在 [proto8/README](../../proto8/README.md)；內部分工 → [code map](../workflows/common/code-map.md) |
| `impl_cpp/` | **使用者手寫重寫的 C++ 實作**（大修；C++23、骨架取自 `archive/aos-v1/`、一個零件一夾在 `core/<零件>/`，自成一體不 include proto8）。環境怎麼建、跑、除錯看 [impl_cpp/README](../../impl_cpp/README.md)；核心程式由使用者自己寫，agent 只動環境 |
| `archive/` | **封存處**：舊原型 `proto/`～`proto7-2/` 共 20 個（使用者 11-04「舊的proto1~7都封存」），與 08～09 月那一代單一執行檔 `aos`（根 `CMakeLists.txt`／`core/`／`modules/`／`app/`／`docs/`／`playground/`／`reference/`…）整組封存成的 `aos-v1/`（arch-refactor 方向題 1）；各版是什麼看索引 [archive/README](../../archive/README.md)。凍結，不再建、不再維護 |
| `wf/` | **本工作流系統**（就是你現在在讀的這包）。入口見 [WORKFLOWS.md](../WORKFLOWS.md)；共享區 [workflows/common/](../workflows/common/README.md) |
| `wf/inbox/` | agent 之間的**信件**收件匣：頂層＝未處理、`done/`＝已處理（樹外專案的放信處，保持乾淨；使用方式見 [workflows/inbox.json](../workflows/inbox.json)）|
| `wf/tools/` | kernel 工具：`tabledb.py`（資料檔 CRUD／連結）、`find_big_lists.py`、`fix_moved_links.py`、`check_anchors.py`（inbox 收發腳本 11-13 刪掉，改走 aos 信箱，見 [inbox.json](../workflows/inbox.json)）；`compact_reload.sh`（compact 後 SessionStart hook 印 user.md＋[HANDOFF](../HANDOFF.md) 最新一條）。資料檔契約見 [common/data-files](../workflows/common/data-files.md) |
| `wf/salvage/` | **`roadmap-run` 打撈包**（2026-08-29）：那條分支跑完 M0→M2 後被凍結、系統要重新架構，這裡是抽出來的教訓與已驗證結論——七篇，給「從零重寫這套系統的人」讀。入口見 [salvage/README](../salvage/README.md) |
| `.claude/` | `.claude/settings.json` 掛 SessionStart（`compact`）hook 跑 `wf/tools/compact_reload.sh`。**必須**放在 repo 根的 `.claude/`，不能收進 `wf/`，否則 Claude Code 讀不到 |
| `README.md` | 給人讀的專案總覽 |

> **非侵入式佈局**：頂層只有 `AGENTS.md`、`CLAUDE.md` 兩個 `.md` 入口（加上 `README.md`），工作流的其他東西全在 `wf/` 底下，程式全在 `proto8/` 底下。
>
> **讀舊紀錄注意**：11-05 以前的 wf 紀錄（日誌、experiments、hackathon、workshop、digest、dispatch 舊交接書）裡講的 `aos run`、`aos deliver`、`build/bin/aos`、`core/…`、`.aos/` 版面，都是甲代（現在在 `archive/aos-v1/`）；proto8 的指令是 `aos-exec`、`aos-loop`、`aos-fsm`、`aos-daemon`… 這類一支一個名字的。
