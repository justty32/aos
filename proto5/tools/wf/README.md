# tools/wf — workflows 工具包

← [tools README](../README.md)｜規格：[catalog T-wf](../../notes/2026-09-24-tool-era/catalog.md#t-wf)

讓 agent 把 workflows（`~/repo/workflows`）那套手冊導入專案、檢查導得乾不乾淨。六支都**不叫模型**，只跑本包自帶的**固定版本快照**（`snapshot/`），不跑專案裡的程式。

## 裝

```sh
aos-agent tools add wf --target $W/bob                  # 工作根目錄＝$W/bob/workspace/
aos-agent tools add wf --target $W/bob --root ~/proj    # 專案在別處
```

根目錄跟 base 同一套（`_common.py` 是 base 那份的逐字副本）：關牢看 `AOS_TOOL_ROOT`，不關牢看本包 `config.json` 的 `root`。關牢時整包（含快照）唯讀掛在 `/opt/tool`，照樣能跑。

## 六支

| 工具 | 一句話 | 參數 |
|---|---|---|
| `wf_doc` | 唯讀讀快照裡的手冊；不給路徑＝列目錄；讀不到快照外 | `path`、`offset`、`limit` |
| `wf_init` | 導入 workflows（先在 staging 做，見下）；回導入幾個檔＋殘留清單 | `flavor`*（例 `["heartbeat"]`）、`non_invasive`（例 `"wf"`；省略＝標準佈局）、`path` |
| `wf_fill` | （第二波 A 隊）照事實表機械填 `{{…}}`、刪〔模板說明〕；（選）刪範例區塊、範本列；對不上的不猜，列出來附原因（見下） | `facts`（事實 JSON 檔，省略＝專案的 `facts.json`）、`values`（多給的事實）、`drop_examples`、`drop_template_rows`、`dry_run`、`path` |
| `wf_lint` | 用**快照裡的** `wf-lint.sh` 檢查；回 `PASS`／`FAIL (exit N)`、`TOTAL`、`SUMMARY`、前 50 條問題；全文存 `<專案>/.wf-lint.log` | `strict`（預設 true）、`path` |
| `wf_residue` | 數所有 `.md` 裡的 `{{`、〔導入判斷〕、〔模板說明〕，列 `檔:行`；讀不到的另列 `UNREADABLE`、不當 0 | `path` |
| `wf_table` | 用快照的 `tabledb.py` 讀寫 `wf-table/1` 資料檔，原樣回 JSON（不開放 `open`） | `file`*、`op`*、`index`、`fields`、`regex`、`start`、`end`、`column` |

描述六支合計 1093 字元（加 wf_fill 之前五支 777）；`wf_init`、`wf_lint` 的 `_timeout_ms`＝180000。

## wf_fill：照事實表填，不猜

規則寫死在 [`_fill.py`](_fill.py) 開頭，改了要改測試（[`test_tools_wf_fill.py`](../../lib/test/test_tools_wf_fill.py)）：

- **佔位的名字**＝`{{ }}` 裡去掉例子那段（「，如…」「，例…」「例：…」「；…」「：…」之後都不算）；表格列另外拿第一格的字當第二個名字。
- **跟事實表的鍵比**，一層一層來：一樣 → 同義詞表（例如「一句話描述」＝「專案一句話」、「測試 / build / lint 指令」＝「驗證指令」）→ 一邊包含另一邊（至少兩個字）。每一層**恰好一條**才填；兩條以上＝不填，列「more than one fact looks like it」。
- **範本列**（第一格整格是佔位，例如 INDEX 的 `{{src/ 或主要產出目錄}}`）：整列都不填；`drop_template_rows` 才整列刪。
- 事實值是「今天…」或 `today`：換成今天的日期（照事實表的時區）。
- 〔模板說明〕一律刪（整段引用，IMPORT.md 第 4 步）。
- `drop_examples`：講「範例」的〔導入判斷〕，認得出範圍的才刪——上方表格第一格是「（範例）」的列，或底下「下面…」指的 `###` 小節（到下一個同級以上標題）——連同那段判斷一起刪。認不出的不動、列出來。
- 輸出：填了哪幾條（事實＝值 → 檔:行）、還剩哪些佔位（附原因）、還剩哪些〔…〕、**沒用到的事實**（常常就是「剩下的怎麼辦」的答案）、可以加的選項。
- 跟 `wf_init` 同一把專案鎖（拿不到＝`Busy`）；每個檔暫存檔＋rename；再跑一次什麼都不動。
- heartbeat 包＋T5 的 `facts.json`：一次 `wf_fill {"drop_examples": true, "drop_template_rows": true}` 就殘留 0、`wf_lint` PASS（填 16 個、刪 5 段說明、3 段範例、2 列範本列）。
`wf_residue` 照 IMPORT.md 的 grep 掃所有 `.md`（只跳過 `.git`、`.wf-staging-*`、`.wf-backup-*`）；wf-lint 另外跳過 `archive/`、`inbox/` 等，有封存區時兩邊數字會不同。

## wf_init：砍了重跑同一行就好

1. 在專案**裡**開 `.wf-staging-<id>/tree/`（關牢時專案常是掛載點，不能整個換），在那裡跑快照的 `wf-init.sh --quiet`。失敗或逾時＝刪 staging，專案沒動。
2. 成功：寫 `commit.json`（搬檔清單），一個個 `rename` 進專案；已有同名檔先挪進 `.wf-backup-<id>/`。**`AGENTS.md` 最後搬**（它在＝導入完成）。
3. 重跑時先收拾：有 `commit.json` 的 staging＝往前做完；沒有的＝丟掉重來。已有 `AGENTS.md` 又沒有待完成的＝`AlreadyImported`。
4. 第 3 步到搬完整段 `flock` 專案資料夾本身（不建鎖檔）；同時來第二個＝立刻 `Busy`。

`commit.json` 模型的 bash 改得到，所以**當不可信輸入**：`id` 對上資料夾名、`backup` 只能是 `.wf-backup-<id>`、路徑要相對、不含 `..`、`normpath` 不變、不指到 staging／backup；來源要真的在 `tree/` 裡；目的地與備份途中不能有符號連結。不過＝`BadJournal`／`UnsafePath`，**不寫也不刪**，請人看過再刪那個 staging。
wf-init 把 staging 絕對路徑寫進檔＝`InitFailed`。不支援 `--skills`。`.wf-backup-*` 裡的 `.md` 會被 wf-lint 掃到，看過就刪。

**環境**：跑快照程式時清掉 `PYTHONPATH`、`PYTHONSTARTUP`、`PYTHONHOME`、`BASH_ENV`、`ENV` 等，設 `PYTHONNOUSERSITE`；tabledb 用 `python3 -E -s`（`-I` 會拿掉腳本目錄，tabledb 就 import 不到自己）。cwd（專案）不在 `sys.path`，專案裡的 `.py` 不會被載入。
專案的 `fmt-vars.local.json` 會被 tabledb 讀來合併 `$fmt` 變數表，只是資料（算法固定幾種），不會被執行。wf-lint 會對專案跑唯讀的 `git rev-parse`／`git config --file .gitmodules`。

## 快照

`~/repo/workflows` 某個 commit 的 `tools/`（不含測試）、`template/`、`flavors/`、`docs/`、`IMPORT.md`、`README.md`、`CHANGELOG.md`、`skills/README.md`：136 檔、約 0.9 MB，版本在 `snapshot/SNAPSHOT.json`（`2021d9b`、kernel v0.6）。
更新（人做）：`tools/wf/update-snapshot.sh <commit> [repo]`，一律 `git archive`，不抄工作樹；`test_tools_wf.py` 寫死了 commit，要一起改。已裝的 agent 要 `tools add wf --force`。

## 給別隊的 Python 介面（T2 驗收員）

```python
import sys; sys.path.insert(0, '<proto5>/tools/wf'); import _wf
_wf.residue(p)   # {'total', 'counts', 'hits': [(檔, 行, 記號)], 'unreadable': [(檔, 原因)]}
_wf.lint(p, strict=True)   # {'status', 'exit', 'ok', 'total_line', 'summaries', 'problems', 'output'}
```

`status` 三態：`pass`（退 0 且有 TOTAL）、`fail`（退 1 且有 TOTAL）、`error`（檢查器本身壞了：退出碼不是 0／1 或沒 TOTAL；**不算通過也不算不通過**）。`error` 不 raise；只有逾時、叫不起 bash 才 raise `_wf.WfError`。都不改專案（`lint` 給 `log_path` 才寫那個檔）。
Done when 例：`residue(p)['total'] == 0 and not residue(p)['unreadable'] and lint(p)['status'] == 'pass'`。

## 錯誤代號

成功純文字退 0；失敗最後一行 `{"ok": false, "error": …, "message": …}` 退 1。

| 代號 | 什麼時候 |
|---|---|
| `BadArguments` | 型別不對、flavor 不存在（列出有哪些）、`non_invasive` 不是單純資料夾名、table 缺 `index`／`fields`、不是 .json／.csv；wf_fill 的事實檔不是 JSON 物件、`values` 不是物件、沒有可用的事實 |
| `OutsideRoot`／`NotFound`／`NotADirectory` | 出了根目錄（`wf_doc`：出了快照）；路徑不在；不是資料夾 |
| `AlreadyImported`／`Busy` | 已導入過；另一個 wf_init 正在跑（等它結束再叫） |
| `BadJournal`／`UnsafePath` | staging 的 `commit.json` 壞了或被改；要寫或備份的路徑途中是符號連結。都沒動，請人處理 |
| `InitFailed`／`TableFailed` | 快照的 wf-init／tabledb 自己失敗（附最後一行） |
| `LintFailed` | 快照的 wf-lint 本身故障（退出碼不是 0／1 或沒 TOTAL），附最後幾行；不是專案的問題 |
| `Timeout`／`SpawnFailed`／`WriteFailed` | 跑太久；叫不起 bash／python3；寫檔失敗（wf_init 重跑同一行收尾） |
| `RootMissing`／`ConfigInvalid`／`InternalError` | 同 base |

測試：[`lib/test/test_tools_wf.py`](../../lib/test/test_tools_wf.py)（兩個真 SIGKILL 窗口、偽造 journal、兩個 wf_init 同時跑、壞掉的檢查器、惡意環境變數）。
