← [code map 總圖](../code-map.md)｜[各分冊導覽](README.md)

## proto8 逐檔總覽（10-19 proto8-2 併入、舊 lib 進 git 後重寫）

（新增或刪檔時這裡與 [proto8/bin/README.md](../../../../proto8/bin/README.md)（aos-tick、aos-tools…）、[proto8/impls/README.md](../../../../proto8/impls/README.md)（C++ 命令列與庫）一起改。）

### `proto8/bin/`（Python 純標準庫）

逐支說明在 [proto8/bin/README.md](../../../../proto8/bin/README.md)。**10-23 Python 版刪了**（使用者 10-23）：`aos-exec`、`aos-loop`、`aos-fsm`、`aos-daemon` 與只有它們用的 `aos_inst.py`、`aos_loop.py`、`aos_run.py`、`aos_window.py` 刪了（在 git 歷史，刪前最後一版 60d677cc），四支只剩 C++ 版，見下面 `proto8/impls/`。

- `aos_flags.py`（10-21）：旗標解析 `parse()`（10-22 多收一張不帶值的旗標表 `switches`）；`Error.code`＝錯誤代號。aos-tick、aos-tools、aos-eca-turn 用；10-28～11-01 aos-parts 也用（10-23 刪了 `load_cfg()`、`target()`）。
- `aos-tools`（10-28）：agent 資料夾工具註冊檔 `tools.json` 的命令列；aos agent 範本與 aos-mcp 都經它。11-03 `add --no-cache`：exe 項記 `"cache": false`、每次重跑 `--tooldef`。
- ~~`aos-parts`~~（10-28 晚加、**11-01 刪**，A 題 parts 瘦身）：`parts.json` 換成 aos-exec 格式，找格（註冊檔 → 固定名字）改在 `lib/agent/parts.py`（器官共用，見 [proto8/12-agent-round](proto8/12-agent-round.md)）；`test_aos_parts.py` 一起刪、查找順序的測試在 `tests/test_round_parts.py`。
- `aos-daemon-ctl`（10-30，agent-lifecycle 實作第 7 步的補）：把東西掛到 daemon 上（add／rm 往 `$AOS_DAEMON_STACK/loops_ctl_mailbox/`〔11-02 原 `$AOS_DAEMON`、旗標 `--daemon-stack`〕（11-02 晚原 `loops_mailbox/`）投 `loops_added`／`execs_added`／`*_removed` 的信、經 aos-post；add 有 `loop.json`＝loop 子項（exec 是單子＝換成 `<XXX>/loop.json#/exec` 指回原檔，11-01 取代 pin_cd）、沒有＝`execs`；ls 讀 `loops_state.json` 兩張表（11-02 起只有還在跑的，另判 daemon 活不活〔`pid`＋`started_at_ticks`＋`boot_id` 對 /proc〕）；11-02 `--kind` 拿掉、`add XXX -- 參數...`〔exec 型＝`[XXX, 參數...]`，loop 型帶參數＝ArgumentsBad〕；10-30 eca 第 2 步 `add --ws`：子項物件帶 `ws`，ls 多一欄 ws（11-03 起不碰 `<WS>/.stack`：`link_stack`／`unlink_stack` 拿掉，[thinking 11-03 stack-where](../../../../proto8/thinking/2026-11-03-stack-where.md)）；11-03 `where --stack 名字`：表上（loops、execs）的才印小格 `<D>/loops/<名字>`〔`cell_of` 一處拼，[thinking 11-02 stack-tools](../../../../proto8/thinking/2026-11-02-stack-tools.md)〕、表上沒有＝`ProcMissing`；ls 與 where 共用 `read_state`）；**11-03 procs**（[thinking 11-03 procs](../../../../proto8/thinking/2026-11-03-procs.md)）：信箱改 `procs_ctl_mailbox/`、讀 `procs_state.json` 一張 `procs` 表（ls 沒有種類欄、stopped 的 pid 印 -、`--json`＝`{"procs": 表}`），add 一律寄 `procs_added`（loop 型一定帶 ctl／state）、多 `--stack S`（從呼叫的 cwd 轉絕對、不驗在不在，寫進子項物件的 `stack`；exec 型有 `--ws`／`--stack`＝`{"exec", "ws"?, "stack"?}`），rm＝`procs_removed`；新子命令 `stop`／`start`（寄 `procs_stopped`／`procs_started`）、`pause`／`resume`（不經 daemon，`write_cmd` 直接往它 stack 裡 `loop.json` 的 ctl 寫 `{"cmd", "seq": 現有＋1}`、印 seq）；`need_ctl`：stack 裡沒有 daemon 寫的 `loop.json`（exec 型）或 ctl 是 null＝`CtlMissing`、不送信（stopped 的列 start 不看）；`row_of`（表上沒有＝`ProcMissing`）；`where --stack`／`cell_of` 改讀那一列的 `stack`（不再自己拼 `<D>/loops/<名字>`）；**11-03 晚 sleep／wake**：表上多一態 `sleeping`（daemon 收工時還在跑的 loop 型、再開自動 wake），`start` 對 `sleeping` 的列同 `stopped` 不查 `loop.json`，其餘只改說明（sleep／wake 不是子命令）。測試 `tests/test_aos_daemon_ctl.py`（14 案）。
- `aos-round`（10-30）：11-01 刪了（使用者「刪掉」）；agent 的 loop.json 直接叫 aos-fsm 跑 `lib/agent/round/` 的表，見 [12-agent-round](proto8/12-agent-round.md)。
- `aos-eca-turn`（10-31 改名＋升 bin：前身 10-30 的 `lib/eca/turn/turn.py`，`lib/eca/` 整層刪了；C-54 R13）：`aos-eca-turn [--one] [--on-empty stop|idle] [--on-busy yield|answer] <定義>`＝外部 coding agent 的一輪（queue → `cli_session.ask` → history）；`--on-empty` 取代環境變數 `ECA_ON_EMPTY`、`--on-busy answer`＝不因 SessionBad 退讓；11-03 起不寫 trace；錯 `aos-eca-turn: 代號 原因`。逐檔見 [proto8/17-eca](proto8/17-eca.md)。測試 `tests/test_eca_turn.py`。
- `aos-tick`（10-21 晚，計畫第 4 段）：`aos-tick [旗標] FILE`＝時鐘往前走一格，讀 n 寫 n＋1（沒檔＝0，先寫 `.名字` 再改名）；唯一的位置參數、旗標表是空的；錯退 1 一行 `aos-tick: 代號 原因`（10-23 起帶代號）、檔不動。

### `proto8/demo/`

逐字下放到 [proto8/13-demo](proto8/13-demo.md)（本檔超過 8 KB）：agent-bob、ann、eve、daemon、daemon-2、daemon-3、tick 的逐檔說明；說明另在 [proto8/demo/README.md](../../../../proto8/demo/README.md)。

### `proto8/tests/`

逐字下放到 [proto8/02-tests](proto8/02-tests.md)、[proto8/02-tests-2](proto8/02-tests-2.md)（2026-10-21 晚，本檔超過 8 KB；後又拆成兩份）；10-24 新增的測試檔在 [proto8/08-tests-10-24](proto8/08-tests-10-24.md)（10-24 收尾實跑全部 452 個，5 個 skip；同日函式庫遷移後 453 個）。每個測試檔涵蓋什麼、幾個；共 248 個（10-23 改跑 C++ 版後 233，加 `test_dan.py` 14；10-24 `test_fsm.py` 的「物件＝表壞」換成兩案：物件＝內嵌單子、形狀壞＝自己的錯），`python3 -m unittest discover -s proto8/tests`（先建 impls）。

### `proto8/impls/` 與舊 lib

逐字下放到 [proto8/01-impls與舊lib](proto8/01-impls與舊lib.md)（2026-10-21 下午，本檔超過 8 KB）：impls 是使用者的 C／C++ 實作（10-23 起進 git；舊快照 `backup/` 10-23 已刪）；舊 lib 是 10-16 那套、10-19 刪進 git 歷史。

LLM kernel 兩支（`aos-llm-kernel`、`aos-llm-send`，10-24）的逐檔表另開一份：[proto8/03-llm-kernel](proto8/03-llm-kernel.md)。aos-daemon 的 `src/` 逐檔（10-29 下放；同日加信箱模式 `mailbox.cpp`；11-03 loops／execs 合成 `procs`、加 stop／start 與每項的 `stack`，tests 也列在那）：[proto8/14-aos-daemon](proto8/14-aos-daemon.md)。改 JSON 的工具集 `aos-json`（10-24）：[proto8/07-aos-json](proto8/07-aos-json.md)。投遞 `aos-post`、鎖 `aos-lock`（10-29）：[proto8/15-aos-post](proto8/15-aos-post.md)、[proto8/16-aos-lock](proto8/16-aos-lock.md)。

### agent-round 的格（10-28 晚）

`proto8/lib/agent/` 的 round、queue、history、compact（`_entry`、`ask.py`、`prompts/`）、act 與 `proto8/lib/endpoint/` 的 fake、openai（agent 自己的格，不是工具），範本 `demo/agent-nia`，加上 `tests/test_round_*.py`（endpoint、act、fsm、bin，共用 `round_common.py`）、`test_round_queue.py`、`test_lib.py` 跳過這些格：逐檔一列在 [proto8/12-agent-round](proto8/12-agent-round.md)、[proto8/12-agent-round-2](proto8/12-agent-round-2.md)（本檔超過 8 KB，另開分檔）。

### 外部 coding agent 的格（10-30）

`proto8/bin/aos-eca-turn`（claude／codex 當平級 agent 的一輪：queue → CLI → history；10-31 改名＋升 bin，前身 `lib/eca/turn`）、範本 `demo/eca-claude`、`eca-codex`（10-31 起沒有 `parts.json`）與 `tests/test_eca_turn.py`、`test_eca.py`：逐檔一列在 [proto8/17-eca](proto8/17-eca.md)。

### 10-24 一天的嘗試（收尾補）

各作者做的時候沒改 code map，10-24 下午收尾一次補成幾份分檔：

- demo 的 agent（eve、gus、hal、kai、liv、meg、pip；fay 11-03 晚刪、llm-kernel/agent-ivy 11-03 封存）逐檔：[proto8/04-demo-agents](proto8/04-demo-agents.md)、[04-demo-agents-2](proto8/04-demo-agents-2.md)。
- demo 的 talk、pi-tools、file-tools（self-improve、llm-kernel 11-03 封存到 proto8/archive/）：[proto8/05-demo-其他](proto8/05-demo-其他.md)、[05-demo-其他-2](proto8/05-demo-其他-2.md)。
- `proto8/extras/` 周邊工具 human、ai_tools、grow、langs/janet、langs/lua、sandbox（editors/nvim 11-03 封存）（10-26 從頂層收進）、eca（10-30 aos-eca，11-03 前叫 eca_ctl，前身 10-27 的 cli_hub，在 -3）：[proto8/06-周邊工具](proto8/06-周邊工具.md)、[06-周邊工具-2](proto8/06-周邊工具-2.md)、[06-周邊工具-3](proto8/06-周邊工具-3.md)；`proto8/lib`（函式庫，10-24 下午遷移後三層）：[proto8/09-lib](proto8/09-lib.md)。
- 10-24 新增的測試檔：[proto8/08-tests-10-24](proto8/08-tests-10-24.md)。

改 proto8 的檔就同步那份。
