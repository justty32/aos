# tools/wf — workflows 工具包

← [tools README](../README.md)｜規格：[catalog T-wf](../../notes/2026-09-24-tool-era/catalog.md#t-wf)

讓 agent 把 workflows（`~/repo/workflows`）那套手冊導入一個專案、檢查導得乾不乾淨。五支工具**都不叫模型**，只跑本包自帶的**固定版本快照**（`snapshot/`），不跑專案裡的任何程式。

## 裝

```sh
aos-agent tools add wf --target $W/bob                  # 工作根目錄＝$W/bob/workspace/
aos-agent tools add wf --target $W/bob --root ~/proj    # 專案在別處
```

根目錄照 base 同一套算法（`_common.py` 是 base 那份的逐字副本）：關牢時是牢裡的起點（`AOS_TOOL_ROOT`），不關牢時看本包 `config.json` 的 `root`。關牢時整包（含快照）被唯讀掛到 `/opt/tool`，照樣跑得動。

## 五支

| 工具 | 一句話 | 參數 |
|---|---|---|
| `wf_doc` | 唯讀讀快照裡的手冊；不給路徑＝列目錄。讀不到快照外（`OutsideRoot`） | `path`、`offset`、`limit` |
| `wf_init` | 把 workflows 導入專案（staging 先做，見下）；回導入了幾個檔＋殘留清單 | `flavor`（陣列，例 `["heartbeat"]`）*、`non_invasive`（子資料夾名，例 `"wf"`；省略＝標準佈局）、`path`（預設 `.`） |
| `wf_lint` | 用**快照裡的** `wf-lint.sh` 檢查專案；第一行 `PASS`／`FAIL (exit N)`，再來 `TOTAL`、`SUMMARY`、前 50 條問題；全文存 `<專案>/.wf-lint.log` | `strict`（預設 true）、`path` |
| `wf_residue` | 數專案所有 `.md` 裡的 `{{`、〔導入判斷〕、〔模板說明〕（出現次數，跟 wf-lint 同算法），列 `檔:行`；讀不到的檔另列 `UNREADABLE`，不當成 0 | `path` |
| `wf_table` | 用快照的 `tabledb.py` 讀寫 `wf-table/1` 資料檔（.json／.csv），原樣回 JSON；`open` 不開放 | `file`*、`op`*（info／get／find／grep／add／update／delete／columns／slice／links／check／resolve／fmt）、`index`、`fields`（欄→字串）、`regex`、`start`、`end`、`column` |

給模型的描述五支合計 777 字元（description＋參數說明）。`wf_init`、`wf_lint` 的 `_timeout_ms` 是 180000。

`wf_residue` 的範圍照 IMPORT.md 的 grep（所有 `.md`，只跳過 `.git`、`.wf-staging-*`、`.wf-backup-*`，不跟符號連結）；`wf-lint` 會另外跳過 `archive/`、`inbox/` 等封存區，所以兩邊數字在有封存區的專案可能不同。

## wf_init 怎麼做到「砍了重跑就好」

1. 在專案裡開 `.wf-staging-<id>/tree/`（放專案**裡面**：關牢時專案常是掛載點，整個資料夾換不過去），在那裡跑快照的 `wf-init.sh --quiet`。失敗或逾時＝刪 staging，專案一個字都沒動。
2. 成功：寫 `commit.json`（要搬的檔清單），再一個個 `rename` 進專案。專案裡已有同名檔就先挪進 `.wf-backup-<id>/`（原檔不會丟）。**`AGENTS.md` 最後搬**——它在＝導入完成。
3. 重跑同一行時先收拾上次的：有 `commit.json` 的 staging＝往前做完；沒有的＝丟掉重來。專案已有 `AGENTS.md`、又沒有沒做完的 staging＝`AlreadyImported`（跟 wf-init 一樣不覆蓋既有導入）。

另外兩道檢查：要搬進去的路徑途中有符號連結＝`UnsafePath`（不寫穿連結）；wf-init 把 staging 的絕對路徑寫進檔＝`InitFailed`（搬過去會指到已刪的地方）。不支援 `--skills`（快照沒帶 skills 本體）。
被蓋掉的舊檔留在 `.wf-backup-<id>/`，裡面的 `.md` 會被 wf-lint 掃到；看過沒問題就刪掉。

## 快照

`snapshot/` 是 `~/repo/workflows` 某個 commit 的 `tools/`（不含測試）、`template/`、`flavors/`、`docs/`、`IMPORT.md`、`README.md`、`CHANGELOG.md`、`skills/README.md`，共 136 檔、約 0.9 MB。版本記在 `snapshot/SNAPSHOT.json`（現在是 `2021d9b`、kernel v0.6）。
更新（人做）：`tools/wf/update-snapshot.sh <commit> [workflows repo]`——一律用 `git archive` 從 commit 取，不抄工作樹；換完跑 `test_tools_wf.py`（它寫死了 commit，要一起改）。已裝的 agent 要 `tools add wf --force` 才會換到新快照。

## 給別隊的 Python 介面（T2 驗收員用）

```python
import sys; sys.path.insert(0, '<proto5>/tools/wf'); import _wf
_wf.residue(project_dir)   # {'total', 'counts': {'{{', '〔導入判斷〕', '〔模板說明〕'}, 'hits': [(檔, 行, 記號)], 'unreadable': [(檔, 原因)]}
_wf.lint(project_dir, strict=True)   # {'exit', 'ok', 'total_line', 'summaries', 'problems', 'output'}；給 log_path 才寫檔
```

兩個都不改專案、不叫模型，只跑快照裡的程式。Done when 可以寫成 `residue(p)['total'] == 0 and not residue(p)['unreadable'] and lint(p)['ok']`。

## 錯誤代號

成功純文字退 0；失敗最後一行 `{"ok": false, "error": …, "message": …}` 退 1。

| 代號 | 什麼時候 |
|---|---|
| `BadArguments` | 參數型別不對、flavor 不存在（訊息列出有哪些）、`non_invasive` 不是單純資料夾名、table 的 op 缺 `index`／`fields`、檔不是 .json／.csv |
| `OutsideRoot` | 路徑出了工作根目錄；`wf_doc` 出了快照 |
| `NotFound`／`NotADirectory` | 路徑不在；給的是檔不是專案資料夾 |
| `AlreadyImported` | 專案已導入過（有 `AGENTS.md`） |
| `UnsafePath` | 要寫的路徑途中是符號連結 |
| `InitFailed` | 快照的 wf-init 自己失敗（附它最後一行）；專案沒動 |
| `TableFailed` | tabledb 失敗（附它最後一行，例如 IndexError） |
| `Timeout`／`SpawnFailed`／`WriteFailed` | 跑太久；叫不起 bash／python3；寫檔失敗（wf_init 的話重跑同一行收尾） |
| `RootMissing`／`ConfigInvalid`／`InternalError` | 同 base |

測試：[`lib/test/test_tools_wf.py`](../../lib/test/test_tools_wf.py)（含兩個真 SIGKILL 的崩潰窗口：wf-init 跑到一半、搬檔搬到一半）。
