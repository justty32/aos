# proto5/lib — 六支 Python 模組

← [proto5 README](../README.md)｜規範：[spec/directives.md](../spec/directives.md)、
[spec/inst-posix.md](../spec/inst-posix.md)、[spec/exec.md](../spec/exec.md)、
[spec/agent.md](../spec/agent.md)、[spec/aos-llm-ask.md](../spec/aos-llm-ask.md)、[spec/aos-agent.md](../spec/aos-agent.md)

Python 3.12、只用標準庫。六個檔，一層疊一層、下層不知道上層（inst／exec 一條線，agent_info／llm_ask
另一條線，兩條線都踩在 aos_directives 上，最後由 aos_agent 接起來）：

| 檔 | 職責 | 規範 |
|---|---|---|
| [`aos_directives.py`](aos_directives.py) | 指示詞機制的純函式庫：一個值是不是指示詞、怎麼解成別的值。**不知道 inst.json** | [directives.md](../spec/directives.md) |
| [`aos_inst.py`](aos_inst.py) | inst.json（posix v1）的讀、驗、解：`_metainfo`、七個欄位、各位置的 `$opt` 選項表，指示詞全交給上面那個。回一個執行者能直接用的 dict | [inst-posix.md](../spec/inst-posix.md) 第 1～5 節 |
| [`aos_exec.py`](aos_exec.py) | 執行者：`run_target()` 把一個目標跑一次、回 `(code, kind)`，`main()` 是命令列；入口是 [`../cli/aos-exec`](../cli/aos-exec) | [inst-posix.md](../spec/inst-posix.md) 第 6 節（行為）、[exec.md](../spec/exec.md)（命令列） |
| [`aos_agent_info.py`](aos_agent_info.py) | agent 資料夾的讀、驗：`info.json` 每格解指示詞、人格／記憶／工具檔原樣讀、工具表合併與去 `_` key、`engine` 補預設。只讀不寫，**不碰 `state.json`** | [agent.md](../spec/agent.md) §1～§3、§5（資料夾本身）＋ [aos-llm-ask.md](../spec/aos-llm-ask.md) §2（四格與指到的檔） |
| [`aos_llm_ask.py`](aos_llm_ask.py) | 把一個 agent 資料夾問模型一次：`build_request()` 組 chat/completions 的 body、`call()`／`ask()` 用 `urllib` 打出去回 `choices[0].message`，`main()` 是命令列；入口是 [`../cli/aos-llm-ask`](../cli/aos-llm-ask) | [aos-llm-ask.md](../spec/aos-llm-ask.md) |
| [`aos_agent.py`](aos_agent.py) | `step()` 先判 waits，再走 idle／think／act 一格；記憶、input 消化、state 原子寫回與自癒；入口 [`../cli/aos-agent`](../cli/aos-agent) | [aos-agent.md](../spec/aos-agent.md)、[agent.md](../spec/agent.md) §4 |

```sh
cd proto5/lib && python3 -m unittest discover -s test      # 571 條全綠（directives 101、inst 139、exec 89、agent_info 88、llm_ask 53、agent 101）
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
                                 on_spawn=None, stderr=None, args=None)
```

- `kind`：`"child"`＝子程式真的跑完了一次（它的碼／128+N／126／127／143／137，有 `exit` 就寫）、
  `"aos"`＝aos-exec 自己失敗那次沒跑（code 1，命令列換成 125，不寫 exit）、`"usage"`＝用法錯（2）。
- 三種目標（普通檔案／`.json`／資料夾）、旗標、退出碼與 stderr 印什麼，見 [exec.md](../spec/exec.md)。
- 行為：驗完才跑；`mkdir` 在 chdir／開檔前 `makedirs`；`append` 用 `ab`；`inherit` 傳 `None` 給
  `Popen`；`merge` 傳 `subprocess.STDOUT`（跟著 stdout 的 append／inherit）；`clear` 從空環境開始
  否則複製 `os.environ` 再疊 `envs`；`argv[0]` 走疊加後的 PATH；`start_new_session=True`；逾時
  對整個 group SIGTERM → 2 秒 → SIGKILL；exit 檔十進位＋換行、fsync 檔與父目錄。
- `on_spawn(popen)`／`on_spawn(None)`：子行程開起來／收完屍各叫一次（aos-run 用）。

`run_inst(inst, stdin_text, timeout_ms=0) -> (code, kind, stdout_text)`：吃 `load_obj()` 解好的 dict，
用 UTF-8 把文字送入 stdin，stdout 全收回（壞位元組以替代字元表示）。stdin／stdout 由 API 接管，
stderr／exit／cwd／envs 照 inst；stderr 沒寫就是 /dev/null、`merge` 則併進回傳的 stdout。
kind 是 child／aos，錯誤跟 `run_target()` 一樣印 stderr。兩個入口共用前置檢查、mkdir、
啟動、126／127、exit 檔與逾時砍 group；管線用 `communicate()`，同時收送避免大輸出卡住。

## aos_agent_info — agent 資料夾的讀、驗

`aos_agent_info.py` 是 [agent.md](../spec/agent.md) §1～§3、§5（資料夾本身：`_metainfo`、指示詞解不解、共用代號）＋
[aos-llm-ask.md](../spec/aos-llm-ask.md) §2（`system`／`history`／`tools`／`engine` 四格與它們指到的檔）的實作：只讀、只驗、不寫任何檔，
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
history        記憶（陣列；檔不存在＝[]），每則照 aos-llm-ask.md §2.3 驗過、原樣   history_path  絕對路徑
tools          送模型用的工具表：所有檔接成一個、每個元素去掉所有 `_` 開頭的 key
tools_raw      原始工具表：同順序、含 `_meta`（跑工具時用）      tool_paths    絕對路徑、照 info.json 順序
engine         {"endpoint", "model", "params", "api_key", "timeout_ms"}（api_key 沒寫＝None、timeout_ms 沒寫＝120000）
```

- 兩種讀法（agent.md §2）：**`info.json` 每一格都解指示詞**（含 `_metainfo`、`engine`——這點跟 inst
  不同），中心路徑＝agent 資料夾、位置＝實體路徑（`/tools/0`…）、容器（`tools`、`engine`、`engine.params`
  整棵）用 `resolve_located` 走進去、每個頂層欄位各自從空的循環鏈開始；**`system`／`history`／`tools`
  指到的檔原樣讀、不解**。agent.md 沒給任何 `$opt` 選項表，所以哪一格放了 `$opt` 都是 `UnknownOption`。
- 錯誤是 `AgentError(code, msg)`，`str(e)` 是「代號: 白話」，代號照 agent.md §5＋aos-llm-ask.md §2（`NotAnAgent`、`ReadFailed`、
  `JsonSyntax`、`NotAnObject`、`NotAnArray`、`MetainfoInvalid`、`UnsupportedVersion`、`FieldTypeMismatch`、
  `MessageInvalid`、`ToolInvalid`、`EngineInvalid`）；`DirectiveError` 在 `load()` 裡包成同形狀的 `AgentError`。
- 工具元素只驗 `type`／`function`／`function.name`／`_meta` 是物件、`_meta` 沒寫 `stdin`／`stdout`、合併後不同名；
  `_meta` 是不是合法 inst 是**跑的時候**由 aos_inst 解（那時才解它裡面的指示詞）。
- `strip_private(tool)`：一個工具元素去掉頂層所有 `_` 開頭 key 的樣子（`tools` 就是每個元素過一次它）。

## aos_llm_ask — 把一個 agent 資料夾問模型一次

`aos_llm_ask.py` 是 [aos-llm-ask.md](../spec/aos-llm-ask.md) 的實作＋命令列（[`../cli/aos-llm-ask`](../cli/aos-llm-ask)）。
讀驗交給 aos_agent_info，這個檔只做「組請求、打出去、挖 message」。aos-agent 的 `think` 格直接 import
這裡的函式，不開子進程。

```python
import aos_llm_ask
body    = aos_llm_ask.build_request("agent-bob")     # 讀驗＋組 body，不碰網路；讀驗錯誤丟 AgentError
message = aos_llm_ask.ask("agent-bob")               # build_request 再打引擎，回 choices[0].message；引擎失敗丟 EngineFailed
message = aos_llm_ask.call(info["engine"], body)     # 只打不讀（aos-agent 已經有 info 時用）
```

- body：`model` ＝ `engine.model`；`messages` ＝（`system` 非空才加一則 system）＋ 記憶原樣；`tools` ＝ 合併後去
  `_` key 的工具表，**空的就不送這個欄位**；`engine.params` 原樣併到同一層，撞到 `model`／`messages`／`tools`／
  `stream` 就忽略；`stream` 永遠不送。
- HTTP：`urllib.request` POST 到 `endpoint.rstrip("/") + "/chat/completions"`，`Content-Type: application/json`；
  `api_key` 有值才送 `Authorization: Bearer`；等 `timeout_ms`。連不上、非 2xx、逾時、回來不是 JSON、回應讀到一半
  斷掉、沒有 `choices[0].message` → `EngineFailed(msg)`（**不是** `AgentError`：一個是設定壞、一個是這次連線出包）。
- 命令列 `aos-llm-ask [dir] [--dry-run]`：stdout **只印一行** JSON（`--dry-run` 印 body，不然印 message；
  `ensure_ascii=False`、緊湊分隔）；退出碼 0／1（讀驗錯，stderr `aos-llm-ask: <代號>: <白話>`）／2（用法錯、
  `dir` 不是資料夾）／3（引擎失敗，stderr `aos-llm-ask: engine: <白話>`）。不寫任何檔、不碰 `state.json`、不跑
  工具、不重試。

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
- think：問一次模型，message 原樣接進記憶（content 為 null 且沒 tool_calls 時補空字串）；
  非空 tool_calls 陣列去 act，否則回 idle。引擎失敗 stderr 一行 `aos-agent: engine: …`、
  記憶和 state 值不動、退 0；已完成的 waits 劃除仍保留。尾巴已是帶 tool_calls 的 assistant，
  直接轉 act，不再問模型。
- act：依序用 `_meta` 的 `load_obj()`／`run_inst()` 跑所有 call，arguments 字串原樣進 stdin，
  非字串用 `json.dumps`。每個結果接一則 tool（保留 tool_call_id）；找不到、非零退出、inst 解錯或
  跑不起來都變成文字結果，其他工具照跑。尾巴沒有待跑的 assistant，就直接回 think。
- 記憶整份 `ensure_ascii=False, indent=2` 加換行；state 只改原始 JSON 的 state／waits。
  寫 JSON 先 `.tmp` 再 `os.replace`，缺父目錄會建立；走格順序＝記憶 → input rename → state。
  **沒有鎖，也沒有跨檔交易**；同一個 agent 不要同時跑兩份。
- 命令列 `aos-agent [dir]`（省略＝`.`）：0／101／1（讀驗錯）／2（用法錯）；沒有其他旗標。
  檔案操作中途失敗另印 `aos-agent: io: …`、退 1，可能已有部分寫入；不把它冒充讀驗錯。

未定細節的實作選擇：`since` 讀字面數字（bool 不算、指示詞物件不算數字）；空路徑陣列
all 為真、any 為假。既有訊息驗法只驗 tool_calls 是陣列，殘缺 call 當找不到工具；id 缺了用空字串，
非字串轉成字串，避免新寫的 tool 訊息下次讀不回來。

## 測試

```sh
cd proto5/lib && python3 -m unittest discover -s test      # 571 條
```

| 檔 | 條數 | 開不開進程 |
|---|---|---|
| `test/test_directives.py` | 101 | 不開：純記憶體＋暫存資料夾 |
| `test/test_inst.py` | 139 | 不開：直接叫 `aos_inst.load()`，驗回傳的 dict 與錯誤代號（案例從 proto4-3 的 test_fields／opts／ref／fmt／env／reject 搬來） |
| `test/test_exec.py` | 89 | 開：透過 `cli/aos-exec` 真的跑（三種目標、`--stderr`、選項落地、環境、退出碼、逾時 143／137）＋ `run_target()` API |
| `test/test_agent_info.py` | 88 | 不開：直接叫 `aos_agent_info.load()`——預設值與回傳形狀、`_metainfo`／`NotAnAgent`、info.json 的指示詞（每格都解、位置、循環、`$opt` 不吃、指到的檔不解）、人格檔、記憶檔每則怎麼驗、工具檔（合併、去 `_` key、`ToolInvalid` 各種）、engine |
| `test/test_llm_ask.py` | 53 | 兩種都有：`build_request()` 直接叫；`call()`／`ask()` 打**執行緒裡一個假的 chat/completions**（`http.server`：回正常、500、壞 JSON、沒 choices、回到一半斷線、故意慢讓逾時觸發），不打真模型；命令列那群開 `cli/aos-llm-ask` 子進程驗退出碼 0／1／2／3 與 stdout 只有一行。「連不上」用 `nope.invalid` 這個保證解不開的主機名（這台 WSL 連 localhost 死 port 會等到逾時而不是被拒） |
| `test/test_agent.py` | 101 | 新入口 load_obj／run_inst、waits 五選項與指示詞、idle／think／act、自癒、寫檔順序、命令列；真的 sh／Python 工具＋沿用 `test_llm_ask.FakeLLM` |
| `test/_util.py` | — | 共用：暫存資料夾、寫 inst、`InstCase`（直接 load）、`ExecCase`（開進程）、`AgentCase`（寫一個 agent 資料夾、直接 load、開 `aos-llm-ask` 進程） |
