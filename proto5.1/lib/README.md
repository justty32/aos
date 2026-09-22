# proto5.1/lib — 十二支 Python 模組

← [proto5.1 README](../README.md)｜規範：[spec/directives.md](../spec/directives.md)、
[spec/inst-posix.md](../spec/inst-posix.md)、[spec/exec.md](../spec/exec.md)、
[spec/agent.md](../spec/agent.md)、[spec/aos-llm-ask.md](../spec/aos-llm-ask.md)、[spec/aos-agent.md](../spec/aos-agent.md)

Python 3.12、只用標準庫。十二個檔，一層疊一層、下層不知道上層（inst／exec 一條線，agent_info／llm_ask
另一條線，兩條線都踩在 aos_directives 上，aos_cpu 提供共用佇列，llm_cpu／tool_cpu 各自接 llm_ask／exec，最後由 aos_agent 接起來；run 疊 exec、daemon 管 run、kernel 使用 daemon）：

| 檔 | 職責 | 規範 |
|---|---|---|
| [`aos_directives.py`](aos_directives.py) | 指示詞機制的純函式庫：一個值是不是指示詞、怎麼解成別的值。**不知道 inst.json** | [directives.md](../spec/directives.md) |
| [`aos_inst.py`](aos_inst.py) | inst.json（posix v1）的讀、驗、解：`_metainfo`、七個欄位、各位置的 `$opt` 選項表，指示詞全交給上面那個。回一個執行者能直接用的 dict | [inst-posix.md](../spec/inst-posix.md) 第 1～5 節 |
| [`aos_exec.py`](aos_exec.py) | 執行者：`run_target()` 把一個目標跑一次、回 `(code, kind)`，`main()` 是命令列；入口是 [`../cli/aos-exec`](../cli/aos-exec) | [inst-posix.md](../spec/inst-posix.md) 第 6 節（行為）、[exec.md](../spec/exec.md)（命令列） |
| [`aos_agent_info.py`](aos_agent_info.py) | agent 資料夾的讀、驗：`info.json` 每格解指示詞、人格／記憶／工具檔原樣讀、工具表合併與去 `_` key、`engine` 讀模型代號與 CPU 路徑。只讀不寫，**不碰 `state.json`** | [agent.md](../spec/agent.md)（資料夾、設定與指到的檔） |
| [`aos_llm_ask.py`](aos_llm_ask.py) | `build_request()` 組不含 model 的 body；`call()` 留給 LLM CPU 用 `urllib` 取回 `choices[0].message`，`main()` 是命令列；入口是 [`../cli/aos-llm-ask`](../cli/aos-llm-ask) | [aos-llm-ask.md](../spec/aos-llm-ask.md) |
| [`aos_cpu.py`](aos_cpu.py) | 共用檔案佇列：`load()` 驗呼叫者指定的 CPU 身分、`submit()` 交件、`tick()` 認領／收屍／原子發布；短鎖只包檔案轉移、壞單隔離到 bad | [cpu-queue.md](../spec/cpu-queue.md)、[aos-cpu.md](../spec/aos-cpu.md) |
| [`aos_llm_cpu.py`](aos_llm_cpu.py) | LLM 薄層：解 models 表、以代號查連線設定並驗 body，以 `aos_llm_ask.call()` 執行；入口 [`../cli/aos-llm-cpu`](../cli/aos-llm-cpu) | [llm-cpu.md](../spec/llm-cpu.md)、[aos-llm-cpu.md](../spec/aos-llm-cpu.md) |
| [`aos_tool_cpu.py`](aos_tool_cpu.py) | 工具薄層：驗已解好的 inst，以 `aos_exec.run_inst()` 執行；入口 [`../cli/aos-tool-cpu`](../cli/aos-tool-cpu) | [tool-cpu.md](../spec/tool-cpu.md)、[aos-tool-cpu.md](../spec/aos-tool-cpu.md) |
| [`aos_agent.py`](aos_agent.py) | `step()` 先判 waits，再走 idle／think／act 一格；記憶、input 消化、state 原子寫回與自癒；think 一律交 CPU，act 收回混合工具批次、工具限時、引擎連敗暫停；入口 [`../cli/aos-agent`](../cli/aos-agent) | [aos-agent.md](../spec/aos-agent.md)、[agent.md](../spec/agent.md) §4 |
| [`aos_run.py`](aos_run.py) | 反覆呼叫 run_target、完成後間隔、run.json／ctl.json、可選 kill-tree | [aos-run.md](../spec/aos-run.md) |
| [`aos_daemon.py`](aos_daemon.py) | 三 op 檔案請求、管理 runner、原子 state、done 先寫與 ctl | [daemon-home.md](../spec/daemon-home.md)、[aos-daemon.md](../spec/aos-daemon.md) |
| [`aos_kernel.py`](aos_kernel.py) | kernel 家與 inst 讀驗、FIFO／quantum／100／101／bad_after 排程、rm syscall與防重疊 | [kernel-home.md](../spec/kernel-home.md)、[aos-kernel.md](../spec/aos-kernel.md) |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=proto5.1/lib python3 -m unittest discover -s proto5.1/lib/test      # 802 條
```

## aos_directives — 指示詞機制的純函式庫

`aos_directives.py` 是 [指示詞規範](../spec/directives.md) 的獨立實作：沒有命令列。它**不知道
inst.json**——只管「一個值是不是指示詞、怎麼解成別的值」；哪些位置要解、解完該是什麼型別、
`$opt` 認得哪些選項，都是宿主（用它的那份文件規範）的事。

```
$opt  >  $ref  >  $fmt  >  $env      同一個物件有多個指示詞 key 只跑最前面的，其他 key 一律忽略
```

### API

所有錯誤都是 `DirectiveError`：`.code` 是規範的錯誤代號（`ReferenceCycle`…）、`.msg` 是白話，
`str(e)` 是「代號: 白話」。

```python
from aos_directives import *
```

#### `Document(path, root)`／`load_document(path)`

一份 JSON 文件：`path`（realpath；純記憶體的文件是 `None`）＋ `root`（解析好的 JSON，還沒解指示詞）。

```python
doc = load_document("inst.json")          # 讀不到 → ReferenceReadFailed；壞 JSON → ReferenceJsonInvalid
doc = Document(None, {"argv": ["sh"]})    # 純記憶體
```

#### `Context(doc, base_dir=None, env=None)`

解析時一路帶著的東西：目前文件、中心路徑（`$ref` 的相對檔名從哪裡找；沒給＝文件所在資料夾，純記憶體
的文件＝現在的工作目錄）、`$env` 查的表（沒給＝`os.environ`）。`child()` 派生一個換了文件／中心路徑的。

```python
ctx = Context(doc, base_dir=cwd, env=os.environ)
ctx2 = ctx.child(base_dir="/somewhere/else")
```

#### `resolve(value, ctx, position) -> Any`

把 `position` 這一格的值解到底。`position` 是 token 串（`["envs", "PATH"]`＝`/envs/PATH`，根＝`[]`），
**必須是這個值在原始 JSON 裡的實體路徑**——相對 `$at`、循環偵測都靠它。

- 不是指示詞的值（字串、陣列、沒有 `$` key 的物件…）原樣回，**不走進容器**——要不要解容器裡的每一格，
  宿主自己決定、自己算位置。
- 有 `$opt` 的物件**原樣回**，交給 `split_option`。
- `$ref`／`$fmt`／`$env` 解開；解出來還是指示詞就繼續（巢狀）。
- 有 `$` key 但四個都不是 → `UnknownDirective`。

```python
resolve({"$env": "HOME"}, ctx, ["cwd"])                                   # "/home/me"
resolve({"$fmt": {"$val": "${p}:/opt/bin", "p": {"$env": "PATH"}}}, ctx, ["envs", "PATH"])
resolve({"$ref": "vals.json", "$at": "/msg"}, ctx, ["envs", "M"])          # vals.json 的 /msg
resolve({"$ref": "vals.json#/msg"}, ctx, ["envs", "M"])                    # 同上（# 後面＝位置；$at 有寫就 $at 贏）
resolve({"$ref": "", "$at": "../GREET"}, ctx, ["envs", "G2"])              # 目前文件的 /envs/GREET
resolve({"$ref": "#../GREET"}, ctx, ["envs", "G2"])                        # 同上
```

`$fmt` 的變數 `p` 位置是 `<這格>/$fmt/p`、模板是 `<這格>/$fmt/$val`，所以變數之間能用
`{"$ref": "", "$at": "../a"}` 互指。指別的檔時相對位置從那份檔的根算（`x.json#./a`＝`/a`）。

#### `resolve_located(value, ctx, position) -> Located(value, ctx, position)`

跟 `resolve` 一樣，但連「值現在在哪」一起回：經過 `$ref` 之後文件與位置會換成被引用的那邊。
**要往解出來的容器裡繼續解，一定要用這個**，不然裡面的 `$ref:""`／相對 `$at`／循環偵測會比錯文件。

```python
loc = resolve_located({"$ref": "envs.json"}, ctx, ["envs"])     # loc.value 是 envs.json 整份
for k, v in loc.value.items():
    loc.value[k] = resolve(v, loc.ctx, loc.position + [k])       # 位置＝envs.json 的 /k
```

#### `is_directive(value)`／`is_option_object(value)`

有 `$` 開頭 key 的 dict 就是指示詞物件（含選項物件）；有 `$opt` key 的就是選項物件。

#### `split_option(value) -> Option(is_option, opt, val, has_val)`

把選項物件拆開，**零驗證**：`$opt` 的值任何 JSON 都可以，機制不解讀、不驗、不解指示詞，原樣交出；
`$val` 也原樣（宿主要的話再 `resolve`，位置＝`<這格>/$val`）；其他 key 一律忽略。
不是選項物件 → `Option(False, None, value, True)`（值就是原本那個）。

```python
split_option({"$opt": ["append", "mkdir"], "$val": "out.txt"})   # Option(True, ["append","mkdir"], "out.txt", True)
split_option({"$opt": {"anything": 1}})                          # Option(True, {"anything": 1}, None, False)
split_option("out.txt")                                          # Option(False, None, "out.txt", True)
```

#### `option_names(opt, has_val, position, table) -> frozenset`

給「`$opt` 是選項名字串或非空名字陣列」慣例的宿主（例如 inst）用的驗證：`table` 是這個位置認得的選項
`{名字: {"val": "required"|"forbidden"|"optional", "alone": bool}}`（沒寫＝`optional`／`False`），
空表＝這個位置不吃選項。錯誤：不是字串／非空字串陣列 → `DirectiveValueTypeMismatch`；重複、不認得、
空表 → `UnknownOption`；`val` 規則不合、`alone` 的跟別的一起 → `OptionConflict`。

```python
STDOUT = {"append": {"val": "required"}, "mkdir": {"val": "required"},
          "inherit": {"val": "forbidden", "alone": True}}
option_names(["append", "mkdir"], True, ["stdout"], STDOUT)   # frozenset({"append", "mkdir"})
option_names("inherit", True, ["stdout"], STDOUT)             # OptionConflict：inherit 不能帶 $val
```

#### `parse_options(value, position, table) -> (names, val, has_val)`

上面兩個合在一起：不是選項物件 → `(frozenset(), value, True)`。

```python
names, val, has_val = parse_options({"$opt": "append", "$val": {"$env": "OUT"}}, ["stdout"], STDOUT)
```

### 宿主怎麼用

像 inst 這種宿主，每個要解的欄位照這個順序：先 `resolve_located` 把這格解到底（`$opt` 物件會原樣停下來），
再用 `parse_options` 拆選項並照這個位置的表驗，`$val` 再 `resolve` 一次（位置加 `$val`），最後才驗型別
（`FieldTypeMismatch` 之類是宿主自己的代號）。中心路徑是宿主給的（inst＝解出來的 `cwd`），跟指示詞所在
的檔案無關。

```python
ctx = Context(load_document("inst.json"), base_dir=cwd)
loc = resolve_located(raw["stdout"], ctx, ["stdout"])
names, val, has_val = parse_options(loc.value, loc.position, STDOUT)
if has_val:
    val = resolve(val, loc.ctx, loc.position + ["$val"])
if not isinstance(val, str):
    raise MyError("FieldTypeMismatch", "stdout 要是字串")
stdout = {"path": val, "append": "append" in names, "mkdir": "mkdir" in names, "inherit": "inherit" in names}
```

容器（`argv` 的每個元素、`envs` 的每個值）由宿主自己走：先把容器那格 `resolve_located`，再對每個元素用
回傳的 `ctx`／`position + [索引或 key]` 逐格解。

## aos_inst — inst.json 的讀、驗、解

`aos_inst.py` 是 [inst-posix.md](../spec/inst-posix.md) 第 1～5 節的實作（讀、驗、解；第 6 節的
「怎麼跑」在 aos_exec）。指示詞一律用上面的 aos_directives，這個檔只做 inst 這個宿主自己的事。

```python
import aos_inst
inst = aos_inst.load("job/.aos/inst.json", base="job")      # env=None → $env 查 os.environ
```

`load(path, base, env=None)`：`base` 是這份 inst 的家（給資料夾就是那個資料夾，給 `.json` 就是它
所在的資料夾）。解的順序固定：頂層整份 → `cwd`（以 base 為中心）→ `argv` → `envs` → 四個路徑欄
（以解出來的 `cwd` 為中心）。回一個 dict，路徑都是絕對的、`""`＝沒寫：

```
argv       list                                    非空字串陣列，argv[0] 非空
stdin      {"path", "inherit"}
stdout     {"path", "append", "mkdir", "inherit"}
stderr     {"path", "append", "mkdir", "inherit", "merge"}
exit       {"path", "append", "mkdir"}
cwd        絕對路徑；另有 cwd_mkdir（bool）
envs       dict；另有 envs_clear（bool）
metainfo   {"_type": "posix", "_version": 1}
```

`load_obj(obj, base, env=None)`：inst 已經是 dict（例如工具的 `_meta`）時用這個入口。
用 `Document(None, obj)` 表示純記憶體文件，`$ref:""` 指向 obj 自己；與 `load()` 共用 `_load`，
解析順序、回傳 dict 與錯誤代號相同。`load()` 保留檔案身分，不把檔案當純記憶體文件。

- 錯誤是 `InstError(code, msg)`，`str(e)` 是「代號: 白話」；aos_directives 丟的 `DirectiveError`
  在 `load()` 裡包成同形狀的 `InstError`（代號不變），呼叫者只要接一種。
- `OPTIONS` 是各位置認得的選項表（inst-posix.md 3.3），用 `option_names` 的表格式寫：
  `{"append": {"val": "required"}, "inherit": {"val": "forbidden", "alone": True}, …}`。
  不吃選項的位置（頂層、`argv` 整包與元素、`envs` 的值、`$val` 裡面）放了 `$opt`＝`UnknownOption`（空表）。
- 每個欄位從空的循環鏈開始（directives.md 第 5 節）；走進容器（`argv` 的元素、`envs` 的值）時
  把 `resolve_located` 回來的 ctx／位置帶進去，所以 `$ref:""`／相對 `$at` 在被引用的檔裡也對得上。
- 路徑欄給空字串＝沒寫；`append`／`mkdir` 的 `$val` 是空字串＝`OptionConflict`。

## aos_exec — 執行者

`aos_exec.py` 是 [inst-posix.md 第 6 節](../spec/inst-posix.md) 的實作＋命令列（[exec.md](../spec/exec.md)）。
核心是一個函式，之後的 aos-run 直接 import 它反覆叫：

```python
import aos_exec
code, kind = aos_exec.run_target(xxx, dir_target=".aos/inst.json", timeout_ms=0,
                                 on_spawn=None, stderr=None, args=None, on_target=None)
```

- `kind`：`"child"`＝子程式真的跑完了一次（它的碼／128+N／126／127／143／137，有 `exit` 就寫）、
  `"aos"`＝aos-exec 自己失敗那次沒跑（code 1，命令列換成 125，不寫 exit）、`"usage"`＝用法錯（2）。
- 三種目標（普通檔案／`.json`／資料夾）、旗標、退出碼與 stderr 印什麼，見 [exec.md](../spec/exec.md)。
- 行為：驗完才跑；`mkdir` 在 chdir／開檔前 `makedirs`；`append` 用 `ab`；`inherit` 傳 `None` 給
  `Popen`；`merge` 傳 `subprocess.STDOUT`（跟著 stdout 的 append／inherit）；`clear` 從空環境開始
  否則複製 `os.environ` 再疊 `envs`；`argv[0]` 走疊加後的 PATH；`start_new_session=True`；逾時
  對整個 group SIGTERM → 2 秒 → SIGKILL；exit 檔十進位＋換行、fsync 檔與父目錄。
- `on_spawn(popen)`／`on_spawn(None)`：子行程開起來／收完屍各叫一次（aos-run 用）。
- `on_target(path)`：runner 用來在讀 inst 前公布選定的絕對目標；公布後從同一路徑 load，不再追可被替換的 CPU 槽。

`run_inst(inst, stdin_text, timeout_ms=0) -> InstResult`（三元素 tuple：`code, kind, stdout_text`）：吃 `load_obj()` 解好的 dict，
用 UTF-8 把文字送入 stdin，stdout 全收回（壞位元組以替代字元表示）。stdin／stdout 由 API 接管，
stderr／exit／cwd／envs 照 inst；stderr 沒寫就是 /dev/null、`merge` 則併進回傳的 stdout。
另帶 `.timed_out` 布林旗標，真正撞到 TimeoutExpired 才為真，不靠退出碼猜；三值解包與 tuple 相等比較保持相容。
kind 是 child／aos，錯誤跟 `run_target()` 一樣印 stderr。兩個入口共用前置檢查、mkdir、
啟動、126／127、exit 檔與逾時砍 group；管線用 `communicate()`，同時收送避免大輸出卡住。

## aos_agent_info — agent 資料夾的讀、驗

`aos_agent_info.py` 是 [agent.md](../spec/agent.md) 的資料夾、指示詞、設定與內容讀驗實作：只讀、只驗、不寫任何檔，
也**不碰 `state.json`**（走格子是 aos-agent 的事）。

```python
import aos_agent_info
info = aos_agent_info.load("agent-bob")          # env=None → $env 查 os.environ
```

`load(dir, env=None)` 回一個 dict：

```
dir            agent 資料夾的絕對路徑
metainfo       {"_type": "llm_agent", "_version": 1}
system         system prompt 本文（字串；檔不存在＝""）        system_path   絕對路徑
history        記憶（陣列；檔不存在＝[]），每則照 agent.md §3.2 驗過、原樣   history_path  絕對路徑
tools          送模型用的工具表：所有檔接成一個、每個元素去掉所有 `_` 開頭的 key
tools_raw      原始工具表：同順序、含 `_meta`／可選 `_timeout_ms`／`_run`（跑工具時用）      tool_paths    絕對路徑、照 info.json 順序
tool_cpu       工具 CPU 絕對路徑；沒寫＝None，有 _run:cpu 工具時必填
engine         {"cpu", "model", "params"}（cpu 必填，回絕對路徑；model 是非空代號；params 沒寫＝{}）
```

- 兩種讀法（agent.md §2）：**`info.json` 每一格都解指示詞**（含 `_metainfo`、`engine`——這點跟 inst
  不同），中心路徑＝agent 資料夾、位置＝實體路徑（`/tools/0`…）、容器（`tools`、`engine`、`engine.params`
  整棵）用 `resolve_located` 走進去、每個頂層欄位各自從空的循環鏈開始；**`system`／`history`／`tools`
  指到的檔原樣讀、不解**。agent.md 沒給任何 `$opt` 選項表，所以哪一格放了 `$opt` 都是 `UnknownOption`。
- 錯誤是 `AgentError(code, msg)`，`str(e)` 是「代號: 白話」，代號照 agent.md（`NotAnAgent`、`ReadFailed`、
  `JsonSyntax`、`NotAnObject`、`NotAnArray`、`MetainfoInvalid`、`UnsupportedVersion`、`FieldTypeMismatch`、
  `MessageInvalid`、`ToolInvalid`、`EngineInvalid`）；`DirectiveError` 在 `load()` 裡包成同形狀的 `AgentError`。
- 工具元素只驗 `type`／`function`／`function.name`／`_meta` 是物件、`_meta` 沒寫 `stdin`／`stdout`、合併後不同名、`_timeout_ms` 若有必須是正整數、`_run` 只認字面 sync／cpu；
  `_meta` 是不是合法 inst 是**跑的時候**由 aos_inst 解（那時才解它裡面的指示詞）。
- `strip_private(tool)`：一個工具元素去掉頂層所有 `_` 開頭 key 的樣子（`tools` 就是每個元素過一次它）。

## aos_llm_ask — 組 body 與 CPU 用的 HTTP 函式

規範：[aos-llm-ask.md](../spec/aos-llm-ask.md)。`build_request(dir_or_info, env=None)` 把 system、history、tools 與
engine.params 組成 body，不寫 model；真實模型名由 LLM CPU 填入。model／messages／tools／stream／cpu
是保留欄位，params 不能覆蓋；空 tools 不送。

`call(engine, body)` 是 CPU 用的 HTTP 函式，engine 來自 CPU 的 models 表；使用 urllib POST 到
endpoint 加 `/chat/completions`，有 api_key 才帶 Bearer，timeout_ms 是 socket 阻塞期限。
回 `choices[0].message`，連線／HTTP／回應失敗丟 `EngineFailed`，其中 code 區分 Timeout 與 EngineFailed。這個函式不讀 agent 家。

`aos-llm-ask [dir]` 只印一行 body；退出碼 0／1（讀驗）／2（用法）。
agent 的送件與收回由 `aos_agent.step()` 處理，沒有同步問模型的入口。

## aos_cpu — 共用檔案佇列

格式：[cpu-queue.md](../spec/cpu-queue.md)；程式：[aos-cpu.md](../spec/aos-cpu.md)。只用一個模組與函式，不建類別階層。

```python
import aos_cpu
info = aos_cpu.load("cpu-A", "tool_cpu")
aos_cpu.submit(info["dir"], "job-1.json", request)  # 回請求絕對路徑；三處重名＝AgentError
code = aos_cpu.tick(info["dir"], execute)
```

- `execute(request)` 回結果 dict；`tick()` 在鎖外執行它、鎖內發布結果。共用層不懂 LLM 或 inst。
- payload 在 execute 裡讀驗，能讀出 result 的壞 payload 回 BadPayload；`timeout_ms(request)` 提供收屍期限，缺省 120000 ms；
  `reap_error` 可指定收屍 msg 文字，code 固定 Reaped。
  `load(dir, cpu_type, env=None)` 驗 CPU 身分；`submit`／`tick` 的呼叫者先做 load。
- `queue_lock(dir)` 建缺少的 requests／running／done／bad 並拿 `.queue.lock` 的 flock；交件查三處同名，並驗 result 父目錄存在。
- running 超過 timeout_ms＋30 秒就收屍，已有結果保留、否則寫 ok:false；掃完後至多認領一份新單。
  認領刷新 mtime，按檔名排序，跨目錄同名跳過；壞 JSON／共同 result 路徑移到 bad、stderr 一行，繼續掃下一單，最後退 1。
- 完成前核對 running inode，收屍後的遲到回覆不覆蓋結果；結果同目錄唯一 .tmp 再 rename，發布後搬 done；結果寫入 OSError 也搬 done 並退 1，不留 running。
  `tick` 回 0（有做事，含只收屍）、101（沒事）或 1（隔離壞檔／結果寫入失敗）；家／佇列操作失敗丟 AgentError。execute 的例外由各 CPU 薄層轉換。

## aos_llm_cpu／aos_tool_cpu — 兩種執行薄層

```python
import aos_llm_cpu, aos_tool_cpu
code = aos_llm_cpu.tick("llm-C")   # load llm_cpu → call(engine, body)
code = aos_tool_cpu.tick("tool-T") # load tool_cpu → run_inst(inst, stdin, timeout_ms)
```

- 兩者 `load(dir, env=None)` 只驗 info；`tick(dir, env=None)` 回 0／101／1；CLI 都是 `[dir]`、預設 `.`，退出碼 0／101／1／2。
- LLM 在 load 時解 models 表的指示詞；請求只帶 model 代號／body／result。CPU 用真名填 body.model，
  失敗一律回 `{ok:false,code,msg}`，代號包括 UnknownModel／Timeout／EngineFailed／BadPayload／Reaped；成功寫 message。
- tool CPU 不讀 agent 家、不解指示詞。已解好 inst／stdin／timeout_ms 的 payload 壞了，只要 result 可用就寫 ok:false；
  inst.stdin／stdout 不交件、不讀驗；正常 run_inst 回 ok:true＋code／kind／timed_out／stdout，子程式非零與逾時仍算已執行。
- `$env` 在 agent 解；envs 未 clear 時，子程式繼承的是 CPU 進程環境。收屍期限是各自 timeout_ms＋30 秒。
- 交件者使用 aos_cpu.submit。沒有背景 worker、重試、優先序、usage、排隊期限或請求對帳。
  固定結果路徑與跨檔中斷限制見 [findings](../notes/findings.md)。

## aos_agent — 先看門，再走一格

規範：[aos-agent.md](../spec/aos-agent.md)、[agent.md §4](../spec/agent.md)。

```python
import aos_agent
code = aos_agent.step("agent-bob", env=None)  # 0＝做了一格，101＝在等；讀驗錯丟 AgentError
```

- 先用 `aos_agent_info.load()` 讀驗，再讀 `state.json`（不存在＝idle、input.json、不用等）。
  state 必須是字面三格之一，waits 接受字面陣列或單條；input、waits 的每條與 `$val` 解指示詞，
  中心＝agent 資料夾，位置沿用原始文件。未知 key 保留，讀驗失敗不寫檔。
- 門：exists／mtime、consume、any／all。資料夾只看當時的 `*.json` 普通檔，按檔名排序；
  mtime 嚴格大於 since，資料夾任一檔達標就算到。consume rename 成 `.done`，覆蓋舊檔；
  資料夾一旦到就 consume 裡面全部 JSON，any 只 consume 達標的路徑。依原始索引劃掉到的條目，
  有剩退 101，空了接著走格。沒寫或本來空 waits，不為了門另外寫 state。
- idle：原樣讀 input（字串／一則訊息／訊息陣列），先全部驗好，才接進記憶、rename 讀過的檔、
  把 state 換 think。沒有訊息＝101，不 consume 空陣列。若其他檔有訊息，同批讀過的空陣列也清掉；
  重複輸入路徑只讀、消化一次。門開了才讀 input，仍在門的 consume 與寫回之前完成讀驗。
- think 交件：結果不存在就驗 CPU 身分（models 留給 CPU 自己解），在共用短鎖內查三處同名，再發布
  requests/<agent 名>-<epoch ns>.json（model 代號＋不含 model 的 body＋result 絕對路徑），最後加字面 ask-result.json 等待。
  結果未到時門退 101；到了同一格讀驗並收回，ok:true 接記憶、ok:false 算引擎失敗，兩種都封存 .done。
  壞結果在門變更前報 1，原檔保留；門未全開不讀結果。
- 引擎失敗共用 errors 計數（非負字面整數）：每次加一、成功清零，第三敗歸零並等 continue.json。
  等待條目是 `{"$opt":"consume","$val":"continue.json"}`，門開時吃掉檔案，下次暫停需要新檔；input 不能解鎖。
  每次 engine stderr 一行，第三次另印 stuck；失敗那格仍退 0。
- 尾巴帶 tool_calls 的 assistant 優先自癒到 act；若成功結果恰好等於尾巴，先封存已接過的結果、清 errors，
  避免工具跑完再次收同一結果；壞結果不阻擋此自癒。無 request id 的跨檔限制見 [findings](../notes/findings.md)。
- act 全同步：依序用 `_meta` 的 `load_obj()`／`run_inst()` 跑所有 call，arguments 字串原樣進 stdin，
  非字串用 `json.dumps`；傳 `_timeout_ms`，預設 60000。`.timed_out` 為真時結果是
  `工具 xxx 逾時（60000 ms）：` 加收到的 stdout（毫秒用實際值），退出碼不拿來猜逾時。每個結果接一則 tool（保留 tool_call_id）；找不到、非零退出、inst 解錯或
  跑不起來都變成文字結果，其他工具照跑。尾巴沒有待跑的 assistant，就直接回 think。
- act 有 `_run:cpu`：先解 inst、交所有 CPU call 到 tool_cpu，結果指向 tool-results/<原 call 索引>.json；sync 留待收回。
  加一條 all waits、留 act 退 0；結果全到且全部驗過才按原順序執行 sync／讀 CPU 結果，整批 tool 訊息接記憶、封存結果、轉 think。
  同批 CPU 工具的訊息照呼叫順序，執行沒有先後保證。以 `code == "Reaped"` 辨認結果不明，給模型固定 JSON 字串
  `{"ok":false,"error":"結果不明：工具可能已經跑了，也可能沒有"}`，不自動重試；已知逾時／非零退出維持各自文字。
  記憶已有完整 tool 批次時，act 重跑只封存殘留結果，不重做工具；不能判斷任意舊結果身分，也沒有跨檔交易。
- 記憶整份 `ensure_ascii=False, indent=2` 加換行；state 只改原始 JSON 的 state／waits／errors。
  寫 JSON 先 `.tmp` 再 `os.replace`，缺父目錄會建立；走格順序＝記憶 → input rename → state。
  **沒有鎖，也沒有跨檔交易**；同一個 agent 不要同時跑兩份。
- 命令列 `aos-agent [dir]`（省略＝`.`）：0／101／1（讀驗錯）／2（用法錯）；沒有其他旗標。
  檔案操作中途失敗另印 `aos-agent: io: …`、退 1，可能已有部分寫入；不把它冒充讀驗錯。

未定細節的實作選擇：`since` 讀字面數字（bool 不算、指示詞物件不算數字）；空路徑陣列
all 為真、any 為假。既有訊息驗法只驗 tool_calls 是陣列，殘缺 call 當找不到工具；id 缺了用空字串，
非字串轉成字串，避免新寫的 tool 訊息下次讀不回來。

## aos_run — 反覆執行

`main(argv=None)` 反覆呼叫 `aos_exec.run_target()`；旗標見 [aos-run](../spec/aos-run.md)，家格式見 [run-home](../spec/run-home.md)。
`--home DIR` 可省，給了才原子寫 run.json、每次執行前讀 ctl.json；hold 固定每 50 ms 再看且 held 只在變化時寫，stop 正常退出。
帶 home 時記住啟動的父 PID，每圈比對，父程序換了就做完本次後停。
保證先寫 busy:true／target:null，再確定絕對目標、寫 target，才讀 inst。完成後 busy:false，更新 runs／last_*（含完成工作的 last_target）。
kind=aos 的 library code 1 在 run.json 與 stop-exit 判斷換成 125。沒有 status-fd 或槽鎖。

預設第一次 TERM／INT 等本次完成，第二次 TERM 直接子程式 group；`--kill-tree` 開啟時第一次就走
`aos_exec.terminate(popen)`。terminate 在 Linux 先從 `/proc` 快照後代 groups，TERM、兩秒後 KILL、收屍。
每次 timeout 仍走 terminate；`run_target`／`run_inst` 的回傳形狀不變，主動停止不冒充 timed_out。

## aos_daemon — 管 runner

`home(path=None)`、`read_state(path=None)` 依明給路徑／AOS_DAEMON_HOME／預設家解析。
`serve(path=None)` 是前景主迴圈，`main`／`ctl_main` 是兩個 CLI。三個檔案 op 與 request API 見
[aos-daemon](../spec/aos-daemon.md)，檔案格式見 [daemon-home](../spec/daemon-home.md)。

每個 runner 有 `runners/<名>/`；daemon entry 的 home 指向它，busy／runs／last_* 直接讀其 run.json。
add 的 kill_tree 預設 false，真才傳 `--kill-tree`。stop 同時 TERM 全部 runner：預設等五秒、再 TERM、
再五秒才 KILL；kill_tree 模式 TERM 後五秒 KILL。remove 等該 runner 收屍，stop 清 state／pidfile 後才回音。
done 先原子發布才刪原單，既有 done 不重做；失敗回音是 `{ok:false,code,msg}`。
啟動缺 info.json 就建 daemon/version1 身分，ctl 先驗身分；`.daemon.lock` 防同家雙開，
啟動再掃舊 runner 快照，pid 還活著就回 AlreadyRunning。state 只在變動時寫；ctl ls 直接讀快照。

## aos_kernel — 排程普通 inst

`load(dir, env=None)` 解 info，`init(dir, ncpu=3)` 建家；add 在來源家完整 load inst，固定路徑後存入 procs。
`boot(dir)` 把 daemon 的絕對家記進 info.json；tick／ls／rm 從此讀這格、不依環境換家。
`tick(dir)` 排程，`status(dir)` 組 ls，`remove(dir, name)` 交 rm syscall。
格式見 [kernel-home](../spec/kernel-home.md)，命令列與排程見 [aos-kernel](../spec/aos-kernel.md)。

procs 保留行程原檔，空轉用固定的 idle.json；cpus/N.json 一律是原子換上的符號連結；換人先換掉舊槽，再讀所有 runner 家的 run.json。
有 busy:true 且 target 是候選行程或 null，該格就不排。runner 保證先宣告 busy 再讀目標，
兩個順序合起來防止舊工作未完成便在另一顆重開。換人不停止 runner，不使用槽鎖或讓位標記。

`.kernel.lock` 只序列化 tick／add。info.kill_tree 傳給 daemon add，預設 false。
state 與 rm syscall 以 name 表示行程名稱，沒有 since／bad_exit。
未指派 procs 每格讀驗，只有尚未固化的內容才寫回；add 已固化的檔不反覆重寫。
queue／waiting 保存排隊與跨換人的行程計數；100／101／quantum／bad_after 沿既有排程。
run.json 是目前工作與最新完成碼的快照，沒有逐次歷史；以 last_target 對應最新完成的工作，busy 時也能收一次新結果；每個可確認的新快照最多增加一次等待／失敗計數。
`KernelError` 與 `DaemonError` 保留具名錯誤；沒有 module，LLM CPU、tool CPU、agent 都是普通行程。

## 測試

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=proto5.1/lib python3 -m unittest discover -s proto5.1/lib/test      # 802 條；從 repo 根執行
```

| 檔 | 條數 | 開不開進程 |
|---|---|---|
| `test/test_directives.py` | 101 | 不開：純記憶體＋暫存資料夾 |
| `test/test_inst.py` | 139 | 不開：直接叫 `aos_inst.load()`，驗回傳的 dict 與錯誤代號（案例從 proto4-3 的 test_fields／opts／ref／fmt／env／reject 搬來） |
| `test/test_exec.py` | 94 | 開：透過 `cli/aos-exec` 真的跑（三種目標、`--stderr`、選項落地、環境、退出碼、逾時 143／137）＋ `run_target()` API |
| `test/test_agent_info.py` | 98 | 不開：直接叫 `aos_agent_info.load()`——預設值與回傳形狀、`_metainfo`／`NotAnAgent`、info.json 的指示詞（每格都解、位置、循環、`$opt` 不吃、指到的檔不解）、人格檔、記憶檔每則怎麼驗、工具檔（合併、去 `_` key、`ToolInvalid` 各種）、engine |
| `test/test_llm_ask.py` | 53 | build_request 與 CLI 只印 body；HTTP 案例搭 CPU 家、交件後 tick，驗成功、HTTP／JSON／連線／timeout 失敗 |
| `test/test_agent.py` | 144 | waits／idle／think／act、混合工具、自癒、兩次 consume 暫停、結果不明不重試；agent 沒 KEY、CPU 自己解 KEY 的 HTTP 往返 |
| `test/test_llm_cpu.py` | 38 | models 指示詞／型別、代號查表與未知代號、覆蓋 body.model、佇列排序／收屍／遲到結果、跨進程認領與 HTTP 並行、BadPayload／Timeout 等失敗代號 |
| `test/test_cpu.py` | 18 | 共用層交件、三處重名、認領、收屍、原子結果 I/O、執行鎖外並行與遲到回覆、壞單隔離後續單、結果發布失敗仍搬 done |
| `test/test_tool_cpu.py` | 18 | 真工具 stdin／stdout、非零／timeout、壞 payload、CPU 環境、固定收屍文字、CLI、跨進程認領 |
| `test/test_run.py` | 30 | run.json 寫入順序、ctl hold／stop、完成後間隔、首次等完成／二次 TERM、kill-tree 關時孫存活／開時死亡、hold 0 ms 不重寫、last_target |
| `test/test_daemon.py` | 35 | runner 家、kill_tree 布林與 CLI、done 先寫、並行 5＋5／5 秒停止、I/O／signal 清理與 home 傳遞、kill -9 後自停與拒重啟、閒置不重寫 |
| `test/test_kernel.py` | 34 | FIFO／完成／等待／跨換人計數；0 interval＋2 秒 X 用 run.json 驗防重疊；固定 idle 身分、未知完成差值、15 ms／0 ms 公平性、busy 對帳、固定 daemon 家與頂層引用、procs 不重寫 |
| `test/_util.py` | — | 共用：暫存資料夾、寫 inst、`InstCase`（直接 load）、`ExecCase`（開進程）、`AgentCase`（寫一個 agent 資料夾、直接 load、開 `aos-llm-ask` 進程） |
