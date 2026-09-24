# CHANGELOG — kernel 變動記錄

每次 kernel（`template/`）或導入契約變動記一節：改了哪檔、**既有專案要不要跟**。本檔只留**每版摘要與去向**，完整條列拆在 `docs/`——變動記錄只會長不會短，留在母檔一定會撞 8 KB 上限。版本戳在 `template/AGENTS.md` 尾端 `<!-- wf-kernel vX.Y (日期) -->`，導入後 `grep wf-kernel AGENTS.md` 查自己是哪一版。kernel-owned / project-owned 分類見 [IMPORT.md](IMPORT.md)。

## 未發布

lint：`done/`／`superseded/` 與放信的 `inbox/`（頂層＋`done/`；`workflows/inbox/` 照掃）比照 `archive/` 封存不下鑽——信件是寄件原文不該改，BIGLIST／壞連結／錨點都不掃，`inbox_pending` 照數；STRUCTURE archive 規則補一句；測試拆出 `test_wf_lint_scope.py`（掃描範圍）。來自 paper_readings、engineer_study 導入回饋。**既有專案要跟**：`tools/` 整包覆蓋（本 repo 自用的 `wf/tools/` 已同步），engineer_study 可拿掉自家 `lint.sh` 過濾 `^BIGLIST inbox/done/` 的包裝。

## v0.6 (2026-09-02)

`skills/` 進契約：新增頂層 agent skill 資料夾，與 `template/`／`flavors/` 平行，8 KB 上限一體適用。8 個技能——本 repo 自有兩個（CC0）＋ vendor 自 effective-html 六個（MIT），本 repo 因此變**混合授權**，授權全文在 `skills/LICENSES/`。不 vendor 的產品向外部技能（`dashi-ppt-skill`、`archify`）改以 git submodule 掛在 `skills/external/`，授權維持上游、豁免 8 KB 契約，`--skills`（含 `all`）不觸碰它，要用自己 `git submodule update --init`。`wf-init.sh` 加 `--skills a,b|all`：複製到 `<wfroot>/skills/`，並在專案根 `.claude/skills/<name>/` 產轉址 `SKILL.md` 供 Claude Code 自動發現；skills 可選、不進 `WORKFLOWS.md` 派發表。`wf-lint.sh --self` 加對 `skills/` 的連結／錨點檢查（BIGLIST／`$fmt` 檢查跳過該目錄）。kernel 新增 `workflows/common/reply-style.md`（對話回覆風格），`common/README.md` 導覽表與 `user.md` 回覆風格欄同步指向它。另**文檔精簡**（工作流語意沒動）：kernel 的 `tidy/README.md` 不再重述 STRUCTURE、`common/gotchas.md` 與 `common/user.md` 補齊 TEMPLATE 段落；七個 flavor README 的通用導入步驟改連 `IMPORT.md`。既有專案要跟的只有 kernel 那幾檔。

**完整條列與升級判準**：[docs/CHANGELOG-v0.6.md](docs/CHANGELOG-v0.6.md)。

## v0.5.1 (2026-09-02)

檢查器的修正版，**工作流內容沒動**。四個 bug：`broken` 計數溢位、掃描沒排除 submodule／`vendor/`／`reference(s)/`、`OVERSIZE` 範圍、連結目標 percent-encoding 誤判（存在的檔被重複報 `BROKEN`）。`tools/` 因為 8 KB 上限拆成多檔（新增 `wf-lint-checks.sh`、`tabledb_table.py`、`tabledb_fmt_expand.py`、`fix_moved_links_scan.py`，公開用法不變）——**拆完彼此相依，要跟就整包覆蓋 `tools/`**。另加 `workflows/tidy/gotchas.md` 的「執行環境」段。

**完整條列與升級判準（含怎麼查自己是哪一版）**：[docs/CHANGELOG-v0.5.1.md](docs/CHANGELOG-v0.5.1.md)。

## v0.5 (2026-08-30)

來源專案一輪整理長出的通用做法回抽進 kernel：tidy 升成資料夾並附踩坑與管理線簡報、`WORKFLOWS.md` 加「可以跳流程」、`WAIT_USER` 拆法定死、`wf-lint` 加 `#錨點` 檢查；dev 包補 moving-things（搬檔六類斷裂）、「綠燈不等於有檢查」、真相層優先序，以及 analysis／patch 兩個可選工作流。

**完整條列**：[docs/CHANGELOG-v0.5.md](docs/CHANGELOG-v0.5.md)。

## v0.4.1 (2026-08-30) 與更早

見 [docs/CHANGELOG-history.md](docs/CHANGELOG-history.md)。
