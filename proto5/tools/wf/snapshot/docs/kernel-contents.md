# kernel 與 tools 的內容清單

[docs](README.md)｜[repo README](../README.md)

本檔由 [repo README](../README.md) 拆出（母檔抵 8 KB 上限）：`template/` 裡有哪些檔、`tools/` 裡有哪些工具。挑 flavor 包與導入流程仍在母檔。`skills/` 的內容清單在 [skills/README.md](../skills/README.md)，不在本檔。

## template/（kernel）內容

| 檔案 | 角色 |
|------|------|
| [AGENTS.md](../template/AGENTS.md) | 最頂層路由器（≈1.5 KB）：開場 checklist＋入口＋鐵律 |
| [CLAUDE.md](../template/CLAUDE.md) | 轉址 → AGENTS.md |
| [WORKFLOWS.md](../template/WORKFLOWS.md) | 派發器：flavor 派發表貼入區＋kernel 內建表＋活狀態判別表 |
| [INDEX.md](../template/INDEX.md) | 結構地圖 |
| [STRUCTURE.md](../template/STRUCTURE.md) | 被動結構參考：分層、膨脹即拆、四級成長、archive |
| [SESSION-LOG.md](../template/SESSION-LOG.md) | open 進度 |
| [WAIT_USER.md](../template/WAIT_USER.md) | 等使用者做／驗證的事（open-only）|
| [workflows/TEMPLATE.workflow.md](../template/workflows/TEMPLATE.workflow.md) | 新工作流入口檔骨架 |
| [workflows/planning.md](../template/workflows/planning.md) | idea → roadmap → 詳規 → 執行 管線 |
| [workflows/decisions.md](../template/workflows/decisions.md) | 為什麼選 A 不選 B |
| [workflows/tidy/](../template/workflows/tidy/README.md) | 文件整理：封存／分類／合併小檔／抽資料檔／拆大檔；附 `gotchas.md` 踩坑與 `manager-brief.md` 管理線簡報 |
| [workflows/common/](../template/workflows/common/README.md) | 共享：gotchas、user、glossary、data-files |
| [workflows/common/reply-style.md](../template/workflows/common/reply-style.md) | 對話回覆風格：先講結論、一步一動作、何時可以破例 |
| [workflows/common/data-files.md](../template/workflows/common/data-files.md) | 資料檔契約 `wf-table/1` |
| [data-files-fmt.md](../template/workflows/common/data-files-fmt.md) | `$fmt` 代號 |
| [.claude/commands/wf-lint.md](../template/.claude/commands/wf-lint.md) | `/wf-lint` 薄殼（Claude Code 適配層）|

## tools/

| 工具 | 做什麼 |
|------|--------|
| `wf-init.sh` | 導入：複製 kernel、合入 flavor 包、非侵入式改寫連結（改寫那段在 `wf-init-relink.sh`）；`--skills` 裝 agent skill 並產 `.claude/skills/` 轉址（邏輯在 `wf-init-skills.sh`）|
| `wf-lint.sh` | 檢查：壞連結與錨點／超標檔／條列／資料檔連結／殘留；檢查函式在 `wf-lint-checks.sh` |
| `check_anchors.py` | 驗 md 連結的 `#錨點`（heading slug 與顯式 id）在目標檔存不存在 |
| `tabledb.py` | 資料檔 CRUD 與連結查驗；`Table` 在 `tabledb_table.py`，連結在 `tabledb_links.py`，`$fmt` 在 `tabledb_fmt*.py` |
| `find_big_lists.py` | 列出超標的表／清單，附連結數判斷是不是連結表 |
| `fix_moved_links.py` | 搬檔後照 `moves.tsv` 重寫連結；掃描與搬移表在 `fix_moved_links_scan.py`，`$fmt` 那半段在 `fix_moved_links_fmt.py` |
