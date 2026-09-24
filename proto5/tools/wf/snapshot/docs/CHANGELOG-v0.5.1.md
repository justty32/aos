# CHANGELOG — v0.5.1 完整條列與升級判準

[docs](README.md)｜[CHANGELOG](../CHANGELOG.md)｜[v0.5](CHANGELOG-v0.5.md)

由 [CHANGELOG](../CHANGELOG.md) 拆出（母檔只留每版摘要與去向）。**本檔是 kernel repo 自用的變動記錄，不隨導入複製到專案。**

## v0.5.1 (2026-09-02)

只動 `tools/`、`workflows/tidy/gotchas.md` 與 multi-agent `team-model.md` 的兩張表，**工作流的流程內容沒動**。

**要不要跟？** 符合任一條就該跟：① repo 裡有 submodule、`vendor/` 或 `reference(s)/`；② md 連結目標寫過 `%20`／`%28`（檔名含空白或括號）；③ `wf-lint` 報的 `broken` 數字大到不合理（曾經超過 255）。都不符合的話行為一樣，可以不動。

**怎麼查自己是哪一版**：版本戳只寫 `v0.5` 的專案分不出有沒有這些修正，改查特徵——

```
grep -ho 'checked_broken\|list_owned_files\|link_exists' <專案>/tools/wf-lint*.sh | sort -u | wc -l
```

**3** ＝ v0.5.1（三項都有）；**2** ＝ v0.5 發布之後、本輪之前的中間版（少 percent-encoding 那條）；**0** ＝ v0.5 發布版。三種狀態實測過。

**怎麼跟**：`tools/` 拆檔後彼此相依，**只能整包覆蓋、不可只挑一支**（`wf-lint.sh` 缺 `wf-lint-checks.sh` 會 `FATAL` 並 exit 2；`tabledb.py` 缺 `tabledb_table.py` 會 ImportError）。

```
cd <kernel>/tools
cp wf-lint.sh wf-lint-checks.sh fmt-vars.json <專案>/tools/
for f in *.py; do case "$f" in test_*) continue;; esac; cp "$f" <專案>/tools/; done
```

非侵入式佈局的目標是 `<專案>/wf/tools/`。覆蓋後跑一次 `tools/wf-lint.sh --strict <專案根>`；**`broken` 數字下降是正常的**（掃描邊界修好、假 `BROKEN` 消失），不是漏檢。

### 逐檔

- 承 v0.5 節末兩條（v0.5 **發布之後**才補進去的）：`broken` 透過 0–255 exit status 傳值造成的計數溢位、掃描排除 `archive/`／`reference(s)/`／`vendor/` 與 `.gitmodules` 宣告的 submodule、`OVERSIZE` 只算 `*/workflows/*`。**還停在 v0.5 發布版的專案這次會一起拿到。**
- `tools/wf-lint.sh`＋新增 `tools/wf-lint-checks.sh` → kernel-owned 覆蓋。修 percent-encoding 誤判：連結目標含空白或括號要寫成 `%20`／`%28`，原本拿原樣字串判存在，存在的檔會被重複報 `BROKEN`；新增 `link_exists()`，原樣找不到且含 `%` 才解碼再判，只判存在、不改寫文件。母檔已抵 8 KB，檢查函式與 `lint_dir` 同時拆到 `wf-lint-checks.sh` 由 `source` 載入——**既有專案要一併複製這支新檔**，`wf-init.sh` 的複製清單與 IMPORT.md 的 kernel-owned 表已納入。`test_wf_lint.py` 加 4 條。
- `workflows/tidy/gotchas.md` → kernel-owned 覆蓋，加「執行環境」段：`command -v` 只判存在不判可執行，假 `python3` shim 會讓 BIGLIST／錨點／資料檔靜默跳過卻仍綠燈；CRLF 的 `.sh` 在 Linux／WSL 跑不動、`wc -c` 每行多 1 byte，8 KB 上限在 Windows 工作區會誤報。
- multi-agent `workflows/team-model.md` 二、三節兩張表 → 預填默認值並標「2026/09/02 由 justty32 給出的個人判斷」，`{{}}` 清空；表仍 project-owned，換自己的模型清單就整張改掉。
- `README.md`（8058→6033）與 `tools/wf-init.sh`（7922→6365）拆檔，兩者都是本 repo 自用、不隨導入複製：README 的 `template/` 逐檔表與 `tools/` 工具表移到新增的 `docs/kernel-contents.md`，母檔留一行去向；`wf-init.sh` 的非侵入式連結改寫（`normalize`／`relpath`／改寫迴圈）移到新增的 `tools/wf-init-relink.sh`，由母檔 `source`，缺檔 FATAL 並 exit 2。順手把 `wf-lint --self` 的 repo 根連結掃描從寫死清單改成掃整個 `docs/*.md`。
- `tools/tabledb.py`（8133→5249）、`tabledb_fmt.py`（7979→6061）、`fix_moved_links.py`（7946→5373）→ kernel-owned 覆蓋。三支都貼著 8 KB 上限，各拆出一支同目錄模組：`Table` 資料模型 → 新增 `tabledb_table.py`；`$fmt` 的變數解析（`context`／`expand`／`names`／`canon`）→ 新增 `tabledb_fmt_expand.py`，`tabledb_fmt` 仍是對外門面；`fix_moved_links` 的掃描與搬移表（`git_root`／`files`／`load_moves`／`remap`／`old_dir_of`）→ 新增 `fix_moved_links_scan.py`，順手把 `scanned()`／`load_moves(specs)` 改成吃 `root` 參數、不再靠模組全域。**公開用法完全不變**（`from tabledb import load`、`tabledb.Table`、`tabledb_fmt.*`），三支新模組隨 `tools/*.py` 自動複製，既有專案覆蓋 `tools/` 時照舊整包拿。
- `AGENTS.md` 版本戳 → **v0.5.1**，project-owned 手動套；既有專案跟完 `tools/` 後一併改，否則下次還是分不出自己是哪一版。`README.md`、`IMPORT.md`、`docs/` 同步。
