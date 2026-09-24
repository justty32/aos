# inst.json posix v1 ＋ 指示詞——使用者 2026-09-21 逐輪拍板的修訂（任務書副本；正式規範在 ../spec/）

目前規範：../spec/inst-posix.md
目前程式：../../proto4-3/aos_inst.py、aos_inst_resolve.py、aos_exec.py
使用手冊：../../proto4-3/docs/exec.md

仍然是 posix `_version` 1（v1 還沒對外凍結，直接改 v1）。

## A. 不認識的頂層 key → 忽略

- 頂層物件裡七個欄位＋`_metainfo` 以外的 key **一律忽略**，不再有 `UnknownKey`。
- `_metainfo` 裡面 `_type`／`_version` 以外的 key **也忽略**；`_type`／`_version` 仍必填、仍嚴驗
  （`_type` 只認 `"posix"`、`_version` 只認整數 1、bool 不算）。`MetainfoInvalid` 現在只剩
  「`_metainfo` 不是物件」或「缺 `_type`／`_version`」兩種。
- 錯誤代號 `UnknownKey` 整個拿掉（程式、測試、文件）。

## B. `$opt` 統一形狀

一個「選項物件」長這樣：

    {"$opt": "名字"}                       單一選項、不帶值
    {"$opt": "名字", "$val": 值}           單一選項、帶值
    {"$opt": ["名字1", "名字2"], "$val": 值}  多個選項

- `$opt` 的值是**字串**或**非空字串陣列**；別的型別 → `DirectiveValueTypeMismatch`。
  陣列裡重複同一個名字 → `UnknownOption`（訊息說「重複」）。
- `$val` 是「本來要直接寫在那一格的值」，型別照那一格的規則驗；**`$val` 本身可以再是指示詞**
  （`$env`／`$fmt`／`$ref`），解完再驗。
- 選項物件只能有 `$opt`、`$val` 兩個 key；多了 → `DirectiveKeyCountInvalid`。
  **舊的 `$envs` 這個 key 不再認得**（等同多了一個 key → 拒絕）。
- 這個位置不認得的選項名 → `UnknownOption`。
- 有些選項**不能帶 `$val`**（帶了 → `OptionConflict`）；有些**一定要帶**（沒帶 → `OptionConflict`）。
- 互斥的選項一起出現 → `OptionConflict`。
- 選項名區分大小寫，只認小寫。

## C. 各位置能用的選項

| 位置 | 選項 | `$val` | 意思 |
|---|---|---|---|
| `stdin` | `inherit` | 不能帶 | 繼承執行者（aos-exec）的標準輸入 |
| `stdout` | `append` | 必帶（路徑） | `>>`：檔案存在就接在後面，不存在就建 |
| `stdout` | `mkdir` | 必帶（路徑） | 父目錄不在就先建（`makedirs`） |
| `stdout` | `inherit` | 不能帶 | 繼承執行者的標準輸出 |
| `stderr` | `append`／`mkdir`／`inherit` | 同 stdout | 同上 |
| `stderr` | `merge` | 不能帶 | 跟 stdout 走同一條（`2>&1`），照 stdout 的設定（含 append／inherit） |
| `exit` | `append` | 必帶（路徑） | `>>`：結束碼一行一行接在後面 |
| `exit` | `mkdir` | 必帶（路徑） | 父目錄不在就先建 |
| `cwd` | `mkdir` | 必帶（路徑） | 目錄不在就先建（`makedirs`） |
| `envs` | `clear` | 可省（物件；省略＝`{}`） | 從空環境開始，只放 `$val` 裡的 |

可以合併的：`append`＋`mkdir`（stdout／stderr／exit）。
互斥的：`inherit` 跟 `append`／`mkdir`／`merge` 任何一個；`merge` 跟 `append`／`mkdir`／`inherit`。
`inherit`／`merge` 帶了 `$val` → `OptionConflict`。

`cwd` 的 `mkdir` 是先解 cwd、建目錄，之後其他相對路徑一樣以它為中心。
`exit`／`stdout`／`stderr` 的 `mkdir` 在開檔前做；`makedirs` 失敗 → 執行者自己失敗（125）。
`append` 對 `exit`：寫「十進位＋換行」接在檔尾，fsync 檔與父目錄照舊。
`inherit`：Popen 那條串流傳 None（跟普通檔案模式一樣）。aos-exec 命令列的 `--stderr -`／`--stderr PATH`
仍然蓋過 inst.json 的 stderr 設定（包括 merge／inherit／append）。

## D. `load()` 回傳值

除了原本的欄位，每條串流／路徑欄要把選項帶出來讓執行者用。建議形狀（實作者可以微調，但要一致）：

    "stdin":  {"path": "/abs/或空字串", "inherit": bool}
    "stdout": {"path": ..., "append": bool, "mkdir": bool, "inherit": bool}
    "stderr": {"path": ..., "append": bool, "mkdir": bool, "inherit": bool, "merge": bool}
    "exit":   {"path": ..., "append": bool, "mkdir": bool}
    "cwd":    "/abs"        另加 "cwd_mkdir": bool
    "envs":   dict          另加 "envs_clear": bool（照舊）
    "metainfo": {...}       照舊

舊的 `stderr_merge` 欄位併進 `stderr.merge`。凡是 import `aos_inst.load()` 的地方
（aos_exec.py、測試、proto4-4／4-5／4-6／4-7 如果有用到）都要跟著改——先 grep：
`grep -rn "aos_inst\|stderr_merge\|envs_clear\|\"\$envs\"" --include=*.py --include=*.json --include=*.md --include=*.sh ../.. --exclude-dir=build --exclude-dir=.git`

## E. 舊寫法要遷移

repo 裡所有用到 `{"$opt":"clear","$envs":{…}}` 的地方（測試、docs、playground、proto4-x 範例）
都改成 `{"$opt":"clear","$val":{…}}`。

## F. 錯誤代號表（讀／驗階段，最終版）

ReadFailed、JsonSyntax、NotAnObject、MetainfoInvalid、UnsupportedInstType、UnsupportedInstVersion、
EmptyArgv、FieldTypeMismatch、EnvKeyInvalid、DirectiveKeyCountInvalid、UnknownDirective、
DirectiveValueTypeMismatch、UnknownOption、OptionConflict（新）、EnvironmentVariableMissing、
UnknownFormatVariable、ReferenceReadFailed、ReferenceJsonInvalid、ReferencePointerInvalid、ReferenceCycle。
（UnknownKey 刪除。）

## G. `$fmt` 改成「模板＋變數表」，沒有 `${env:…}` 特例（使用者 2026-09-21 最終拍板）

只有一種寫法：

    {"$fmt": {"$val": "aaa${xxx}, bbb${zzz}", "xxx": {"$env":"yyy"}, "zzz": "haha"}}

- `$fmt` 的值**必須是物件**；是字串或別的 → `DirectiveValueTypeMismatch`（舊的字串寫法不再認得）。
- `$val` **必填**，是模板；它自己可以是指示詞，解完必須是字串（不是 → `DirectiveValueTypeMismatch`）。
- 物件裡 `$val` 以外的每個 key 都是**本地變數名**，值是字串或任何指示詞（`$env`／`$ref`／`$fmt`…），
  解完必須是字串（不是 → `DirectiveValueTypeMismatch`）。變數用同一個中心路徑／同一條 `$ref` 鏈解。
- 變數名不能 `$` 開頭、不能是空字串、不能含 `{`、`}` → `FormatVariableInvalid`（新代號）。
- 模板裡 `${name}` **只查本地變數表**，沒有任何 namespace、沒有 `${env:…}` 特例；表裡沒有 →
  `UnknownFormatVariable`。要環境變數就在表裡寫 `"x": {"$env": "NAME"}`。
- 只有 `${…}` 會被代換；單獨的 `$`、`$NAME` 是字面。**展開一次、不再掃結果**：變數值裡再出現
  `${…}` 是字面。定義了沒用到的變數沒關係。
- 取值指示詞「值一定是字串」那條，改成「`$env`／`$ref` 的值是字串；`$fmt` 的值是物件」。
- **遷移**：repo 裡所有 `{"$fmt": "…${env:NAME}…"}` 改成 `{"$fmt": {"$val": "…${v}…", "v": {"$env": "NAME"}}}`
  （測試、docs/exec.md、playground、proto4-x 範例都要 grep：`grep -rn '\$fmt' --include=*.py --include=*.json --include=*.md --include=*.sh`）。

## H. 指示詞物件可以混寫；多個指示詞照優先順序（使用者 2026-09-21 第三次拍板）

- 一個物件只要有 `$` 開頭的 key 就是指示詞物件（照舊）。**裡面可以有任何其他 key**：
  不認得的 key（`_note`、`x`…）一律忽略。
- 同一個物件裡出現多個指示詞 key 時，**只跑優先順序最高的那一個，其餘忽略**：
      $opt  >  $ref  >  $fmt  >  $env
  例：`{"$ref": "a.json", "$fmt": {...}}` → 跑 `$ref`，`$fmt` 不看；
      `{"$ref": "a.json", "_note": "說明"}` → 跑 `$ref`。
- 選項物件（有 `$opt`）：認 `$opt`／`$val`，其他 key（含 `$ref`／`$fmt`／`$env`、舊的 `$envs`）一律忽略。
  → 舊寫法 `{"$opt":"clear","$envs":{…}}` 不再報錯，`$envs` 被忽略、等於清空成空環境（要寫進「容易踩的」）。
- `$fmt` 物件內部的變數表不受此影響：`$val` 以外的 key 是變數名，`$` 開頭仍是 `FormatVariableInvalid`。
- 有 `$` 開頭的 key、但四個都不是（例如只有 `{"$xyz": 1}`）→ 仍是 `UnknownDirective`。
- **`DirectiveKeyCountInvalid` 這個代號整個拿掉**（程式、測試、兩份規範、docs）。
- 「取值指示詞＝剛好一個 key」的說法整個拿掉。

## I. `$ref` 尋址拆成 `$ref`＋`$at`，支援相對位置（使用者 2026-09-21 第四次拍板）

    {"$ref": "a.json"}                       整份 a.json
    {"$ref": "a.json", "$at": "/x/y/0"}      a.json 裡的 /x/y/0（開頭 / ＝從那份文件的根算）
    {"$ref": "",       "$at": "/envs/PATH"}  $ref 空字串＝「這個值所在的那份檔案」自己
    {"$ref": "",       "$at": "./a", "a": true}   ./ ＝這個指示詞物件自己的位置 → 它的 key a → true
    {"$ref": "",       "$at": "../GREET"}    ../ ＝往上一層（兄弟 key）

- `$ref` 值一定是字串（不是 → `DirectiveValueTypeMismatch`）；相對路徑仍以宿主給的中心路徑（inst＝cwd）找檔；
  **空字串＝目前正在解析的那份文件**（頂層 inst.json，或透過 `$ref` 取進來後、值所在的那份檔）。
- `$at` 可省＝整份；有寫必須是字串（不是 → `DirectiveValueTypeMismatch`）。
- `$at` 語法：用 `/` 分段。開頭 `/`＝絕對（從那份文件的根）；開頭 `./` 或 `../`＝相對於**目前位置**
  （＝這個指示詞物件在文件裡的位置）；`.` 段略過、`..` 段往上一層、爬過根 → `ReferencePointerInvalid`；
  其他段：`~1`→`/`、`~0`→`~`，物件用 key、陣列用十進位索引；走不到 → `ReferencePointerInvalid`。
  不是 `/`、`./`、`../` 開頭的 `$at` → `ReferencePointerInvalid`。
- **相對寫法只有 `$ref:""` 能用**：指別的檔卻用 `./`／`../` → `ReferencePointerInvalid`（別的檔沒有「目前位置」）。
- 舊的 `檔案#/pointer` 寫法拿掉：`#` 只是檔名的一部分（會變 `ReferenceReadFailed`）。repo 裡的舊寫法要遷。
- 取回來的值原樣放進那一格；值裡若再有指示詞，繼續解時「目前文件」＝被引用的那份檔、「目前位置」＝取到的位置。
  所以解析器要一路帶著 (目前文件的 realpath, 目前文件的根物件, 目前位置 pointer)。
- 循環：鏈記 (檔案 realpath, 解出來的絕對位置)；`{"$ref":"", "$at":"."}` 指到自己＝`ReferenceCycle`。
- 頂層 inst.json 的「目前文件」就是它自己、位置是根 `/`；各欄位的位置就是 `/argv/0`、`/envs/PATH`、
  `$fmt` 物件內的變數是 `/envs/PATH/p` 這種自然路徑（`$val` 是 `/envs/PATH/$val`）。
- 錯誤代號：`ReferenceReadFailed`／`ReferenceJsonInvalid`／`ReferencePointerInvalid`／`ReferenceCycle` 照舊沿用。
- **`$envs` 那條「容易踩的」不用寫**（使用者說舊用法沒人在用）——規範裡拿掉。

## J. `$opt` 的值不限型別（使用者 2026-09-21 第五次拍板）

- **機制層（directives.md）**：選項物件＝有 `$opt` key 的物件。`$opt` 的值**任何 JSON 都可以**
  （字串、數字、物件、陣列、null…），機制**不解讀、不驗型別、不解指示詞**，原樣交給宿主；`$val`
  照舊是「本來要寫在那格的值」（宿主要的話再拿去 resolve）。其他 key 一律忽略。
  → lib 的 `parse_options` 拆成兩層：`split_option(value) -> (opt_raw, val, has_val)`（零驗證），
    加一個給「名字／名字陣列」慣例宿主用的 helper `option_names(opt_raw, position, table)`（原本那套
    驗證：字串或非空字串陣列、重複、不認得、val 必帶／不能帶、alone）。
- **inst 宿主（inst-posix.md 3.3）**：維持「`$opt` 是選項名字串或非空名字陣列」，別的型別 →
  `DirectiveValueTypeMismatch`（這是 inst 的規則，不是機制的）。
- 機制層錯誤代號表：`DirectiveValueTypeMismatch` 的說明拿掉「`$opt` 的值不是字串／陣列」那半句；
  `UnknownOption`／`OptionConflict` 標明「由宿主的選項表決定」。

## K. `$ref` 字串可以帶 `#位置`；相對位置在別的檔也能用（使用者 2026-09-21 第六次拍板）

    {"$ref": "main.json#/a/b"}        ＝ {"$ref": "main.json", "$at": "/a/b"}
    {"$ref": "main.json#./a/b"}       別的檔的「目前位置」＝它的根，所以 ＝ /a/b
    {"$ref": "#../GREET"}             檔案空＝目前文件，從目前位置往上
    {"$ref": "", "$at": "../GREET"}   同上

- `$ref` 字串以**第一個 `#`** 切開：前面是檔案（空＝目前文件）、後面是位置字串（等同 `$at`）。
  沒有 `#` ＝整份。代價：檔名含 `#` 的檔沒辦法被 `$ref`。
- `$at` key 跟 `#` 位置**同時有 → `$at` 贏，`#` 後面那段忽略**。
- 相對位置（`./`、`../`）的規則統一成：**相對於「目前位置」**。`$ref` 指目前文件時，目前位置＝這個
  指示詞物件所在的位置；`$ref` 指別的檔時，目前位置＝那份檔的根。所以 `x.json#./a` ＝ `/a`，
  `x.json#../a` 爬過根 → `ReferencePointerInvalid`。I 節「相對寫法只有 `$ref:""` 能用」那條**作廢**。
- 其餘（`.`／`..` 段、`~1`／`~0`、陣列索引、走不到 → `ReferencePointerInvalid`、循環身分）照 I 節。

## L. 「位置」一律是原始 JSON 的實體路徑（我依 proto4-3 第四輪的發現補的，使用者未反對即照做）

- 相對 `$at` 用的「目前位置」＝這個指示詞物件**在原始文件裡的實體路徑**，含 `$fmt`、`$val`、`$opt`
  這些 key：`envs` 的 `PATH` 用 `$fmt`、變數 `p` 的位置是 `/envs/PATH/$fmt/p`；`$fmt` 的模板在
  `/envs/PATH/$fmt/$val`；選項物件的值在 `/stdout/$val`。I 節「`$fmt` 變數是 `/envs/PATH/p`」那句作廢。
- 這樣 `$fmt` 變數之間才能互指：`"b": {"$ref": "", "$at": "../a"}` 從 `/…/$fmt/b` 往上到 `/…/$fmt/a`。
- `$at` 的空段（`"/"`、`"./"` 尾巴的空字串）照 RFC 6901 當 key `""`，不略過。
