← [INDEX](../INDEX.md)｜所在段落：Repo 佈局

## Repo 佈局

本專案自己一個 git repo，remote 是 `git@github.com:justty32/aos.git`。**在兩台機器上開發**，checkout 路徑不同（家裡 Linux／WSL、公司 Windows），所以**文件裡一律用 repo 相對路徑，不要寫死絕對路徑**。「從 repo 根目錄」指的是有 `AGENTS.md` 的那一層（11-05 起根上沒有 CMake）。

| 路徑 | 內容 |
|------|------|
| `proto8/` | **現役本體**（10-11 開的第八版原型；使用者 11-05「我們在proto8內……畢竟是prototype-8」）：C／C++ 的基礎層與標準庫在 `proto8/impls/`（各專案獨立 CMake，建法見 [testing「proto8」](../workflows/testing.md#proto8)），Python／sh 的指令、腦叫的工具、agent 範本在其他夾；概念 CONCEPTS、規範 NORMS、慣例 CONVENTION 在 `proto8/docs/`，討論紀錄在它的 [thinking/](../../proto8/thinking/README.md)，使用者自己的意見稿在 `proto8/user-advice/`（含原 repo 根 `thinking/` 的 09 月草稿，11-05 搬來）。（`proto8-1/` 10-15 深夜併進它的 lib、`proto8-2/` 10-19 併進它，兩個資料夾都已刪，舊 lib 找回用 git 5546be29）。各夾一覽在 [proto8/README](../../proto8/README.md)；內部分工 → [code map](../workflows/common/code-map.md) |
| `archive/` | **封存處**：舊原型 `proto/`～`proto7-2/` 共 20 個 11-04 封存到這裡（使用者 11-04「舊的proto1~7都封存」）；08～09 月那一代單一執行檔 `aos`（根 `CMakeLists.txt`／`core/`／`modules/`／`app/`／`docs/`／`playground/`／`reference/`…）11-05 整組封存成 `aos-v1/`（arch-refactor 方向題 1），索引 [archive/README](../../archive/README.md)。到 10-10 為止的主線是 `proto7-2/`（10-04 起，照使用者建議重做 daemon／tick，之後長出 kernel、agent、`packs/` 工具包與選單包；Python 純標準庫，導覽在它的 INDEX）；`proto7/` 是 10-03 新開的 aos 時空架構（核心 spec，proto7-2 照它做）；`proto7-1/` 是照核心 spec 一路做到 kernel／agent 的 Python 試做，重點是遇到的問題；`proto6/` 是到 10-03 為止的主線（Linux agent 新方向；規格 `spec/`、Python POC `src/py/`、各段狀態 `plan/`，分工見 roadmap）；上一代可執行原型是 `proto5/`（規範先行：`spec/` 規範、`lib/` Python 實作、`cli/` 六支指令 daemon→kernel→cpu＋agent，`notes/` 見 notes 索引；09-24 已納入池式的 `proto5-2/`，那邊只剩規範草稿與筆記當歷史）；`proto5.1/` 是 09-22 的實驗場、只當紀錄；更早的 `proto4-3/` 作業系統層（2026-09-21 凍結當參考）、`proto4-4/` 逐步 lisp、`proto4-5/` LLM 兩層、`proto4-6/` 逐步 JSON／Python／Lua、`proto4-7/` 簡單 agent；playground 的設計筆記在 `proto4/notes/`，其餘舊版留著參考 |
| `wf/` | **本工作流系統**（就是你現在在讀的這包）。入口見 [WORKFLOWS.md](../WORKFLOWS.md)；共享區 [workflows/common/](../workflows/common/README.md) |
| `wf/inbox/` | agent 之間的**信件**收件匣：頂層＝未處理、`done/`＝已處理（放信處，保持乾淨；使用方式見 [workflows/inbox/](../workflows/inbox/README.md)）|
| `wf/tools/` | kernel 工具：`wf-lint.sh`（檢查壞連結／錨點／超標檔／條列／殘留）、`tabledb.py`（資料檔 CRUD／連結）、`find_big_lists.py`、`fix_moved_links.py`、`check_anchors.py`；inbox 腳本：`inbox_send.sh`／`inbox_read.sh`（單一收件匣），`inbox_mail.sh`／`inbox_poll.sh`／`inbox_team.sh`／`notify_watch.sh`（五通道升級後才用）；`compact_reload.sh`（compact 後 SessionStart hook 印 user.md＋[HANDOFF](../HANDOFF.md) 最新一條）。資料檔契約見 [common/data-files](../workflows/common/data-files.md) |
| `wf/salvage/` | **`roadmap-run` 打撈包**（2026-08-29）：那條分支跑完 M0→M2 後被凍結、系統要重新架構，這裡是抽出來的教訓與已驗證結論——七篇，給「從零重寫這套系統的人」讀。入口見 [salvage/README](../salvage/README.md) |
| `.claude/commands/` | slash 指令（[`/wf-lint`](../../.claude/commands/wf-lint.md) 跑文檔檢查；`/wf-tick` 11-05 隨甲代封存）；`.claude/settings.json` 掛 SessionStart（`compact`）hook 跑 `wf/tools/compact_reload.sh`。**必須**放在 repo 根的 `.claude/`，不能收進 `wf/`，否則 Claude Code 讀不到 |
| `README.md` | 給人讀的專案總覽 |

> **非侵入式佈局**：頂層只有 `AGENTS.md`、`CLAUDE.md` 兩個 `.md` 入口（加上 `README.md`），工作流的其他東西全在 `wf/` 底下，程式全在 `proto8/` 底下。
>
> **讀舊紀錄注意**：11-05 以前的 wf 紀錄（日誌、experiments、hackathon、workshop、digest、dispatch 舊交接書）裡講的 `aos run`、`aos deliver`、`build/bin/aos`、`core/…`、`.aos/` 版面，都是甲代（現在在 `archive/aos-v1/`）；proto8 的指令是 `aos-exec`、`aos-loop`、`aos-fsm`、`aos-daemon`… 這類一支一個名字的。
