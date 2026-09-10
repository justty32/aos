# proto4-3 — aos-exec 單發、aos-run 連續、aos-daemon 管一堆、aos-kernel 排程（Python）

這是 [proto4 筆記第 11 節](../proto4/notes/2026-09-08-ideas.md)（aos-exec）、
[第 12 節](../proto4/notes/2026-09-08-ideas.md)（aos-run）與
[第 13 節](../proto4/notes/2026-09-08-ideas.md)（aos-daemon）的原型，規格以那三節為準
（跟第 10 節衝突的地方都聽第 11 節的）；第 14 節（拍板的那一輪）與第 15 節（daemon 的
key 改成 inst.json 的路徑）是後來的修正，衝突時聽新的。

← [proto4-2](../proto4-2/README.md)（inst.json ＋ cpu ＋ daemon ＋ kernel；那一版的
inst.json 是八欄、相對路徑以資料夾為中心、串流沒寫會被 cpu 抓回 `last.json`）

換的思路是：**inst.json 只是我們規定的第一版指令集**，像 ARM 那樣小而統一——欄位少、
但每個都有定義。最陽春的指令集是「一個檔讀進來就跑」，inst.json 只是在不增加複雜度的
前提下多給了 stdin／stdout／stderr／exit／cwd／envs。

跟 proto4-2 比，這一版改了四件事：

1. **`timeout_ms` 拿掉**。時限不是指令的事，是「反覆執行 inst.json 的傢伙」的事。單發的
   aos-exec 只用命令列旗標 `--timeout-ms` 自己管；寫在 inst.json 裡＝未知 key、拒絕。
2. **沒寫的串流一律 `/dev/null`**，不是繼承、也不是抓回哪個檔。單發執行器不替你收輸出，
   要就自己寫檔名。
3. **相對路徑的中心是 cwd**（解析完的那個工作目錄），不是 `xxx`。只有 `cwd` 自己的相對
   路徑從 `xxx` 起算，不然沒有中心可言。
4. 環境欄位叫 **`envs`**（寫 `env` ＝未知 key），多一個整個物件層級的 `$opt: clear`。

**「一直跑」是 aos-run 的事**（往下看那一節）。它就是 `import aos_exec` 反覆叫
`run_target()`，所以核心就是那一個函式，兩支命令列都只是包它。

## 怎麼跑

```sh
cd proto4-3
python3 -m unittest discover -s test        # 185 條測試，真的開進程，暫存在 /tmp、跑完自己收

./aos-exec /path/to/folder                  # 跑 folder/.aos/inst.json
./aos-exec /path/to/folder --dir-target my/inst.json
./aos-exec /path/to/one.json                # 直接指一份 inst.json
./aos-exec /path/to/script.sh               # 普通檔案：直接執行它
./aos-exec /path/to/folder --timeout-ms 3000
echo $?                                     # 子程式的結束狀態；125＝aos-exec 自己失敗
```

```sh
./aos-run /path/to/folder --interval-ms 5000            # 一直跑，每 5 秒一次

./aos-daemon &                                          # 普通前台程式，自己丟去背景
./aos-daemon-ctl add /path/to/inst.json --interval-ms 5000    # daemon 只收 .json 的路徑
./aos-daemon-ctl ls

./aos-kernel-init K --ncpu 2                            # 排程的家；開機順序往下看
./aos-daemon-ctl add K/inst.json --interval-ms 1000
```

當成函式用（aos-run 就是這樣接的）：

```python
import aos_exec
code, kind = aos_exec.run_target("/path/to/folder", dir_target=".aos/inst.json",
                                 timeout_ms=3000)
# kind："child"＝子程式跑完了、"aos"＝aos-exec 自己失敗、"usage"＝用法錯
```

## 三種目標

`aos-exec xxx [--dir-target REL] [--timeout-ms N]`，看 `xxx` 是什麼決定怎麼跑：

| `xxx` 是 | 做什麼 | cwd 預設 | 串流 |
|---|---|---|---|
| 普通檔案（副檔名不是 `.json`） | 直接執行它：`argv` 就是它的絕對路徑 | 它所在的資料夾 | **繼承** aos-exec 的 |
| `.json` 檔（**不存在也走這條**） | 讀進來當 inst.json 解析、執行 | 那個 `.json` 所在的資料夾 | 照 inst.json |
| 資料夾 | 執行 `xxx/.aos/inst.json`（`--dir-target` 可改） | `xxx` 自己 | 照 inst.json |

普通檔案模式什麼都不解析：環境就是繼承的、沒有 exit 檔、沒有重導向。它沒有執行位＝126。

先看是不是資料夾再看副檔名，所以一個名字剛好以 `.json` 結尾的**資料夾**還是照資料夾走。

**一個以 `.json` 結尾但不存在的路徑不是用法錯**，是 aos-exec 自己失敗（`kind=aos`、退出碼
125）：這樣 aos-daemon 才能收下一份還沒出現的 inst.json，檔案一出現就自然跑起來。不存在
的**非** `.json` 路徑照舊是用法錯（退出碼 2）。

`--timeout-ms` 三種模式都吃；`0` 或不給＝不限。

## inst.json 長什麼樣

只能是**一個 JSON 物件**，七個欄位，只有 `argv` 必填，**沒寫在表上的 key 一律拒絕**——
不是忽略，舊的執行檔碰到新欄位寧可硬失敗，也別默默少一個限制。

```json
{
  "argv": ["sh", "-c", "cat; echo $GREET"],
  "stdin": "in.txt",
  "stdout": "out.txt",
  "stderr": {"$opt": "merge"},
  "exit": "code.txt",
  "cwd": "sub",
  "envs": {"GREET": "hi", "PATH": {"$fmt": "${env:PATH}:/opt/bin"}}
}
```

| 欄位 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `argv` | 字串陣列 | **必填** | 跑什麼；`argv[0]` 走**疊加後**的 `envs` 裡的 PATH |
| `stdin` | 路徑 | `/dev/null` | 拿這個**檔案**當標準輸入（不是塞字串） |
| `stdout` | 路徑 | `/dev/null` | 標準輸出寫到這個檔（建立並清空） |
| `stderr` | 路徑或 `{"$opt":"merge"}` | `/dev/null` | 寫到檔；`merge`＝跟 stdout 走同一條 |
| `exit` | 路徑 | 不寫 | 跑完把結束碼（十進位＋換行）寫進去，fsync 檔案與父目錄 |
| `cwd` | 路徑 | `xxx` | 工作目錄 |
| `envs` | 物件 | `{}`＝只有繼承的 | 疊在 aos-exec 的環境上只加不減；key 不能空、不能含 `=`、不能 `$` 開頭；整包也可以用 `$ref` 從別的檔拿 |

**相對路徑的中心是 cwd**：`stdin`／`stdout`／`stderr`／`exit` 和 `$ref` 都從**解析完的
cwd** 起算。只有 `cwd` 自己從 `xxx` 起算——它是最先解的那一個。絕對路徑照字面用。

這裡沒有任何 shell 解讀：引數不會被切分、展開，也不會被當成重導向語法。真的要 shell 行為
就自己寫 `argv: ["sh", "-c", "..."]`。

### `envs` 的兩種寫法

```json
"envs": {"GREET": "hi"}                                認 aos-exec 的環境當底，只加不減
"envs": {"$opt": "clear", "$envs": {"LANG": "C"}}      從空環境開始，只放 $envs 裡的
"envs": {"$opt": "clear"}                              $envs 可省＝完全空的環境
```

清空之後 PATH 也沒了，`argv[0]` 退回 Python 的 `os.defpath`（這台機器上是 `/bin:/usr/bin`），所以
`sh` 之類的還是找得到。想讓它找不到就自己塞一個 `$envs: {"PATH": "..."}`。

**aos-exec 不注入任何 `AOS_*` 環境變數**——tick 是 aos-run 的事，這裡保持乾淨。

### 指示詞：任何位置都能放

**先解、再驗。** inst.json 裡**任何一個值的位置**都可以不寫本來該寫的東西，改寫一個
**指示詞**——剛好一個 key、值一定是字串的物件。位置包括：**頂層整份**、每個欄位、
`argv` **整個陣列**與它的每個元素、四個路徑欄位、`cwd`、`envs` **整個物件**與它的每個值、
`$envs`。指示詞解出來的東西就當成本來寫在那裡，**解出來又是指示詞就繼續解**，最後才照
那個位置該有的型別驗（頂層要物件、`argv` 要非空字串陣列、路徑欄要字串、`envs` 要物件）。

| 指示詞 | 意思 |
|---|---|
| `{"$env":"NAME"}` | 從 **aos-exec 自己的**環境取值。變數不存在＝錯誤；存在但空＝空字串（兩件不同的事） |
| `{"$fmt":"模板"}` | 接字串用的，見下面 |
| `{"$ref":"file.json#/a/b"}` | 相對於 **cwd** 讀那份 JSON，`#` 後面是 RFC 6901 的 JSON Pointer（`~1` 代表 `/`、`~0` 代表 `~`），沒有 `#` 就取整份 |
| `{"$opt":"merge"}` | 只有 `stderr` 能用，等於 shell 的 `2>&1` |

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

**一個物件只要有 `$` 開頭的 key 就被當指示詞看**（`$opt` 那兩種型式除外）。所以 `envs` 的
key——也就是環境變數名——不能 `$` 開頭，混寫（`{"$ref": "e.json", "X": "1"}`）＝兩個 key
＝拒絕。`envs` 的 key 本身不吃指示詞。

**`$fmt`** 的模板寫法沿用 repo 裡本來就有的那套（[data-files-fmt](../wf/workflows/common/data-files-fmt.md)），
這裡只有 `env:` 這一個 namespace，不做 tabledb 那些 `${gitRoot}` 路徑變數：

- 只有 `${…}` 會被代換。單獨的 `$` 與 `$NAME` 都是**字面**，不展開也不用跳脫。
- `${env:NAME}` 讀 **aos-exec 自己的**環境（不是這份 inst.json 的 `envs`，跟 `$env` 同一個
  來源）。不存在＝錯誤；存在但空＝空字串。
- 不是 `env:` 開頭的 `${…}`＝不認得的變數＝錯誤，不猜。
- **展開一次、不再掃結果**：換進來的值裡再出現 `${…}` 就是字面。

`envs` 的清空型式 `{"$opt":"clear","$envs":{…}}` 是**唯一一個**兩個 key 的指示詞物件
（`$envs` 一樣可以再是 `$ref`）。代價：這一版沒辦法傳 `$` 開頭的環境變數。

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
| 2 | 用法錯（旗標不認得、沒給 `xxx`、`--timeout-ms` 是負數）、`xxx` 是不存在的**非** `.json` 路徑、`--dir-target` 指的檔不存在 |
| **125** | **aos-exec 自己失敗**：inst.json 讀不到（**指名的 `.json` 不存在也算**）／不是 JSON 物件／格式壞（未知 key、型別錯、`argv` 空、`envs` 的 key 壞、指示詞壞）／`$env`／`${env:…}` 的變數不存在／`$ref` 讀不到、pointer 壞、繞回來了／`exit` 檔的父目錄不存在／`cwd` 不是資料夾／重導向的檔開不起來 |
| 126 | 沒執行權 |
| 127 | 找不到程式 |
| 143 / 137 | `--timeout-ms` 到了：SIGTERM 就死＝143，要 SIGKILL 才死＝137 |
| 其他 | **原樣**是子行程的結束狀態：正常結束＝它的 exit code，被訊號 N 砍＝128+N |

**為什麼是 125**：子程式回 1 是很常見的事，aos-exec 自己失敗也回 1 的話，看的人分不出
「指令跑了但失敗」跟「指令根本沒跑」。125 撞不到 shell 那套（126／127／128+N），跟
`timeout(1)`、`env(1)` 挑的號碼是同一個理由。

125 與 2 會印一行 `aos-exec: <原因>` 到 **aos-exec 自己的 stderr**（格式壞掉的那行開頭是
代號，像 `UnknownKey:`、`ReferenceCycle:`）。126／127 也印一行。

有寫 `exit` 欄位的話，126／127／逾時一樣算「跑完了一次」，那個數字照樣寫進 exit 檔。
125 與 2 是 **aos-exec 自己**失敗，不寫 exit 檔。

**逾時怎麼砍**：先對**整個 process group** 送 SIGTERM，給 2 秒，直接子行程還活著就 SIGKILL
整個 group（收完屍再補一發，因為直接子行程死了不代表群組空了）。

## aos-run：一直跑同一個目標

```sh
aos-run xxx [--dir-target REL] [--timeout-ms N] [--interval-ms N] [--from-start]
            [--max-runs N] [--time-limit-ms N] [--stop-exit CODE]...
            [--status-fd N] [--stop-on-error]
```

[proto4 筆記第 12 節](../proto4/notes/2026-09-08-ideas.md)的原型。**執行那一段完全不重寫**：
就是反覆叫 `aos_exec.run_target()`，`xxx` 是哪三種目標、退出碼怎麼來，通通照上面 aos-exec
那幾節。aos-run 只管三件事——下一次什麼時候開始、什麼時候停、跑完印一行。

**時間旗標一律是毫秒整數**，跟 aos-exec 的 `--timeout-ms` 同一個單位。

| 旗標 | 預設 | 意思 |
|---|---|---|
| `--dir-target REL` | `.aos/inst.json` | 同 aos-exec，原樣傳給 `run_target()` |
| `--timeout-ms N` | `0`＝不限 | **每一次**執行的上限，原樣傳給 `run_target()` |
| `--interval-ms N` | `1000` | 兩次執行之間的間隔 |
| `--from-start` | 沒有＝從結束算 | 間隔改從上一次**開始**的時刻算 |
| `--max-runs N` | `0`＝不限 | 跑滿 N 次就停 |
| `--time-limit-ms N` | `0`＝不限 | 從 aos-run 起跑算的整體時限（**硬的**） |
| `--stop-exit CODE` | 沒有 | 某一次的退出碼是 CODE 就停，可以給很多次 |
| `--status-fd N` | 沒有＝不寫 | 往這個 fd 寫事件（給程式看的，見下面） |
| `--stop-on-error` | 沒有＝不停 | 某一次是 **aos-exec 自己失敗**（`kind=aos`）就停 |

### 間隔從哪裡算

`--interval-ms 5000`、某一次跑了 1.2 秒：

| | 下一次什麼時候開始 |
|---|---|
| 預設（從上一次**結束**算） | 第 **6.2** 秒 |
| `--from-start`（從上一次**開始**算） | 第 **5** 秒 |

`--from-start` 時一次跑超過 interval（例如 interval 5 秒、跑了 7 秒），下一次**立刻**開始，
**不補跑**錯過的格：下一次的起點是 `max(現在, 上次起點 + interval)`。長跑會慢慢往後漂
（因為是「上次起點＋interval」不是「起跑＋n×interval」），要對齊格子之後再說。

計時用 `time.monotonic()`，改系統時間不影響。

### 給程式看的：`--status-fd N`

stderr 那些 `aos-run: …` 行是**給人看的**，照舊印。`--status-fd N` 是**給程式看的**
（aos-daemon 讀的就是它，不再去解 stderr）：一行一個事件、`\n` 結尾、寫完就到。

```
ready                                 裝好訊號處理器了、第一次還沒開跑
start #1                              第 1 次要開跑了
done #1 exit=0 kind=child 0.3s        第 1 次跑完了（kind 見 aos-exec 那節）
done #2 exit=125 kind=aos 0.0s        第 2 次：aos-exec 自己失敗（inst.json 壞／沒出現）
stop max_runs                         停了；然後這個 fd 就關掉
```

`kind=aos` 那種的 `exit=` 一律報 **125**（跟 aos-exec 命令列的退出碼同一個數字），所以
「aos 自己失敗」跟「子程式回 1」在這條流上分得開。

沒給 `--status-fd` 就什麼都不寫。寫失敗（對方把管子關了）＝忽略，不影響執行——回報狀態
不該把工作弄倒。`ready` 特別重要：daemon 靠它知道「訊號處理器裝好了，現在 SIGSTOP／
SIGTERM 送得過去」。

### 什麼時候停

五個條件，任一成立就停；退出碼多數是 **0**，兩個例外：

| 原因 | 什麼時候 | 退出碼 |
|---|---|---|
| `max_runs` | 跑滿 `--max-runs N` 次 | 0 |
| `time_limit` | 撞到 `--time-limit-ms`。**硬時限**：正在睡→醒來就退；正在跑→**那次被砍** | 0 |
| `stop_exit` | 某一次的退出碼在 `--stop-exit` 那組裡面 | 0 |
| `error` | 給了 `--stop-on-error`，而且某一次 `kind` 是 `aos`（aos-exec 自己失敗） | **125** |
| `signal` | 收到**第一次** SIGTERM／SIGINT | 0 |
| `signal_forced` | 同一個訊號又收到**第二次**（腰斬正在跑的那次） | 128+N（SIGTERM＝143、SIGINT＝130） |

`signal_forced` 退出碼不是 0：**第二次代表有工作被腰斬，不算乾淨**。

**硬時限怎麼砍正在跑的那次**：不另開執行緒，而是每次呼叫 `run_target()` 時把 `timeout_ms`
換成 `min(原本的或無限, 剩下的毫秒)`，交給 aos-exec 本來就有的那套砍法（SIGTERM 整個
process group、2 秒、SIGKILL），所以被砍那次印出來的碼是 143 或 137。

**訊號**：第一次 SIGTERM／SIGINT ＝ 讓正在跑的那次**跑完**再退，退出碼 0；第二次**同一個**
訊號 ＝ 直接 SIGKILL 掉正在跑的那個 process group 再退，退出碼變 128+N。睡覺是小步睡的
（0.05 秒一步），所以 `--interval-ms 5000` 睡到一半也叫得醒，不會不理你五秒。

**aos-exec 自己失敗（inst.json 壞掉）預設不算停止條件**，照 interval 一直試——壞了也活著，
跟 proto4-2 的 cpu 一樣。要它停就給 `--stop-on-error`（退出碼 125）。

### 印什麼、回什麼

不寫檔。每跑完一次，在 **aos-run 自己的 stderr** 印一行（秒數一位小數）：

```
aos-run: #1 exit=0 0.3s
aos-run: #2 exit=1 0.0s
aos-run: stop max_runs
```

那個 `exit=` 是 `run_target()` 回的 code，只有一個地方不是原樣：**aos-exec 自己失敗
（`kind=aos`）一律報 125**，跟子程式自己回的 1 分得開。要看是誰的碼就看 status-fd 那條的
`kind=`。

aos-run 自己的退出碼：**2**＝用法錯（旗標不認得、沒給 `xxx`、`xxx` 是不存在的**非**
`.json` 路徑、時間／次數旗標是負數）；**0**＝`max_runs`／`time_limit`／`stop_exit`／第一次訊號（`signal`）；
**125**＝`--stop-on-error` 撞到 aos-exec 自己失敗（`error`）；**128+N**＝同一個訊號收到
第二次（`signal_forced`，正在跑的那次被腰斬）。子行程的退出碼只出現在那些 `#n exit=`
行裡，不會變成 aos-run 的退出碼。

`xxx` 只在起跑前檢查一次，而且**以 `.json` 結尾的路徑連這一次都不查**（不存在就每次回
`exit=125 kind=aos`，檔案出現了就跑起來——daemon 靠的就是這條）。資料夾跑到一半被搬走，
之後每次就是 `run_target()` 回 `kind=usage` 的那行，迴圈照樣繼續——**`--stop-on-error`
只看 `kind=aos`，不管 `usage`**（資料夾被人搬走是外面的事，不是這份 inst.json 壞了）。

當成函式用（daemon 之後就是這樣接）：

```python
import aos_run
code, reason = aos_run.run_loop("/path/to/folder", interval_ms=5000, max_runs=10,
                                from_start=True, status_fd=w, stop_on_error=True)
```

## aos-daemon：一個 dict，key＝一份 inst.json 的路徑，value＝正在跑的 aos-run

[proto4 筆記第 13 節](../proto4/notes/2026-09-08-ideas.md)的原型（key 那條照
[第 15 節](../proto4/notes/2026-09-08-ideas.md)改過）。**daemon 就是一個常駐進程，裡面
一個 dict**——key 是**那份 inst.json 的路徑**，value 是一個正在跑的 `aos-run` 子進程，
一份 inst.json 最多一個。value 是**子進程**不是執行緒，所以進程的事通通交給 Linux：暫停＝SIGSTOP、
繼續＝SIGCONT、刪＝SIGTERM。

**`aos-daemon` 是一支普通程式，你自己開著它、自己管它的生死**（要放背景 `aos-daemon &`、
tmux、systemd 都行，aos 不管）；**`aos-daemon-ctl` 是另一支對它下指令的工具**，兩支分開。

```sh
./aos-daemon &                                               # 普通前台程式，自己丟去背景

./aos-daemon-ctl add /path/to/inst.json --interval-ms 2000   # 旗標原樣傳給 aos-run
./aos-daemon-ctl add /path/to/other.json --interval-ms 500   # 同資料夾第二份＝另一筆
./aos-daemon-ctl ls
./aos-daemon-ctl pause /path/to/inst.json
./aos-daemon-ctl resume /path/to/inst.json
./aos-daemon-ctl rm /path/to/inst.json --force
./aos-daemon-ctl stop                                        # 請 daemon 收工、進程退出
```

### key＝那份 inst.json 的路徑

**key 就是那個 `.json` 檔的 realpath**（[§15](../proto4/notes/2026-09-08-ideas.md)），
所以 symlink、`..`、相對路徑寫法通通算同一筆。同一個 key 第二次 `add`＝`ok:false`、
**舊的不動**；**同一個資料夾可以掛好幾份不同的 inst.json，各自一支 aos-run**。

| 你給的路徑 | 收不收 |
|---|---|
| `.json` 檔 | **收** |
| `.json` 路徑但檔案**還不存在** | **收**——aos-run 每次跑回 `exit=125 kind=aos`，檔案出現了就自然跑起來 |
| 資料夾（連名字叫 `x.json` 的資料夾也是） | 拒絕：「只收 .json 檔，這是資料夾：…」 |
| 普通檔案（副檔名不是 `.json`） | 拒絕：「只收 .json 檔：…」 |

`add`／`restart` 照上表擋；`rm`／`get`／`pause`／`resume` 不擋，存不存在都照 realpath
查表（表上有就找得到）。**不拿 inst.json 裡的 `cwd` 欄位當 key**——那個每次執行都可能被
改，還可能是 `$ref` 解出來的。

`aos-daemon-ctl` 的 `add`／`restart` **不收 `--dir-target`**（那是給資料夾當目標用的，
這裡的目標一定是一份 `.json`）：寫了就是用法錯、退出碼 2，不會被偷偷吞掉。daemon 開
aos-run 時也不會加這個旗標。`aos-run`／`aos-exec` 單獨用時照舊有這個旗標。

### 五個狀態

每一筆有一個 `state`，`get`／`ls`／`state.json` 都帶著它：

| `state` | 意思 |
|---|---|
| `running` | 正常跑著 |
| `pause_pending` | 收到 `pause` 了，**等它睡著**才會真的 SIGSTOP |
| `paused` | 已經 SIGSTOP 住了 |
| `stopping` | 送過 SIGTERM 了，等它自己退（5 秒還不退＝SIGKILL 整個 group） |
| `restarting` | 跟 `stopping` 一樣，只是收屍之後要用新旗標同 key 再開一顆 |

### 七個動作：全部立刻回，等待是主迴圈的事

**主迴圈不等任何人。** 七個動作都是「送個訊號、標個狀態、立刻回 `(ok, result)`」，真正的
「等它退」「等它睡著」交給每 0.2 秒跑一次的那一圈。所以 `rm` 一個手上那次要跑一小時的
aos-run，daemon 照樣立刻收下一個請求——只有收工（`stop`）會同步等，那時候本來就該等。

| 動作 | 做什麼 | 回什麼 |
|---|---|---|
| `add` | 先擋掉資料夾／非 `.json`，再開一個 `aos-run FILE.json 旗標… --status-fd N` 子進程（`start_new_session`），記進表 | 那一筆 |
| `remove` | 暫停中的先 SIGCONT → SIGTERM → 標 `stopping`、記 5 秒的 deadline。`force`＝0.2 秒後再補一發 SIGTERM（腰斬，退出碼 143）。過了 deadline 還活著＝SIGKILL 整個 group | `"stopping"` |
| `restart` | 跟 `remove` 一樣送 SIGTERM，但標 `restarting`、把新旗標存在那一筆上；**收屍時**用新旗標同 key 再 `add`——aos-run 開跑後旗標改不了 | `"restarting"` |
| `get` | 一筆：`pid`／`target`／`args`／`started_at`／`state`／`ready`／`running`／`runs`／`last_exit`／`last_kind`／`last_line`／`alive` | 那一筆 |
| `ls` | 全部的 `get`，key 是那份 `.json` 的路徑 | 整張表 |
| `pause` | 標 `pause_pending`；主迴圈每圈看，`ready` 且 `running == False`（在睡覺）才送 SIGSTOP、改 `paused` | `"pause_pending"` 或 `"paused"` |
| `resume` | `paused`→SIGCONT、改 `running`；`pause_pending`→取消那個等待 | `"running"` |

**pause 不腰斬正在跑的那次**——等 aos-run 說它 `done` 了才停，所以暫停之後那份 inst.json
沒有做到一半的工作。代價：`interval` 極短時 SIGSTOP 可能剛好落在下一次開跑之後，那次會跑完才真的停，
**不保證從此零次**。已經 `paused`／`pause_pending` 的再 `pause`＝冪等；`stopping`／
`restarting` 的再 `rm`＝冪等 ok（`restarting` 途中改 `rm` 就不再重開）。

### 近況從哪來：讀 status-fd，不解 stderr

`add` 的時候開一條 `os.pipe()`，寫端用 `pass_fds` 交給子進程、命令列加
`--status-fd <寫端>`，daemon 這邊立刻關掉自己那份寫端（不然讀端永遠等不到 EOF），
**每一筆兩條執行緒**：

- **status 那條**逐行讀事件，更新 `ready`／`running`／`runs`／`last_exit`／`last_kind`／
  `last_line`。這是給程式看的，格式固定，不用猜。
- **stderr 那條**照舊逐行讀，原樣（前面加 key）append 進 `daemon.log`——純流水帳，
  **不再從這裡解近況**。

```
22:24:49 /tmp/w/inst.json aos-run: #1 exit=5 0.0s
22:24:49 /tmp/w/inst.json aos-run: stop max_runs
22:24:49 自己退了 /tmp/w/inst.json pid=223053 exit=0 last=stop max_runs
```

aos-run **自己退了**（`--max-runs` 跑滿、時限到、`--stop-exit`、被別人殺）→ daemon 收屍、
從表上拿掉、`daemon.log` 記一行。不自動重開；那份 inst.json 之後可以再 `add`。

### 請求格式

daemon 與外面之間只有檔案：寫一個 JSON 到 `H/requests/`（先 `.tmp` 再 rename），daemon
每 0.2 秒掃一次（`.tmp` 忽略），處理完搬到 `H/requests/done/` 同名、內容＝**原請求 ＋
`ok` ＋ `result`**。**daemon 自己讀請求**，不經過 kernel——kernel（往下看那一節）只是
另一個會叫 `aos-daemon-ctl` 的使用者，不碰 `requests/`。

```json
{"op":"add",     "target":"/path/to/inst.json", "args":["--interval-ms","2000"]}
{"op":"remove",  "target":"/path/to/inst.json", "force":false}
{"op":"restart", "target":"/path/to/inst.json", "args":["--interval-ms","5000"]}
{"op":"get",     "target":"/path/to/inst.json"}
{"op":"ls"}
{"op":"pause",   "target":"/path/to/inst.json"}
{"op":"resume",  "target":"/path/to/inst.json"}
{"op":"stop"}
```

目標欄位七個動作**一律叫 `target`**（舊的 `dir` 沒了），值是那份 inst.json 的路徑、先
realpath 再查表。不認得的 op、缺欄位、`add`／`restart` 給了資料夾或非 `.json`＝`ok:false`
（不是炸掉）；**`add` 的 `.json` 不存在不算錯**，照收。`stop`＝daemon 收工：所有 aos-run 送 SIGTERM、等它們退、自己退；daemon 收到
**SIGTERM 也一樣**。

### 家目錄

`--home H` → 環境變數 `AOS_DAEMON_HOME` → 預設 `~/.aos-daemon`。`aos-daemon` 與
`aos-daemon-ctl` 要指到同一個家才對得上話。

```
H/requests/         請求檔
H/requests/done/    處理完的
H/daemon.pid        daemon 的 pid
H/state.json        每 0.5 秒寫一次（先 .tmp 再 rename）
H/daemon.log        daemon 自己的話 ＋ 每個 aos-run 的 stderr（原樣，前面加 key）
```

`state.json` 就是 `ls` 的內容：

```json
{"pid": 223051, "home": "/tmp/myaos",
 "runs": {"/tmp/w/inst.json": {"pid": 223053, "target": "/tmp/w/inst.json",
                     "args": ["--interval-ms","200"],
                     "started_at": 1788963889.1, "state": "running", "ready": true,
                     "running": false, "runs": 3, "last_exit": 5, "last_kind": "child",
                     "last_line": "done #3 exit=5 kind=child 0.0s", "alive": true}}}
```

### CLI：aos-daemon 與 aos-daemon-ctl 分開兩支

```sh
aos-daemon [--home H]
```

普通的**前台程式**，不會自己背景化。跑起來就寫 `daemon.pid`、進主迴圈，直到收到
SIGTERM／SIGINT（Ctrl-C）或 `aos-daemon-ctl stop` 才收工。家裡已經有一個活著的 daemon
（`daemon.pid` 那個 pid 還活著）→ 印「已經在跑（pid N）」、退出碼 1，不會搶著跑。沒有
子命令；要放背景自己 `aos-daemon &`，或交給 tmux／systemd 之類的常駐管理員，aos 不管。

```sh
aos-daemon-ctl add FILE.json [aos-run 旗標…]|rm FILE.json [--force]
              |restart FILE.json [旗標…]|get FILE.json|ls
              |pause FILE.json|resume FILE.json|stop       [--home H]
```

**FILE 是一份 inst.json 的路徑**（不是資料夾），`--dir-target` 在這裡是用法錯（退出碼 2）。

| 指令 | 怎麼做的 |
|---|---|
| `stop` | 丟 `{"op":"stop"}` 請 daemon 收工，等 `daemon.pid` 的 pid 真的死掉才回（上限 10 秒） |
| `ls`／`get` | **直接讀 `state.json`** 印表（`FILE PID STATE RUNS LAST_EXIT`），不丟請求、不用等 daemon 回，所以看到的最多是 0.5 秒前的樣子；daemon 沒在跑時照樣印最後一份 state.json，但 stderr 提醒一句 |
| `add`／`resume` | 丟請求檔、等 `done/` 出現（上限 10 秒）、印 `ok`／`result`；`ok:false`＝退出碼 1 |
| `rm`／`restart`／`pause` | 同上，但因為 daemon 是「收到了、開始做」就回，**這裡再多等一步**（見下面） |

**`rm`／`restart`／`pause` 回來時事情已經做完了。** daemon 那邊回的是 `stopping`／
`restarting`／`pause_pending`，ctl 拿到之後**輪詢 `state.json`**（上限 10 秒）等到真的到位
才印結果、才退出：

| 指令 | 等到什麼 | 印 | 等不到 |
|---|---|---|---|
| `rm FILE.json` | 那個 key 從表上**消失** | `removed <key>` | 「等不到它退掉，還在表上」、退出碼 1 |
| `restart FILE.json …` | 那個 key 的 `pid` **換成新的**且 `state` 是 `running` | `restarted <key>` | 「等不到新的那顆起來」、退出碼 1 |
| `pause FILE.json` | `state` 變成 `paused` | `paused <key>` | 「還在等它睡著」、退出碼 1 |

等不到只是**這支 CLI 不等了**，daemon 那邊該做的還是會做完。

`daemon` 沒在跑時，`ls`／`get` 照上面讀最後狀態，其他指令直接印「daemon 沒在跑」、退出碼
1、不丟檔。`--home` 可以擺在任何位置，其他旗標**原樣**留給 aos-run（所以這支不用
argparse，不然 `--max-runs` 之類會被吃掉）。

## aos-kernel：作業系統的第一個程序，管「哪顆 cpu 上是哪個行程」

[proto4 筆記第 16～18 節](../proto4/notes/2026-09-08-ideas.md)的原型。名詞先對齊：

- **daemon ＝硬體**。`aos-daemon-ctl add foo.json` ＝**插一顆 cpu**，`rm` ＝拔掉。一份
  inst.json 就是那顆 cpu 的「指令暫存器」，aos-run 每隔 interval 讀它一次、跑一次。
- **kernel ＝第一個程序**。它是**唯一**會叫 `aos-daemon-ctl` 的人（cpu 的存在與使用權），
  也是**唯一**會改 cpu 那份 inst.json 的人（cpu 下一次去跑誰）。
- kernel 自己也是被 daemon 跑著的一個 proc：它的家裡有一份 `inst.json`，使用者手動
  `ctl add` 它＝**上電**，之後 kernel 每隔一段時間自己跑一次 `aos-kernel-tick`。

### 家長什麼樣

```
K/inst.json         kernel 自己那顆 cpu 的指令：{"argv":["…/aos-kernel-tick"],"cwd":"."}
K/config.json       {"ncpu":2,"interval_ms":1000,"timeout_ms":0,"quantum":5}
K/procs/<pid>.json  就緒佇列：等著上 cpu 的行程，檔名去掉 .json ＝ pid
K/procs/bad/        退件（不是 JSON 物件／沒有 argv／沒寫 cwd 的都搬來這裡）
K/cpus/<n>.json     每顆 cpu 一份 inst.json，這個路徑就是 daemon 表上的 key
K/state.json        kernel 自己的表：cpu n → pid、上去的時間、上去時的 runs、佇列
K/kernel.log        每回合 append 一行
```

`aos-kernel-init` 寫進 `inst.json` 的 `argv[0]` 是 **`aos-kernel-tick` 的絕對路徑**——
daemon→aos-run→aos-exec 的 PATH 是使用者開 daemon 時那一份，未必找得到 proto4-3；寫死絕對
路徑就不用管 PATH。串流三條都不寫（aos-exec 開 `stdout` 是清空重寫，當不了 log，要看流水帳
就看 `kernel.log`）；`envs` 也不寫，`AOS_DAEMON_HOME` 從 daemon 一路繼承下來。

### 指令：一支系列，各管各的壽命

`init`（重灌作業系統、很久一次）跟 `tick`（心跳、每回合）不是同一種壽命的東西，`ls`
（給人看）也不是心跳的一部分，所以三個都是各自獨立的指令，不擠在一支程式的子命令裡
（[proto4 筆記 §19.4／§19.7](../proto4/notes/2026-09-08-ideas.md)）：

```sh
aos-kernel-init DIR --ncpu N [--interval-ms X] [--timeout-ms Y] [--quantum Q]
aos-kernel-tick         # 心跳：在家裡（cwd ＝ K）跑一回合，不吃參數
aos-kernel ls           # 印給人看：每顆 cpu 上是誰、上去多久、跑了幾次、誰在等
```

| 指令 | 做什麼 | 退出碼 |
|---|---|---|
| `aos-kernel-init` | 建家與四個檔；`--interval-ms`／`--timeout-ms` 是**每顆 cpu** `ctl add` 時給 aos-run 的旗標（預設 1000／0），`--quantum` 是時間片（預設 5，單位是「cpu 跑了幾次」） | 0；**DIR 已經存在＝1**（不動它） |
| `aos-kernel-tick` | 跑一回合，見下面五步 | **一律 0**；cwd 不是家（沒有 `config.json`）＝1 |
| `aos-kernel ls` | 讀 `state.json` ＋ daemon 的 `state.json` 印表；目前 `aos-kernel` 只剩這一個子命令 | 0；不是家＝1 |

`aos-kernel init`／`aos-kernel tick`（舊的子命令）都拿掉了：退出碼 2，stderr 提示改用
`aos-kernel-init`／`aos-kernel-tick`。以後 `aos-kernel-boot`（§19.3，一條指令做完「開
daemon → kernel init → ctl add kernel 的 inst.json」）也會是同一系列的獨立指令。

### aos-kernel-tick 每回合五步（順序固定）

1. **讀自己的表**（`state.json`，沒有＝空表）。
2. **點 cpu**：直接讀 daemon 的 `state.json`（不開 ctl 進程），看 `cpus/0.json`…
   `cpus/N-1.json` 這 N 個 key 哪些在 daemon 表上。不在表上的：檔案不見了就先寫一份 idle
   指令（`{"argv":["true"],"cwd":"."}`），再 `aos-daemon-ctl add <絕對路徑> --interval-ms X`
   把它插上去（**不開 `--stop-on-error`**）。所以 aos-run 被 `ctl rm` 掉、或 daemon 重開過，
   下一回合就自己補回來。add 失敗（daemon 沒在跑之類）＝記一行 log、**那顆 cpu 這回合不排程**，
   退出仍是 0——kernel 不會因為外面的事死掉。
3. **檢查佇列**：`procs/*.json`（不含 `bad/`）逐個讀，不是 JSON 物件／沒有 `argv`／`cwd`
   沒寫或不是字串 → 搬去 `procs/bad/` 同名並記 log。**cwd 一定要寫死**：檔案會被搬到
   `cpus/n.json`，沒寫 cwd 的話預設 cwd 會跟著變成 cpu 的資料夾，行程就跑錯地方了。
   （這道檢查**只有 kernel 做**，daemon／aos-run／aos-exec 維持原本行為。）
4. **排程**：每顆 cpu 看一次——
   - 上面是 idle（或沒記錄）而且有人在等 → 把隊首那位 `rename` 上去。
   - 上面有人，而且「daemon 現在的 `runs` － 它上去時記的 `runs` ≥ quantum」，而且**還有人在等**
     → 換人。**沒人在等就讓它續跑**（v1 的行程不會自己結束）。
   - **換檔不留空窗**：先 `os.link(cpus/n.json, procs/<舊>.json)`（舊的先在 `procs/` 有一個
     名字），再 `os.rename(procs/<新>.json, cpus/n.json)`（原子蓋過去）。任何時刻
     `cpus/n.json` 都存在、內容不是完整的舊檔就是完整的新檔，所以 aos-run 剛好開跑也吃不到
     125。要換成 idle（例如 cpu 那個檔被人刪了）就寫 `.tmp` 再 rename。
   - **佇列是 FIFO**：新出現在 `procs/` 的排尾巴、被換下來的也排尾巴、檔案不見的（人手動刪）
     從佇列拿掉。純照 pid 大小挑的話小 pid 會永遠優先，所以 `state.json` 自己記一個
     `queue` 陣列；同一回合新冒出來的照 pid 順序排（數字比數字、非數字排在數字後面）。
5. **寫表寫 log**：`state.json` 先 `.tmp` 再 rename、`kernel.log` append 一行，退出 0。

`state.json` 長這樣：

```json
{"cpus": {"0": {"pid": "3", "since": 1788999123.4, "runs_at": 12},
          "1": null},
 "queue": ["5", "7"]}
```

`runs_at` 是「這位上 cpu 那一刻，那顆 cpu 的 aos-run 總共跑過幾次」，時間片就是拿它跟現在
的 `runs` 相減。cpu 被 `ctl rm` 過再插回來時 `runs` 會從 0 重數，kernel 看到「現在的比記的
還小」就把 `runs_at` 重設，不會卡住不換人。

### 開機順序

```sh
./aos-daemon &                                          # 硬體上電
./aos-kernel-init K --ncpu 2 --interval-ms 1000 --quantum 5
./aos-daemon-ctl add K/inst.json --interval-ms 1000     # 插上第一顆 cpu ＝ 跑 aos-kernel-tick
cp my-proc.json K/procs/3.json                          # 把行程丟進就緒佇列（cwd 要寫死）
./aos-kernel ls                                         # 看誰在哪顆 cpu 上（cd K 再跑）
```

`AOS_DAEMON_HOME` 那三支要對得上：kernel 是從 daemon 繼承下來的，所以 daemon 用
`AOS_DAEMON_HOME=…` 開比用 `--home` 保險（`--home` 不會傳給子孫）。

### kernel 這一版沒做什麼

- **行程不會自己結束**：v1 就是永遠輪流。要拿掉一個，趁它不在 cpu 上時手動刪 `procs/` 的檔
  （kernel 下一回合就把它從佇列拿掉）。
- **沒有優先級、沒有 nice**，時間片一律 quantum 次，佇列純 FIFO。
- **沒有 syscall 收件匣**（行程不能 fork、不能自己丟東西進 `procs/`）、**不改 cpu 的韌體設定**
  （`ctl add` 給的 interval／timeout 定死不改）、**沒有 daemon↔kernel 專用通道**（每回合只看
  `state.json`，中間的退出碼看不到）。
- **`procs/` 裡就是原封不動的 inst.json**，直接搬上 cpu。以後那裡會多權限、優先級之類的欄位，
  到時就得由 kernel 轉一手。
- **kernel 只做格式檢查，不做權限檢查**：能寫 `procs/` 的人就能用你的身分跑任何東西。
- **搶佔不了正在跑的那一次**：rename 只影響「下一次」開跑讀到誰，手上那次會跑完。
- **一個家只該有一個 kernel 在 tick**：兩個 tick 同時跑會搶同一批檔案，v1 沒有鎖。

## 檔案

- `aos-exec`：命令列入口，可執行，薄薄一層。
- `aos_exec.py`：認目標是哪一種、組出要跑的東西、跑一次、砍逾時、寫 exit 檔。核心是
  `run_target(xxx, dir_target=…, timeout_ms=…) -> (code, kind)`，`kind` 是
  `child`／`aos`／`usage`。
- `aos_inst.py`：inst.json 的讀、驗、解指示詞（格式那一層），從 proto4-2 抄來改的。
- `aos-run`：aos-run 的命令列入口，可執行，一樣薄薄一層。
- `aos_run.py`：迴圈本體——什麼時候跑下一次、什麼時候停、跑完印一行（給人）＋寫一個事件
  （給程式）。核心是 `run_loop(xxx, *, dir_target=…, timeout_ms=…, interval_ms=…,
  from_start=…, max_runs=…, time_limit_ms=…, stop_exits=…, log=…, status_fd=…,
  stop_on_error=…) -> (退出碼, 停止原因)`。
- `aos-daemon`：daemon 本人的命令列入口——普通前台程式，解 `--home`、檢查已經在跑、
  `Daemon(home).serve()`。不背景化，自己 `&` 或交給 systemd。
- `aos_daemon.py`：daemon 本體——那個 dict、七個動作（都是 `Daemon` 的方法、都回
  `(ok, result)`、都立刻回，測試可以不開 daemon 進程直接叫）、主迴圈一圈 `tick()`
  （收請求、推狀態機、收屍）、落地與收工。
- `aos_daemon_entry.py`：表上的**一筆**長什麼樣（`Entry`）＋五個狀態的**狀態機**
  （`advance()`／`begin_stop()`）＋兩條讀取執行緒（讀 status 更新近況、讀 stderr 進 log）
  ＋ key 那兩條規則：`key_of()`（那份 `.json` 的 realpath）與 `json_only()`（只收 `.json`）。
- `aos_daemon_req.py`：**請求檔**那一層——`dispatch()`（一個請求 →`(ok, result)`）與
  `handle_requests()`（掃 `requests/`、處理、搬到 `done/`）。
- `aos-daemon-ctl`：命令列入口，可執行，薄薄一層，真東西在 `aos_daemon_ctl.py`。
- `aos_daemon_ctl.py`：對 daemon 下指令——丟請求等回音、讀 `state.json` 印表；daemon 沒在
  跑時 `ls`／`get` 讀最後狀態、其他指令直接說「daemon 沒在跑」。
- `aos-kernel`：命令列入口，可執行，薄薄一層，真東西在 `aos_kernel.py`。
- `aos_kernel.py`：家的版面（`KHome`：哪個檔在哪、讀寫 config／state／log，`here_or_die()`
  共用）＋剩下的唯一子命令 `ls`。`init`／`tick` 都拿掉了，被人叫到只回退出碼 2、提示改用
  `aos-kernel-init`／`aos-kernel-tick`。
- `aos-kernel-init`：命令列入口，可執行，薄薄一層，真東西在 `aos_kernel_init.py`。
- `aos_kernel_init.py`：`init` 本體——建家與四個檔（`inst.json`／`config.json`／
  `state.json`／`kernel.log`／`procs/`／`cpus/`），從 `aos_kernel.py` 拆出來的獨立指令
  （§19.4：重灌作業系統跟每回合跑的心跳／給人看的 ls 不是同一種壽命），共用
  `aos_kernel.KHome`。
- `aos-kernel-tick`：命令列入口，可執行，薄薄一層，真東西在 `aos_kernel_tick.py`。
- `aos_kernel_tick.py`：心跳本體——一回合那五步：點 cpu（`poll_cpus`／`ctl_add`）、檢查佇列
  （`check_queue`／`bad_reason`）、排程（`schedule`／`_take`／`_swap`，硬連結＋rename 那招），
  也是從 `aos_kernel.py` 拆出來的獨立指令（§19.7），共用 `aos_kernel.here_or_die()`。
- `aos_home.py`：家目錄的版面（哪個檔在哪）＋家的優先序（`--home` → `AOS_DAEMON_HOME` →
  `~/.aos-daemon`）＋原子寫檔＋pid 活不活，從 proto4-2 改的。
- `test/`：`python3 -m unittest discover -s test`（185 條）。kernel 的在
  `test_kernel.py`（真的開一支 daemon ＋ 真的跑 aos-kernel）。daemon 的測試分三支：
  `_daemon.py`（共用基底，底線開頭＝discover 不撿）、`test_daemon.py`（key 與查）、
  `test_daemon_ops.py`（暫停／刪／restart／請求），另外 `test_daemon_cli.py` 真的開一支
  daemon 進程走完一輩子。

## 沒做什麼

**最簡原型，邊緣狀況一律沒做。** 列出來免得以為它會：

- **沒有覆蓋串流的旗標**。「用 aos-exec 自己的 stdin／stdout／stderr／exit 蓋掉 inst.json
  裡寫的」是後續要做的方便功能，這次不做。
- **不注入 `AOS_*` 環境變數**（`AOS_DIR`／`AOS_TICK` 都沒有），aos-exec 與 aos-run 都一樣
  （§8：proc 不需要知道自己被誰、以什麼節奏跑）。要不要有之後撞到再說。
- **不寫任何紀錄檔**。不抓子行程的輸出、不寫 `last.json`／`runs.jsonl`，`exit` 欄位是唯一
  會被寫出去的東西。想看輸出就自己寫 `stdout`。aos-run 的每次一行只印在**它自己的 stderr**，
  `--status-fd` 也只是**寫給誰**的事，不落檔。
- **整合進 aos-daemon 是之後的事**。aos-run 只是概念驗證：proto4-2 的 `aos_cpu.py`「跑一次」
  那段要換成這裡的東西、`last.json`／`runs.jsonl`／`cpu.json` 歸誰寫，都還沒動。
- aos-run **沒有對齊格子**：`--from-start` 是「上次起點＋interval」，不是「起跑＋n×interval」，
  長跑會慢慢往後漂。
- aos-run **不重讀自己的旗標**、不吃設定檔、沒有健康檢查、沒有退避（壞掉就是照原速一直試）。
- `exit` 檔的父目錄不存在就直接失敗（退出碼 125），**不幫忙 mkdir**，那個指令也不會被跑。
- `$ref` 沒有範圍限制（能不能指到 cwd 外＝行程權限說了算），也**沒有深度上限**——只有循環
  會被擋（同一條鏈撞到同一個 realpath＋pointer），一條夠長的鏈可以一直解下去。
- **`$ref` 的相對路徑一律以 cwd 為中心**，不是以「被 `$ref` 的那個檔所在的資料夾」為中心。
  所以從別的資料夾 `$ref` 進來的一份 inst.json，它裡面的相對路徑還是照 cwd 算。
- `$fmt` 只有 `env:` 一個 namespace，沒有路徑變數、沒有預設值語法、沒有跳脫。
- 沒有並行（凍結版的 `parallel`）、沒有批次、沒有重試、沒有退避。

aos-daemon 這一版另外沒做的：

- **不自動重開**。aos-run 自己退了（跑滿、時限到、`--stop-exit`、被別人殺）就只是從表上
  消失、`daemon.log` 記一行，不會替你再開一個。
- **只看副檔名，不看內容**：`add` 只確認「不是資料夾、以 `.json` 結尾」，裡面是不是一份
  合法的 inst.json 完全不驗——驗那個是 aos-exec 每次跑的事（壞了就每次 `exit=125 kind=aos`）。
- **不監看檔案出現**：收下一個還不存在的 `.json` 之後，就是照 `--interval-ms` 一直試，
  沒有 inotify、沒有退避，`runs` 會一直往上加。
- **暫停中 `--timeout-ms` 不生效**：砍逾時的是 aos-run，它被 SIGSTOP 了就沒人砍，正在跑
  的那個子行程會一直跑下去。要不要讓 daemon 代砍，之後再說。
- **`pause` 不保證從此零次**：等它睡著才 SIGSTOP，`interval` 極短時那一刀可能剛好落在下一次
  開跑之後，那次會跑完才真的停。要「馬上凍住、正在跑的也不管」得另外做。
- **`restart` 的空窗期表上還在**（狀態 `restarting`，別人趁隙 `add` 會被擋掉），但那段時間
  它就是沒在跑，`pause`／`resume` 也會被拒絕。
- **等不到就放棄的是 CLI，不是 daemon**：`aos-daemon-ctl` 的 rm／restart／pause 等 10 秒
  就印一句退出碼 1，daemon 那邊該做的還是照做。要對帳自己再 `ls` 一次。
- **daemon 這一層不知道有 kernel**：請求是 daemon 自己讀的，`aos-kernel` 對它來說就是
  另一個下 `ctl` 指令的人。
- **沒有 `.aos/` 紀錄檔**（proto4-2 的 `last.json`／`runs.jsonl`／`cpu.json` 都沒有），
  只剩 `daemon.log` 一條線；aos-run 子進程的 stdout 直接進 `/dev/null`。
- **daemon 的生死歸使用者**（§9）：它就是硬體，一支普通程式，你自己開著、自己管它的生死
  （背景放 `&`、tmux、systemd 都行），掛了 aos 不管、也不會有人替你重開。
- 沒有權限、沒有認證：**誰能寫 `H/requests/` 就能叫 daemon 用你的身分跑任何東西**。
- 不檢查 inst.json 的權限。一份 inst.json 就是可執行的權柄：它可以指名任意程式、引數、
  輸入輸出檔、工作目錄與環境變數值，全都用你的憑證跑。能改它的人就等於能用你的身分執行
  任意程式碼。
