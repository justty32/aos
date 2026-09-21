# proto4-3／aos-exec
← [README](../README.md)

## 三種目標

`aos-exec xxx [--dir-target REL] [--timeout-ms N] [--stderr PATH|-] [-- ARG...]`，看 `xxx` 是什麼決定怎麼跑：

| `xxx` 是 | 做什麼 | cwd 預設 | 串流 |
|---|---|---|---|
| 普通檔案（副檔名不是 `.json`） | 直接執行它：`argv[0]` 是它的絕對路徑，`--` 後原樣接成 `argv[1:]` | 它所在的資料夾 | **繼承** aos-exec 的 |
| `.json` 檔（**不存在也走這條**） | 讀進來當 inst.json 解析、執行 | 那個 `.json` 所在的資料夾 | 照 inst.json |
| 資料夾 | 執行 `xxx/.aos/inst.json`（`--dir-target` 可改） | `xxx` 自己 | 照 inst.json |

普通檔案模式不解析 `--` 後的內容：空字串、空白、看起來像旗標的字串都原樣當一個
argv 元素。環境就是繼承的、沒有 exit 檔、沒有重導向。它沒有執行位＝126。

`.json` 或資料夾目標給了 `--`（就算後面沒有元素）是用法錯，退出碼 2：**inst 目標的
參數寫在 inst.json 的 `argv` 裡**。

先看是不是資料夾再看副檔名，所以一個名字剛好以 `.json` 結尾的**資料夾**還是照資料夾走。

**一個以 `.json` 結尾但不存在的路徑不是用法錯**，是 aos-exec 自己失敗（`kind=aos`、退出碼
125）：這樣 aos-daemon 才能收下一份還沒出現的 inst.json，檔案一出現就自然跑起來。不存在
的**非** `.json` 路徑照舊是用法錯（退出碼 2）。

`--timeout-ms` 三種模式都吃；`0` 或不給＝不限。

## inst.json 長什麼樣

只能是**一個 JSON 物件**，七個欄位，只有 `argv` 必填；**沒寫在表上的頂層 key 一律忽略**
（2026-09-21 起；以前是拒絕，`UnknownKey` 這個代號已經沒了）。頂層另外允許一個可選的
`_metainfo`，見下方說明。這是 posix v1 格式，規範本文在
[proto5/spec/inst-posix.md](../../proto5/spec/inst-posix.md)。

```json
{
  "_metainfo": {"_type": "posix", "_version": 1},
  "argv": ["sh", "-c", "cat; echo $GREET"],
  "stdin": "in.txt",
  "stdout": {"$opt": ["append", "mkdir"], "$val": "logs/out.txt"},
  "stderr": {"$opt": "merge"},
  "exit": "code.txt",
  "cwd": "sub",
  "envs": {"GREET": "hi", "PATH": {"$fmt": {"$val": "${p}:/opt/bin", "p": {"$env": "PATH"}}}}
}
```

### `_metainfo`：這份 inst 是哪一種、第幾版（可選）

只講「這份 inst.json 用的是哪一種格式、第幾版」，不參與執行——不是環境變數、不是參數、
不會傳給子程式：

- **沒寫就等於 `{"_type": "posix", "_version": 1}`**，所以以前寫的 inst.json 都不用改。
- 寫了就必須是一個 JSON 物件、**一定有** `_type` 跟 `_version` 這兩個 key；`_type` 是字串
  `"posix"`；`_version` 是整數 `1`（JSON 的 `true`／`false` 不算整數）。這兩個以外的 key
  忽略。
- 不符合上面任何一條都拒絕（見下面 125 的表）：不是物件或缺 `_type`／`_version`＝
  `MetainfoInvalid`、`_type` 不是 `"posix"`＝`UnsupportedInstType`、`_version` 不是 `1`＝
  `UnsupportedInstVersion`。

| 欄位 | 型別 | 沒寫時 | 意思 | 選項（見下一節） |
|---|---|---|---|---|
| `argv` | 字串陣列 | **必填** | 跑什麼；`argv[0]` 走**疊加後**的 `envs` 裡的 PATH | 無 |
| `stdin` | 路徑 | `/dev/null` | 拿這個**檔案**當標準輸入（不是塞字串） | `inherit` |
| `stdout` | 路徑 | `/dev/null` | 標準輸出寫到這個檔（建立並清空） | `append`／`mkdir`／`inherit` |
| `stderr` | 路徑 | `/dev/null` | 同上 | `append`／`mkdir`／`inherit`／`merge` |
| `exit` | 路徑 | 不寫 | 跑完把結束碼（十進位＋換行）寫進去，fsync 檔案與父目錄 | `append`／`mkdir` |
| `cwd` | 路徑 | `xxx` | 工作目錄 | `mkdir` |
| `envs` | 物件 | `{}`＝只有繼承的 | 疊在 aos-exec 的環境上只加不減；key 不能空、不能含 `=`、不能 `$` 開頭；整包也可以用 `$ref` 從別的檔拿 | `clear` |

**相對路徑的中心是 cwd**：`stdin`／`stdout`／`stderr`／`exit` 和 `$ref` 都從**解析完的
cwd** 起算。只有 `cwd` 自己從 `xxx` 起算——它是最先解的那一個。絕對路徑照字面用。

這裡沒有任何 shell 解讀：引數不會被切分、展開，也不會被當成重導向語法。真的要 shell 行為
就自己寫 `argv: ["sh", "-c", "..."]`。

### 選項物件 `{"$opt": …, "$val": …}`

一格本來要寫值的地方，可以改寫一個**選項物件**，替那一格開一些開關：

```json
{"$opt": "名字"}                          單一選項、不帶值
{"$opt": "名字", "$val": 值}              單一選項、帶值
{"$opt": ["名字1", "名字2"], "$val": 值}   多個選項一起開
```

- `$val` 就是「本來要直接寫在那一格的值」：型別照那一格的規則驗（路徑欄要字串、`envs`
  要物件），**自己還能再是指示詞**（`$env`／`$fmt`／`$ref`），解完再驗。
- 選項物件**只能有** `$opt`、`$val` 兩個 key，多了＝`DirectiveKeyCountInvalid`。舊寫法
  `{"$opt":"clear","$envs":{…}}` 裡的 `$envs` 已經不認得，就是多了一個 key。
- `$opt` 是字串或**非空**字串陣列，別的型別＝`DirectiveValueTypeMismatch`。陣列裡同一個
  名字寫兩次＝`UnknownOption`。
- 選項名區分大小寫、只認小寫；這個位置不認得的名字＝`UnknownOption`（包括根本不吃選項的
  位置，像 `argv` 的元素）。
- 帶／不帶 `$val` 不合規定、或互斥的一起開＝`OptionConflict`。

| 位置 | 選項 | `$val` | 意思 |
|---|---|---|---|
| `stdin` | `inherit` | 不能帶 | 繼承 aos-exec 的標準輸入（普通檔案模式本來就是這樣） |
| `stdout`／`stderr` | `append` | 必帶（路徑） | `>>`：檔案存在就接在後面，不存在就建 |
| `stdout`／`stderr` | `mkdir` | 必帶（路徑） | 父目錄不在就先 `makedirs` |
| `stdout`／`stderr` | `inherit` | 不能帶 | 繼承 aos-exec 的那一條 |
| `stderr` | `merge` | 不能帶 | 跟 stdout 走同一條（`2>&1`）——**照 stdout 的設定走**，stdout 是 append／inherit 它就跟著 |
| `exit` | `append` | 必帶（路徑） | 結束碼一行一行接在檔尾（fsync 照舊） |
| `exit` | `mkdir` | 必帶（路徑） | 父目錄不在就先建 |
| `cwd` | `mkdir` | 必帶（路徑） | 目錄不在就先建；建好之後其他相對路徑一樣以它為中心 |
| `envs` | `clear` | 可省（物件；省略＝`{}`） | 從空環境開始，只放 `$val` 裡的 |

可以一起開的：`append`＋`mkdir`。互斥的：`inherit` 跟任何別的、`merge` 跟任何別的。
`append`／`mkdir` 的 `$val` 不能是空字串（空字串在路徑欄的意思是「沒寫」）。

`mkdir` 在 chdir／開檔**之前**做，`makedirs` 做不到（路徑中間卡一個普通檔、沒權限）＝
aos-exec 自己失敗，退出碼 125。沒開 `mkdir` 就照舊：父目錄不存在＝125，不幫你建。

```json
"stdout": {"$opt": "append", "$val": "log.txt"}                   每次跑都接在 log.txt 後面
"stdout": {"$opt": ["append", "mkdir"], "$val": "logs/out.txt"}   logs/ 不在就先建
"stderr": {"$opt": "merge"}                                        跟 stdout 同一條
"stdin":  {"$opt": "inherit"}                                      讀 aos-exec 的 stdin
"exit":   {"$opt": "append", "$val": "codes.txt"}                  一行一個結束碼
"cwd":    {"$opt": "mkdir", "$val": "work/1"}                      work/1 不在就先建
"envs":   {"$opt": "clear", "$val": {"LANG": "C"}}                 從空環境開始，只放 $val 裡的
"envs":   {"$opt": "clear"}                                        完全空的環境
```

清空之後 PATH 也沒了，`argv[0]` 退回 Python 的 `os.defpath`（這台機器上是 `/bin:/usr/bin`），所以
`sh` 之類的還是找得到。想讓它找不到就自己塞一個 `$val: {"PATH": "..."}`。

**aos-exec 不注入任何 `AOS_*` 環境變數**——tick 是 aos-run 的事，這裡保持乾淨。

### 指示詞：任何位置都能放

**先解、再驗。** inst.json 裡**任何一個值的位置**都可以不寫本來該寫的東西，改寫一個
**指示詞**——剛好一個 key、值一定是字串的物件。位置包括：**頂層整份**、每個欄位、
`argv` **整個陣列**與它的每個元素、四個路徑欄位、`cwd`、`envs` **整個物件**與它的每個值、
選項物件的 `$val`。指示詞解出來的東西就當成本來寫在那裡，**解出來又是指示詞就繼續解**，
最後才照那個位置該有的型別驗（頂層要物件、`argv` 要非空字串陣列、路徑欄要字串、`envs`
要物件）。

| 指示詞 | 意思 |
|---|---|
| `{"$env":"NAME"}` | 從 **aos-exec 自己的**環境取值。變數不存在＝錯誤；存在但空＝空字串（兩件不同的事） |
| `{"$fmt":{"$val":"模板", 變數名: 值, …}}` | 接字串用的：`$val` 是模板、其餘 key 是本地變數表，見下面 |
| `{"$ref":"file.json#/a/b"}` | 相對於 **cwd** 讀那份 JSON，`#` 後面是 RFC 6901 的 JSON Pointer（`~1` 代表 `/`、`~0` 代表 `~`），沒有 `#` 就取整份 |

（`{"$opt": …}` 不是指示詞，是上一節的選項物件——它是唯一可以有兩個 key 的東西。）

```json
{"$ref": "base.json"}                              整份 inst.json 從別的檔拿
{"argv": {"$ref": "a.json#/argv"}}                 argv 整個陣列從別的檔拿
{"argv": ["true"], "envs": {"$ref": "e.json"}}     envs 整包從別的檔拿
```

`$ref` **取回來的值原樣當成本來寫在那裡**：字串、陣列、物件都行，型別對不對是那個**位置**
說了算——所以 `envs` 的 `$ref` 解出來是字串＝`FieldTypeMismatch`、`argv` 的解出來是字串
也一樣。`$env`／`$fmt` 解出來一定是字串，放在 `envs` 那種要物件的位置就是型別錯。

**循環**：`$ref` 沿著一條鏈記「檔案 realpath ＋ pointer」，**任何深度都記**，同一條鏈再
撞到同一個身分＝繞回來了＝錯誤。頂層寫 `{"$ref": "自己"}` 也擋得到。

**一個物件只要有 `$` 開頭的 key 就被當指示詞看**（有 `$opt` 的選項物件除外）。所以 `envs`
的 key——也就是環境變數名——不能 `$` 開頭，混寫（`{"$ref": "e.json", "X": "1"}`）＝兩個
key＝拒絕。`envs` 的 key 本身不吃指示詞。代價：這一版沒辦法傳 `$` 開頭的環境變數。

**`$fmt`**：模板＋本地變數表，值**一定是物件**（2026-09-21 起；舊的字串寫法
`{"$fmt": "…${env:NAME}…"}` 不再認得＝`DirectiveValueTypeMismatch`）：

```json
{"$fmt": {"$val": "aaa${xxx}, bbb${zzz}", "xxx": {"$env": "yyy"}, "zzz": "haha"}}
{"$fmt": {"$val": "${p}:/opt/bin", "p": {"$env": "PATH"}}}        把 /opt/bin 接在 PATH 後面
```

- `$val` **必填**，是模板；它自己可以再是指示詞，解完必須是字串。
- 物件裡 `$val` 以外的每個 key 都是**本地變數名**，值是字串或任何指示詞（`$env`／`$ref`／
  巢狀 `$fmt`），跟這份 `$fmt` 用同一個中心（cwd）與同一條 `$ref` 鏈解，解完必須是字串
  （不是＝`DirectiveValueTypeMismatch`）。
- 變數名不能 `$` 開頭、不能空、不能含 `{`／`}`＝`FormatVariableInvalid`。
- 模板裡 `${name}` **只查這張本地表**，沒有任何 namespace、沒有 `${env:…}` 特例；表裡沒有＝
  `UnknownFormatVariable`。要環境變數就在表裡寫 `"x": {"$env": "NAME"}`（不存在＝錯誤；
  存在但空＝空字串）。
- 只有 `${…}` 會被代換。單獨的 `$` 與 `$NAME` 都是**字面**，不展開也不用跳脫。
- **展開一次、不再掃結果**：變數值裡再出現 `${…}` 就是字面。定義了沒用到的變數沒關係。

## 看不到錯誤？加 `--stderr -`

inst.json 沒寫 `stderr` 時，子程式的錯誤預設進 `/dev/null`。加 `--stderr -` 就會印到
aos-exec 自己的 stderr；給檔案路徑則寫進那個檔，路徑以你呼叫 aos-exec 時的 cwd 為中心。
它會蓋過 inst.json 原有的 `stderr` **整個設定**，包括 `merge`／`inherit`／`append`／`mkdir`
（被蓋掉的 `mkdir` 也不會建）；stdin／stdout／exit 不會蓋。

## aos-exec 的退出碼：自己的失敗跟子程式的碼分開

`run_target()` 回的是 **`(code, kind)`**，`kind` 說這個碼是誰的：

| `kind` | 意思 | 命令列的退出碼 |
|---|---|---|
| `child` | **子程式真的跑完了一次**：它的 exit code、被訊號 N 砍＝128+N、沒執行權＝126、找不到程式＝127、逾時＝143／137 | **原樣** |
| `aos` | **aos-exec 自己失敗，那次根本沒跑**（`code` 是 1） | **125** |
| `usage` | 用法錯（`code` 是 2） | 2 |

`kind == "child"` ⇔「跑完了一次」⇔ `exit` 欄位有被寫，這條線兩邊都對得起來。

| 退出碼 | 什麼時候 |
|---|---|
| 2 | 用法錯（旗標不認得、沒給 `xxx`、`--timeout-ms` 是負數、inst 目標卻給了 `--`）、`xxx` 是不存在的**非** `.json` 路徑、`--dir-target` 指的檔不存在 |
| **125** | **aos-exec 自己失敗**：inst.json 讀不到（**指名的 `.json` 不存在也算**）／不是 JSON 物件／格式壞（型別錯、`argv` 空、`envs` 的 key 壞、指示詞壞、選項物件壞＝`UnknownOption`／`OptionConflict`、`_metainfo` 形狀不對＝`MetainfoInvalid`／`UnsupportedInstType`／`UnsupportedInstVersion`）／`$fmt` 的變數表壞＝`FormatVariableInvalid`、模板用了表裡沒有的變數＝`UnknownFormatVariable`／`$env` 的變數不存在／`$ref` 讀不到、pointer 壞、繞回來了／`mkdir` 建不起來／`exit` 檔的父目錄不存在／`cwd` 不是資料夾／重導向的檔開不起來 |
| 126 | 沒執行權 |
| 127 | 找不到程式 |
| 143 / 137 | `--timeout-ms` 到了：SIGTERM 就死＝143，要 SIGKILL 才死＝137 |
| 其他 | **原樣**是子行程的結束狀態：正常結束＝它的 exit code，被訊號 N 砍＝128+N |

**為什麼是 125**：子程式回 1 是很常見的事，aos-exec 自己失敗也回 1 的話，看的人分不出
「指令跑了但失敗」跟「指令根本沒跑」。125 撞不到 shell 那套（126／127／128+N），跟
`timeout(1)`、`env(1)` 挑的號碼是同一個理由。

125 與 2 會印一行 `aos-exec: <原因>` 到 **aos-exec 自己的 stderr**（格式壞掉的那行開頭是
代號，像 `OptionConflict:`、`ReferenceCycle:`）。126／127 也印一行。

讀／驗階段的代號全表：`ReadFailed`、`JsonSyntax`、`NotAnObject`、`MetainfoInvalid`、
`UnsupportedInstType`、`UnsupportedInstVersion`、`EmptyArgv`、`FieldTypeMismatch`、
`EnvKeyInvalid`、`DirectiveKeyCountInvalid`、`UnknownDirective`、`DirectiveValueTypeMismatch`、
`FormatVariableInvalid`、`UnknownOption`、`OptionConflict`、`EnvironmentVariableMissing`、
`UnknownFormatVariable`、
`ReferenceReadFailed`、`ReferenceJsonInvalid`、`ReferencePointerInvalid`、`ReferenceCycle`。

有寫 `exit` 欄位的話，126／127／逾時一樣算「跑完了一次」，那個數字照樣寫進 exit 檔。
125 與 2 是 **aos-exec 自己**失敗，不寫 exit 檔。

**逾時怎麼砍**：先對**整個 process group** 送 SIGTERM，給 2 秒，直接子行程還活著就 SIGKILL
整個 group（收完屍再補一發，因為直接子行程死了不代表群組空了）。
