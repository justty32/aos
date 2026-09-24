← [aos-agent](README.md)｜[tools-llm.md](tools-llm.md)｜實作：[wrapcli](../../lib/aos_agent_tools_wrapcli.py)

# 1.8（續三）`tools wrap-cli CMD`（09-24 第三波 W3-2）

指令格式、`--describe-with-llm` 與「人確認才寫入」的共通流程、失敗代號見 [tools-llm.md](tools-llm.md)。

**CMD**：含 `/`（或存在的 `.py`）＝檔，產包時存副本到 `src/`（`.py` 用 `python3` 跑，其他直接執行）；其他＝PATH 上的指令名（找不到＝`NotFound`）。包名預設＝檔名去副檔名／指令名；包名不能讓 `wrapcli.json`、`config.json` 撞名。

**原文**（依序挑第一個成立的）：`--help-file F` → `--spec` 記的 `help_file` → `.py` 裡有 `ArgumentParser(...)`＝argparse 模式（原文＝原始碼）→ 跑 `CMD --help`（不經 shell、stdin 關、`LC_ALL=C`、10 秒逾時砍整個群組；stdout 空就用 stderr；什麼都沒印或逾時＝`HelpFailed`）。help 文字先去掉終端機控制碼（GNU 的超連結、粗體）與 backspace 疊字、tab 換空白。

## 機械版（預設）：argparse

`ast` 靜態讀（不 import、不執行）。收 action `store`／`store_true`／`store_false`／`store_const`／`count`／`append`，type `int`／`float`／`str`，nargs `?`／`*`／`+`／正整數，`choices` 字面清單或 `range(常數)`，`required`、`dest`、`default`（字面值才記）。`store_false` 用旗標取名（`--no-header`→`no_header`）。**拒收並說原因**：子命令（subparsers 本身與子命令的參數）、旗標或 action／type／nargs／choices／required／dest 不是字面值、`*`／`**` 展開、`type=bool`、自訂 type／action、看不出是哪個 parser、檔裡不只一個 `ArgumentParser`（全拒）、`prefix_chars` 不是 `-`（全拒）、`parents=`。help、default、metavar 不是字面值只丟那欄。`help=SUPPRESS`、help／version「不收」。互斥群組：收，但不檢查，同時給由指令自己報錯（表上註明）。

## 機械版（預設）：help 文字

**`usage:` 行**（可在下一行；更縮排的續行接起來；`or:` 或程式名開頭的另一種用法只記附註、不解）：`[x]` 選填、`x ...`／`[X]...` 陣列、`{a,b}` choices、`<x>` 去角括號；`[OPTION]...`／`[options]` 是佔位；`[-abc]` 一串開關；`[-f file]`、`[--foo=FOO]`、`[-a | -b]`；方括號外的旗標＝必填。

**選項行**（去掉縮排後 `-` 開頭）：`-x, --long=ARG`、`--long ARG`、`-x ARG`、`--long[=ARG]`、`-o <file>`，旗標之間用 `,`／`|`／`/`；說明在兩格以上空白之後、`:` 之後，或寫在下一行（更縮排的都是續行）。**只隔一格就接字的列為解不出來**（分不出是參數名還是說明）。

**型別**：參數名 `N`／`NUM`／`NUMBER`／`INT`／`INTEGER`／`COUNT`（不分大小寫、含 `<n>`）＝integer，`FLOAT`＝number，其他 string；`{a,b}`、`a|b`、說明裡「X can be: a, b, c」＝choices；說明寫了 `-vv`＝count；寫了 repeatable／multiple times＝陣列。

**別名與撞名**：同一個旗標另有光溜溜寫法時，`--check=quiet` 這種是固定值別名，不當參數（註明）。`--help`、`--version`、單獨的 `-h`（說明有 help）不收。旗標重複＝後面的拒收；名字撞＝後面的拒收，位置參數撞到選項名加 `_arg`。

**解不出來的行**列出來、不猜：上面那種一格空白、「Options:」這類段落裡不是選項行的縮排行、說明文字提到但沒有選項行的旗標（`Pass -z to …`）。

**印表**：每格一行「收／拒收／不收 名字 旗標 型別 必填 第幾行」，接著解不出來的行、附註。一格都沒收＝`NothingToWrap`（不寫檔）。

## 參數表（`wrapcli.json`，提案檔與包裡同一格式）

`{"_type": "aos_wrap_cli", "_version": 1, "command", "mode": "help"|"argparse", "help_sha256", "help_file", "made_by": "mechanical"|"llm"|"spec", "description", "params": [...], "timeout"}`；提案另有 `model`、`alias`、`usage`、`ms`、`dropped`；包裡另有 `exec`（`@` 開頭＝包內路徑）。
每格 `{"name", "flags", "kind": "flag"|"count"|"option"|"positional", "type", "array", "required", "choices"?, "help", "joiner"?（"=" 或 " "）, "multi"?（"repeat" 或 "once"）, "default"?, "line"}`。

**機械檢查**（模型回的、`--spec` 給的都走）：名字 `[A-Za-z_][A-Za-z0-9_]{0,63}` 且不重複；kind 只收那四種；flag＝boolean、count＝integer、option／positional 只收 string／integer／number；位置參數沒旗標、其他至少一個；旗標 `-`／`--` 開頭、不含 `=`、**在原文逐字出現**、不重複、不是 help／version；choices 跟型別一致、≤ 100 個；array／required 是布林；flag／count 不能是陣列。help 壓成一行、截 200 字；沒給 joiner 就看原文有沒有 `--x=`。

**`--spec FILE`**：`_type`／`_version` 不對＝`SpecInvalid`；`command` 不是這個 CMD 或 mode 不同＝`SpecMismatch`；原文 sha256 不同＝`HelpChanged`；任何一格不過機械檢查＝`SpecInvalid`。改參數表的做法：改包裡的 `wrapcli.json`，再 `wrap-cli CMD --spec PACK/wrapcli.json --force`。

**提案**：`<out>/<PACK>.wrapcli.json`，最後一行 `看過沒問題：aos-agent tools wrap-cli CMD --spec <那個檔>`。argparse 模式送模型的是「第一個 `ArgumentParser` 到最後一個 `add_*`」那段原始碼；help 文字超過 12000 字截斷。

## 產的包與 `run`

`PACK.json`（一支工具，名字＝包名的 `-` 換 `_`；`_meta.argv`＝`["tools/PACK/run"]`；不寫 `_jail`＝預設關牢）、`run`、`wrapcli.json`、`src/`（檔才有）、`_common.py`、`config.json`、`README.md`。
`run`：stdin 的 arguments 照參數表驗（多給、少給必填、型別、choices、字串含 NUL、count 超過 0～50＝`BadArguments`）→ 組 argv：開關 true 才加、count 重複 N 次、帶值選項照順序（優先用長旗標；joiner `=` 寫成 `--x=v`；陣列 `repeat` 每個值一次、`once` 一次接全部）、位置參數最後（有 `-` 開頭的值先放 `--`）→ **不經 shell** 跑，cwd＝工作根目錄、stdin 關。回 stdout（只留結尾 2000 行）；stdout 空就附 stderr。退出碼非 0＝`CommandFailed`（stdout 在前，JSON 帶 `exit_code`、`stderr` 尾巴 2000 字）；`timeout`（預設 50 秒）到了砍整個群組＝`Timeout`；跑不起來＝`SpawnFailed`。
**不支援**：子命令（`git log` 這種兩層）、互斥與相依關係、選項的選填值（`--color[=WHEN]` 只能帶值給）、環境變數與 stdin 輸入。

