# inst.json 規範：`posix` 呼叫（第 1 版）

← [proto5 README](../README.md)｜規範先行；指示詞機制的實作是
[proto5/lib/aos_directives.py](../lib/aos_directives.py)（[lib README](../lib/README.md)）；inst
本身（讀、驗、執行）的 proto5 實作還沒寫，proto4-3 的 [aos_inst.py](../../proto4-3/aos_inst.py)／
[aos_exec.py](../../proto4-3/aos_exec.py) 是凍結的舊版參考（大致照這份做到 §I 為止；使用手冊
[docs/exec.md](../../proto4-3/docs/exec.md)）

這份文件把「一份 inst.json 到底長什麼樣、怎麼解讀」寫成規範。規範先行：程式照本文做；程式跟
本文對不上、又不是本文寫錯的地方，回來改本文。

一句話：**一份 inst.json 就是「叫作業系統跑一個程式」那一句話的 JSON 版**——跑什麼（`argv`）、
在哪跑（`cwd`）、三條串流接哪（`stdin`／`stdout`／`stderr`）、結束碼寫哪（`exit`）、環境變數
（`envs`）。沒有 shell、沒有管線、沒有萬用字元，就是一次 `execve`。

---

## 1. `_metainfo`：這份 inst 是哪一種、第幾版

從 proto5 起，inst.json 頂層**可以**多一個 `_metainfo` 欄位，說明「這份 inst 用的是哪一種格式、
第幾版」：

```json
{
  "_metainfo": {"_type": "posix", "_version": 1},
  "argv": ["sh", "-c", "echo hi"]
}
```

| 鍵 | 型別 | 意思 |
|---|---|---|
| `_type` | 字串 | 格式種類。目前只有一種：`"posix"`＝本文描述的這套 |
| `_version` | 整數 | 該種格式的版本。`posix` 目前是 `1` |

**規則：**

1. **沒寫 `_metainfo`，就等於 `{"_type": "posix", "_version": 1}`**。所以之前寫的所有 inst.json
   都不用動、意思不變。
2. `_metainfo` 本身要是物件；除了 `_type`、`_version`，裡面**其他 key 一律忽略**，不要求「剛好
   只有這兩個 key」。少了 `_type` 或 `_version` → `MetainfoInvalid`。
3. `_type` 只認字面的 `"posix"`；別的字串（例如以後可能的 `"step"`）或非字串 →
   `UnsupportedInstType`。
4. `_version`（`posix`）只認整數 `1`；JSON 的 `true`／`false` 不算數（有些語言把 bool 當
   int 的子類，這裡特地擋掉）→ `UnsupportedInstVersion`。版號大於本文版號的 `posix` inst，
   讀的人**不該假裝看得懂**：要嘛拒絕（同一個代號），要嘛明講降級。
5. `_metainfo` 只描述格式，**不參與執行**——不是環境變數、不是參數、不會傳給子程式；它的值也
   **不吃指示詞**：是從 JSON 直接拿出來驗，不會丟進第 4 節那套 `$env`／`$fmt`／`$ref` 展開。
   所以寫 `{"_metainfo": {"$ref": "x.json"}}`，`$ref` 這個 key 不是 `_type`／`_version`，會被
   忽略——這個例子等於沒寫 `_type`／`_version`，一樣是 `MetainfoInvalid`（原因是缺欄位，不是
   多欄位）。
6. `_type` 不是 `"posix"` 的 inst，本文管不到；那是之後別種 inst（例如以後可能有的
   `"step"`、`"llm"` 之類）各自的規範。
7. 以 `_` 開頭的頂層鍵保留給 metainfo 這類「講格式本身」的東西，**不會**拿來當一般欄位名。

---

## 2. 整體形狀

- 一份 inst.json 是**嚴格一個 JSON 物件**（頂層不能是陣列、字串、null）。
- 七個欄位，**只有 `argv` 必填**，其餘沒寫就用預設。
- **不認得的頂層鍵一律忽略**，不會拒絕、也不會參與執行。`_metainfo` 走自己的規則（見上，
  裡面 `_type`／`_version` 以外的 key 也是忽略）。
- 任何一個「值」的位置都可以改寫成**指示詞**（第 4 節），解出來的東西就當成本來寫在那裡。

```json
{
  "_metainfo": {"_type": "posix", "_version": 1},
  "argv":   ["sh", "-c", "cat; echo $GREET"],
  "stdin":  "in.txt",
  "stdout": "out.txt",
  "stderr": {"$opt": "merge"},
  "exit":   "code.txt",
  "cwd":    "sub",
  "envs":   {"GREET": "hi", "PATH": {"$fmt": {"$val": "${p}:/opt/bin", "p": {"$env": "PATH"}}}}
}
```

## 3. 七個欄位

| 欄位 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `argv` | 非空字串陣列 | **必填** | 跑什麼。`argv[0]` 是程式，其餘是參數。`argv[0]` 用**疊加後的 `envs` 裡的 PATH** 找；`argv[0]` 不能是空字串 |
| `stdin` | 路徑或 `$opt` 選項物件 | `/dev/null` | 拿這個**檔案**當標準輸入（是檔案，不是字串內容）；也可以用 `inherit` 選項繼承執行者的標準輸入（見 3.3） |
| `stdout` | 路徑或 `$opt` 選項物件 | `/dev/null` | 標準輸出寫到這個檔（預設建立並清空，即 `>` 不是 `>>`）；可以用 `append`／`mkdir`／`inherit` 選項（見 3.3） |
| `stderr` | 路徑或 `$opt` 選項物件 | `/dev/null` | 寫到檔；可以用 `merge`（跟 stdout 同一條，shell 的 `2>&1`）／`append`／`mkdir`／`inherit` 選項（見 3.3） |
| `exit` | 路徑或 `$opt` 選項物件 | 不寫 | 跑完把結束碼（十進位＋換行）寫進去；寫完 fsync 檔案與父目錄。預設**父目錄要先存在**，不會幫忙建，除非用 `mkdir` 選項；也可以用 `append` 選項一行一行接在檔尾（見 3.3） |
| `cwd` | 路徑或 `$opt` 選項物件 | base（見 3.1） | 工作目錄；跑之前必須已經是資料夾，除非用 `mkdir` 選項先建（見 3.3） |
| `envs` | 物件 | `{}` | 環境變數，兩種寫法見 3.2 |

### 3.1 路徑怎麼算：中心是解出來的 `cwd`

- **base** ＝ 這份 inst 的「家」：給資料夾就是那個資料夾，給 `.json` 檔就是它所在的資料夾。
- `cwd` **最先解**，它的相對路徑以 base 為中心；沒寫就是 base。如果 `cwd` 用了 `mkdir`
  選項，是先解出路徑、再建目錄，之後其他相對路徑一樣以它為中心（不管資料夾原本存不存在）。
- 之後 `stdin`／`stdout`／`stderr`／`exit`、以及 `$ref` 指的檔，相對路徑**一律以解出來的 `cwd`
  為中心**。
- 絕對路徑照字面用。

所以解的順序固定是：頂層整份 → `cwd` → `argv` → `envs` → 四個路徑欄。

### 3.2 `envs` 的兩種寫法

```json
"envs": {"GREET": "hi"}                                疊在執行者的環境上，只加不減
"envs": {"$opt": "clear", "$val": {"LANG": "C"}}       從空環境開始，只放 $val 裡的
"envs": {"$opt": "clear"}                              $val 可省＝完全空的環境
```

- key 是純字串、**不解指示詞**；不能是空字串、不能含 `=`（這兩種才是 `EnvKeyInvalid`），
  也不能 `$` 開頭——但 `$` 開頭時程式實際走的是另一條路，看 4.1。
- 值可以是字串或指示詞，解完必須是字串。
- 清空之後 PATH 也沒了，`argv[0]` 退回系統預設路徑（Python 的 `os.defpath`，一般是
  `/bin:/usr/bin`），所以 `sh` 之類的還是找得到；想讓它找不到就自己塞一個 `PATH`。
- 整包 `envs` 或 `$val` 都可以是 `$ref` 從別的檔拿來的。
- 執行者（aos-exec）**不注入任何 `AOS_*` 變數**。

### 3.3 `$opt` 選項物件

`stdin`／`stdout`／`stderr`／`exit`／`cwd`／`envs` 這幾個位置，除了路徑（或 `envs` 的物件），
還可以放一個「選項物件」，統一長這樣：

```json
{"$opt": "名字"}                         單一選項、不帶值
{"$opt": "名字", "$val": 值}             單一選項、帶值
{"$opt": ["名字1", "名字2"], "$val": 值}  多個選項一起用
```

> 機制層（[directives.md](./directives.md) 第 4 節）的 `$opt` 值**任何 JSON 都可以**、不限
> 型別——機制本身不解讀、不驗。「`$opt` 必須是選項名字串或非空字串陣列」是 **inst 這個
> 宿主自己訂的規則**，不是指示詞機制規定的。

- `$opt` 的值是**字串**或**非空字串陣列**；別的型別 → `DirectiveValueTypeMismatch`。
  陣列裡重複同一個名字 → `UnknownOption`（訊息會說「重複」）。
- `$val` 是「本來要直接寫在那一格的值」，型別照那一格的規則驗；`$val` 本身**可以再是
  指示詞**（`$env`／`$fmt`／`$ref`），解完再驗。
- 選項物件只**讀 `$opt`、`$val`** 這兩個 key，其他 key 一律忽略（含 `$ref`／`$fmt`／`$env`），不會報錯。
- 這個位置不認得的選項名 → `UnknownOption`。
- 選項名區分大小寫，只認小寫。

各位置能用的選項：

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

可以合併的：同一個位置的 `append`＋`mkdir`（`stdout`／`stderr`／`exit`）。

互斥、一起出現就是 `OptionConflict`：

- `inherit` 跟 `append`／`mkdir`／`merge` 任何一個一起出現。
- `merge` 跟 `append`／`mkdir`／`inherit` 任何一個一起出現。
- `inherit`／`merge` 帶了 `$val`（這兩個選項規定不能帶值）。
- 該帶 `$val` 卻沒帶（`append`／`mkdir` 都是必帶）；給了空字串也算沒帶（空路徑的舊意思是 `/dev/null`，跟 append／mkdir 兜不起來，不默默放過）。
- `$opt` 放在不吃選項的位置（`argv` 的元素、`envs` 的值）→ `UnknownOption`。

執行時 mkdir／append／inherit／merge 各自實際發生什麼，見第 6 節。

### 3.4 沒有 shell

參數不會被切分、展開，也不會被當成重導向。要 shell 行為就自己寫 `["sh", "-c", "…"]`。

## 4. 指示詞：任何值的位置都能放

指示詞（`$env`／`$fmt`／`$ref`）與選項物件（`$opt`／`$val`）的**機制**——怎麼判定、先解再驗、
巢狀、`$fmt` 模板、`$ref`／`$at` 與循環、錯誤代號——**獨立成一份規範：
[directives.md](directives.md)**，本文不重講。這裡只寫 inst.json 這個宿主自己決定的事：

- **哪些位置能放指示詞**：頂層整份、每個欄位、`argv` 整個陣列與它的每個元素、`envs` 整個物件
  與它的每個值、選項物件的 `$val`。`envs` 的 key 不吃指示詞。
- **`$env` 讀的是執行者（aos-exec）自己的環境**，不是這份 inst 的 `envs`。
- **`$ref` 找檔案用的中心路徑是解出來的 `cwd`**（3.1）；只有頂層整份與 `cwd` 自己以 base 為
  中心。`$ref:""`（或 `#` 前面留空）＝**這份 inst.json 自己**。
- **位置一律是原始 JSON 裡的實體路徑**，例如 `argv` 第一個元素是 `/argv/0`；某格改寫成
  `$fmt` 之後，它底下的變數 `p` 的位置是 `.../$fmt/p`，模板本身（`$val`）是 `.../$fmt/$val`。
  完整語法（`$ref`／`$at`、相對 `./`／`../` 怎麼算、位置怎麼記）見
  [directives.md](directives.md) 第 3.2 節。
- **各位置認得的選項名**在 3.3；不在表上的名字＝`UnknownOption`。
- 解完之後那一格的型別由本文驗：頂層要物件、`argv` 要非空字串陣列、路徑欄要字串、`envs` 要物件，
  不對＝`FieldTypeMismatch`。

### 4.1 幾個容易踩的

- `envs` 的 key 不能 `$` 開頭：只要 `envs` 這個物件裡出現 `$` 開頭的 key，整包 `envs` 就會
  先被當成指示詞（或選項物件）看，不會被當成一般的環境變數清單。例如 `envs` 寫成
  `{"$ref":"e.json","X":"1"}`，現在會照優先順序跑 `$ref`，`"X":"1"` 被當成指示詞物件裡的
  多餘 key **忽略**——不會變成一個名叫 `X` 的環境變數。只有一個 `$xyz` 這種不認得的 `$` key
  （不是 `$opt`／`$ref`／`$fmt`／`$env`）單獨出現 → `UnknownDirective`。這些狀況都不會走到
  `EnvKeyInvalid`（那個代號只管空字串跟含 `=` 的 key）。代價：這一版沒辦法傳 `$` 開頭的
  環境變數。
- `$env`／`$fmt` 一定解出字串，放在 `envs` 這種要物件的位置就是 `FieldTypeMismatch`；`$ref`
  解出字串放在 `argv`（要陣列）也一樣。

## 5. 錯誤代號（讀／驗階段）

驗不過就是一個 `InstError`，`str(e)` 是「代號: 白話」。執行者原樣印一行到自己的 stderr，
退出碼 125（執行者自己失敗，那次**根本沒跑**，不寫 `exit` 檔）。

| 代號 | 什麼時候 |
|---|---|
| `ReadFailed` | inst.json 讀不到（指名的 `.json` 不存在也算） |
| `JsonSyntax` | 不是合法 JSON |
| `NotAnObject` | 頂層解完不是物件 |
| `MetainfoInvalid` | `_metainfo` 不是物件，或缺 `_type`／`_version`（裡面其他 key 忽略，不算多餘） |
| `UnsupportedInstType` | `_metainfo` 的 `_type` 不是字串 `"posix"` |
| `UnsupportedInstVersion` | `_metainfo`（posix）的 `_version` 不是整數 `1`（`true`／`false` 也不算） |
| `EmptyArgv` | 沒有 `argv`、解出來是空陣列、或 `argv[0]` 是空字串 |
| `FieldTypeMismatch` | 某個位置解完型別不對（頂層要物件、`argv` 要非空字串陣列、路徑欄要字串、`envs` 要物件） |
| `EnvKeyInvalid` | `envs` 的 key 空、或含 `=`（`$` 開頭不會走到這裡，實際代號是 `UnknownDirective`，見 4.1） |

指示詞機制的代號（`UnknownDirective`、`DirectiveValueTypeMismatch`、`FormatVariableInvalid`、
`UnknownOption`、`OptionConflict`、`EnvironmentVariableMissing`、`UnknownFormatVariable`、
`ReferenceReadFailed`／`ReferenceJsonInvalid`／`ReferencePointerInvalid`／`ReferenceCycle`）見
[directives.md](directives.md) 第 6 節，本文不重複定義；本文只在 3.3／第 4 節訂了「這個位置
認不認得這個選項」之類的宿主規則，實際判定與報錯代號是機制層的事。

## 6. 執行語意（執行者要做到的）

這一節講「照這份 inst 跑一次」是什麼意思，執行者（現在是 aos-exec）必須照做：

1. **驗完才跑**：任何一個讀／驗錯誤＝那次根本沒跑，退 125、不寫 `exit`。
2. **前置檢查也算「沒跑」**：`exit` 的父目錄不存在（且沒用 `mkdir` 選項）、`cwd` 不是資料夾
   （且沒用 `mkdir` 選項）、重導向的檔開不起來，都是執行者自己失敗（125）。
   - **`mkdir`**：`cwd` 是先解出路徑、`makedirs` 把目錄建好，再拿它當中心解其他相對路徑；
     `stdout`／`stderr`／`exit` 的 `mkdir` 是在**開檔前**先把父目錄建好。`makedirs` 失敗
     （例如路上卡了一個同名的檔案）＝執行者自己失敗（125）。
   - **`append`**：`stdout`／`stderr` 是照 `>>` 開檔（存在就接在後面、不存在就建）；`exit`
     是把「十進位＋換行」的結束碼接在檔尾，一樣寫完 fsync 檔與父目錄。
   - **`inherit`**：那條串流直接沿用執行者（aos-exec）自己的標準輸入／輸出／錯誤（傳給
     `Popen` 的參數是 `None`），不開檔、不重導向。aos-exec 命令列的 `--stderr -`／
     `--stderr PATH` 仍然蓋過 inst.json 的 `stderr` 設定，包括 `merge`／`inherit`／
     `append`。
   - **`merge`**：`stderr` 跟 `stdout` 走同一條（`2>&1`），照 `stdout` 當時的設定走——
     `stdout` 是 `append` 就跟著 append、是 `inherit` 就跟著 inherit。
3. 環境：`envs` 用 `clear` 選項時從空的開始，否則從執行者自己的環境複製一份；再把 `envs`
   疊上去（只加不減）。
4. 用 `argv[0]` 在**疊加後**的 PATH 找程式；找不到＝127、沒執行權＝126——**這兩種算
   「跑完了一次」**，有 `exit` 就照樣寫進去。
5. 子程式開在**新的 process group**（`setsid`），逾時砍的是整個 group：先 SIGTERM、等 2 秒、
   還在就 SIGKILL。被 SIGTERM 砍死＝143、SIGKILL＝137。
6. 結束碼：正常結束＝它的 exit code；被訊號 N 砍＝128+N。有 `exit` 就寫進去（十進位＋換行，
   `append` 就接在檔尾，否則覆蓋；都要 fsync 檔與父目錄）。
7. 執行者的**自己的**失敗碼固定 125、用法錯 2，跟子程式的碼分開，看的人才分得出
   「跑了但失敗」跟「根本沒跑」。

## 7. 這份規範沒管的事

- **怎麼反覆跑、多久跑一次**：那是 cpu（aos-run）與 kernel 的事，inst 只描述「一次」。
- **退出碼的約定語意**（100＝做完、101＝在等）：那是 kernel 跟程式之間的約定，不是 inst 格式
  的一部分。
- **`_type` 不是 `posix` 的 inst**：各自另寫規範。

## 修訂記錄

- 2026-09-21 A：頂層未知 key（含 `_metainfo` 內未知 key）一律忽略，`UnknownKey` 代號刪除。
- 2026-09-21 B：`$opt` 統一成 `{$opt: 名|[名…], $val}` 形狀，`$val` 可再是指示詞。
- 2026-09-21 C：訂出 `stdin`／`stdout`／`stderr`／`exit`／`cwd`／`envs` 各自認得的選項與互斥規則。
- 2026-09-21 D：`aos_inst.load()` 回傳值把每個選項位置的選項一起帶出來給執行者用（proto4-3 實作細節）。
- 2026-09-21 E：repo 裡舊的 `{"$opt":"clear","$envs":{…}}` 一律遷移成 `{"$opt":"clear","$val":{…}}`。
- 2026-09-21 F：錯誤代號表定案：拿掉 `UnknownKey`，加入 `OptionConflict`。
- 2026-09-21 G：`$fmt` 改成「模板＋變數表」（`{$val:模板, 變數:值…}`），拿掉 `${env:…}` 特例。
- 2026-09-21 H：指示詞物件可以混寫其他 key；多個指示詞照優先序 `$opt`＞`$ref`＞`$fmt`＞`$env`
  只跑一個；`DirectiveKeyCountInvalid` 代號刪除。
- 2026-09-21 I：`$ref` 拆成 `$ref`＋`$at`，支援 `/`（絕對）、`./`／`../`（相對「目前位置」）；
  舊的 `檔案#/pointer` 寫法先刪。
- 2026-09-21 J：機制層 `$opt` 值型別不限；「值是選項名字串或非空名字陣列」是 inst 自訂的宿主規則。
- 2026-09-21 K：`$ref` 字串可帶 `#位置`（等同另寫 `$at`）；相對位置指到別的檔時也能用，統一
  相對於「目前位置」，取代 I 的限制。
- 2026-09-21 L：「位置」一律是原始 JSON 的實體路徑，`$fmt`／`$val`／`$opt` 這些 key 也算一段。
