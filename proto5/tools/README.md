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

**工作根目錄**：`<家>/tools/base/config.json` 的 `root`（相對 agent 家；沒寫＝`workspace`）。改了下一次叫工具就生效。
read／write／edit／grep／find／ls 碰不到根目錄以外（`../`、絕對路徑、符號連結指出去都算，回 `OutsideRoot`）；**bash 關不住**，只是從根目錄開始跑。

## 七個工具

給模型看的描述是英文（在 [`base/base.json`](base/base.json)），路徑一律相對工作根目錄（描述裡叫 project directory）。

| 工具 | 一句話 | 參數（* 必填） | 上限 |
|---|---|---|---|
| `read` | 讀文字檔 | `path`*、`offset`（第幾行起，從 1）、`limit`（幾行，預設 2000） | 2000 行或 50 KB；單行超過 2000 字切掉；結尾提示下一個 `offset` |
| `write` | 建新檔或整個覆蓋 | `path`*、`content`* | 父資料夾自動建；已有的檔保留權限位；暫存檔再 rename |
| `edit` | 精確字串取代 | `path`*、`old_string`*、`new_string`*、`replace_all` | `old_string` 要剛好出現一次（或 `replace_all`）；保留 CRLF、權限 |
| `bash` | 在根目錄跑一句 bash | `command`*、`timeout`（秒，預設 120、上限 600） | stdout＋stderr 合併；只留最後 2000 行或 50 KB；stdin 是空的；結束時收掉它留下的背景行程 |
| `grep` | 搜內容，印 `路徑:行號:內容` | `pattern`*、`path`、`glob`（如 `*.py`）、`ignore_case`、`literal`、`context`（0～20）、`limit`（預設 200 行） | 單行超過 500 字切掉；最多 30 秒；rg 會跳過 .gitignore 列的與二進位檔 |
| `find` | 用 glob 找檔名 | `pattern`*、`path`、`limit`（預設 1000） | 不含 `/` 比對檔名（任何深度），含 `/` 比對相對路徑（`**` 跨資料夾）；資料夾結尾 `/`；跳過 `.git` |
| `ls` | 列一個資料夾 | `path`、`limit`（預設 500） | 照名字排序、資料夾結尾 `/`、含 `.` 開頭的 |

逾時（kernel 那層的 `_timeout_ms`）：bash 是 630000（比它自己的上限 600 秒多一點，讓它自己的 `Timeout` 先到），其他沿用預設 60000。

## 錯誤長怎樣

成功：純文字、退 0。失敗：退 1，stdout **最後一行**是一個 JSON，模型看到的是 aos-agent 包好的「工具 <名> 失敗（exit 1）：…」＋這行：

```json
{"ok": false, "error": "NotUnique", "message": "old_string occurs 2 times in a.py (lines 3, 9); include more surrounding lines to make it unique, or set replace_all=true", "count": 2}
```

bash 的 `ExitCode`／`Timeout` 先原樣印輸出，JSON 在最後一行（多一格 `exit_code` 或 `timeout`）。代號：

| 代號 | 什麼時候 |
|---|---|
| `BadArguments` | arguments 不是 JSON 物件、缺必填、型別不對、數字超出範圍、`old_string` 空或跟 `new_string` 一樣 |
| `NotFound` | 路徑不存在 |
| `OutsideRoot` | 路徑（解開符號連結後）在工作根目錄外 |
| `IsADirectory`／`NotADirectory` | read／write／edit 給了資料夾；ls／find 給了檔 |
| `BinaryFile` | read 讀到含 NUL 的檔；edit 讀到不是 UTF-8 的檔 |
| `NoMatch`／`NotUnique` | edit 找不到 `old_string`／找到不只一個（附 `count` 與前 10 個行號） |
| `ExitCode`／`Timeout` | bash 退出碼非 0（附 `exit_code`）／逾時被砍（附 `timeout`） |
| `SearchFailed` | grep 本身出錯（例如壞的 regex） |
| `ReadFailed`／`WriteFailed`／`SpawnFailed` | 權限、磁碟等作業系統錯誤 |
| `RootMissing`／`ConfigInvalid` | 工作根目錄不存在／`config.json` 壞了 |

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

## 測試

- 七個工具的單元測試：[`lib/test/test_tools_base.py`](../lib/test/test_tools_base.py)（bash 另在 [`test_tools_base_bash.py`](../lib/test/test_tools_base_bash.py)）。
- `tools add` 與真 daemon＋kernel＋agent 的往返（假模型照劇本叫 write→bash→edit→bash）：[`lib/test/test_agent_tools.py`](../lib/test/test_agent_tools.py)。
- 真模型實跑（LiteLLM `deepseek-chat`）的紀錄在 [tools-base 報告](../notes/2026-09-24-tools-base.md)。
