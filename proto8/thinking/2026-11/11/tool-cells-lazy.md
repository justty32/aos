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

- `subagent`：`write_children` 寫 `children.json` 前 `makedirs`（原本就有）；讀帳不在＝`[]`。
- `shell`、`run_python`：`shell_observed.prepare` → `observed.prepare_strict` 先 `mkdir(parents=True)` 再寫 `interfaces.json`／`observed.jsonl`。
- `thought`：`makedirs(children/)`。claude／codex：`Cell` 建構時建。`copy_child` 寫前 `mkdir(parents=True)`。
- `aos-sandbox`（沙箱包著的工具）：`rw` 綁 `$AOS_STACK` 而它不在原本會 `PathMissing`——改成 rw 裡**正好是 `$AOS_STACK`** 而它不在就先建，其他路徑不在照舊 `PathMissing`（`--dry-run` 不建）。
- tooldef 快取（`aos-tools` 的 `$AOS_STACK/tooldef_cache.json`）：規則本來就是「`AOS_STACK` 沒設或不是資料夾＝不快取、不寫任何檔」，沒改。它平常寫在 agent 的 stack（`aos-agent tools` 給的是 agent stack），不是工具小格。
- hook 小格 `$AOS_STACK/hooks/<名>/`：使用者這次講的是工具，hook 照舊（`hooks.py` 跑 hook 前建）。

讀自己小格的地方都容許不在：`ctl state` 的 children（`FileNotFoundError`＝`[]`）、`ctl ls` 看 `busy.txt`（`exists`）、`shell_report`／`measure` 的 `records`（沒 `interfaces.json`＝`[]`）、`observed_children`、`ctl who`（`realpath` 對不存在的路徑照算）。

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
- 實跑（暫存資料夾、真 aos-daemon、範本 agent-fsm 生一隻 mom、暫停它，把假腦會給的 tool_calls 一輪一輪寫進 history 交範本的 `act.py`）：`peek_now_time`、`math`、`knowledge_read ls`、`self_state`、`shell`、`subagent ls／add kid／ls／rm --purge` 全部退 0、結果對；跑完 `tools/` 底下只有 `shell`（`interfaces.json`、`observed.jsonl`）與 `subagent`（`children.json`、`daemon_reply`）。
- 受影響各夾的 Python 測試（改完後重跑）：aos-tools 103、aos-exec 12、aos-eca 58、aos-mcp 17、lib/tests 32、lib/agent/tests 16、subagent 18、thought 4、self_state 3、measure 26、review_round 12、watch 11、shell_report 5、shell 5、run_python 5、templates/tests/agent-fsm 73、judge-llm 4、reviewer 1、tool-python 4 全綠；第一輪全量（act.py 那處還沒改前）另有 50 夾全綠；全部改完後 test_daily（假腦假 claude 的兩台機器日常劇本）20 支再跑一次 OK（skipped 2、expected failures 2）。紅的只有兩處、都跟這次無關、改前也紅：`cmd/aos-agent` 的 `test_daemon_down` 2 支（這台 WSL 的 pid 命名空間不是最外層，`daemon_up` 照設計不核）、`lib/aos/box_check` 2 支（缺 `s6-softlimit`）。
- aos-sandbox：手跑 `rw` 綁一個不在的 `$AOS_STACK`，裡面寫得進去；`--dry-run` 不建。

## 待裁

**直接當工具登記的 agent（入口是 `aos-loop`／`aos-fsm`）**：這兩支往 `$AOS_STACK` 寫窗、`stage.txt` 不會先建資料夾（N-28／N-59「建 stack 只在 aos-exec 做」），所以小格不在＝`WriteFailed`。repo 裡現在沒有這樣登記的（範本 agent 都經 `aos-agent ctl add` 掛 daemon，daemon 自己建 proc 的 stack；沙箱包著的 `examples/agent.json` 靠上面 aos-sandbox 那條會先建）。選項：

- 甲（現狀）：不管；要把 agent 直接當工具的，入口自己先 `mkdir -p "$AOS_STACK"`，或走 `subagent`／daemon。
- 乙：aos-loop、aos-fsm 起來時 `$AOS_STACK` 不在就建（改「建 stack 只在 aos-exec 做」這條）。
- 丙：`aos-tools call` 對資料夾／JSON 種類照舊建、只有可執行檔不建（lib 工具都是 python，會變回「lib 工具也建」，等於沒做）。

## 沒驗到的

- 真腦（照交代不跑）；試驗場沒重刷（照交代不動 `~/code/playground*`）。
- 沙箱實跑 shell-boxed：這台缺 `s6-softlimit`，`lib/aos/box_check` 兩支照舊紅（改前也紅）。
- 字串轉向的登記工具：轉向後的那一跳不吃 `--stack-lazy`，照舊會建；沒有實例、沒測。
