# proto5/lib — 五十四支 Python 模組

← [proto5 README](../README.md)｜規範：[cpu](../spec/cpu/README.md)、[daemon](../spec/daemon/README.md)、[kernel](../spec/kernel/README.md)、[aos-agent](../spec/aos-agent/README.md)

Python 3.12 以上、只用標準庫（3.12.13 與 3.14.7 都實跑全綠，見 [notes/2026-09-24-py312-run.md](../notes/2026-09-24-py312-run.md)）。
由下往上：`aos_directives` → `aos_inst` → `aos_exec`（跑一次）；`aos_home` 共用檔案範式、`aos_client` 交件；
`aos_exec_cpu` 是長命的 cpu、`aos_daemon` 按池管孩子、`aos_kernel` 用一格接一格的 tick 排程；agent 線（`aos_agent*`）
把模型與工具都交給 exec cpu 跑。

09-24 起 daemon／kernel 是 proto5-2 的**池式**版本（納入 commit 08dac8a）：daemon 手上是「每池要哪幾號」的宣告、
kernel 手上是「池 P 要 N 顆」，都不再逐顆 spawn／kill。三支指令的家一律 `--target`：`aos_home.resolve_target()`
照「`--target` → 環境變數（`AOS_DAEMON_HOME`／`AOS_KERNEL_HOME`）→ 目前資料夾」找。

一檔一行（新增模組照這個格式插一行）：

| 檔 | 職責 |
|---|---|
| [`aos_directives.py`](aos_directives.py) | 指示詞（`$env`／`$fmt`／`$ref`／`$opt`）解析的純函式庫，不知道 inst |
| [`aos_directives_edit.py`](aos_directives_edit.py) | `aos-directives`（tool-era T3）：人格（system prompt）按 Markdown 標題分節 ls／show／set／add／rm／export／import／versions／revert，並解／驗一份 aos JSON 檔的指示詞（resolve／check） |
| [`aos_inst.py`](aos_inst.py) | inst.json 的讀、驗、解，回執行用的 dict |
| [`aos_exec.py`](aos_exec.py) | 執行一次的上層：三種目標的解讀（`run_target`／`run_target_full`／`run_inst`）與 `aos-exec` 命令列 |
| [`aos_exec_run.py`](aos_exec_run.py) | 執行一次的底層：前置檢查、開串流、起子行程、等待／逾時／強停整組、寫 exit 檔 |
| [`aos_exec_spawn.py`](aos_exec_spawn.py) | daemon 的非同步入口 `spawn_target`：讀目標、開控制 pipe、交出孩子（`launcher` 決定 fd 0／1 怎麼接） |
| [`aos_home.py`](aos_home.py) | JSON-RPC 信封、原子放單與狀態、ack／stop、開機對帳、`--target` 找家 |
| [`aos_client.py`](aos_client.py) | 交件者：取名、放單、先查原單再等回音、讀與 ack |
| [`aos_exec_cpu.py`](aos_exec_cpu.py) | 長命 exec cpu（`aos-cpu`）：go／stop、逐件執行、訊號與對帳、回完音往 kernel 家丟 `notify` 通知 |
| [`aos_daemon.py`](aos_daemon.py) | daemon 的家、info 讀驗、`is_alive`、給 kernel 讀的 `pool_summary`／`pool_summary_state`／`pool_kid`、`run`（boot）與 `stop`（halt） |
| [`aos_daemon_pools.py`](aos_daemon_pools.py) | 池的資料形狀（`pool.json`／`kids/<i>.json`／`summary.json`）、檔案動作、拉孩子（只留 fd 0 一條 pipe） |
| [`aos_daemon_loop.py`](aos_daemon_loop.py) | daemon 的一圈：收屍、狀態機、退避、節流、fd 預算、批次停機階梯 |
| [`aos_daemon_rpc.py`](aos_daemon_rpc.py) | daemon 收的單 `scale`／`kill`／`ls` 怎麼驗、怎麼判（同步做完才回） |
| [`aos_daemon_cli.py`](aos_daemon_cli.py) | `aos-daemon boot／halt／ls／scale／kill` 命令列 |
| [`aos_kernel.py`](aos_kernel.py) | kernel 入口（`aos-kernel` 取 `main`）＋小匯出層（只留測試真的從這裡拿的名字） |
| [`aos_kernel_info.py`](aos_kernel_info.py) | 池表讀驗（info.json 第 2 版）、成員公式、`init`、初始帳本、反覆工作判定 `classify`、共用錯誤 |
| [`aos_kernel_ledger.py`](aos_kernel_ledger.py) | `KernelLedger` 帳本第 2 版：排隊、syscall、busy／on、四個出貨箱重放 |
| [`aos_kernel_engine.py`](aos_kernel_engine.py) | `Kernel` 一格十步（只碰有事的 cpu）與模組函式 `tick` |
| [`aos_kernel_pools.py`](aos_kernel_pools.py) | kernel 這邊怎麼增減 cpu（每格第 7 步：收 scale 回音、重算、送單、寫 envs／模板、搬池） |
| [`aos_kernel_boot.py`](aos_kernel_boot.py) | `boot` 交接換鏈、`status` 偷看、`stop`（halt）等停好 |
| [`aos_kernel_cpu.py`](aos_kernel_cpu.py) | `aos-kernel cpu add／rm／ls`：只改 `K/info.json` 的池表（鎖、指示詞原樣保留） |
| [`aos_kernel_rows.py`](aos_kernel_rows.py) | 按池摘要（每池一格／一行）與一顆一行的資料與排版，`cpu ls` 與 `ls` 共用 |
| [`aos_kernel_health.py`](aos_kernel_health.py) | `health(home)` 一句話健康判定（看每池摘要、不逐顆查）與 agent 暫停／重試標記 |
| [`aos_kernel_ls.py`](aos_kernel_ls.py) | `aos-kernel ls`：`ls_data()` 收成穩定資料（就是 `--json`），`render()` 排成對齊表 |
| [`aos_kernel_check.py`](aos_kernel_check.py) | `aos-kernel check`：啟動前唯讀檢查；`kernel_checks()`／`finish()` 給 `aos-agent check` 共用 |
| [`aos_kernel_cli.py`](aos_kernel_cli.py) | `aos-kernel` 參數解析與 `main` |
| [`aos_llm_call.py`](aos_llm_call.py) | `aos-llm call`：讀驗 llm.json、組 body、HTTP、正規化並驗 message |
| [`aos_agent.py`](aos_agent.py) | agent 的 tick 三格流程、批次派工與 kernel 排程登記；`main` 轉給 aos_agent_cli |
| [`aos_agent_cli.py`](aos_agent_cli.py) | `aos-agent` 各子命令的 argparse 與分派 |
| [`aos_agent_home.py`](aos_agent_home.py) | agent 家的內容讀驗（人格／記憶／工具、message）與 `aos-llm call` 的六格 loader |
| [`aos_agent_info.py`](aos_agent_info.py) | agent 的 info 設定、state 進度與恢復紀錄讀驗，原子寫回 state |
| [`aos_agent_batch.py`](aos_agent_batch.py) | 批次建立、inst 產生（含 aos-jail 包裝）、kernel 交件、收回音、結清 |
| [`aos_agent_inputs.py`](aos_agent_inputs.py) | waits 門、輸入讀驗與 intake／consuming 的恢復流程 |
| [`aos_agent_results.py`](aos_agent_results.py) | 模型與工具結果判定、失敗分類與輸出轉換 |
| [`aos_agent_runtime.py`](aos_agent_runtime.py) | 持久化操作、恢復清理、tick 鎖、交件與測試掛鉤 |
| [`aos_agent_init.py`](aos_agent_init.py) | `aos-agent init`：寫死的單一預設家 |
| [`aos_agent_say.py`](aos_agent_say.py) | `aos-agent say`：原子投一則訊息，可等回話 |
| [`aos_agent_listen.py`](aos_agent_listen.py) | `aos-agent listen --last／--wait／--follow` |
| [`aos_agent_listen_render.py`](aos_agent_listen_render.py) | listen 的印法：挑最後 N 則、輪次標頭、工具呼叫行 |
| [`aos_agent_talk.py`](aos_agent_talk.py) | `aos-agent talk`：讀一行、投遞、等這一輪回話、印，slash 指令 |
| [`aos_agent_status.py`](aos_agent_status.py) | `aos-agent status`：收集診斷並印文字／`-v`／`--json` |
| [`aos_agent_pause.py`](aos_agent_pause.py) | `aos-agent pause`／`continue` |
| [`aos_agent_check.py`](aos_agent_check.py) | `aos-agent check`：找 K、跑 kernel 檢查、再查 agent 家、工具與權限牆 |
| [`aos_agent_tools.py`](aos_agent_tools.py) | `aos-agent tools add`：裝工具包或原地引用工具檔／資料夾 |
| [`aos_agent_tools_edit.py`](aos_agent_tools_edit.py) | `aos-agent tools ls／rm／alias／unalias` 與共用的 info 編輯（管理鎖、試算後整份重寫） |
| [`aos_agent_access.py`](aos_agent_access.py) | 權限牆（access.json）讀驗、信任資料、重疊檢查、快照 |
| [`aos_agent_access_cli.py`](aos_agent_access_cli.py) | `aos-agent access ls／set／rm／cwd／net` |
| [`aos_jail.py`](aos_jail.py) | `aos-jail`：組 bwrap 參數並 exec（工具關進牢裡跑） |
| [`aos_json_cli.py`](aos_json_cli.py) | `aos-json`（tool-era T3）：人用的 JSON Pointer 改檔（get／set／del／append／merge），照原檔縮排重寫、`--expect-sha` 防衝突，`--check-directives` 先過 aos_directives 才寫 |
| [`aos_team_format.py`](aos_team_format.py) | 團隊共用格式（spec/team/）：資料夾佈局、名冊 `team.json`、信、申請、任務單、問題的讀驗，以及共用的 id／時間／寫檔 |
| [`aos_team_requests.py`](aos_team_requests.py) | 申請登記表：`kind → 處理函式`，郵差讀到 outbox 裡帶 `kind` 的檔就叫 `handle()`；別隊新增 kind 在這裡加一行 |
| [`aos_team_task.py`](aos_team_task.py) | 任務單（交接書）與狀態機：只有郵差寫，處理函式改單子並回「後續動作」清單；同一 `src` 重跑冪等 |
| [`aos_team_ask.py`](aos_team_ask.py) | 問人：成員 `ask_human` 寄 `kind=ask` 建問題檔，人用 `aos-team answer` 把答案投回發問者 |
| [`aos_team_cli.py`](aos_team_cli.py) | `aos-team` 的分派表：子命令 →（模組、函式、哪一隊做、一句話），還沒做的印「還沒做（第 N 隊）」退 1 |

命令列入口在 [`../cli/`](../cli/)，每支都是薄殼：`aos-exec`→`aos_exec.main`、`aos-cpu`→`aos_exec_cpu.main`、
`aos-daemon`→`aos_daemon.main`、`aos-kernel`→`aos_kernel.main`、`aos-agent`→`aos_agent.main`、
`aos-jail`→`aos_jail.main`、`aos-llm`→`aos_llm_call.main`、`aos-directives`→`aos_directives_edit.main`、
`aos-json`→`aos_json_cli.main`、`aos-team`→`aos_team_cli.main`。

超過約 400 行但刻意不拆：`aos_agent_access.py`、`aos_agent_talk.py`（agent 線別隊正在改，拆了難合併）。

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=proto5/lib python3 -m unittest discover -s proto5/lib/test  # 1724 條；repo 根目錄
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

## aos_exec — 執行者（三支：aos_exec／aos_exec_run／aos_exec_spawn）

[inst-posix.md 第 6 節](../spec/inst-posix/exec.md) 的實作＋命令列（[aos-exec.md](../spec/aos-exec/README.md)）。
09-24 拆成三支、行為不變：`aos_exec.py` 是上層（三種目標怎麼解讀、`run_target`／`run_target_full`／`run_inst`、`main`）；
`aos_exec_run.py` 是底層（前置檢查與串流 `_execute_inst`、起子行程與等待 `_spawn`／`_wait_full`、`terminate`、
寫 exit 檔 `_finish`，以及常數 `DEFAULT_DIR_TARGET`／`GRACE`／`CHILD`／`AOS`／`USAGE`，`aos_exec` 照樣匯出這些常數）；
`aos_exec_spawn.py` 是 daemon 的非同步入口。舊同步 API 保持原回傳形狀：

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

`aos_exec_spawn.spawn_target(xxx, dir_target=".aos/inst.json", launcher=None) -> Spawned`：給 daemon 的非同步入口。
`launcher` 省略時 `.process`（Popen）的 stdin／stdout 是兩條控制 pipe；daemon 的池式孩子傳
`aos_daemon_pools._launch`（只留 fd 0、fd 1 接 `/dev/null`），`aos_daemon_pools.spawn_child()` 就是這樣叫它。
四端 CLOEXEC、`close_fds=True`，孩子獨立 pgid、與 daemon 同 session。inst 顯式寫 stdin／stdout 即拒絕；
stderr、cwd、envs、exit 沿用 inst。登記、送 go、輪詢及收屍由 daemon 負責；收屍後 `Spawned.finish(code=None)`
寫 exit、回 `(code, kind)`。起不了 Popen 丟 `SpawnError(code, msg)`，不登記假 pid；與同步 126／127 的差異見
[實作發現](../notes/2026-09-23-rearch/impl-findings.md)。目標不存在（含非 `.json`）、資料夾缺 dir_target 也是
`SpawnFailed`（同步入口仍是 Usage）。

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
回完音若 info 有 `notify`（kernel 家的絕對路徑），往那裡丟一張 `resp-` 通知讓 kernel 下一格就收；開機補丟上一任沒丟到的（[spec/cpu/notify.md](../spec/cpu/notify.md)）。

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

日常 CLI（09-24 試玩 r2 補；fix-r4 改）：`aos_agent_init.init(dir)` 寫單一內建預設家；`aos_agent_say.say(dir, text, *, wait, timeout_ms)` 原子投遞並可等回話；`aos_agent_status.collect(dir, env)` 回診斷 dict、`status()` 印文字或 JSON；`aos_agent_pause.pause(dir)`／`resume(dir)` 是 `pause`／`continue`；`aos_agent_listen.listen(dir, mode, *, count, calls)` 是 listen（calls＝None／'short'／'full'，印法在 `aos_agent_listen_render`），`wait_reply()`／`print_message()` 給 listen 與 say 共用；（09-24 talk）`aos_agent_talk.talk(dir, *, timeout_ms, show_calls)` 是 talk（stdin 讀行，tty 才載 readline、印提示符）。

拆分模組：`aos_agent_batch` 建批、送件與收尾；`aos_agent_inputs` 處理門與輸入消費；
`aos_agent_results` 判定模型／工具結果；`aos_agent_runtime` 集中持久化、恢復清理與測試掛鉤。

## aos_daemon — 池的主人（五支：aos_daemon／pools／loop／rpc／cli）

09-24 由 proto5-2 納入：daemon 手上不再是一顆一顆孩子的 `spawn／kill`，而是一份「每池要哪幾號」的
宣告（`pool.json`），每圈把孩子往宣告靠（死了自己拉、多了自己收）。規範在 [spec/daemon/](../spec/daemon/README.md)。

`aos_daemon.py`：`daemon_home(value=None)` 依 `--target／AOS_DAEMON_HOME／` 目前資料夾找家；`run(home)`
是前景主迴圈（開機先整批殺掉上一任的孩子、kids 檔改成 pending、照 `pool.json` 節流拉回來；舊版 proto5 家
的 `children` 表也照殺）；`stop(home, wait_ms=30000)` 是 `halt`：不活就不放單、印 `not running`，活的放
stop notification、flock 等退出。`is_alive(home)` 非阻塞共享 flock 探測。給 kernel 讀的小函式：
`pool_summary(home, dpool)`（讀 `summary.json`，不在或壞了回 `None`；顯示用）、`pool_summary_state(home, dpool)`
（回 gone／ok／unknown，只有 gone 才算池已拿掉；交接用）、`pool_kid(home, dpool, i)`（讀 `kids/<i>.json`）。
`main` 轉給 aos_daemon_cli。

`aos_daemon_pools.py`：池與一顆一檔的形狀（`pool.json`／`kids/<i>.json`／`summary.json`）、
`valid_pool_name()`（1～64 bytes、只用 `A-Za-z0-9_.-`）、`peek(path)`（讀一個 JSON 物件，讀不到回 `None`）、
`spawn_child()`（叫 `aos_exec_spawn.spawn_target`，`launcher` 換成只留 fd 0 一條控制 pipe、fd 1 接 `/dev/null`）。

`aos_daemon_loop.py`：`Daemon` 的一圈——`waitpid(-1)` 收屍；dead／failed 的到期、活滿 `stable_ms` 取消
重拉標記、批次階梯的下一段，全部放在同一個按時間排的堆積；可以拉的號每池一條佇列，只有佇列不空的池參加
輪流（`spawn_per_sec` 節流，`max_children` 是 fd 預算）；每圈只碰有事的池。

`aos_daemon_rpc.py`：`Requests.scale {pool,count,skip?,inst?,home?,decl?,owner?}`（池不在要給 `inst`
樣板；`owner` 是別人的池要 `--force` 才能改）、`kill {pool, names|all}`、`ls`，一律同步做完才回。
`stop／ack` 走既有的 `aos_home.scan_controls`。

`aos_daemon_cli.py`：`aos-daemon boot／halt／ls／scale／kill`，家一律 `--target`。`ls` 只偷看檔案、
不放單（daemon 沒在跑也看得到最後的摘要，第一行講 daemon 有沒有在跑）；給 `--pool` 才一顆一行；
`running` 那格寫成 `2（含 restarting 1）`（restarting 是 running 的子集，0 就只印 `2`；`--json` 照舊兩欄）；
`scale／kill` 放單等回音（10 秒）。

## aos_kernel — 池表、帳本第 2 版與 tick 鏈（十二支：aos_kernel＋info／ledger／engine／pools／boot／cpu／rows／health／ls／check／cli）

09-24 由 proto5-2 納入：kernel 不再逐顆記 cpu，而是「池 P 要 N 顆」的宣告；一格只碰有事的
cpu（收到通知的、上一格剛派的、輪到巡檢的），派工從閒號堆疊直接拿。規範在 [spec/kernel/](../spec/kernel/README.md)。

`aos_kernel.py`：入口（`cli/aos-kernel` 取 `main`）＋小匯出層，只留測試真的從這裡拿的名字
（`CLI`、`KernelError`、`classify`、`init`、`load_info`、`members`、`new_pool`、`new_state`、`Kernel`、`tick`、
`boot`、`status`、`main`）；其餘請直接 import 各模組。

`aos_kernel_info.py`：池表讀驗（`info.json` 第 2 版：`pools.P.count／skip／envs／daemon／dpool`）、
成員公式（`count` 顆扣掉 `skip` 那幾號）、`init(home, config=None, daemon=None)`（CLI 是 `init --config FILE`：
沒給就只建 `kernel` 池 `{"count": 1}`，成功印 `initialized <K>`）、`new_state()` 建初始帳本、
`classify()` 判定反覆工作結果。

`aos_kernel_ledger.py`：`KernelLedger` 帳本第 2 版——`ready／delayed` 堆積排隊（懶刪）、`busy`／`on`
記誰在哪格忙、`pools` 每格記 `want／sent／dirty／redeclare` 等、`sends／acks／replies／deletes` 四個
出貨箱，一格最多寫四次（提交點 1～4）。

`aos_kernel_engine.py`：`Kernel`（`PoolsMixin` ＋ `KernelLedger`）一格十步：讀通知、收回音、（第 7 步）交給
`aos_kernel_pools` 對池做事、派工、四出貨箱重放、停機。模組函式 `tick(home, chain, seq)` 跑一格。

`aos_kernel_pools.py`：kernel 這邊怎麼增減 cpu——每格第 7 步：收 scale 回音 → info 變了沒 → `dirty`
才重算 → 送下一張 scale 單 → 重寫 `envs.json`／池模板 `inst.json` → 搬池／池消失，只碰有變化的池。

`aos_kernel_boot.py`：`boot(home, wait_ms=30000)`——交接：驗每個池解得出 daemon、把「帳本裡的 kernel 池」
與「info 的 kernel 池」各縮到 0、寫新帳本（新 chain、`pools` 全部標 `dirty` 待第一格整份重送）、建家與模板、
拉 kernel 池 1 顆、放第 1 格。`status(home)` 偷看帳本＋各池 daemon 摘要；`stop(home, wait_ms)` 是 `halt`：
每個工作池先縮到 0，全部回成功才縮 kernel 池，等 daemon 那邊全部消失才印 `stopped`。

`aos_kernel_cpu.py`：`cpu_add()`／`cpu_rm()`／`cpu_ls()`——只改 `K/info.json` 的池表：拿
`K/.info.lock` 獨占鎖（等 10 秒）→ 讀 → 改 → 驗 → 唯一 `.tmp` → rename；不放任何單、不用 `boot`，
kernel 在跑的話下一格就照新數字做。指示詞（`$env`…）原樣保留，不是字面值就退 1、不寫。

`aos_kernel_rows.py`：`pool_rows()`／`pool_row()` 每池一格 dict（`--json` 讀的就是它）、`row_line()`／`pool_lines()`
一池一行（`running` 那格同 daemon ls，restarting 寫進括號）、`cpu_rows()`／`cpu_line()` 一顆一行（逐顆讀 kids 檔）；
`cpu ls`、`aos-kernel ls`、health、check 共用。

`aos_kernel_health.py`：`health(home)` 先中先印：缺目錄 → 停機中 → daemon 沒在跑 → kernel cpu 不在
→ tick 停住 → 某池出錯／池不見了 → 搬池中或池少幾顆（`recovering`）→ ok；只看每池的 `summary.json`。
`agent_marks()`／`agents_health()` 給 `ls` 標 agent 的暫停／重試。

`aos_kernel_ls.py`：`ls_data()` 收成 `aos_kernel_ls` 第 2 版資料（就是 `--json`，欄位表在
[kernel/cli-ls.md](../spec/kernel/cli-ls.md)），`render()` 排成對齊表（第一行 health、按池摘要、行程）；
`stderr_hint()` 給 bad 行程指路。

`aos_kernel_check.py`：啟動前唯讀檢查（info、K 家目錄、daemon、PATH、池表、llm 設定；`--probe` 真的打一次
endpoint）；`kernel_checks()`／`finish()` 給 `aos-agent check` 共用。

CLI（`aos_kernel_cli.py`）：每個子命令都用 `--target K`（省略找 `AOS_KERNEL_HOME` 再目前資料夾，
退 1 的錯誤行附來源）：`aos-kernel init --config FILE [--daemon D]／boot [--wait-ms N]／cpu add／rm／ls／tick／
add INST／rm NAME／ack NAME／ls [--pool P] [--procs] [--json] [-v]／halt [--wait-ms N] [--no-wait]／
check [--daemon-target D] [--probe]`（`--agent` 一律用法錯、指到 `aos-agent check`），各有 `-h`。
反覆 add 等回音印 NAME；once 預設印 request 與回音路徑，帶 `--wait-ms` 才等；CLI 收到回音代 ack，
JSON-RPC error 退 1；exec result 即使工作失敗仍退 0、由內容判成敗。

## 測試

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=proto5/lib python3 -m unittest discover -s proto5/lib/test  # 1724 條；repo 根目錄
```

共 57 個測試檔、1724 條（09-24 拆檔＋tidy 後實跑，約 100～130 秒）；涵蓋底層執行、daemon／kernel 按池行為、
agent 讀驗與走格、工具與權限牆、HTTP、崩潰恢復及整合。真子行程測試使用 tempdir、輪詢上限與清理回呼；
崩潰接手的隔離 driver 代替不收孤兒的容器 init 收屍。一檔一行：

| 檔 | 驗證內容 |
|---|---|
| [test_directives.py](test/test_directives.py) | 指示詞、引用、選項與錯誤 |
| [test_directives_edit.py](test/test_directives_edit.py) | `cli/aos-directives`（人格分節編輯＋resolve／check）與 `cli/aos-json`（人用 JSON Pointer 改檔）：子行程跑、退出碼、錯誤格式、檔案真的改對 |
| [test_inst.py](test/test_inst.py) | inst 讀驗、指示詞位置、欄位與選項 |
| [test_exec.py](test/test_exec.py) | 三種目標、串流、env、退出碼、逾時及舊 API（`run_target`／`run_inst`／`main`） |
| [test_exec_full.py](test/test_exec_full.py) | `run_target_full`：三類 timed_out、強停、TERM 後退 0、相容性 |
| [test_exec_spawn.py](test/test_exec_spawn.py) | `aos_exec_spawn.spawn_target`：控制 pipe、pgid／session、顯式串流拒絕、exit 與啟動失敗 |
| [test_exec_cpu.py](test/test_exec_cpu.py) | 真 cpu：握手、EOF、訊號、stop、Interrupted、timeout、工作串流、`notify` 通知與開機補丟 |
| [test_home.py](test/test_home.py) | 三類信封、原子放單、ack、五列對帳與 info |
| [test_client.py](test/test_client.py) | 取名、先查原單、逾時、端到端與 ack |
| [test_daemon.py](test/test_daemon.py) | 真 daemon 按池、宣告式：scale、補／收／重拉、退避、節流、fd 預算、kill、halt、重開 |
| [test_daemon_cli.py](test/test_daemon_cli.py) | `aos-daemon` 命令列：boot／halt（家的三種來源、flock 探測、逾時）與 ls／scale／kill |
| [test_daemon_crash.py](test/test_daemon_crash.py) | daemon 崩潰窗口（按池版）：閘門卡住真 daemon、真 SIGKILL、下一任接手 |
| [test_daemon_fix.py](test/test_daemon_fix.py) | astra 審查 daemon 側定點：`pool_summary_state` 三態、摘要寫／刪失敗重試、每圈只碰有事的池 |
| [test_kernel.py](test/test_kernel.py) | kernel 判定、syscall、收回音與派工（帳本第 2 版）；不開外部行程 |
| [test_kernel_pools.py](test/test_kernel_pools.py) | info 第 2 版讀驗、成員公式、`init --config`、家與模板（不需要 daemon） |
| [test_kernel_tick2.py](test/test_kernel_tick2.py) | 一格十步：池的長大／縮小、scale 回音、通知三路、排隊懶刪、提交點、搬池、停機縮池（假 daemon） |
| [test_kernel_halt2.py](test/test_kernel_halt2.py) | 搬池、池從 info 消失、停機縮池與 halt 等待（假 daemon） |
| [test_kernel_boot2.py](test/test_kernel_boot2.py) | kernel boot 交接與崩潰窗口（某一步丟 Crash，下一格／下一次 boot 照常跑） |
| [test_kernel_cpu.py](test/test_kernel_cpu.py) | `aos-kernel cpu add／rm／ls`：只改 info、鎖、指示詞保留、按池摘要與一顆一行的字眼 |
| [test_kernel_check.py](test/test_kernel_check.py) | `aos-kernel check` 各項 ok／warn／bad（假家、flock、手寫 summary.json） |
| [test_kernel_cli.py](test/test_kernel_cli.py) | kernel 命令列：`--target` 來源、`init`、help、`ack`、`ls` 的摘要與表、halt、舊 `--agent` 指到新指令 |
| [test_kernel_health.py](test/test_kernel_health.py) | health 優先序、錯誤邊界、`ls` 第一行與 `--json` |
| [test_kernel_crash.py](test/test_kernel_crash.py) | 閘門卡住真 tick、真 SIGKILL、下一格（或 boot）接手：不重派、不重算、無鬼回音 |
| [test_kernel_fix_r5.py](test/test_kernel_fix_r5.py) | （fix-r5）check `--probe` 與總結行、ls 的恢復中與 agent 標記、真 daemon 的 boot 印行 |
| [test_kernel_fix_astra.py](test/test_kernel_fix_astra.py) | astra 審查 kernel 側必修定點：boot 等待中舊 tick 又提交、draining 中拒 boot、摘要讀不到要等、壞通知 |
| [test_kernel_integration.py](test/test_kernel_integration.py) | 真 daemon＋cpu：反覆／once、halt、重 boot、pool、Interrupted |
| [test_kernel_recovery.py](test/test_kernel_recovery.py) | 出貨重放、先記未放、鏈與 boot 交接、ack 唯一性 |
| [test_p52_e2e.py](test/test_p52_e2e.py) | 真 daemon＋真 aos-cpu＋真 tick 鏈的端到端（加減 cpu、忙的做完才收、崩潰退避、halt→boot） |
| [test_rearch_e2e.py](test/test_rearch_e2e.py) | k／0／llm、envs PATH 的假 llm-http、once 輸出、done_exit、完整停機 |
| [test_advice_r1.py](test/test_advice_r1.py) | （advice-r1）`aos-agent check` 找 K 與各情形、`aos-kernel ls --json` 欄位與文字表 |
| [test_llm_call.py](test/test_llm_call.py) | 模型表、組 body、HTTP 與 message 正規化；`aos-llm call`、裸 `aos-llm` 退 2 |
| [test_agent_home.py](test/test_agent_home.py) | 共用內容六格、人格／記憶／工具與訊息讀驗 |
| [test_agent_info.py](test/test_agent_info.py) | 完整設定、排程欄位、state 與恢復紀錄讀驗 |
| [test_agent_tick.py](test/test_agent_tick.py) | waits、三格、批次收送、錯誤與 start／stop |
| [test_agent_crash.py](test/test_agent_crash.py) | 持久化邊界崩潰與重啟恢復 |
| [test_agent_fix_cli.py](test/test_agent_fix_cli.py) | start／stop 印行、stop 不讀 info、KernelMismatch、listen --last |
| [test_agent_fix_r4.py](test/test_agent_fix_r4.py) | （fix-r4）`--target` 與錯誤來源、listen 三態、pause／continue／status、tick 鎖、舊 tick.json |
| [test_agent_fix_r5.py](test/test_agent_fix_r5.py) | （fix-r5）status 重試中／恢復中、continue 兩階段與 --all、say／--wait 各情形、init --force |
| [test_agent_fix_storage.py](test/test_agent_fix_storage.py) | done/ 封存、舊式紀錄相容、錯誤訊息的 log 路徑、126／127、ToolInvalid 位置 |
| [test_agent_daily.py](test/test_agent_daily.py) | init／say／status／continue、stop 用 tick.json、listen 退回讀記憶、help、用法錯 |
| [test_agent_daily_edges.py](test/test_agent_daily_edges.py) | say --wait 的等待條件、暫態壞檔、逾時與連敗提前結束 |
| [test_agent_status_r3.py](test/test_agent_status_r3.py) | status 的 health、這次原因／已恢復、連敗次數、-v、--json 新鍵 |
| [test_agent_listen_tweak.py](test/test_agent_listen_tweak.py) | listen `--last N`、輪次標頭與收話時間、`--show-calls`／`--show-calls-full`、即時呼叫行 |
| [test_agent_talk.py](test/test_agent_talk.py) | `aos-agent talk`：一句問答、不重印、slash 指令、逾時補印、Ctrl-C／EOF |
| [test_agent_integration.py](test/test_agent_integration.py) | 真 daemon／kernel／exec cpu 的 agent 整合（池表） |
| [test_agent_tools.py](test/test_agent_tools.py) | `tools add` 各情形，真 daemon／kernel／agent＋假模型照劇本用工具 |
| [test_agent_tools_manage.py](test/test_agent_tools_manage.py) | `tools` 元素 `$opt`（as／only）、`tools ls／rm／alias／unalias`、管理鎖串行化 |
| [test_agent_access.py](test/test_agent_access.py) | 權限牆 access.json 讀驗、重疊、送件快照、`access` 子命令、check／status |
| [test_access_more.py](test/test_access_more.py) | 權限牆補測：一批共用快照、壞表整批跑不起來、下一批才用新表、壞 JSON 拒寫 |
| [test_access_round2.py](test/test_access_round2.py) | 09-24 使用者裁決 1：檔案工具根＝整個 `/work`、唯讀掛點寫不進去、錯誤看得懂；真跑 bwrap（沒有就 skip）與不用 bwrap 兩路 |
| [test_jail.py](test/test_jail.py) | `aos-jail` 單元與真 bwrap（沒有就 skip）：路徑、環境、網路、唯讀 mount、經真 aos-exec 跑 |
| [test_tools_base.py](test/test_tools_base.py) | base 工具包：共用參數／config／OutsideRoot、read／write／edit／grep／find／ls |
| [test_tools_base_bash.py](test/test_tools_base_bash.py) | base 的 bash：輸出合併、cwd、退出碼、逾時、截斷、背景行程收掉 |
| [test_tools_base_fix.py](test/test_tools_base_fix.py) | base 工具包 astra 後修正：暫存檔與符號連結、大檔、CRLF、grep 各種退路、tools add 併發 |
| [test_tools_files.py](test/test_tools_files.py) | `proto5/tools/files/`：json_edit、md_section 兩支工具；files／wf 的 `_common.py` 跟 base 逐字一樣；描述字數；`tools add files` 裝得起來 |
| [test_tools_wf.py](test/test_tools_wf.py) | `proto5/tools/wf/`：workflows 工具包（wf_doc／wf_init／wf_lint／wf_residue／wf_table）；wf_init 兩個崩潰窗口真 SIGKILL 重跑收得回來 |
| [test_team_format.py](test/test_team_format.py) | 工具大開發時代 T1 第 0 步：團隊共用格式（spec/team/）、任務狀態機、問人、申請登記表、`aos-team` 分派 |

共用工具（不是測試檔）：[\_util.py](test/_util.py)（底層／agent）、[\_daemon_util.py](test/_daemon_util.py)
（控制協議孩子、輪詢、孤兒隔離 driver、`read_json`／`wait_for`）、[\_kernel_util.py](test/_kernel_util.py)
（真 daemon／kernel 測試家，`aos-kernel init --config` 建、`pools=` 傳池表）、[\_kernel_fake.py](test/_kernel_fake.py)
（假 daemon：只處理 `D/requests/` 的 scale 與 ack、手寫 summary.json，不拉任何 cpu）。
