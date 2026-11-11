# 01 grep／glob：照內容搜、照檔名找（設計稿，未施工）

← [new-tools](README.md)｜下一份：[02 todo](02-todo.md)

## 一句話結論

做**兩支** base 工具 `grep`（搜內容）與 `glob`（照檔名樣式找檔），**純 Python 標準庫**、不靠系統的 ripgrep／grep，放進第 1 包「看」（`look.json`）。輸出照 `ls` 的口徑：一行一筆、最多 100 筆（上限 500）、多的用 `offset` 翻頁、尾巴用 `... ` 開頭的行說還有多少、跳過了什麼。二進位檔跳過、超大檔跳過並計數、符號連結的資料夾不跟進、工作區外照 base 工具的規矩（絕對路徑照用、能不能讀看 Linux 權限）。

## 現況與為什麼要做

- 現在找東西只能靠 `shell`（`grep -rn`、`find`）；`shell` 的輸出留**最後** 2000 行或 50KB，一次 `grep -r` 打到 `node_modules` 或建置產物，前面的結果被截掉、後面塞滿雜訊，小模型的 history 一次就被灌爆。
- `shell` 的 tooldef 現在寫「Use it to search (grep, find)」，要改成指向新工具。
- `ls` 只看一層、`read`／`view` 只看一個檔；中間缺「整棵樹裡哪裡有這個字／哪些檔叫這個樣子」。

## 分工

| 工具 | 回答什麼 | 回什麼 |
|---|---|---|
| `ls` | 這個資料夾裡有什麼（一層） | 名字＋類型 |
| `glob` | 整棵樹裡哪些路徑長這樣（`**/*.py`） | 路徑 |
| `grep` | 整棵樹（或一個檔）裡哪幾行有這個樣式 | `路徑:行號:那一行`，或只要路徑 |
| `read`／`view` | 這個檔第幾行到第幾行 | 內容 |
| `shell` | 上面都做不到的（管線、`sed`、`wc`） | 任意 |

印出來的路徑一律照 `tool_io.shown_path`：在工作區裡＝相對 `$AOS_WS`，否則絕對——**可以直接貼回 `read` 的 `path`**，`grep` 的行號可以直接當 `read` 的 `offset`。

## 參考市面

| 市面 | 取 | 不取、為什麼 |
|---|---|---|
| Claude Code `Grep`（包 ripgrep） | 兩支分開；`glob` 篩檔名、`-i`、前後文行數、「只要檔名」模式；預設尊重 `.gitignore` | 三種 output_mode（content／files_with_matches／count）縮成一個布林 `files`；`multiline`、`type`（語言別名表）不做——小模型很少用、別名表要維護；預設模式不學它的「只給檔名」（小模型拿到檔名還要再叫 read，多一輪），預設給行 |
| Claude Code `Glob` | `**` 遞迴；可指定起點資料夾 | 它照 mtime 排（新的在前），這裡預設照名字排：結果穩定、翻頁不跳；mtime 排序做成選項 |
| Codex | 沒有專用搜尋工具，靠 shell 跑 `rg` | 正是要避免的情況 |
| OpenHands | 也主要靠 bash；編輯器工具帶 `view` 目錄 | 同上 |
| ripgrep 本身 | 二進位跳過（看前段有沒有 NUL）、隱藏檔預設跳過、不跟符號連結 | 不依賴它：這台 WSL 就沒裝 `rg`；Rust regex 與 Python `re` 語法不同，「有 rg 就用 rg」會讓同一個樣式在兩台機器結果不同 |

## 介面草稿

### grep

stdin：

| 鍵 | 型別 | 預設 | 意思 |
|---|---|---|---|
| `pattern` | string | （必要） | Python `re` 正規式 |
| `path` | string | `.` | 資料夾或單一檔；相對從 `$AOS_WS` |
| `glob` | string | — | 只搜檔名合這個樣式的（同 `glob` 工具的語法，例 `*.py`、`src/**/*.json`） |
| `fixed` | boolean | false | true＝`pattern` 當一般字串、不當正規式 |
| `ignore_case` | boolean | false | 不分大小寫 |
| `context` | integer | 0 | 每筆前後各帶幾行（0～5） |
| `files` | boolean | false | true＝只列有中的檔，一行一個路徑（後面接 `TAB 中幾行`） |
| `hidden` | boolean | false | true＝也搜 `.` 開頭的檔與資料夾（同 `ls`） |
| `gitignore` | boolean | true | 在 git 工作樹裡時跳過 `.gitignore` 擋掉的（見待裁 G3） |
| `offset` | integer | 0 | 從第幾筆開始給 |
| `max_matches` | integer | 100 | 一次最多幾筆（1～500；`files` 時算檔數） |

stdout（預設）：

```
proto8/lib/tool_io.py:181:def workspace():
proto8/lib/base/read/_entry:47:path = tool_io.ws_path(args["path"])
... next_offset 100 (at least 340 matches in 41 files)
... skipped 3 binary files, 1 file over 8MB
```

- 一行一筆 `路徑:行號:那一行`（`grep -rn` 的樣子，模型最熟）；那一行超過 300 字元截斷、尾巴加 `…[cut]`。
- `context` > 0：前後文行用 `路徑-行號-內容`（照 `grep -C`），組與組之間 `--`。
- 尾巴行全部以 `... ` 開頭（同 `ls`）：`... next_offset N (M matches in all)`（掃完了才知道總數）或 `(at least M …)`（掃描預算用完）；`... skipped …`（二進位、超大、讀不了的各幾個）；`... stopped after 20 s / 20000 files; narrow path or glob`；沒中＝`... no matches`。
- 照檔名、再照行號排，結果穩定、翻頁不重複。

錯誤代號：`ArgumentsBad`、`PatternBad`（正規式編不過，原因帶 `re.error` 的訊息）、`FileMissing`（path 不在）、`ReadFailed`（path 本身讀不了；樹裡個別讀不了的只計數不報錯）、`WsMissing`。

tooldef description 草稿：

> Search file contents with a regular expression (Python re syntax), like grep -rn. Default output: one line per match, PATH:LINE:TEXT; paste PATH into read and use LINE as its offset. "files": true lists only the matching files. "glob" limits which files are searched (e.g. "*.py", "src/**/*.json"); "fixed": true searches for the plain text; "context": N adds N lines around each match. Skips binary files, files over 8MB, names starting with . (unless "hidden": true) and, inside a git work tree, files ignored by .gitignore (unless "gitignore": false). At most max_matches per call; a last line "... next_offset N" means more: call again with offset N. To find files by name, use glob. Errors: PatternBad (fix the regular expression, or use "fixed": true), FileMissing.

### glob

stdin：

| 鍵 | 型別 | 預設 | 意思 |
|---|---|---|---|
| `pattern` | string | （必要） | `*` 一層內任意、`?` 一字、`[abc]`、`**` 任意層；不含 `/` 的樣式＝比對任何一層的檔名（`*.py`＝整棵樹的 .py） |
| `path` | string | `.` | 從哪個資料夾開始 |
| `type` | string | `file` | `file`／`dir`／`any` |
| `sort` | string | `name` | `name`（照路徑）／`mtime`（新的在前） |
| `hidden`、`gitignore`、`offset` | | 同 grep | |
| `max_items` | integer | 100 | 一次最多幾個（1～500，同 `ls`） |

stdout：一行一個路徑（資料夾結尾加 `/`）；尾巴 `... next_offset N (M paths in all)`、`... stopped after …`、`... no matches`。

錯誤代號：`ArgumentsBad`、`PatternBad`（例 `[` 沒關）、`FileMissing`、`FileBad`（path 是檔不是資料夾）、`ReadFailed`、`WsMissing`。

tooldef description 草稿：

> Find files by name pattern under a folder. * matches within one folder level, ** matches any number of levels, ? one character; a pattern without / matches the file name at any depth ("*.py" finds every .py file). Prints one path per line (folders end with /), sorted by path ("sort": "mtime" = newest first); paste a path into read, view or ls. Skips names starting with . unless "hidden": true and, inside a git work tree, paths ignored by .gitignore unless "gitignore": false. At most max_items per call; a last line "... next_offset N" means more. To search inside files, use grep. Errors: PatternBad, FileMissing, FileBad.

### _metainfo（兩支相同口徑）

`resource: disk`、`side_effect: false`、`idempotent: true`、`deterministic: true`（`sort: mtime` 時檔變了結果會變，但同一棵樹同結果）、`interrupt: safe`、`parallel: true`、`cost.time_ms: 300`、`timeout_ms: 30000`（工具自己 20 秒就收手，留 10 秒給輸出）。

## 實作路線

- **依賴**：只用 Python 標準庫（`os.scandir`、`re`、`fnmatch` 的片段自己組 `**`；這台是 3.12，沒有 3.13 的 `glob.translate`）。尊重 `.gitignore` 時叫一次 `git -C <path> ls-files -z --cached --others --exclude-standard`（只在 `git rev-parse --is-inside-work-tree` 成立時）；`git` 不在或失敗＝當不在 git 裡、照常搜，stderr 一行 warning。
- **共用模組**：兩支共用的「走樹」（隱藏、gitignore、符號連結、掃描預算、計數）放 `lib/base/file_walk.py`（同 `lib/agent/knowledge_fs.py` 的做法：同層共用、不 import 隔壁工具）。沙箱要把它跟 `tool_io.py` 一起綁唯讀。
- **新增**：`lib/base/grep/`、`lib/base/glob/`（`_entry`、`_tooldef.json`、`_metainfo.json`、`tests/`）、`lib/base/file_walk.py`。
- **要動的既有檔**：`lib/packs/look.json`（加兩格）、`lib/packs/README.md`（第 1 包那列）、`lib/base/shell/_tooldef.json`（「Use it to search (grep, find)」改成「for searching, prefer grep and glob」）、兩範本 README 與 `templates/docs/02` 的工具支數（35 → 37）、`lib/docs/02-索引-base與索引-aos.md`、知識庫每支一個節點（線 C 正在補「每支工具都有節點」，跟著它的格式；放 `knowledge/aos/tools.json` 或它新開的地方）、codemap 重生。不動 aos-tools、aos-mcp、brain、act（新工具照一般登記走）。
- **測試**（pytest，照 `lib/base/shell/tests` 的樣子，暫存資料夾、直接跑 `_entry`）：正規式與 fixed、大小寫、context 與組間 `--`、files 模式、翻頁與 next_offset、二進位跳過計數、超大檔跳過（用 sparse 檔造 9MB 不佔空間）、隱藏檔、符號連結資料夾不跟進（含指回自己的環）、gitignore 有 git／沒 git／git 不在 PATH、PatternBad、path 是單一檔、工作區外絕對路徑、掃描預算（把上限用測試鉤子調小）、長行截斷、非 UTF-8 檔。glob 另測 `**` 零層、不含 `/` 的樣式任何深度、`type`、`sort: mtime`。
- **工作量**：程式約 500 行（file_walk 120、grep 250、glob 130）、測試約 300 行、文件與知識節點零碎；**一個人約 1 天**（含 codemap、兩範本實跑一次假腦叫到）。

## 邊緣狀況

1. **二進位**：前 8KB 有 NUL＝跳過、計數（同 `read` 的判法）。`grep` 指定的 `path` 本身是二進位檔＝不報錯、尾巴 `... skipped 1 binary file`。
2. **超大檔**：超過 8MB 跳過、計數（`read` 一次只讀 50KB，這裡要整檔掃）；單一行超過 1MB 的檔（壓縮過的 JS）照掃，但印出的行截 300 字元。
3. **編碼**：一律 UTF-8 `replace`；Big5 之類會變成亂碼，但不會壞。
4. **符號連結**：走樹時連到資料夾的捷徑**不跟進**（避免環、避免一個捷徑把整個 `/` 拉進來），連到檔的照搜、印捷徑自己的路徑；`path` 本身是捷徑＝照 Linux 跟過去（是人明指的）。壞掉的捷徑跳過不計。
5. **工作區外**：絕對路徑照用（同 base 13 支）；`path: "/"` 合法，靠掃描預算（20 秒或 2 萬個檔先到先停）收手，尾巴說停在哪、叫它縮小範圍。
6. **讀不了的資料夾／檔**（權限）：跳過、計數 `... skipped N unreadable`；不是錯。
7. **正規式災難回溯**（`(a+)+$`）：Python `re` 沒有逾時；靠工具自己每個檔之間看時鐘＋`_metainfo.timeout_ms` 讓叫它的那層整群收掉。單一檔裡卡死只能靠外層逾時，tooldef 不提（太細）。
8. **pattern 含換行**：不支援跨行；`\n` 在逐行比對裡永遠不中，文件寫明「一行一行比」。
9. **stack 底下**：工作區裡的 `.stack/`、`.trash/` 是隱藏的，預設不搜；要搜 history 得 `hidden: true`（或用 `self_history`）。
10. **gitignore 只看工作樹最上層的 git**：子模組、巢狀 repo 照 `git ls-files` 的行為；path 在 git 外＝不擋。
11. **結果數在掃描中途變動**（別人同時在寫）：不保證快照一致；翻頁可能重複或漏一兩筆，可接受。
12. **`glob` 的 `**` 與隱藏**：`**` 不進 `.` 開頭的資料夾，除非 `hidden: true`；樣式自己明寫 `.git/**` 也算明指、照進（代定 D4）。
13. **行號與 `read` 的 offset 對得上**：兩邊都從 1 算、都以 `\n` 切；`\r\n` 檔的行尾 `\r` 印的時候去掉。

## 代定（我先定的小事，可翻案）

- D1 名字 `grep`、`glob`（市面同名、模型最熟；C-54 允許大家本來就知道的詞）。備選：`search_text`／`search_files`（主題在前，兩支排在一起）、`find_text`／`find_files`。
- D2 放第 1 包 `look`（唯讀、跟 read／ls 同一類；兩範本預設就有）。
- D3 預設輸出給行（不學 Claude Code 預設只給檔名），`files: true` 才只給檔名。
- D4 不含 `/` 的 glob 樣式比對任何深度的檔名（照 `.gitignore`／rg `--glob` 的語意，小模型寫 `*.py` 多半就是想找全部）；明寫的 `.xxx` 路徑段算明指、不受 `hidden` 擋。
- D5 上限：每次 100 筆、最多 500；每行 300 字元；超過 8MB 的檔跳過；掃描預算 20 秒或 2 萬個檔；`context` 最多 5。
- D6 正規式語法＝Python `re`（說明裡寫明），不做 rg／PCRE 相容。
- D7 不做 `multiline`、`type`（語言別名）、`count` 模式；`files: true` 每行附中幾行，就是 count。
- D8 錯誤代號新加一個 `PatternBad`（C-54 `…Bad`）。

## 待裁

**G1 一支還是兩支**
- 甲 兩支 `grep`＋`glob`（推薦）：名字一看就知道做什麼，參數各自少；多 1 支 tooldef（約 300 tokens）。
- 乙 一支 `search`，`mode: text|name`：工具表少一支，但參數混在一起，小模型常把 glob 樣式丟進 pattern。
- 丙 只做 `grep`，找檔名繼續用 `ls`／`shell`：最省，但「整棵樹的 .py」又回到 shell。

**G2 搜尋引擎**
- 甲 純 Python 標準庫（推薦）：哪台都一樣、不多依賴；大 repo（10 萬檔）會慢，靠掃描預算收手。
- 乙 有 ripgrep 就用、沒有退回 Python：快，但兩種正規式語法不同，同一句結果會因機器而異。
- 丙 一律要 ripgrep：最快最準，沒裝就整支不能用（這台 WSL 就沒裝）。

**G3 要不要尊重 .gitignore**
- 甲 預設尊重（在 git 裡時問 `git ls-files`），`gitignore: false` 關掉（推薦）：結果乾淨，跟 Claude Code 一樣；多依賴 git（不在就當沒有）。
- 乙 不尊重，只跳過 `.` 開頭的：最單純，但 `node_modules`、`build/` 會淹掉結果。
- 丙 自己解析 `.gitignore`：不靠 git，但巢狀與否定規則要寫一百多行、容易跟 git 不一致。
