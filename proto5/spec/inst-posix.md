# inst.json 規範：`posix` 呼叫（第 1 版）

← [proto5 README](../README.md)｜實作在 [proto4-3/aos_inst.py](../../proto4-3/aos_inst.py)、[aos_inst_resolve.py](../../proto4-3/aos_inst_resolve.py)，跑的那一半在 [aos_exec.py](../../proto4-3/aos_exec.py)（使用手冊 [docs/exec.md](../../proto4-3/docs/exec.md)）

這份文件把「一份 inst.json 到底長什麼樣、怎麼解讀」寫成規範。內容照 proto4-3 **現在的程式碼**寫，
不是照想像；程式碼跟本文對不上的地方，以程式碼為準、回來改本文。

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

1. **沒寫 `_metainfo`，就等於 `{"_type": "posix", "_version": 1}`**。所以 proto4-3 之前寫的所有
   inst.json 都不用動、意思不變。
2. `_metainfo` 只描述格式，**不參與執行**——不是環境變數、不是參數、不會傳給子程式。
3. `_type` 不是 `"posix"` 的 inst，本文管不到；那是之後別種 inst（例如以後可能有的
   `"step"`、`"llm"` 之類）各自的規範。
4. `_version` 大於本文版號的 `posix` inst，讀的人**不該假裝看得懂**：要嘛拒絕、要嘛明講降級。
5. 以 `_` 開頭的頂層鍵保留給 metainfo 這類「講格式本身」的東西，**不會**拿來當一般欄位名。

> **現況提醒（程式已經跟上了）**：proto4-3 的 `aos_inst.load()` 現在**認得** `_metainfo`，
> 而且不是「讀完丟掉」那麼隨便，驗得很嚴：
>
> - `_metainfo` 本身要是物件，而且**剛好**只有 `_type`、`_version` 這兩個 key，多一個
>   少一個都拒絕（`MetainfoInvalid`）。
> - `_type` 只認字面的 `"posix"`；別的字串（例如以後可能的 `"step"`）現在就直接退件
>   （`UnsupportedInstType`），不是「本文管不到、放過」。
> - `_version` 只認整數 `1`；JSON 的 `true`／`false` 在 Python 裡雖然是 `int` 的子類，
>   程式特地擋掉、不算數（`UnsupportedInstVersion`）。
> - `_metainfo` 的值**不吃指示詞**：它是從 JSON 直接拿出來驗，不會丟進第 4 節那套
>   `_resolve` 展開。所以寫 `{"_metainfo": {"$ref": "x.json"}}` 不會被當成「整個
>   `_metainfo` 從別的檔拿」，而是被當成「多了一個 `$ref` key、少了 `_type`／
>   `_version`」，一樣是 `MetainfoInvalid`。
> - 沒寫 `_metainfo`、或寫對了，`load()` 回傳的 dict 都會多一個 `metainfo` 欄位
>   （`{"_type": "posix", "_version": 1}`），但目前 aos-exec 沒用到它，不影響執行結果。

---

## 2. 整體形狀

- 一份 inst.json 是**嚴格一個 JSON 物件**（頂層不能是陣列、字串、null）。
- 七個欄位，**只有 `argv` 必填**，其餘沒寫就用預設。
- **不認得的頂層鍵一律拒絕**（`UnknownKey`），不是忽略。`_metainfo` 是唯一的例外（見上）。
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
  "envs":   {"GREET": "hi", "PATH": {"$fmt": "${env:PATH}:/opt/bin"}}
}
```

## 3. 七個欄位

| 欄位 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `argv` | 非空字串陣列 | **必填** | 跑什麼。`argv[0]` 是程式，其餘是參數。`argv[0]` 用**疊加後的 `envs` 裡的 PATH** 找；`argv[0]` 不能是空字串 |
| `stdin` | 路徑 | `/dev/null` | 拿這個**檔案**當標準輸入（是檔案，不是字串內容） |
| `stdout` | 路徑 | `/dev/null` | 標準輸出寫到這個檔（建立並清空，即 `>` 不是 `>>`） |
| `stderr` | 路徑或 `{"$opt":"merge"}` | `/dev/null` | 寫到檔；`merge`＝跟 stdout 同一條（shell 的 `2>&1`） |
| `exit` | 路徑 | 不寫 | 跑完把結束碼（十進位＋換行）寫進去；寫完 fsync 檔案與父目錄。**父目錄要先存在**，不會幫忙建 |
| `cwd` | 路徑 | base（見 3.1） | 工作目錄；跑之前必須已經是資料夾 |
| `envs` | 物件 | `{}` | 環境變數，兩種寫法見 3.2 |

### 3.1 路徑怎麼算：中心是解出來的 `cwd`

- **base** ＝ 這份 inst 的「家」：給資料夾就是那個資料夾，給 `.json` 檔就是它所在的資料夾。
- `cwd` **最先解**，它的相對路徑以 base 為中心；沒寫就是 base。
- 之後 `stdin`／`stdout`／`stderr`／`exit`、以及 `$ref` 指的檔，相對路徑**一律以解出來的 `cwd`
  為中心**。
- 絕對路徑照字面用。

所以解的順序固定是：頂層整份 → `cwd` → `argv` → `envs` → 四個路徑欄。

### 3.2 `envs` 的兩種寫法

```json
"envs": {"GREET": "hi"}                                疊在執行者的環境上，只加不減
"envs": {"$opt": "clear", "$envs": {"LANG": "C"}}      從空環境開始，只放 $envs 裡的
"envs": {"$opt": "clear"}                              $envs 可省＝完全空的環境
```

- key 是純字串、**不解指示詞**；不能是空字串、不能含 `=`（這兩種才是 `EnvKeyInvalid`），
  也不能 `$` 開頭——但 `$` 開頭時程式實際走的是另一條路，看 4.3。
- 值可以是字串或指示詞，解完必須是字串。
- 清空之後 PATH 也沒了，`argv[0]` 退回系統預設路徑（Python 的 `os.defpath`，一般是
  `/bin:/usr/bin`），所以 `sh` 之類的還是找得到；想讓它找不到就自己塞一個 `PATH`。
- 整包 `envs` 或 `$envs` 都可以是 `$ref` 從別的檔拿來的。
- 執行者（aos-exec）**不注入任何 `AOS_*` 變數**。

### 3.3 沒有 shell

參數不會被切分、展開，也不會被當成重導向。要 shell 行為就自己寫 `["sh", "-c", "…"]`。

## 4. 指示詞：任何值的位置都能放

**先解、再驗。** 一個 dict **只要有 `$` 開頭的 key 就當指示詞看**（`$opt` 的兩種型式除外）。
指示詞＝**剛好一個 key、值一定是字串**的物件。解出來的東西當成本來寫在那個位置；**解出來
又是指示詞就繼續解**（巢狀）；最後才照那個位置該有的型別驗。

可以放指示詞的位置：**頂層整份**、每個欄位、`argv` 整個陣列與它的每個元素、`envs` 整個物件
與它的每個值、`$envs`。

| 指示詞 | 解出來是 | 意思 |
|---|---|---|
| `{"$env":"NAME"}` | 字串 | 從**執行者自己的**環境取值。變數不存在＝錯誤（`EnvironmentVariableMissing`）；存在但空＝空字串（兩件不同的事） |
| `{"$fmt":"模板"}` | 字串 | 接字串用，見 4.1 |
| `{"$ref":"file.json#/a/b"}` | 任何 JSON | 相對於 **cwd** 讀那份 JSON；`#` 後面是 RFC 6901 JSON Pointer（`~1`＝`/`、`~0`＝`~`）；沒有 `#` 就取整份。取回來的值**原樣**放進那個位置，型別由那個位置驗 |
| `{"$opt":"merge"}` | — | 只有 `stderr` 能用 |
| `{"$opt":"clear","$envs":{…}}` | — | 只有 `envs` 能用；規則上是**唯一**該有兩個 key 的指示詞物件（程式現況的小例外看 4.3） |

### 4.1 `$fmt` 模板

沿用 repo 既有的那套（[data-files-fmt](../../wf/workflows/common/data-files-fmt.md)），這裡只有
`env:` 一個 namespace：

- 只有 `${…}` 會被代換；單獨的 `$` 與 `$NAME` 都是**字面**，不展開、不用跳脫。
- `${env:NAME}` 讀**執行者自己的**環境（跟 `$env` 同一個來源，**不是**這份 inst 的 `envs`）。
  不存在＝錯誤；存在但空＝空字串。
- 不是 `env:` 開頭的 `${…}`＝錯誤（`UnknownFormatVariable`），不猜。
- **展開一次、不再掃結果**：換進來的值裡再出現 `${…}` 就是字面。

### 4.2 `$ref` 的循環

沿著一條鏈記「檔案 realpath ＋ pointer」，任何深度都記；同一條鏈再撞到同一個身分＝
`ReferenceCycle`。頂層寫 `{"$ref": "自己"}` 也擋得到。

### 4.3 幾個容易踩的

- `envs` 的 key 不能 `$` 開頭——因為那樣整包（或 `$envs`）會先被當指示詞，實際冒出來
  的代號是 `UnknownDirective`（剛好一個 key）或 `DirectiveKeyCountInvalid`（不只一個
  key），不是 `EnvKeyInvalid`（那個代號只管空字串跟含 `=` 這兩種）。代價：這一版沒辦法
  傳 `$` 開頭的環境變數。
- `stderr` 的 `{"$opt":"merge"}` 混進一個 `$envs` 鍵不會被擋掉：`$opt` 的共用檢查不分
  位置，一律放行 `$opt`／`$envs` 這兩個 key，所以 `{"stderr": {"$opt":"merge",
  "$envs":{...}}}` 會安靜通過、`$envs` 被無聲丟掉，不算多餘的 key。「`envs` 清空型式是
  唯一兩個 key 的指示詞」只是規則上這樣講，程式沒有真的把這條路堵死。
- 混寫 `{"$ref": "e.json", "X": "1"}`＝兩個 key＝拒絕（`DirectiveKeyCountInvalid`）。
- `$env`／`$fmt` 一定解出字串，放在 `envs` 這種要物件的位置就是 `FieldTypeMismatch`。
- `$ref` 解出字串放在 `argv`（要陣列）也是 `FieldTypeMismatch`。

## 5. 錯誤代號（讀／驗階段）

驗不過就是一個 `InstError`，`str(e)` 是「代號: 白話」。執行者原樣印一行到自己的 stderr，
退出碼 125（執行者自己失敗，那次**根本沒跑**，不寫 `exit` 檔）。

| 代號 | 什麼時候 |
|---|---|
| `ReadFailed` | inst.json 讀不到（指名的 `.json` 不存在也算） |
| `JsonSyntax` | 不是合法 JSON |
| `NotAnObject` | 頂層解完不是物件 |
| `UnknownKey` | 頂層有七個欄位（以及 `_metainfo`）以外的鍵 |
| `MetainfoInvalid` | `_metainfo` 不是物件，或不是剛好只有 `_type`／`_version` 這兩個 key |
| `UnsupportedInstType` | `_metainfo` 的 `_type` 不是字串 `"posix"` |
| `UnsupportedInstVersion` | `_metainfo`（posix）的 `_version` 不是整數 `1`（`true`／`false` 也不算） |
| `EmptyArgv` | 沒有 `argv`、解出來是空陣列、或 `argv[0]` 是空字串 |
| `FieldTypeMismatch` | 某個位置解完型別不對 |
| `EnvKeyInvalid` | `envs` 的 key 空、或含 `=`（`$` 開頭不會走到這裡，實際代號是 `UnknownDirective`／`DirectiveKeyCountInvalid`，見 4.3） |
| `DirectiveKeyCountInvalid` | 指示詞不是剛好一個 key（`$opt` 型式多了別的 key 也算） |
| `UnknownDirective` | `$` 開頭的 key 不是 `$env`／`$ref`／`$fmt`；或 `$opt` 放在不准的位置 |
| `DirectiveValueTypeMismatch` | 指示詞的值不是字串 |
| `UnknownOption` | `$opt` 的值不是那個位置認得的（stderr 只認 `merge`、envs 只認 `clear`） |
| `EnvironmentVariableMissing` | `$env`／`${env:…}` 指的變數不存在 |
| `UnknownFormatVariable` | `$fmt` 裡出現不是 `env:` 開頭的 `${…}` |
| `ReferenceReadFailed`／`ReferenceJsonInvalid`／`ReferencePointerInvalid` | `$ref` 讀不到、不是 JSON、pointer 走不到 |
| `ReferenceCycle` | `$ref` 繞回來了 |

## 6. 執行語意（執行者要做到的）

這一節講「照這份 inst 跑一次」是什麼意思，執行者（現在是 aos-exec）必須照做：

1. **驗完才跑**：任何一個讀／驗錯誤＝那次根本沒跑，退 125、不寫 `exit`。
2. **前置檢查也算「沒跑」**：`exit` 的父目錄不存在、`cwd` 不是資料夾、重導向的檔開不起來，
   都是執行者自己失敗（125）。
3. 環境：`envs_clear` 時從空的開始，否則從執行者自己的環境複製一份；再把 `envs` 疊上去
   （只加不減）。
4. 用 `argv[0]` 在**疊加後**的 PATH 找程式；找不到＝127、沒執行權＝126——**這兩種算
   「跑完了一次」**，有 `exit` 就照樣寫進去。
5. 子程式開在**新的 process group**（`setsid`），逾時砍的是整個 group：先 SIGTERM、等 2 秒、
   還在就 SIGKILL。被 SIGTERM 砍死＝143、SIGKILL＝137。
6. 結束碼：正常結束＝它的 exit code；被訊號 N 砍＝128+N。有 `exit` 就寫進去（十進位＋換行，
   fsync 檔與父目錄）。
7. 執行者的**自己的**失敗碼固定 125、用法錯 2，跟子程式的碼分開，看的人才分得出
   「跑了但失敗」跟「根本沒跑」。

## 7. 這份規範沒管的事

- **怎麼反覆跑、多久跑一次**：那是 cpu（aos-run）與 kernel 的事，inst 只描述「一次」。
- **退出碼的約定語意**（100＝做完、101＝在等）：那是 kernel 跟程式之間的約定，不是 inst 格式
  的一部分。
- **`_type` 不是 `posix` 的 inst**：各自另寫規範。
