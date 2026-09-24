# CHANGELOG — 舊版本（v0.4.1 及更早）

本檔由 [CHANGELOG](../CHANGELOG.md) 拆出（母檔只留每版摘要與去向）；現行版本的完整條列在 [CHANGELOG-v0.5](CHANGELOG-v0.5.md)。**本檔是 kernel repo 自用的變動記錄，不隨導入複製到專案。**

## v0.4.1 (2026-08-30)

**md 不再教查法。** 資料檔契約拿掉三行查法。`wf-lint` 新增 `QUERYCMD`，`--strict` 時算失敗。既有專案套完清掉所報行。**完整條列**：`git show a104604:CHANGELOG.md`。

## v0.4 (2026-08-30)

json 資料檔的路徑值可寫成 `$fmt` 代號（`${fileDirname}`／`${gitRoot}`／`${gitParent}`／`${gitTop}`／`${env:NAME}`，讀取時展開），省去深層 `../../../`；契約仍 `wf-table/1`，附錄 `workflows/common/data-files-fmt.md`。`tabledb.py`（新指令 `fmt`）、`tabledb_links.py`、`fix_moved_links.py` 與 `tabledb_fmt*.py`、`tools/fmt-vars.json`（契約 `wf-fmt-vars/1`，解析器不寫死變數名）→ kernel-owned；專案自加變數放 `tools/fmt-vars.local.json`（project-owned）。**手動覆蓋 .py 升級的專案要一併複製 `fmt-vars.json`**。既有 json 不必改，≥ 2 個 `../` 的路徑建議改 `$fmt`。**完整條列**：`git show a104604:CHANGELOG.md`。

## v0.3 (2026-08-30)

文件整理工具進 kernel：`wf-table/1` 資料檔契約、tidy 工作流、`tabledb.py`／`find_big_lists.py`／`fix_moved_links.py`；同質記錄表 >1 KB 才抽，導航連結表留 md。完整條列：`git show a104604:CHANGELOG.md`。

## v0.2 (2026-08-29) 與更早

v0.2 全面重構分層、flavor、授權與工具中立契約；v0.1 是未拆 heartbeat／multi-agent 的早期 kernel。**完整條列**：`git show a2a4077:CHANGELOG.md`。
