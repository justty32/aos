# proto5/tools — 工具包

← [proto5 README](../README.md)｜怎麼裝：[aos-agent.md §1.8](../spec/aos-agent/tools.md)｜工具格式：[agent.md §3.3](../spec/agent/info.md)

一個資料夾＝一個工具包，用 `aos-agent tools add <名> --target <agent 家>` 裝進 agent 家。現在只有 [`base/`](base/)：
pi coding agent 那一組 read、write、edit、bash、grep、find、ls，裝了就能叫 agent 寫程式、跑程式、改程式。純 Python 標準庫，沒有別的依賴（grep 有 `rg` 就用，沒有退回 `grep`）。

## 裝

```sh
aos-agent tools add base --target $W/bob                  # 工作根目錄＝$W/bob/workspace/（自動建）
aos-agent tools add base --target $W/bob --root ~/proj    # 讓它在 ~/proj 裡工作
aos-agent tools add base --target $W/bob --force          # 重裝（保留原本的 config.json）
```

裝完下一格就生效，不用重 `start`。`aos-kernel check --agent $W/bob` 會逐一列出 `agent/tool/read: 可執行 tools/base/read` 等七行。
人格記得改成 coding agent，例如 `prompts/system.json`：`{"content": "你是 coding agent。用工具實際動手，不要只描述要做什麼。一次只叫一個工具，看到結果再決定下一步。"}`
（agent 同一批工具可能平行跑，「先寫再跑」這種有先後的，叫它一次一個最穩。）

**工作根目錄**：預設在 `<家>/tools/base/config.json` 的 `root`（相對 agent 家；沒寫＝`workspace`）。改了下一次叫工具就生效。
**這只在這支工具不關牢（`_jail: false`）時有效**：agent 家一律要有 `access.json`（`aos-agent init` 現在就會生一份，或 `tools add base` 第一次裝時自動建，見[教程 04b](../tutorials/04b-access-and-tool-admin.md)），要關牢的工具被 `aos-jail` 關進沙盒跑，牢裡的環境變數 `AOS_TOOL_ROOT` 一定被設成牢裡的起點（例如 `/work/ws`），base 工具看到這個環境變數就直接用、**不看 `config.json` 的 `root`**，錯誤訊息印的也是這個牢裡路徑（[aos-jail](../spec/aos-exec/aos-jail.md)）。
**碰得到的範圍不只是起點**：關牢時 aos-jail 還會多給一個環境變數 `AOS_TOOL_FENCE=/work`，read／write／edit／ls／grep／find 因此看得到 `access.json` 掛進 `/work` 的**所有**資料夾，不限起點那一個——例如起點是 `/work/ws`，`access.json` 另外唯讀掛了 `ref`，工具照樣讀得到 `../ref/x.txt` 或 `/work/ref/x.txt`。
read／write／edit／grep／find／ls 碰不到這個範圍以外（`../`、絕對路徑、符號連結指出去都算，回 `OutsideRoot`）——這一條檢查是防模型手滑、不是沙盒（有別的行程同時在換路徑時擋不完全）。唯讀掛的資料夾、或整個牢的根 `/work` 本身（掛完之後也被轉成唯讀）寫不進去，write／edit 回 `ReadOnly`，訊息裡會列出目前有哪些資料夾可寫。
**bash**：家裡有要關牢的工具時真的被關在牢裡，出不去，牢的根（含 `/work` 本身）也唯讀，只有可寫 mount 跟 `/tmp` 寫得進去（除非那支自己 `_jail: false`，[04b](../tutorials/04b-access-and-tool-admin.md)）；**沒有 `access.json` 的舊家**：要關牢的工具（沒寫 `_jail: false` 的那些）直接不送（`NoAccess`），不會像以前那樣退回「不關、碰得到所有檔」。

裝好的樣子：`tools/base.json`（工具檔）＋`tools/base`（符號連結）→`tools/.base-<版>/`（程式與 `config.json`）。重裝是換連結，原子的。

## 七個工具

給模型看的描述是英文（在 [`base/base.json`](base/base.json)），路徑一律相對工作根目錄（描述裡叫 project directory）。

| 工具 | 一句話 | 參數（* 必填） | 上限 |
|---|---|---|---|
| `read` | 讀文字檔 | `path`*、`offset`（第幾行起，從 1）、`limit`（幾行，預設與上限 2000） | 2000 行或 50 KB；單行超過 2000 字切掉；結尾提示下一個 `offset`；邊讀邊丟，大檔不吃記憶體；只收一般檔案 |
| `write` | 建新檔或整個覆蓋 | `path`*、`content`* | 父資料夾自動建；已有的檔保留權限位；暫存檔再 rename |
| `edit` | 精確字串取代 | `path`*、`old_string`*、`new_string`*、`replace_all` | `old_string` 要剛好出現一次（或 `replace_all`）；保留 CRLF、權限；檔案上限 10 MB；CRLF 檔用 LF 片段找不到時提示 |
| `bash` | 在根目錄跑一句 bash | `command`*、`timeout`（秒，預設 120、上限 600） | stdout＋stderr 合併；邊讀邊丟、只留最後 2000 行或 50 KB；stdin 是空的；結束（或它自己被 TERM）時收掉同一行程群組的背景行程——`setsid`／`nohup` 另開群組的逃得掉 |
| `grep` | 搜內容，印 `路徑:行號:內容` | `pattern`*、`path`、`glob`（如 `*.py`）、`ignore_case`、`literal`、`context`（0～20）、`limit`（預設 200、上限 2000 行） | 單行超過 500 字切掉；30 秒到了回 `Timeout`（附已找到的）；rg 帶 `--no-config --no-follow`、會跳過 .gitignore 列的、隱藏的與二進位檔；退回 `grep -E` 時 regex 語法較窄（沒有 `\d`）、不看 .gitignore |
| `find` | 用 glob 找檔名 | `pattern`*、`path`、`limit`（預設 1000、上限 5000） | 不含 `/` 比對檔名（任何深度），含 `/` 比對相對路徑（`**` 跨資料夾）；資料夾結尾 `/`；跳過 `.git`；讀不到的資料夾在結尾加一行 warning |
| `ls` | 列一個資料夾 | `path`、`limit`（預設 500、上限 5000） | 照名字排序、資料夾結尾 `/`、含 `.` 開頭的 |

逾時（kernel 那層的 `_timeout_ms`）：bash 是 630000（比它自己的上限 600 秒多一點，讓它自己的 `Timeout` 先到），其他沿用預設 60000。

## 錯誤長怎樣

成功：純文字、退 0。失敗：退 1，stdout **最後一行**是一個 JSON，模型看到的是 aos-agent 包好的「工具 <名> 失敗（exit 1）：…」＋這行：

```json
{"ok": false, "error": "NotUnique", "message": "old_string occurs 2 times in a.py (lines 3, 9); include more surrounding lines to make it unique, or set replace_all=true", "count": 2}
```

bash 的 `ExitCode`／`Timeout` 先原樣印輸出，JSON 在最後一行（多一格 `exit_code` 或 `timeout`）。代號：

| 代號 | 什麼時候 |
|---|---|
| `BadArguments` | arguments 不是 JSON 物件、缺必填、型別不對、數字超出範圍、字串含 NUL 或編不成 UTF-8、`old_string` 空或跟 `new_string` 一樣 |
| `NotFound` | 路徑不存在 |
| `OutsideRoot` | 路徑（解開符號連結後）在碰得到的範圍外——不關牢時是工作根目錄，關牢時是整個 `/work`（`access.json` 掛進來的所有資料夾） |
| `ReadOnly` | 只有關牢時會遇到：write／edit 寫到唯讀掛的資料夾，或直接寫在 `/work` 底下、不在任何掛進去的資料夾裡；訊息列出目前哪些資料夾可寫 |
| `IsADirectory`／`NotADirectory` | read／write／edit 給了資料夾；ls／find 給了檔 |
| `BinaryFile` | read 讀到前 8 KB 含 NUL 的檔；edit 讀到不是 UTF-8 的檔 |
| `NotARegularFile`／`FileTooLarge` | read／edit 給了 FIFO、裝置等；edit 的檔超過 10 MB |
| `NoMatch`／`NotUnique` | edit 找不到 `old_string`／找到不只一個（附 `count` 與前 10 個行號） |
| `ExitCode`／`Timeout` | bash 退出碼非 0（附 `exit_code`）／bash 逾時被砍（附 `timeout`）、grep 30 秒沒搜完 |
| `SearchFailed` | grep 本身出錯（例如壞的 regex） |
| `ReadFailed`／`WriteFailed`／`SpawnFailed` | 權限、磁碟等作業系統錯誤 |
| `RootMissing`／`ConfigInvalid` | 工作根目錄不存在／`config.json` 壞了 |
| `InternalError` | 工具自己沒料到的例外（照樣是最後一行 JSON，不會噴 Traceback） |

grep 沒找到、find 沒找到、ls 空資料夾都**不是**錯誤：退 0、印一句「No matches found…」之類。

## 自己做一個工具包

照 `base/` 的樣子做一個資料夾，名字跟裡面的 `<名>.json` 一致：

```
hello/
  hello.json     [{"type": "function", "function": {"name": "hello", "description": "…", "parameters": {…}},
                   "_meta": {"argv": ["tools/hello/run"]}}]
  run            #!/bin/sh … （要有執行位；stdin 收 arguments JSON、stdout 印結果）
```

`aos-agent tools add ./hello --target $W/bob`（含 `/` 就當資料夾路徑）。放進 `proto5/tools/` 底下的，就能只寫名字。
`_meta.argv[0]` 寫 `tools/<名>/<程式>`：工具的 cwd 是 agent 家，這個相對路徑才對得上。要設定就在資料夾放 `config.json` 自己讀（重裝會保留）。

**關進牢裡也要找得到程式**：家裡有 `access.json` 時牢裡的 PATH 只有 `/usr/local/bin:/usr/bin:/bin`。`argv[0]` 含 `/`（像上面的 `tools/hello/run`）`aos-jail` 會把它的資料夾唯讀掛進牢裡再執行，照樣找得到；**`argv[0]` 不含 `/`（像 `date`）就只能在牢裡這幾個 `/usr` 路徑下找**，自己寫的工具幾乎不會裝在那裡，所以自己的工具 `argv[0]` 一定要含 `/`。
真的要讓某支工具不關牢（例如它就是要碰家以外的東西），在那支工具元素頂層加 `"_jail": false`（跟 `_meta`、`_timeout_ms` 同層）——這等於讓那支碰得到你碰得到的所有檔，`aos-agent check` 會對它印警告，平常不建議用。

**只有一支工具、或想讓幾個 agent 共用同一份**：不用裝包（複製一份進 `tools/`），`tools add` 給一個單一 `.json` 檔、或一個資料夾（裡面沒有跟資料夾同名的 `<名>.json`）就會**原地引用**：不複製，`info.json` 只記一條路徑，改原始檔案下一批就生效。`--as`、`--only` 怎麼配著用見[教程 04b](../tutorials/04b-access-and-tool-admin.md)。

## 測試

- 七個工具的單元測試（astra 審查後的補強在 [`test_tools_base_fix.py`](../lib/test/test_tools_base_fix.py)）：[`lib/test/test_tools_base.py`](../lib/test/test_tools_base.py)（bash 另在 [`test_tools_base_bash.py`](../lib/test/test_tools_base_bash.py)）。
- `tools add` 與真 daemon＋kernel＋agent 的往返（假模型照劇本叫 write→bash→edit→bash）：[`lib/test/test_agent_tools.py`](../lib/test/test_agent_tools.py)。
- 真模型實跑（LiteLLM `deepseek-chat`）的紀錄在 [tools-base 報告](../notes/2026-09-24-tools-base.md)。
