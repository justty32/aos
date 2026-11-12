# `$ref` 收 `#/` 開頭＝寫著它的那份檔自己（11-12 晚，家機；已施工）

← [11-12 日索引](README.md) ・ 前情：[index-link](index-link.md)（三題裁完時使用者順口問的）、N-45（[06-基礎設施-命令列與指示詞](../../../docs/NORMS/06-基礎設施-命令列與指示詞.md)）

## 使用者原文

> 「1. 甲。2.甲。3.甲，話說ref應該支援#/開頭吧」

頂層問 index 那邊的代定時，使用者順口問 `$ref` 能不能寫 `./`、`../`：

> 「算數。然後$ref支援./, ../嗎」

## 決定

- `{"$ref": "#/a/b"}`（沒寫檔名）＝**寫著這個 `$ref` 的那份檔自己**裡 `/a/b` 的值。N-45 原本那句「只有 `#/…` 沒檔名＝換不了、原封不動」（頂層自定、待確認）作廢，改成這條。
- 「那份檔」跟相對檔名的起點是同一份：被 `$ref` 換進來的檔裡寫的 `#/x`，指的是那份被換進來的檔（不是最外層那份）。取原文、取到的值接著解，跟 `檔#/位置` 一樣。
- 繞圈（指到包著自己的祖先、兩格互指）＝`DirectiveBad`；指不到＝`DirectiveBad`；只有 `#`、或 `#` 後面不是 `/` 照舊不收。
- `./`、`../`：檔名那段本來就能用（接上起點後整理），實跑確認過，補了測試和半句條文。

## 結論（做了什麼）

- **庫**（`impls/aos-directive`）：新型別 `aos::RefBase{dir, file}`＝相對起點加上「寫著它的那份檔」，字串或路徑可以直接當它用（＝只給資料夾、`file` 空）。`resolve`／`resolve_shallow`／`resolve_keys` 改收 `RefBase`，`Resolved` 的 `dir_of` 也回 `RefBase`，所以呼叫者把起點往下傳時，檔也跟著傳下去。被 `$ref` 換進來的檔，庫自己會記下是哪份檔。`#/…` 等於 `file#/…`，繞圈檢查沿用原本的鏈。舊的 `where` 參數本來就沒在用，拿掉了。
- **命令列**：`aos-directive --file 檔`，意思是 stdin 那份 JSON 是從這份檔讀來的：相對 `$ref` 從它的資料夾算，`#/…` 取它。沒給就原封不動。
- **給了「那份檔」的呼叫者**：
  - aos-exec：入口檔（含 `檔#/指標`，`#/` 從檔根算）、argv 陣列入口、JSON `.env` 所在的檔。
  - aos-loop：設定檔（含 `檔#/指標`）、ctl、內嵌單子（`Target::ref_base`）。
  - aos-fsm：fsm.json（整格 `$ref`、格的內嵌單子）。
  - aos-daemon：daemon.json、procs_ctl。內嵌單子寫進小格前，`abs_refs` 會把 `#/…` 補成「daemon.json 絕對路徑#/…」，寫進小格時再轉成相對路徑 `../../../daemon.json#/…`；不補的話，搬進小格後會指到小格自己那份檔。
  - aos-llm-kernel：kernel.json。
  - CMake：aos-exec、aos-llm-kernel 對 aos-directive 的連結改成 PUBLIC（公開標頭用到 `RefBase`）。
- **條文**：N-45 改了四處（寬容那句、`$ref` 段加 `#/` 的語意＋例子＋原話、陣列元素寬容那句、argv 那句），並補半句「檔名可以寫 `./`、`../`」。說明文件 `aos-directive/docs/01`、README 一句話、`knowledge/aos/cli/parts/directive.json`、`knowledge/docs/01` 的 `$ref` 條都跟上了。
- **測試**：新增 `aos-directive/tests/test_ref_hash.py`（9 支，含 `./`、`../`）、`aos-exec`（4 支）、`aos-loop`（2 支）、`aos-fsm`（1 支）、`aos-daemon`（1 支）各一份 `test_ref_hash.py`。exec、loop、fsm、daemon、json、util、lock、llm-kernel（非 live）既有測試全過。
- **要重建什麼**：impls 全部重 build（`aos-directive` 的公開介面變了）；持久檔格式沒動。

```
$ aos-directive --file main.json < main.json    # main.json: {"defs": {"cmd": ["echo","hi"]}, "use": {"$ref": "#/defs/cmd"}, "inc": {"$ref": "sub/inc.json"}, ...}
{"defs": {...}, "use": ["echo", "hi"], "inc": {"mine": "inc-local", "local": "inc-local", "up": "from-other", "dot": "leaf"}, "arr": ["echo", "hi", "echo", "hi"], "mod": "--p=echo/x"}
$ aos-directive < main.json                     # 沒給 --file：頂層 #/ 原封不動，inc.json 裡的照解（那份檔知道）
{"defs": {...}, "use": {"$ref": "#/defs/cmd"}, "inc": {"mine": "inc-local", ...}, ...}
$ aos-directive --file loop2.json < loop2.json  # {"x": {"$ref": "#/y"}, "y": {"$ref": "#/x"}}
aos-directive: error: DirectiveBad $ref loop: …/loop2.json#/y → …/loop2.json#/x → …/loop2.json#/y
$ aos-exec e.json#/tools/t                       # t: {"argv": {"$ref": "#/cmds/echo"}}
hi
```

## 代定（可翻）

- **R1 「那份檔」由呼叫者給、庫不猜**：被 `$ref` 換進來的檔由庫自己記；最外層由讀檔的程式給（上面那張表）。不知道的情況（stdin 沒給 `--file`、daemon 的信、行程內給的 JSON）照寬容規則，原封不動留著。
- **R2 取的是磁碟上那份檔的原文**，不是程式手上已經蓋過旗標的那份。ctl 在兩次讀之間被改的話，取到的是新的（跟 `ctl.json#/x` 一樣）。
- **R3 頂層的 `#/…` 指到包著自己的祖先**：鏈上沒有放「整份檔」那一層，所以會多走一層才報 `$ref loop`。錯誤還是同一個。
- **R4 `$ref` 陣列裡有 `#/…`、但不知道是哪份檔**：整個物件原封不動（等於「有一個元素不合」）。
- **R5 `#/`（空指標）也收**：指的是名字為空字串的那個 key，同 RFC 6901。
- **R6 `--file` 會一起把相對起點改成那份檔的資料夾**（同「從寫著它的那份檔所在的資料夾算」）。
- **R7 daemon 信裡的內嵌單子寫 `#/…`**：信沒有檔可以補，就原樣寫進小格，在小格裡會被當成小格那份檔。屬於邊緣狀況，沒處理。
- **N-45 「（有 `$ref` 時不改試 `$env`；頂層自定，待使用者確認）」那半句留著沒動**：它講的是「不改試 `$env`」，跟 `#/` 無關。

## 其他自己解 `$ref` 的地方

- **aos-json（`src/follow/`，自己照 aos-directive 的規則走一遍）**：11-12 晚 json 線跟上（`6b74fec4c`）。
- **經 aos-directive stdin 的 Python**（`lib/directive_value.py`、`lib/aos_json.py` 的 `value_of`、`cmd/aos-agent/aos_agent/tools.py`）：同一個庫，自然跟上。最外層沒給 `--file`，`#/` 原封不動；`./`、`../` 可以用。`directive_value` 解的是 cli.json 的格，要讓 `#/` 指 cli.json，得改成給 `--file`，牽動 `lib/agent`（別線正在改），沒做。
- **不用跟的**：`py/daemon_ctl/table.py`（讀 daemon 自己切檔的 `$ref` 陣列，只會是檔名，`os.path.join` 本來就認 `./`、`../`）；`lib/mcp_freeze.py`（JSON Schema 的 `$ref`，是另一種東西，本來就只收 `#/`）。

## 未定

- ~~aos-json 要不要跟上 `#/`（json 線）~~：已做（`6b74fec4c`），見 [json-tools 04](json-tools/04-aos-json下沉與len與jsonx-multi.md#追加aos-json-的-ref-收-11-12-晚頂層轉來)。
- ~~`directive_value` 要不要給 `--file`。~~ **已做（11-12 晚，codebase-cleanup 線）**：知道「那份檔」的 Python 呼叫處都給了 `--file`——`lib/directive_value.py`（`resolve` 多一個選填 `file`；`resolve_path` 一律給設定檔＝`cli.json` 的 `tools`／`tools_sub`／`mcp_servers`、server 檔的 `env_file`／`ca_file`）、`lib/mcp_server_file.py` 的 `stdio_launch`（`command`／`args`＝server 檔）、`cmd/aos-tools` 的 `read_bases` 與 `cmd/aos-agent` 的 `check_pointer`（`$override`＝那份登記檔）、`lib/agent/hooks.py` 的 `_target`（`handler`＝那格所在的 hooks.json）、`py/aos_clock_register.py` 的 `resolve_box`（`box`＝登記表）。照 R1 維持原封不動的：`agent_def` 的 `from`（腦給的參數）、`aos-daemon-ctl` 的 `resolve_here`（旗標給的值）、`aos-tools --path-json`（旗標）、`lib/aos_json.py` 的 `value_of`（腦給的 `text`／`value`，不是從檔讀來的；代定、可翻：要它指「要寫進去的那份檔」就給 `t.real`）。
