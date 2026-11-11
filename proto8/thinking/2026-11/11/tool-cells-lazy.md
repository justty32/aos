# tool-cells-lazy：工具小格改成真的寫東西時才建（11-11，線 D）

← [2026-11-11](README.md)

## 使用者原話

> 我確實想改成工具真的寫東西時才建資料夾

背景：agent 每叫一支工具，`aos-tools call` 把子行程的 `AOS_STACK` 設成 `<父 stack>/tools/<工具名>/`（[P-17](../../../docs/CONVENTION/02-題目stack停錯腦/04-五-stack與六-停與錯.md)），叫的當下資料夾就建出來；大部分工具不存東西，stack 底下 `tools/` 一堆空資料夾。

## 誰在建（調查結果）

| 建立點 | 怎麼建 | 改法 |
|---|---|---|
| `aos-exec`（C++，`setup_stack`） | `AOS_STACK` 不管外面有沒有設都 `mkdir -p`（N-59 第 1 件；11-03 使用者「要自動建。要沿用外面的。」）。`aos-tools call` 最後 `execve aos-exec`，所以**真正建小格的是它** | 加不帶值的旗標 `--stack-lazy`：照算、轉絕對、結尾 `/`、export，**只是不建**；沒給＝行為不變。只管這一跳（字串轉向不帶過去，同其他旗標） |
| `aos-tools call` | 自己不建，交給 aos-exec | 有父 stack 時叫 `aos-exec --stack-lazy`；父沒設（交 aos-exec 給預設 `.stack/`）照舊 |
| `templates/agent-fsm/act.py` | 叫之前自己 `mkdir`（為了看子帳記號 `.observed_child.json`） | 拿掉；`clear_child`／`take_child` 本來就容許不在 |
| `lib/observed.py` 的 `call`（measure、review_round、watch 叫下層用） | 自己 `mkdir` 再 `aos-exec` | 拿掉 mkdir、加 `--stack-lazy` |
| `lib/agent/cli_session.py` 的 `Cell`（claude／codex 工具、eca 的 attach） | 建構時就 `makedirs` | 工具形照舊（它一定會寫對話、session）；只有 attach 列表（只看）改 `Cell(…, make=False)`，不再替每支 cli 工具建空小格 |
| aos-mcp、eca 那條路 | 只傳自己的 stack，交 `aos-tools call` | 不用改 |
| `subagent` 跑子的 `self_*` | 直接跑 `_entry`、`AOS_STACK=<子 stack>/tools/<那支>/`，本來就不建 | 不用改 |

## 會寫的工具（寫前自己建，檢查結果）

`proto8/lib`、`proto8/py` 沒有共用的「往 stack 寫檔」helper，各自已經 mkdir，所以沒有新增 helper：

- `subagent`：`write_book` 寫 `subagents.json` 前 `makedirs`（原本就有）；讀帳不在＝`[]`。
- `shell`、`run_python`：`shell_observed.prepare` → `observed.prepare_strict` 先 `mkdir(parents=True)` 再寫 `interfaces.json`／`observed.jsonl`。
- `do_task`（施工當時叫 thought）：`makedirs(children/)`。claude／codex：`Cell` 建構時建。`copy_child` 寫前 `mkdir(parents=True)`。
- `aos-sandbox`（沙箱包著的工具）：`rw` 綁 `$AOS_STACK` 而它不在原本會 `PathMissing`——改成 rw 裡**正好是 `$AOS_STACK`** 而它不在就先建，其他路徑不在照舊 `PathMissing`（`--dry-run` 不建）。
- tooldef 快取（`aos-tools` 的 `$AOS_STACK/tooldef_cache.json`）：規則本來就是「`AOS_STACK` 沒設或不是資料夾＝不快取、不寫任何檔」，沒改。它平常寫在 agent 的 stack（`aos-agent tools` 給的是 agent stack），不是工具小格。
- hook 小格 `$AOS_STACK/hooks/<名>/`：使用者這次講的是工具，hook 照舊（`hooks.py` 跑 hook 前建）。

讀自己小格的地方都容許不在：`ctl state` 的 subagents（`FileNotFoundError`＝`[]`）、`ctl ls` 看 `busy.txt`（`exists`）、`shell_report`／`measure` 的 `records`（沒 `interfaces.json`＝`[]`）、`observed_children`、`ctl who`（`realpath` 對不存在的路徑照算）。

## 代定（線 D 自己定的小事）

1. 機制選「aos-exec 加旗標、aos-tools 傳」，不選「aos-tools 叫完把空的收掉」：後者跟 P-17「叫完不自動收」字面衝突、要把 `execve` 改成留下來當監工（訊號轉送、結束碼），而且同名工具同時叫時會刪到別人剛要用的資料夾。
2. 旗標名 `--stack-lazy`（C-54 主題放前面）；只管這一跳、字串轉向不帶過去（照 N-58「旗標只管這一次」）。
3. 父 stack 沒設時（aos-exec 給預設 `$WS/.stack/`）照舊建，不在這次範圍。
4. `aos-sandbox` 只對 `$AOS_STACK` 開例外，不是「rw 不在一律建」（打錯路徑照樣報錯）。
5. 條文只加 11-11 註：P-17、名詞表「小格」、N-58（第四個旗標）；aos-exec、aos-tools、aos-sandbox 的 README／docs、兩個 knowledge 節點（`aos/me.json` 的 `tools/<name>/` 那行、`aos/cli/tools.json` 的 11-06 note）各補一句事實。

## 要重建什麼

不用重建。已經在的空 `tools/<名>/` 留著無害，要清就手動 `rmdir`；試驗場之後重刷時自然沒有。

## 驗證

- build：`proto8/impls` 全建過。
- 新測試：`impls/aos-exec/tests/test_stack_lazy.py`（4 支：lazy 不建、配 `--stack` 也不建、沒給照建、`--stack-lazy=1`＝ArgumentsBad）；`cmd/aos-tools/tests/test_cell_lazy.py`（2 支：只讀工具不留資料夾、會寫的工具自己建）——先對舊版 aos-tools 跑確認會紅。`templates/tests/agent-fsm/test_integration.py`（真 kernel＋`llm_fake` 假腦叫 `peek_now_time`）加一句：跑完 agent stack 沒有 `tools/`。
- 實跑（暫存資料夾、真 aos-daemon、範本 agent-fsm 生一隻 mom、暫停它，把假腦會給的 tool_calls 一輪一輪寫進 history 交範本的 `act.py`）：`peek_now_time`、`math`、`knowledge_read ls`、`self_state`、`shell`、`subagent ls／add kid／ls／rm --purge` 全部退 0、結果對；跑完 `tools/` 底下只有 `shell`（`interfaces.json`、`observed.jsonl`）與 `subagent`（`subagents.json`、`daemon_reply`）。
- 受影響各夾的 Python 測試（改完後重跑）：aos-tools 103、aos-exec 12、aos-eca 58、aos-mcp 17、lib/tests 32、lib/agent/tests 16、subagent 18、thought 4、self_state 3、measure 26、review_round 12、watch 11、shell_report 5、shell 5、run_python 5、templates/tests/agent-fsm 73、judge-llm 4、reviewer 1、tool-python 4 全綠；第一輪全量（act.py 那處還沒改前）另有 50 夾全綠；全部改完後 test_daily（假腦假 claude 的兩台機器日常劇本）20 支再跑一次 OK（skipped 2、expected failures 2）。紅的只有兩處、都跟這次無關、改前也紅：`cmd/aos-agent` 的 `test_daemon_down` 2 支（這台 WSL 的 pid 命名空間不是最外層，`daemon_up` 照設計不核）、`lib/aos/box_check` 2 支（缺 `s6-softlimit`）。
- aos-sandbox：手跑 `rw` 綁一個不在的 `$AOS_STACK`，裡面寫得進去；`--dry-run` 不建。

## 待裁

（11-11 已裁：選乙，見下面「[線 F 裁定](#線-f-裁定loopfsm-自己建11-11)」。）

**直接當工具登記的 agent（入口是 `aos-loop`／`aos-fsm`）**：這兩支往 `$AOS_STACK` 寫窗、`stage.txt` 不會先建資料夾（N-28／N-59「建 stack 只在 aos-exec 做」），所以小格不在＝`WriteFailed`。repo 裡現在沒有這樣登記的（範本 agent 都經 `aos-agent ctl add` 掛 daemon，daemon 自己建 proc 的 stack；沙箱包著的 `examples/agent.json` 靠上面 aos-sandbox 那條會先建）。選項：

- 甲（現狀）：不管；要把 agent 直接當工具的，入口自己先 `mkdir -p "$AOS_STACK"`，或走 `subagent`／daemon。
- 乙：aos-loop、aos-fsm 起來時 `$AOS_STACK` 不在就建（改「建 stack 只在 aos-exec 做」這條）。
- 丙：`aos-tools call` 對資料夾／JSON 種類照舊建、只有可執行檔不建（lib 工具都是 python，會變回「lib 工具也建」，等於沒做）。

## 沒驗到的

- 真腦（照交代不跑）；試驗場沒重刷（照交代不動 `~/code/playground*`）。
- 沙箱實跑 shell-boxed：這台缺 `s6-softlimit`，`lib/aos/box_check` 兩支照舊紅（改前也紅）。
- 字串轉向的登記工具：轉向後的那一跳不吃 `--stack-lazy`，照舊會建；沒有實例、沒測。

## 線 F 裁定：loop／fsm 自己建（11-11）

### 使用者原話

上面待裁題，使用者在選項框選了：

> loop／fsm 自己建

（選項說明：aos-loop、aos-fsm 起來時發現 stack 不在就自己建。會改掉「建 stack 只在 aos-exec 做」這條規則。）

接著追加：

> stack只能在aos-exec建<-這個規則刪除

### 做法

- **一個點、兩處叫**：aos-loop 的公開 API 加 `aos::loop::make_stack()`（`impls/aos-loop/src/engine/stack.cpp`）：`$AOS_STACK` 有設、不是空的、路徑不在＝`mkdir -p`（相對路徑照 cwd，同窗的算法）；沒設或已經在（不管是不是資料夾）＝什麼都不做；建不了＝`MkdirFailed`，訊息 `cannot create AOS_STACK: <路徑> (<原因>)`（跟 aos-exec 同一句）。aos-loop 的 `main` 在設定讀過（`Loop` 建好）之後、`serve` 之前叫；aos-fsm 的 `main` 在表查過（`check`）之後、`read_state` 之前叫。設定／表壞的不建資料夾。
- **`Loop` 類別本身不叫**，所以 aos-daemon（繼承 `Loop`）行為不變：照舊不建自己的 stack。
- **規則刪掉的地方**（不是獨立一條，都是某條裡的一句；各加 11-11 註記原句與原話）：NORMS N-59 第 1 件（「工作區在不在、建 stack、轉絕對路徑只在這裡做」拿掉「建 stack」）、NORMS 04 開頭 ③（「aos-loop 不自己建——建 stack 只在 aos-exec 做」整句）、N-28 daemon 小格那段的括號。改成事實描述的：aos-daemon docs/02 與 `child.cpp`、`mailbox.cpp` 註解（daemon 照舊不建）、aos-exec `env.hpp` 註解、aos-loop `loop.hpp`／`inline.cpp`／docs 02、03、aos-fsm docs 01、02。knowledge 節點沒有寫這條規則（`aos/me.json`「小格寫東西才建」、`aos/cli/tools.json`「寫的工具自己建」照樣成立），沒動。
- 現在 stack 不在時誰建：aos-exec 預設建（`--stack-lazy` 那一跳不建）；aos-loop、aos-fsm 起來時不在就建；工具寫小格前自己建；aos-daemon 不建自己的 stack。

### 代定

1. 建的時機放在「設定／表驗過之後」：壞設定不留空資料夾。
2. `$AOS_STACK` 在但不是資料夾＝不碰，之後照舊 `WriteFailed`（只管「不在」這一種）。
3. 窗全關（`ctl`／`state`／`state_flux` 都 `null`）也照建：照使用者的說法「起來時發現 stack 不在就自己建」，不看窗開不開。
4. 內嵌單子行程內跑（`run_inline`）照舊不建；那時 loop／fsm 起來已經建過了。

### 要重建什麼

不用重建。

### 驗證

- build：`proto8/impls` 全建過。
- 新測試：`impls/aos-loop/tests/test_stack_make.py`（4 支：不在的兩層 stack 會建、state 照寫；相對路徑照 cwd；建不了＝`MkdirFailed`；設定壞不建）、`impls/aos-fsm/tests/test_stack_make.py`（3 支：會建、格寫進去、`stage.txt` 照寫；建不了；表壞不建）。先把兩處 `make_stack()` 註掉重建跑過，loop 紅 2、fsm 紅 1，再還原。
- 實跑線 D 的情境（暫存資料夾）：資料夾工具 `tl`（`_entry`＝`["aos-loop", "loop.json"]`，窗照預設開）與 `tf`（`_entry`＝`["aos-fsm", "fsm.json"]`）用 `aos-tools add` 登記、`AOS_STACK=<暫存>/stack aos-tools call` 叫：都退 0、沒有 `WriteFailed`；`stack/tools/tl/` 有 `body.txt`、`state.json`、`state_flux.json`，`stack/tools/tf/` 有格寫的檔與 `stage.txt`（叫兩次 s→t→s）。
- 受影響各夾測試（改完重建後）：aos-loop 13、aos-fsm 3、aos-exec 12、aos-daemon 75、aos-tools 103、aos-daemon-ctl 32、aos-mcp 17、subagent 18、lib/agent/tests 16、templates/tests/agent-fsm 73 全綠；aos-agent 58 支紅 2（`test_daemon_down` 的 `test_add`／`test_stop`，線 D 記過的環境問題、改前也紅）；`templates/tests/test_daily`（兩台機器日常劇本）16 支 OK（skipped 2、expected failures 2）。

### 待裁

（11-11 已裁：選「也自己建」，見下面「[線 H 裁定](#線-h-裁定daemon-也自己建11-11)」。）

- **aos-daemon 要不要也自建自己的 stack**：規則刪了以後，daemon 不建只剩「現狀」這個理由（N-28、daemon docs 02、`mailbox.cpp`）。這次照交代只改 loop／fsm，daemon 沒動。選項：甲 照舊不建（現狀）；乙 daemon 起來時也 `make_stack`（daemon 直接當工具登記、或直接跑時不再 `WriteFailed`／`MkdirFailed`）。

### 沒驗到的

- 真腦、試驗場（照交代不動 `~/code/playground*`）。
- 經 `subagent`／daemon 起的 agent：路徑沒變（daemon 先建 proc 的 stack），沒另外實跑。

## 線 H 裁定：daemon 也自己建（11-11）

### 使用者原話

線 F 的待裁「aos-daemon 要不要也自建自己的 stack」，使用者在選項框選了：

> 也自己建

（選項說明：跟 loop／fsm 一致：直接跑或直接當工具登記時，不會再因為 stack 不在而報錯。要動 daemon 和 N-28 的描述。）

### 做法

- **共用線 F 的 `aos::loop::make_stack()`**，不另寫一份：aos-daemon 的 `Daemon` 建構子（`impls/aos-daemon/src/daemon/daemon.cpp`）在設定全部驗過（procs、指示詞、信箱名、小格檔名、兩扇管轄窗、`limits`、`adopt`）之後叫一次；放在算 `AOS_DAEMON`（`dstack_` 的 `canonical`）、上鎖（`check_running` 用 flock 鎖 stack 資料夾）、`adopt`、開信箱之前——這幾步都要 stack 已經在（不在的話鎖不到、`AOS_DAEMON` 解不開捷徑、信箱 `MkdirFailed`）。規則同線 F：`$AOS_STACK` 有設、不是空、路徑不在＝`mkdir -p`（相對照 cwd）；已在（不管是不是資料夾）不碰；建不了＝`MkdirFailed cannot create AOS_STACK: <路徑> (<原因>)`、退 1；沒設照舊 `StackMissing`。
- `Loop` 類別本身照舊不叫；子 loop（daemon fork 出來跑同一個 `Loop`）不經 `make_stack`，它們的小格由 daemon 先建好。
- 條文與文件（事實描述＋11-11 再註，附原話）：N-28 小格那段、NORMS 04 開頭 ③ 的 11-11 註、N-59 第 1 件的 11-11 註；aos-daemon docs 01（`$AOS_STACK` 那條）、02（預設小格那句）、05（信箱起來時）、06（狀態窗寫不了）；程式註解 `child.cpp`、`child.hpp`、`mailbox.cpp`（兩處）、`table.cpp`、`daemon.hpp`、aos-loop `loop.hpp`（三處）、`inline.cpp`、aos-exec `env.hpp`。
- 現在 stack 不在時誰建：aos-exec 預設建（`--stack-lazy` 那一跳不建）；aos-loop、aos-fsm、aos-daemon 起來時不在就建；工具寫小格前自己建。

### 代定

1. 建的時機＝建構子裡設定驗過之後、上鎖之前（比照線 F「設定驗過才建」；不能放 `main` 建構完之後，因為鎖、adopt、信箱都在建構子裡就要 stack）。`check_running` 讀舊 `state.json` 看有沒有活著的 daemon 也在之後，stack 剛建好時當然沒有。
2. 已存在但不是資料夾＝不碰：之後照舊由後面各步報自己的錯（實測 `AOS_STACK=<一個檔>`：`WriteFailed cannot keep <檔>/procs_state.json as …: Not a directory`，adopt 想收舊表時報的，退 1、檔沒被動）；`mailbox.cpp` 那道 `is_dir` 檢查留著當最後一道。
3. 窗與信箱全關也照建（同線 F 代定 3）。
4. 訊息用同一句 `cannot create AOS_STACK: …`，開頭換成 `aos-daemon:`（`aos::fail` 給的）。

### 要重建什麼

不用重建。

### 驗證

- build：`proto8/impls` 全建過（頂層 `build/`）。
- 新測試 `impls/aos-daemon/tests/test_stack_make.py`（5 支：不在的兩層 stack 會建、`state.json`／`procs_state.json`／信箱 `procs_requests/new` 都在；相對路徑照 cwd；建不了＝`MkdirFailed cannot create AOS_STACK: `；`$AOS_STACK` 是檔＝不碰、退 1；設定壞（`adopt: "yes"`）＝`CfgBad`、不建）。改 daemon 之前先對舊版跑：紅 3（會建、相對路徑、建不了那句訊息；舊版報的是 `MkdirFailed cannot create mailbox … ($AOS_STACK is missing: …)`），改完綠 5。
- 實跑（`/tmp/lineH-run`）：資料夾工具 `td`（`_entry`＝`exec aos-daemon daemon.json`、`max: 2`）用 `aos-tools add` 登記，`AOS_STACK=/tmp/lineH-run/stack aos-tools call td {}`（`stack/` 本身也不在）：退 0，`stack/tools/td/` 有 `state.json`、`state_flux.json`、`procs_state.json`、`procs_requests/{tmp,new,cur}`。
- 受影響各夾（改完重建後）：aos-daemon 80（原 75＋新 5）、aos-loop 13、aos-fsm 3、aos-exec 12、aos-daemon-ctl 32、templates/tests/agent-fsm 73 全綠；`templates/tests/test_daily`（兩台機器日常劇本）16 支 OK（skipped 2、expected failures 2）。

### 沒驗到的

- 真腦、試驗場（照交代不動 `~/code/playground*`）。
- 用 `aos-exec` 起 daemon 的慣用路徑沒變（aos-exec 先建好），只靠上面的 test_daily、agent-fsm 間接跑到。
- 跑的途中 `$AOS_STACK` 被刪：行為沒改（只在起來時建一次），沒另測。
