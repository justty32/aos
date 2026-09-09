# proto4-3 — aos-exec：單發執行器＋aos-run：連續執行版（Python）

這是 [proto4 筆記第 11 節](../proto4/notes/2026-09-08-ideas.md)（aos-exec）與
[第 12 節](../proto4/notes/2026-09-08-ideas.md)（aos-run）的原型，規格以那兩節為準
（跟第 10 節衝突的地方都聽第 11 節的）。

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
python3 -m unittest discover -s test        # 125 條測試，真的開進程，暫存在 /tmp、跑完自己收

./aos-exec /path/to/folder                  # 跑 folder/.aos/inst.json
./aos-exec /path/to/folder --dir-target my/inst.json
./aos-exec /path/to/one.json                # 直接指一份 inst.json
./aos-exec /path/to/script.sh               # 普通檔案：直接執行它
./aos-exec /path/to/folder --timeout-ms 3000
echo $?                                     # 退出碼就是子行程的結束狀態
```

```sh
./aos-run /path/to/folder --interval-ms 5000            # 一直跑，每 5 秒一次
```

當成函式用（aos-run 就是這樣接的）：

```python
import aos_exec
code = aos_exec.run_target("/path/to/folder", dir_target=".aos/inst.json", timeout_ms=3000)
```

## 三種目標

`aos-exec xxx [--dir-target REL] [--timeout-ms N]`，看 `xxx` 是什麼決定怎麼跑：

| `xxx` 是 | 做什麼 | cwd 預設 | 串流 |
|---|---|---|---|
| 普通檔案（副檔名不是 `.json`） | 直接執行它：`argv` 就是它的絕對路徑 | 它所在的資料夾 | **繼承** aos-exec 的 |
| `.json` 檔 | 讀進來當 inst.json 解析、執行 | 那個 `.json` 所在的資料夾 | 照 inst.json |
| 資料夾 | 執行 `xxx/.aos/inst.json`（`--dir-target` 可改） | `xxx` 自己 | 照 inst.json |

普通檔案模式什麼都不解析：環境就是繼承的、沒有 exit 檔、沒有重導向。它沒有執行位＝126。

先看是不是資料夾再看副檔名，所以一個名字剛好以 `.json` 結尾的**資料夾**還是照資料夾走。

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
| `envs` | 物件 | `{}`＝只有繼承的 | 疊在 aos-exec 的環境上只加不減；key 不能空、不能含 `=` |

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

### 指示詞

`argv` 的每個元素、四個路徑欄位（`stdin`／`stdout`／`stderr`／`exit`）、`cwd`、`envs` 與
`$envs` 的值，都可以不寫字串，改寫一個**指示詞**——剛好一個 key、值一定是字串的物件：

| 指示詞 | 意思 |
|---|---|
| `{"$env":"NAME"}` | 從 **aos-exec 自己的**環境取值。變數不存在＝錯誤；存在但空＝空字串（兩件不同的事） |
| `{"$fmt":"模板"}` | 接字串用的，見下面 |
| `{"$ref":"file.json#/a/b"}` | 相對於 **cwd** 讀那份 JSON，`#` 後面是 RFC 6901 的 JSON Pointer（`~1` 代表 `/`、`~0` 代表 `~`），沒有 `#` 就取整份 |
| `{"$opt":"merge"}` | 只有 `stderr` 能用，等於 shell 的 `2>&1` |

`$ref` **取回來的值就當成本來寫在那裡**：是字串就直接用，又是指示詞就繼續解（可以巢狀），
陣列或一般物件＝錯誤。同一條鏈再撞到同一個「檔案 realpath ＋ pointer」＝繞回來了＝錯誤。

`envs` 的 key 不吃指示詞。

**`$fmt`** 的模板寫法沿用 repo 裡本來就有的那套（[data-files-fmt](../wf/workflows/common/data-files-fmt.md)），
這裡只有 `env:` 這一個 namespace，不做 tabledb 那些 `${gitRoot}` 路徑變數：

- 只有 `${…}` 會被代換。單獨的 `$` 與 `$NAME` 都是**字面**，不展開也不用跳脫。
- `${env:NAME}` 讀 **aos-exec 自己的**環境（不是這份 inst.json 的 `envs`，跟 `$env` 同一個
  來源）。不存在＝錯誤；存在但空＝空字串。
- 不是 `env:` 開頭的 `${…}`＝不認得的變數＝錯誤，不猜。
- **展開一次、不再掃結果**：換進來的值裡再出現 `${…}` 就是字面。

`envs` 的清空型式 `{"$opt":"clear","$envs":{…}}` 是**唯一一個**兩個 key 的指示詞物件。
（代價：這一版沒辦法傳一個真的叫 `$opt` 的環境變數。）

## aos-exec 的退出碼

| 退出碼 | 什麼時候 |
|---|---|
| 2 | 用法錯（旗標不認得、沒給 `xxx`、`--timeout-ms` 是負數）、`xxx` 不存在、`--dir-target` 指的檔不存在 |
| 1 | inst.json 讀不到／不是 JSON 物件／格式壞（未知 key、型別錯、`argv` 空、`envs` 的 key 壞、指示詞壞）／`$env`／`${env:…}` 的變數不存在／`$ref` 讀不到、pointer 壞、繞回來了／`exit` 檔的父目錄不存在 |
| 126 | 沒執行權、`cwd` 不是資料夾、重導向的檔開不起來 |
| 127 | 找不到程式 |
| 143 / 137 | `--timeout-ms` 到了：SIGTERM 就死＝143，要 SIGKILL 才死＝137 |
| 其他 | **原樣**是子行程的結束狀態：正常結束＝它的 exit code，被訊號 N 砍＝128+N |

1 與 2 會印一行 `aos-exec: <原因>` 到 **aos-exec 自己的 stderr**（格式壞掉的那行開頭是代號，
像 `UnknownKey:`、`ReferenceCycle:`）。126／127 也印一行。

有寫 `exit` 欄位的話，126／127／逾時一樣算「跑完了一次」，那個數字照樣寫進 exit 檔。
只有退出碼 1 和 2 是 **aos-exec 自己**失敗，不寫 exit 檔。

**逾時怎麼砍**：先對**整個 process group** 送 SIGTERM，給 2 秒，直接子行程還活著就 SIGKILL
整個 group（收完屍再補一發，因為直接子行程死了不代表群組空了）。

## aos-run：一直跑同一個目標

```sh
aos-run xxx [--dir-target REL] [--timeout-ms N] [--interval-ms N] [--from-start]
            [--max-runs N] [--time-limit-ms N] [--stop-exit CODE]...
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

### 什麼時候停

四個條件，任一成立就停，退出碼都是 **0**：

| 原因 | 什麼時候 |
|---|---|
| `max_runs` | 跑滿 `--max-runs N` 次 |
| `time_limit` | 撞到 `--time-limit-ms`。**硬時限**：正在睡→醒來就退；正在跑→**那次被砍** |
| `stop_exit` | 某一次的退出碼在 `--stop-exit` 那組裡面 |
| `signal` | 收到 SIGTERM／SIGINT |

**硬時限怎麼砍正在跑的那次**：不另開執行緒，而是每次呼叫 `run_target()` 時把 `timeout_ms`
換成 `min(原本的或無限, 剩下的毫秒)`，交給 aos-exec 本來就有的那套砍法（SIGTERM 整個
process group、2 秒、SIGKILL），所以被砍那次印出來的碼是 143 或 137。

**訊號**：第一次 SIGTERM／SIGINT ＝ 讓正在跑的那次**跑完**再退；第二次**同一個**訊號 ＝
直接 SIGKILL 掉正在跑的那個 process group 再退。睡覺是小步睡的（0.05 秒一步），所以
`--interval-ms 5000` 睡到一半也叫得醒，不會不理你五秒。

**`run_target()` 回 1（inst.json 壞掉）不算停止條件**，照 interval 一直試——壞了也活著，
跟 proto4-2 的 cpu 一樣。要它停就自己寫 `--stop-exit 1`。

### 印什麼、回什麼

不寫檔。每跑完一次，在 **aos-run 自己的 stderr** 印一行（秒數一位小數）：

```
aos-run: #1 exit=0 0.3s
aos-run: #2 exit=1 0.0s
aos-run: stop max_runs
```

aos-run 自己的退出碼只有兩種：**2**＝用法錯（旗標不認得、沒給 `xxx`、`xxx` 不存在、
時間／次數旗標是負數）；**0**＝四種停止條件的任何一種。子行程的退出碼只出現在那些
`#n exit=` 行裡，不會變成 aos-run 的退出碼。

`xxx` 只在起跑前檢查一次；跑到一半被砍掉，之後每次就是 `run_target()` 回 2 的那行，
迴圈照樣繼續（跟回 1 一樣不算停止條件）。

當成函式用（daemon 之後就是這樣接）：

```python
import aos_run
code, reason = aos_run.run_loop("/path/to/folder", interval_ms=5000, max_runs=10,
                                from_start=True, stop_exits=[1])
```

## 檔案

- `aos-exec`：命令列入口，可執行，薄薄一層。
- `aos_exec.py`：認目標是哪一種、組出要跑的東西、跑一次、砍逾時、寫 exit 檔。核心是
  `run_target(xxx, dir_target=…, timeout_ms=…) -> int`。
- `aos_inst.py`：inst.json 的讀、驗、解指示詞（格式那一層），從 proto4-2 抄來改的。
- `aos-run`：aos-run 的命令列入口，可執行，一樣薄薄一層。
- `aos_run.py`：迴圈本體——什麼時候跑下一次、什麼時候停、跑完印一行。核心是
  `run_loop(xxx, *, dir_target=…, timeout_ms=…, interval_ms=…, from_start=…, max_runs=…,
  time_limit_ms=…, stop_exits=…, log=…) -> (退出碼, 停止原因)`，之後 daemon 直接 import。
- `test/`：`python3 -m unittest discover -s test`（125 條）。

## 沒做什麼

**最簡原型，邊緣狀況一律沒做。** 列出來免得以為它會：

- **沒有覆蓋串流的旗標**。「用 aos-exec 自己的 stdin／stdout／stderr／exit 蓋掉 inst.json
  裡寫的」是後續要做的方便功能，這次不做。
- **不注入 `AOS_*` 環境變數**（`AOS_DIR`／`AOS_TICK` 都沒有），aos-exec 與 aos-run 都一樣
  （§8：proc 不需要知道自己被誰、以什麼節奏跑）。要不要有之後撞到再說。
- **不寫任何紀錄檔**。不抓子行程的輸出、不寫 `last.json`／`runs.jsonl`，`exit` 欄位是唯一
  會被寫出去的東西。想看輸出就自己寫 `stdout`。aos-run 的每次一行只印在**它自己的 stderr**，
  落不落檔等整合進 daemon 再說。
- **整合進 aos-daemon 是之後的事**。aos-run 只是概念驗證：proto4-2 的 `aos_cpu.py`「跑一次」
  那段要換成這裡的東西、`last.json`／`runs.jsonl`／`cpu.json` 歸誰寫，都還沒動。
- aos-run **沒有對齊格子**：`--from-start` 是「上次起點＋interval」，不是「起跑＋n×interval」，
  長跑會慢慢往後漂。
- aos-run **不重讀自己的旗標**、不吃設定檔、沒有健康檢查、沒有退避（壞掉就是照原速一直試）。
- `exit` 檔的父目錄不存在就直接失敗（退出碼 1），**不幫忙 mkdir**，那個指令也不會被跑。
- `$ref` 沒有範圍限制（能不能指到 cwd 外＝行程權限說了算），也沒有深度上限。
- `$fmt` 只有 `env:` 一個 namespace，沒有路徑變數、沒有預設值語法、沒有跳脫。
- 沒有並行（凍結版的 `parallel`）、沒有批次、沒有重試、沒有退避。
- 不檢查 inst.json 的權限。一份 inst.json 就是可執行的權柄：它可以指名任意程式、引數、
  輸入輸出檔、工作目錄與環境變數值，全都用你的憑證跑。能改它的人就等於能用你的身分執行
  任意程式碼。
