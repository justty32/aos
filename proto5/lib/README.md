# proto5/lib — 三十二支 Python 模組

← [proto5 README](../README.md)｜新架構：[cpu.md](../spec/cpu/README.md)、[daemon.md](../spec/daemon/README.md)、[kernel.md](../spec/kernel/README.md)

Python 3.12 以上、只用標準庫（3.12.13 與 3.14.7 都實跑全綠，見 [notes/2026-09-24-py312-run.md](../notes/2026-09-24-py312-run.md)）。底層 `aos_directives` → `aos_inst` → `aos_exec`；新架構由
`aos_home` 共用檔案範式、`aos_client` 交件，`aos_exec_cpu` 跑一次、`aos_daemon` 管孩子，
`aos_kernel` 用一格接一格的 tick 排程。`aos_run` 與 `aos-daemon-ctl` 已移除。

agent 線已依 2026-09-24 第 2 版規範接上 kernel：`aos-llm call` 問模型一次，
`aos-agent tick／start／stop／init／say／listen／status／pause／continue` 走格、登記排程、看回話與日常操作；模型與工具都交給 exec cpu，舊 llm／tool cpu 已移除。
（09-24 fix-r4）三支指令的家一律 `--target`：`aos_home.resolve_target()` 照「`--target` → 環境變數（`AOS_DAEMON_HOME`／`AOS_KERNEL_HOME`）→ 目前資料夾」找，`target_note()` 產生錯誤行尾巴「用了哪個家、取自哪裡」。

| 檔 | 職責 | 規範／狀態 |
|---|---|---|
| [`aos_directives.py`](aos_directives.py) | 指示詞解析的純函式庫，不知道 inst | [directives.md](../spec/directives/README.md) |
| [`aos_inst.py`](aos_inst.py) | inst.json 的讀、驗、解，回執行用 dict | [inst-posix.md](../spec/inst-posix/README.md) §1～§5 |
| [`aos_exec.py`](aos_exec.py) | 同步 `run_target`／`run_inst`、完整旗標 `run_target_full`、daemon 用 `spawn_target` | [aos-exec.md](../spec/aos-exec/README.md)、[inst-posix.md](../spec/inst-posix/README.md) §6 |
| [`aos_home.py`](aos_home.py) | JSON-RPC 信封、原子放單與狀態、ack／stop、開機對帳；三支指令共用的 `--target` 找家（fix-r4） | [cpu.md](../spec/cpu/README.md) §2、§3、§6 |
| [`aos_client.py`](aos_client.py) | 取名、放單、先查原單再等回音、讀與 ack | [cpu.md](../spec/cpu/README.md) §3、§6.3 |
| [`aos_exec_cpu.py`](aos_exec_cpu.py) | 長命 exec cpu：go／stop、逐件執行、訊號與對帳；入口 `aos-cpu` | [cpu.md](../spec/cpu/README.md) |
| [`aos_daemon.py`](aos_daemon.py) | flock、spawn 登記與 go、非零重拉、kill／stop 階梯；入口 `aos-daemon boot／halt` | [daemon.md](../spec/daemon/README.md) |
| [`aos_kernel.py`](aos_kernel.py) | 入口與匯出層：把下面五支的公開名字（含舊的底線名字）重新匯出；`aos-kernel` 從這裡取 `main` | [kernel.md](../spec/kernel/README.md) |
| [`aos_kernel_info.py`](aos_kernel_info.py) | info 讀驗、`init`、初始帳本 `new_state`、反覆工作判定 `classify`、共用錯誤與放單小工具 | [kernel.md](../spec/kernel/README.md) §1、§4 |
| [`aos_kernel_ledger.py`](aos_kernel_ledger.py) | `KernelLedger`：帳本、syscall（add／rm）、四出貨箱重放、接 tick 鏈與 ack | [kernel.md](../spec/kernel/README.md) §2、§3 |
| [`aos_kernel_engine.py`](aos_kernel_engine.py) | `Kernel`：收回音、補 cpu、分池派工、停機與一格十步 `step`；模組函式 `tick` | [kernel.md](../spec/kernel/README.md) §3 |
| [`aos_kernel_boot.py`](aos_kernel_boot.py) | `boot` 交接換鏈、`status` 偷看、`halt` 等停好（函式名仍是 `stop`） | [kernel.md](../spec/kernel/README.md) §6 |
| [`aos_kernel_cli.py`](aos_kernel_cli.py) | `aos-kernel` 參數解析、add／rm 交件、`ls` 接線與 `main`；（advice-r1）`check --agent` 變用法錯、指到 `aos-agent check` | [kernel.md](../spec/kernel/README.md) §6 |
| [`aos_kernel_ls.py`](aos_kernel_ls.py) | （advice-r1）`ls_data()` 收成穩定的 `aos_kernel_ls` 第 1 版資料（就是 `--json`），`render()` 排成按池分組的對齊表（中文算 2 格、長名砍中間、`-v` 才印路徑）；`stderr_hint()` 給 bad 行程指路 | [kernel/cli-ls.md](../spec/kernel/cli-ls.md) |
| [`aos_kernel_health.py`](aos_kernel_health.py) | `health(home)`：kernel 整體健康一句話（ok／缺目錄／停機中／daemon 沒活／cpu missing／恢復中（fix-r5）／tick 停住／讀不到），不丟例外；`ls` 與 `aos-agent status` 共用。`agent_marks()`／`agents_health()`（fix-r5）給 `ls` 標 agent 的暫停／重試 | [kernel.md](../spec/kernel/README.md) §6 |
| [`aos_kernel_check.py`](aos_kernel_check.py) | `aos-kernel check`：啟動前唯讀檢查 info、K 家必要目錄、daemon、cpu 在不在孩子表（daemon 重開提示 boot）、PATH、池、llm 設定；`--probe`（fix-r5）真的打一次 endpoint（`probe_endpoint()`），結尾印總結行。（advice-r1）拆出 `kernel_checks()`／`finish()` 給 `aos-agent check` 共用，`Checks.agent()` 只由它呼叫 | [kernel.md](../spec/kernel/README.md) §6 |
| [`aos_agent_check.py`](aos_agent_check.py) | （advice-r1）`aos-agent check`：`find_kernel()` 由 `AOS_KERNEL_HOME`→`tick.json` 找 K，整段跑 kernel 檢查再查 agent 家（池、模型代號、工具），`--probe` 同一套 | [aos-agent/cli-check.md](../spec/aos-agent/cli-check.md) |
| [`aos_agent_home.py`](aos_agent_home.py) | agent 家的內容讀驗（`_metainfo`、人格／記憶／工具、message 驗證）與 `aos-llm call` 的六格 loader，帶原文件與位置解欄位 | [agent.md](../spec/agent/README.md) §2～§3、§5；[aos-llm.md](../spec/aos-llm/README.md) §3 |
| [`aos_llm_call.py`](aos_llm_call.py) | 問模型一次：讀驗 `AOS_LLM_CONFIG` 的 llm.json、組 body、HTTP、正規化並驗 message；入口 `aos-llm call`（fix-r4 由 `aos-llm-call` 改名） | [aos-llm.md](../spec/aos-llm/README.md) |
| [`aos_agent_info.py`](aos_agent_info.py) | 完整 info 設定、state 進度與恢復紀錄讀驗，並原子寫回 state | [agent.md](../spec/agent/README.md)、[aos-agent.md](../spec/aos-agent/README.md) |
| [`aos_agent.py`](aos_agent.py) | tick 三格流程（第 0 步拿 `.tick.lock`、看手動暫停）、批次派工與 kernel 排程登記（stop 不讀 info、沒 `AOS_KERNEL_HOME` 用 tick.json 記的；舊版 tick.json 在 start 改寫）；`main` 轉給 aos_agent_cli | [agent.md](../spec/agent/README.md)、[aos-agent.md](../spec/aos-agent/README.md) §2、§2.1、§11 |
| [`aos_agent_cli.py`](aos_agent_cli.py) | （fix-r4）九個子命令（advice-r1 加 `check`，十個）的 argparse、`--target`、`--wait [秒]`（預設 300）、listen 三態互斥、NotAnAgent 附家的來源 | [aos-agent.md](../spec/aos-agent/README.md) §1 |
| [`aos_agent_listen.py`](aos_agent_listen.py) | （fix-r4，原 aos_agent_last）`listen --last`（info 壞了退回讀 `prompts/history.json`、門關著或手動暫停時警告）、（fix-r5）還沒講完時警告「還在處理中」並在 stderr 附時間；`--wait`（`wait_reply()`，say --wait 共用；fix-r5 起 kernel 家有問題與 bad 也立刻退）、`--follow` | [aos-agent.md](../spec/aos-agent/README.md) §1.5 |
| [`aos_agent_status.py`](aos_agent_status.py) | `aos-agent status`（`collect()` 收集 health（含手動暫停）、state／batch／門／未收輸入、這次卡住的原因與已恢復的舊錯、K 帳本那筆，文字、`-v` 或 `--json`）；`tick_binding()` 讀 tick.json 記的 K（認舊鍵）；（fix-r5）`brief()` 給 kernel ls 的一句標記、`short_error()` 舊錯短版 | [aos-agent.md](../spec/aos-agent/README.md) §1.3 |
| [`aos_agent_pause.py`](aos_agent_pause.py) | （fix-r4）`pause` 放 `paused` 檔；`continue` 刪它並 touch 連敗暫停門，（fix-r5）解了連敗就放 `resumed`；`resume_all()` 是 `continue --all`；都不拿 tick 鎖、不寫 state | [aos-agent.md](../spec/aos-agent/README.md) §1.4、§1.6 |
| [`aos_agent_say.py`](aos_agent_say.py) | `aos-agent say`：原子投一則 user 訊息到 `input` 第一條，沒登記或暫停中 stderr 警告（fix-r5：沒登記時 stdout 另說「已投入…不要再說一次」）；`--wait` 走 `wait_reply()`，逾時退 101，kernel 家有問題／沒登記／手動暫停／連敗暫停／bad 立刻退 101 | [aos-agent.md](../spec/aos-agent/README.md) §1.2 |
| [`aos_agent_init.py`](aos_agent_init.py) | `aos-agent init`：寫死的單一預設家（info／人格／date 工具／`input/`），info 最後寫、已有就拒絕；（fix-r5）非空的非 agent 資料夾要 `force` | [aos-agent.md](../spec/aos-agent/README.md) §1.1 |
| [`aos_agent_tools.py`](aos_agent_tools.py) | （09-24 tools-base）`aos-agent tools add`：找工具包（名字＝`proto5/tools/<名>/`、含 `/`＝資料夾）、驗、同名檢查、程式複製到 `tools/<名>/`、`--root` 寫 `config.json`、工具檔最後寫、`info.tools` 沒涵蓋就補 | [aos-agent.md](../spec/aos-agent/README.md) §1.8 |
| [`aos_agent_batch.py`](aos_agent_batch.py) | 批次建立、inst 產生、kernel 交件、收回音與 ack、結清 | [agent.md](../spec/agent/README.md)、[aos-agent.md](../spec/aos-agent/README.md) |
| [`aos_agent_inputs.py`](aos_agent_inputs.py) | waits 門、輸入讀驗與 intake／consuming 的恢復流程；封存到來源資料夾的 `done/` | [agent.md](../spec/agent/README.md)、[aos-agent.md](../spec/aos-agent/README.md) |
| [`aos_agent_results.py`](aos_agent_results.py) | 模型與工具結果判定、失敗分類與輸出轉換；失敗訊息附 llm.err／cpu.log 路徑與 126／127 的 argv[0] | [agent.md](../spec/agent/README.md)、[aos-agent.md](../spec/aos-agent/README.md) |
| [`aos_agent_runtime.py`](aos_agent_runtime.py) | 持久化操作、恢復清理、交件與測試掛鉤；tick 鎖 `tick_lock()`、`manual_paused()`（fix-r4） | [agent.md](../spec/agent/README.md)、[aos-agent.md](../spec/aos-agent/README.md) |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=proto5/lib python3 -m unittest discover -s proto5/lib/test  # 1287 條；repo 根目錄
```

## aos_directives — 指示詞機制的純函式庫

`aos_directives.py` 是 [指示詞規範](../spec/directives/README.md) 的獨立實作：沒有命令列。它**不知道
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

`aos_inst.py` 是 [inst-posix.md](../spec/inst-posix/README.md) 第 1～5 節的實作（讀、驗、解；第 6 節的
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

`aos_exec.py` 是 [inst-posix.md 第 6 節](../spec/inst-posix/exec.md) 的實作＋命令列（[aos-exec.md](../spec/aos-exec/README.md)）。
舊同步 API 保持原回傳形狀：

```python
import aos_exec
code, kind = aos_exec.run_target(xxx, dir_target=".aos/inst.json", timeout_ms=0,
                                 on_spawn=None, stderr=None, args=None, on_target=None)
```

- `kind`：`"child"`＝子程式真的跑完了一次（它的碼／128+N／126／127／143／137，有 `exit` 就寫）、
  `"aos"`＝aos-exec 自己失敗那次沒跑（code 1，命令列換成 125，不寫 exit）、`"usage"`＝用法錯（2）。
- 三種目標（普通檔案／`.json`／資料夾）、旗標、退出碼與 stderr 印什麼，見 [aos-exec.md](../spec/aos-exec/README.md)。
- 行為：驗完才跑；`mkdir` 在 chdir／開檔前 `makedirs`；`append` 用 `ab`；`inherit` 傳 `None` 給
  `Popen`；`merge` 傳 `subprocess.STDOUT`（跟著 stdout 的 append／inherit）；`clear` 從空環境開始
  否則複製 `os.environ` 再疊 `envs`；`argv[0]` 走疊加後的 PATH；`start_new_session=True`；逾時
  對整個 group SIGTERM → 2 秒 → SIGKILL；exit 檔十進位＋換行、fsync 檔與父目錄。
- `on_spawn(popen)`／`on_spawn(None)`：子行程開起來／收完屍各叫一次（保留給既有呼叫者）。
- `on_target(path)`：在讀 inst 前公布選定的絕對目標，供呼叫者觀察。

`run_inst(inst, stdin_text, timeout_ms=0) -> InstResult`（三元素 tuple：`code, kind, stdout_text`）：吃 `load_obj()` 解好的 dict，
用 UTF-8 把文字送入 stdin，stdout 全收回（壞位元組以替代字元表示）。stdin／stdout 由 API 接管，
stderr／exit／cwd／envs 照 inst；stderr 沒寫就是 /dev/null、`merge` 則併進回傳的 stdout。
另帶 `.timed_out` 布林旗標，真正撞到 TimeoutExpired 才為真，不靠退出碼猜；三值解包與 tuple 相等比較保持相容。
kind 是 child／aos，錯誤跟 `run_target()` 一樣印 stderr。兩個入口共用前置檢查、mkdir、
啟動、126／127、exit 檔與逾時砍 group；管線用 `communicate()`，同時收送避免大輸出卡住。

### 完整執行結果與 daemon 啟動入口

`run_target_full(xxx, dir_target=".aos/inst.json", timeout_ms=0, on_spawn=None, stderr=None,
args=None, on_target=None, *, on_poll=None, poll_ms=20) -> TargetResult`：三種目標、base、
串流與 Usage 判定同 `run_target`，物件提供 `.code`、`.kind`、`.timed_out`、`.stopped`、`.ms`。
`on_poll(popen)` 定期讀控制狀態，回真值要求強停；逾時與強停只處理工作的 process group。
`.timed_out` 是實際期限旗標，即使 TERM 後退出 0 仍為真；已退出的孩子不標 `.stopped`。

`spawn_target(xxx, dir_target=".aos/inst.json") -> Spawned`：給 daemon 的非同步入口，回
`.process`（Popen），stdin／stdout 是控制 pipe；四端 CLOEXEC、`close_fds=True`，孩子獨立 pgid、
與 daemon 同 session。inst 顯式寫 stdin／stdout 即拒絕；stderr、cwd、envs、exit 沿用 inst。
登記、送 go、輪詢及收屍由 daemon 負責；收屍後 `Spawned.finish(code=None)` 寫 exit、回 `(code, kind)`。
起不了 Popen 丟 `SpawnError(code, msg)`，不登記假 pid；與同步 126／127 的差異見 [實作發現](../notes/2026-09-23-rearch/impl-findings.md)。
目標不存在（含非 `.json`）、資料夾缺 dir_target 也是 `SpawnFailed`（09-24 起，同步入口仍是 Usage）。

## aos_home — 共用家與信封

- `read_request(path) -> Envelope`：`.name`、`.id`、`.notify`、`.method`、`.params`、`.error`。
  壞 JSON／信封回 -32700／-32600；合法 notification 即使 method／params 壞也不回音。
- `result_response(id, result)`、`error_response(id, code, message, data=None)`、
  `params_error(id, msg, position, code="FieldTypeMismatch")` 組完整 JSON-RPC 回音。
- `post_request(home, name, obj)`：同目錄 `.tmp` → `os.link`，已存在丟 `RequestExists`。
  `link_json(path, obj)` 同樣有就失敗；`write_json(path, obj)` 是 `.tmp` → 原子替換。
- `read_state(home, default=None)`：缺檔回預設（未指定時 current=null、runs=0）；
  `write_state(home, state)` 原子替換。`ensure_queue(home)` 建 requests／responses。
- `scan_controls(home, on_stop)` 掃 ack-／stop-：ack 先刪回音、再刪通知；不存在視為完成。
  `reconcile_actions(current, request_exists, response_exists)` 是開機五列表的純判定；
  `reconcile(home, current)` 補 Interrupted／刪原單。
- `load_info(home, kind)` 解共用設定指示詞、驗身分與 poll_ms／timeout_ms；錯誤統一
  `HomeError(code, msg)`。kernel 有保留 envs 原文的專用 `load_info`。

## aos_client — 交件者

```python
import aos_client
response = aos_client.call(cpu_home, "aos-exec", {"target": "/abs/job.json"},
                           client="agent", timeout_ms=5000, poll_ms=20)
```

`call(home, method, params=None, *, name=None, client="client", timeout_ms=None, poll_ms=20,
acknowledge=True)` 完成取名、放單、等回音、讀、放 ack，回完整 response（含 error，交件者自行判定）。
等待先確認原單不在，再讀回音；等待逾時不取消工作。ack 是放通知，不同步等待主人刪回音。

要先記帳再 ack，可傳 `acknowledge=False`，或分別用 `new_name(prefix="client")`、
`submit(home, method, params=None, *, name=None, client="client")`（回 request 檔名）、
`wait_response(home, name, *, timeout_ms=None, poll_ms=20)`、`ack(home, name)`。
名稱是 `<名>-<epoch ns>-<pid>.json`；名稱不可重用。客戶端錯誤為 `ClientError(code, msg)`。

## aos_exec_cpu — exec cpu 的主人

`run(home)`／`main(argv=None)`；CLI：`aos-cpu [DIR]`（fix-r4：省略＝目前資料夾）。stdin 是 pipe 時先等 JSON-RPC go，
EOF 先到則不碰家；啟動後控制 fd 搬高位並設 CLOEXEC，工作 stdin 接 /dev/null、stdout 接 cpu 的 stderr。
stdin 不是 pipe 時直接啟動。info 身分是 `exec_cpu`。

每件依序寫 current、`run_target_full`、寫回音、刪原單、清 current／更新 runs；開機先對帳。
result 含 code／kind／timed_out／stopped／ms；Usage 映射 -32602，kind=aos 仍是 result。
pipe stop／EOF、stop- 檔與第一次訊號溫和停；再次訊號強停工作 group，回音照寫。
控制行要是合法信封（jsonrpc 2.0、字串 method、合法 id，stop 不可帶 id）才算數，否則忽略並在 stderr 記 BadControl。
正常停退 0、主人讀寫錯退 1、CLI 用法錯退 2。

## aos_agent_home — agent 家共用內容讀驗

`load_llm_view(agent_dir, env=None)` 回人格、記憶、原始／送模型的工具表、model／params 與絕對路徑；只解模型輸入六格，不讀 state、不寫檔。
`resolve_field(doc, ctx, position)` 帶原文件位置解欄位；`check_message(m, *, from_model=False)` 驗訊息，錯誤為 `AgentError(code, msg)`。

## aos_llm_call — 問模型一次

`load_config(path, env=None)` 讀驗整份模型表；`build_request(agent_dir, config, env=None, *, with_alias=False)` 回 `(body, entry)`（`with_alias` 多回模型代號），保留欄位不讓 params 覆寫。
`call(agent_dir, env=None)` 從環境 `AOS_LLM_CONFIG` 找模型表、打一次 HTTP、正規化並驗證 assistant message 後回傳；不寫記憶、不重試、不跑工具。`EngineFailed`／`Timeout` 訊息尾附 endpoint 與「代號→真名」，不含金鑰。`main(argv=None)` 提供 `aos-llm call [AGENT_DIR]`（fix-r4；裸 `aos-llm` 退 2）。

## aos_agent_info — 設定與進度讀驗

`load(agent_dir, env=None)` 共用 aos_agent_home 的內容讀驗，再補 llm.pool／timeout_ms、tool_pool 與 tick 排程設定。
`load_state(agent_dir, env=None)` 讀驗三格狀態、waits／input、batch／intake／consuming／sweep，缺檔給初始狀態。
`write_state(agent_dir, st)` 原子寫回 state，保留原始 input、排除內部解析欄位。

## aos_agent — 走格與 kernel 排程

`tick(agent_dir, env=None)` 先拿 `.tick.lock`（被佔退 101、不動檔）、看手動暫停（有就退 0），再讀驗、恢復消費與清理，看門、收批次或走 idle／think／act；模型與工具都透過 kernel once 工作執行。
`start(agent_dir, env=None)` 建立／核對 tick.json，向 `AOS_KERNEL_HOME` 的 kernel 登記反覆工作；`stop(agent_dir, env=None)` 撤銷登記，兩者等回音並 ack。
`main(argv=None)`（在 aos_agent_cli）提供九個子命令、家一律 `--target`；回傳 0（完成）、101（tick 等待或鎖被佔、say／listen --wait 逾時、沒登記或暫停）、1（執行／讀驗錯）、2（用法錯）。tick／start 的 `AOS_KERNEL_HOME` 必須是 kernel 家的絕對路徑；stop 沒設就用 tick.json 記的。

日常 CLI（09-24 試玩 r2 補；fix-r4 改）：`aos_agent_init.init(dir)` 寫單一內建預設家；`aos_agent_say.say(dir, text, *, wait, timeout_ms)` 原子投遞並可等回話；`aos_agent_status.collect(dir, env)` 回診斷 dict、`status()` 印文字或 JSON；`aos_agent_pause.pause(dir)`／`resume(dir)` 是 `pause`／`continue`；`aos_agent_listen.listen(dir, mode)` 是 listen，`wait_reply()`／`print_message()` 給 listen 與 say 共用。

拆分模組：`aos_agent_batch` 建批、送件與收尾；`aos_agent_inputs` 處理門與輸入消費；
`aos_agent_results` 判定模型／工具結果；`aos_agent_runtime` 集中持久化、恢復清理與測試掛鉤。

## aos_daemon — 長命孩子管理者

`daemon_home(value=None)` 依參數／`AOS_DAEMON_HOME`／目前資料夾找家（fix-r4 拿掉 `~/.aos-daemon`）；
`run(home)`（別名 `serve`）是前景主迴圈，`main(argv=None)` 包 CLI `aos-daemon boot [--target D]` 與 `aos-daemon halt [--target D] [--wait-ms N]`（裸 `aos-daemon` 退 2）。
`stop(home, wait_ms=30000)`：daemon 不活就不放檔、印 not running；活的放 stop notification、以 flock 等它退出，逾時 DaemonError(Timeout)。
`read_state(home)` 偷看孩子表，`is_alive(home)` 以非阻塞共享 flock 探測主人，不靠 pid 猜。

客戶用 `aos_client.call` 送 `spawn {name,target,dir_target?,restart?}` 或 `kill {name}`；
stop 是檔名以 stop- 開頭的 notification。daemon 寫孩子表之後才送 go、再回 spawn 回音；
同名同 target 冪等並更新 restart，不同 target 回 NameTaken。非零且未被主動停的孩子按固定延遲重讀目標再拉。
停機各孩子並行走 pipe stop → TERM 給孩子 → KILL 給整組，EPIPE 提前進下一階。
啟動先收掉舊表記錄的孩子，再對帳自己的 current；不收養上一任孩子。

## aos_kernel — 帳本、分池與 tick 鏈

`init(home, cpus=None, config=None)` 建家（CLI 是 `init --config FILE`：`info_from_config()` 把設定檔變成 info、沒 kernel 池自動加 k，成功印 `initialized <K>`；lib 的 cpus 省略＝k＋0／1／2），info.json 已在才拒絕、半成品補齊；`load_info(home)` 每格讀驗設定，cpu.envs 原樣留給 inst。
`boot(home, daemon=None, wait_ms=30000)` 驗 daemon、收舊 kernel cpu、換 chain、保留在途與出貨、拉 cpu、放第 1 格。
`tick(home, chain, seq)` 跑一格；`status(home)` 偷看帳本、daemon 孩子與 kernel cpu 的 current／requests。
`new_state(info, chain, kcpu, cli)` 建初始帳本；`classify(proc, response, info, now=None)` 純判定反覆工作結果。

`Kernel` 包每格操作：syscall 一次記帳、`deletes` 去重、收回音、派工、四出貨箱重放與停機。
只接鏈先放後記；派工與 ack／replies／stops／deletes 都先記後做。收回音先查原單，兩者都沒有才補放原名。
once 把 exec 的 result／error 原樣回給 add；rm 立即讓未回覆的 once add 收到 Removed，
rm 自身回 name，正在跑的行程保留 discard 到收完。
反覆工作按 done_exit／bad_after 判定；pool 只派同池，kernel 池專用。

cpu 家「缺的補齊」：資料夾、info、inst 各自不在才寫，已在不覆蓋。沒有事件的格不寫 kernel.log。

CLI（fix-r4）：每個子命令都用 `--target K`（省略找 `AOS_KERNEL_HOME` 再目前資料夾，退 1 的錯誤行附來源）：`aos-kernel init --config FILE／boot [--daemon-target D]／tick／add INST／rm NAME／ack NAME／ls [--json] [-v]／halt [--wait-ms N] [--no-wait]／check [--daemon-target D] [--probe]`（`--daemon-target` 重複＝用法錯；advice-r1 起 `--agent` 一律用法錯、指到 `aos-agent check`），各有 `-h`，完整參數見 [kernel.md §6](../spec/kernel/cli.md)。
`ls` 預設印文字摘要（第一行 `health`：ok 或哪裡壞、該打什麼指令；advice-r1 起 cpu 按池分組、行程成表、queue 一行；bad 行程附「壞了，看 <stderr 路徑>」），`--json` 印欄位穩定的 `aos_kernel_ls` 第 1 版物件（advice-r1，欄位表在 [kernel/cli-ls.md](../spec/kernel/cli-ls.md)）；`ack NAME` 替 once 不等的人收回音。
反覆 add 等回音印 NAME；once 預設印 request 與回音路徑，帶 `--wait-ms` 才等。
CLI 收到回音代 ack，JSON-RPC error 退 1；exec result 即使工作失敗仍退 0、由內容判成敗。
halt 預設等到 phase=stopped 且此 kernel 的 cpu 都從 daemon 表消失才印 `stopped`；鏈沒在跑印 `not running` 不放單；`--no-wait` 只放單。

## 測試

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=proto5/lib python3 -m unittest discover -s proto5/lib/test  # 1287 條；repo 根目錄
```

共 37 個測試檔、1287 條；涵蓋底層執行、daemon／kernel、agent 讀驗與走格、HTTP、崩潰恢復及整合。
真子行程測試使用 tempdir、輪詢上限與清理回呼；崩潰接手的隔離 driver 代替不收孤兒的容器 init 收屍。

| 檔 | 條數 | 驗證內容 |
|---|---:|---|
| [test_agent_crash.py](test/test_agent_crash.py) | 23 | 持久化邊界崩潰與重啟恢復 |
| [test_agent_home.py](test/test_agent_home.py) | 66 | 共用內容六格、人格／記憶／工具與訊息讀驗 |
| [test_agent_info.py](test/test_agent_info.py) | 95 | 完整設定、排程欄位、state 與恢復紀錄讀驗 |
| [test_agent_fix_cli.py](test/test_agent_fix_cli.py) | 13 | start／stop 印行、stop 不讀 info、KernelMismatch、listen --last |
| [test_agent_fix_r4.py](test/test_agent_fix_r4.py) | 24 | （fix-r4）--target 與錯誤來源、listen 三態（--follow 真程序）、pause／continue／status 兩種暫停、tick 鎖真的兩個程序、舊 tick.json |
| [test_agent_fix_r5.py](test/test_agent_fix_r5.py) | 25 | （fix-r5）status 第一行重試中／恢復中、continue 兩階段與 --all、舊錯短版、listen --last 中間句與時間、已登記 start 退 0、沒登記的 say、--wait 先看 kernel／bad、NotAnAgent 講哪種家、init --force |
| [test_agent_daily.py](test/test_agent_daily.py) | 26 | init／say（含 --wait）／status／continue、stop 用 tick.json、listen 退回讀記憶與門關警告、help、用法錯 |
| [test_agent_status_r3.py](test/test_agent_status_r3.py) | 20 | status 的 health、這次原因／已恢復、連敗次數、-v、--json 新鍵；say 沒登記警告與 --wait 立刻退 |
| [test_agent_daily_edges.py](test/test_agent_daily_edges.py) | 11 | say --wait 的等待條件、暫態壞檔、逾時與連敗提前結束 |
| [test_agent_fix_storage.py](test/test_agent_fix_storage.py) | 13 | done/ 封存、舊式紀錄相容、錯誤訊息的 log 路徑、126／127、ToolInvalid 位置 |
| [test_agent_integration.py](test/test_agent_integration.py) | 6 | 真 daemon／kernel／exec cpu 的 agent 整合 |
| [test_agent_tools.py](test/test_agent_tools.py) | 14 | （tools-base）`tools add`：init 的家、手動家補 info、`--force` 保留 config、`--root`、同名、壞工具包、自訂工具包；真 daemon／kernel／agent＋假模型照劇本 write→bash→edit→bash |
| [test_tools_base.py](test/test_tools_base.py) | 85 | （tools-base）base 工具包：共用參數／config／OutsideRoot（含符號連結）、read／write／edit／grep（rg 與退回 grep）／find／ls、base.json 形狀 |
| [test_tools_base_bash.py](test/test_tools_base_bash.py) | 11 | （tools-base）bash：輸出合併、cwd、退出碼、逾時、截斷、背景行程收掉、stdin 空 |
| [test_agent_tick.py](test/test_agent_tick.py) | 118 | waits、三格、批次收送、錯誤與 start／stop |
| [test_client.py](test/test_client.py) | 12 | 取名、先查原單、逾時、端到端與 ack |
| [test_daemon.py](test/test_daemon.py) | 27 | 真 daemon／cpu、spawn 冪等、重拉、三階停機、flock、崩潰接手 |
| [test_daemon_cli.py](test/test_daemon_cli.py) | 10 | boot／halt、家的三種來源與錯誤行來源、裸 aos-daemon 退 2、halt 等待退出 |
| [test_daemon_crash.py](test/test_daemon_crash.py) | 11 | 握手中段（fork 後／寫表後／go 後／回音後）與接手中（TERM 後／KILL 後／死透後／對帳中／對帳後）真 SIGKILL，下一任收斂；subreaper hub＋測試 driver 閘門 |
| [test_kernel_crash.py](test/test_kernel_crash.py) | 15 | kernel 一格在 log 前（C-7）、派工逐顆與四張出貨箱逐箱（C-8）真 SIGKILL，下一格／boot 收斂：不重派、不重算、無鬼回音；測試啟動器當 kernel cli |
| [test_directives.py](test/test_directives.py) | 101 | 指示詞、引用、選項與錯誤 |
| [test_exec.py](test/test_exec.py) | 94 | 保留三種目標、串流、env、退出碼及舊 API |
| [test_exec_cpu.py](test/test_exec_cpu.py) | 31 | 真 cpu 握手、EOF、訊號、stop、Interrupted、timeout、工作串流 |
| [test_exec_full.py](test/test_exec_full.py) | 14 | 三類 timed_out、強停、TERM 後退 0、相容性 |
| [test_exec_spawn.py](test/test_exec_spawn.py) | 20 | daemon pipe、pgid／session、顯式串流拒絕、exit 與啟動失敗 |
| [test_home.py](test/test_home.py) | 27 | 三類信封、原子放單、ack、五列對帳與 info |
| [test_inst.py](test/test_inst.py) | 139 | inst 讀驗、指示詞位置、欄位與選項 |
| [test_kernel.py](test/test_kernel.py) | 29 | 判定表、syscall 去重、rm／once、pool、設定 |
| [test_kernel_check.py](test/test_kernel_check.py) | 30 | check 各項 ok／warn／bad、daemon 的 /proc 環境、agent 項（advice-r1 起經 `aos-agent check` 跑）、--daemon-target 三種來源與 info.daemon 不同的 warn、K 家目錄、daemon 重開後 cpu 不在 |
| [test_kernel_cli.py](test/test_kernel_cli.py) | 37 | --target 三種來源與錯誤行來源、init --config（壞設定不建家、自動加 k、拒 daemon）／ack／ls（含 bad 提示、第一行 health、advice-r1 的表與 --json）／halt 等停好／check 旗標重複、舊 --agent 指到新指令 |
| [test_advice_r1.py](test/test_advice_r1.py) | 24 | （advice-r1）`aos-agent check`：K 從 AOS_KERNEL_HOME／tick.json、找不到、相對路徑、KernelMismatch（含 tick.json 壞掉，跟 start 同判）、K 壞了仍查 agent、NotAnAgent、預設目前資料夾、--probe ok／bad；`ls --json` 欄位集合、值、stdout 純 JSON、退出碼、daemon 沒活 child=null、proc 缺鍵／null 正規化、broken 退 1、look 指 target；文字表對齊、按池原值分組、長名砍中間、-v |
| [test_kernel_health.py](test/test_kernel_health.py) | 19 | health 各情形與優先序、stall、帳本壞不丟例外、ls 第一行與 --json |
| [test_kernel_fix_r5.py](test/test_kernel_fix_r5.py) | 13 | （fix-r5）check --probe（本機 HTTP 假端點：models／退回一句話／port 錯）與總結行、ls 的恢復中／daemon 沒活的 cpu 行／agent 標記、真 daemon：boot 印 `booted 3 cpus`、kill -9 llm cpu 看到恢復中 |
| [test_kernel_integration.py](test/test_kernel_integration.py) | 15 | 真 daemon＋cpu、反覆／once、halt、重 boot、pool、Interrupted |
| [test_kernel_recovery.py](test/test_kernel_recovery.py) | 21 | 出貨重放、先記未放、鏈與 boot 交接、ack 唯一性 |
| [test_llm_call.py](test/test_llm_call.py) | 47 | 模型表、組 body、HTTP 與 message 正規化；`aos-llm call`、裸 `aos-llm` 退 2 |
| [test_rearch_e2e.py](test/test_rearch_e2e.py) | 1 | k／0／llm、envs PATH 的假 llm-http、once 輸出、done_exit、完整停機 |

共用工具：[\_util.py](test/_util.py)（既有底層／agent）、[\_daemon_util.py](test/_daemon_util.py)
（控制協議孩子、輪詢、孤兒隔離 driver）、[\_kernel_util.py](test/_kernel_util.py)（真 daemon／kernel 測試家與清理）。
