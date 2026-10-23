# proto8/demo — 兩隻 agent 跑一遍

← [proto8](../README.md)｜程式：[impls](../impls/README.md)（aos-exec、aos-loop、aos-fsm、aos-daemon，C++）、[bin/README](../bin/README.md)（aos-tick）｜慣例：[CONVENTION](../CONVENTION.md)

```
sh proto8/demo/run.sh      # 在 WSL／Linux 跑
```

`run.sh` 各建一個暫時工作區、放一題 `new/q1.txt`（10-23 改名，原 `inbox/`）、`cd` 進去跑 agent-bob 與 agent-ann（慣例用法 `aos-exec <agent資料夾>`），再跑一次 daemon、最後跑一次 tick（見下）〔10-23 加 agent-dan（假腦），共五段：bob、ann、dan 三隻 agent，加 daemon、tick〕，印工作區內容（`out/`、`done/`；跑完 `new/`、`cur/` 是空的）與整棵 stack 樹（`$AOS_WS/.stack/`，10-23 改名，原 `.aos/`）（每檔印內容），最後把暫時資料夾刪掉，repo 裡不留東西。**PATH 由 `run.sh` 自己放**：aos 的程式都不動 PATH（ideas § 24，使用者「也套用，都不動path吧」），agent 裡寫的 `aos-loop`、`aos-fsm`、`aos-exec`、`aos-daemon`、`aos-tick` 要呼叫端事先放進 PATH——`run.sh` 開頭就這麼做：10-23 起前四支是 C++ 的 `proto8/impls/<名>/bin/`（使用者「python版本可以刪掉了。aos-exec/loop/daemon都用C++」，fsm 也改 C++、tick 先留 Python；要先建，見 [testing](../../wf/workflows/testing.md#proto8不在-ctest-裡)），aos-tick 是 `proto8/bin/`；沒建好 `run.sh` 會先停、說要先建。自己手動跑也一樣（例：`PATH=$PWD/proto8/impls/aos-exec/bin:$PWD/proto8/impls/aos-loop/bin:$PWD/proto8/impls/aos-fsm/bin:$PATH aos-exec --ws <工作區> proto8/demo/agent-bob`）。預設假腦；`AOS_BRAIN_URL`（OpenAI 相容 base URL，另可設 `AOS_BRAIN_MODEL`、`AOS_BRAIN_KEY`）指到遠端才用真腦〔10-23：agent-dan 的模型名在它自己的 `.env`（`AOS_BRAIN_MODEL`），只要給 `AOS_BRAIN_URL`，見下〕。**這台電腦不要跑本機模型**（10-19 LM Studio 讓整台 Windows 當機，使用者定「放棄跑本機模型」，[ideas § 6](../thinking/2026-10-19-ideas.md)）。

## agent-bob（混合範本，叫 cathy、cathy 叫 stamp：四層）

入口 `_entry`（預設 `$AOS_ENTRY`；10-19 晚改，原 `.aos/exec`；10-23 改名，原 `_exec`）＝`exec aos-loop loop.json`（10-21 傍晚：設定檔是 aos-loop 唯一的位置參數）；`loop.json`＝`{"exec": "fsm.json", "max": 20}`（`exec` 是 aos-exec 的目標，10-21；10-23 統合一度改叫 `val`、同晚改回 `run`，深夜再改 `exec`（使用者「exec，loop／daemon 的 run 也一起改 exec」））；`fsm.json` 帶 `"_entry": ["aos-fsm", {"$env": "AOS_CF"}]`（`AOS_CF`＝aos-exec 實際跑的那份檔），所以它本身就是 aos-exec 的入口、每次 `aos-exec -- fsm.json`（10-21 計畫第 3 段）；表一份看完：idle／act 是子資料夾 `idle/`、`act/`（shell），think 是內嵌單子——`"exec": "fsm.json#/states/think/body"`（fsm 格 10-23 深夜改名，原 `val`；使用者「fsm.json，現在是用val，幫我改成exec」）、單子放那格的 `body`（`python3 brain.py`、stdout 導到 `$AOS_STACK/plan.txt`、逾時 120 秒，aos-exec 當監工）。idle 在 `new/` 空時回 10 讓 loop 停。`brain.py` 挑 `new/` 第一題、搬到 `cur/` 認領（Maildir 的 new → cur）、題名寫 `current.txt`、答案印到 stdout。

act 把 `plan.txt` 當題目交給 `act/tools/cathy/`（另一隻完整 agent，同一套範本；P-32、P-33）：在她的小格 `$AOS_STACK/cathy/` 裡備 `ws/new/<題名>`、`AOS_STACK=$sub aos-exec --ws "$sub/ws" tools/cathy`、從 `$sub/ws/out/<題名>` 拿答案寫進 `$AOS_WS/out/`、題目從 `cur/` 搬 `done/`；cathy 失敗（非 0）bob 的 act 說「cathy 失敗」並退 1。cathy 的 act 再經 `act/tools/cathy/act/tools/stamp`（工具，自己的 stack 在 `$AOS_STACK/stamp/`，前面加一行 UTC 時間戳、`runs.txt` 計次）寫她的 out。一次跑完是四層：bob 的 loop／fsm → act → cathy 的 loop／fsm → 她的 act → stamp；`aos-exec --ws <工作區> proto8/demo/agent-bob/act/tools/cathy` 也能單獨跑 cathy。

stack 樹＝呼叫樹：`.stack/{state.txt,current.txt,plan.txt,trace.jsonl}`、`.stack/cathy/{…,ws/{out,done}/q1.txt,stamp/runs.txt}`（P-38）。

## agent-ann（全內嵌對照）

跟 bob 做同一件事（一題一答），零子資料夾：入口 `_entry`＝`exec aos-exec loop.json`，`loop.json` 是 `{"_entry": ["aos-loop", {"$env": "AOS_CF"}], "exec": "loop.json#/body", "body": {"argv": ["aos-fsm", "fsm.json"]}, "max": 20}`——loop.json 自己帶 `_entry`，`aos-exec loop.json` 就把 loop 跑起來（10-21 傍晚；跟 bob 的 `exec aos-loop loop.json`、`"exec": "fsm.json"` 對照，兩種都行），`fsm.json` 三格全是單子（`"exec": "fsm.json#/states/<名>/body"`、單子放 `body`），各指一支小腳本——`idle.py`（`new/` 空退 10）、`brain.py`（同 bob 的那份，複製）、`act.py`（`plan.txt` 寫 out、題目從 cur 搬 done）。資料夾裡只有 `_entry`、`loop.json`、`fsm.json`、三支 `.py`，和一份 `.env` 範例（10-22，全是註解、不設任何東西：示範 API key 與 `PATH=${AOS_CD}/bin:${PATH}` 怎麼寫。10-22 起 `.env` 預設不蓋環境裡已有的名字，PATH 那行要從外面叫 `aos-exec --dotenv-override agent-ann` 才生效；旗標只管那一次，入口的 `aos-exec loop.json`、loop 每次、fsm 每格三層照樣各讀一次這份檔但不蓋，所以格裡的 PATH 只多一份 `${AOS_CD}/bin`——原本是四份）。適合「格全是一行、不叫工具」的小 agent；要叫工具、要用 sh 搬檔，就回到 bob 的混合寫法。

## agent-dan（真腦＋工具，10-23）

會問真模型、會用工具的問答 agent（範本，混合寫法接 bob：idle 是資料夾，think／act 是內嵌單子）。慣例是 [P-41](../CONVENTION/02-題目stack停錯腦.md)，設計結論在 [thinking 2026-10-23-tool-calls](../thinking/2026-10-23-tool-calls.md)。

```
agent-dan/
  _entry              #!/bin/sh、exec aos-loop loop.json
  loop.json           {"exec": "fsm.json", "max": 40}
  fsm.json            三態 idle → think → act → idle；think、act 是 body 裡的單子（逾時 120 秒、60 秒）
  .env                AOS_BRAIN_MODEL=chatgpt-gpt-6-luna-low（模型名；不蓋外面已設的）
  system.txt          核心人格：每次問腦時當 system 訊息送、不進 history
  idle/_entry         同 bob：cur/ 或 new/ 有題退 0，沒題退 10
  brain.py            think 格：認領題目、把 tools/*/tool.json 組成 tools、帶 history 問腦、回覆接一行
  act.py              act 格：有 tool_calls 就逐個 aos-exec tools/<名>、結果接回 history；沒有就把 content 寫成答案
  tools/math/         工具：stdin 收 {"expr": "17*23"}、stdout 印 391（只做四則運算）
  tools/clock/        工具：stdin 不讀、stdout 印 UTC 時間
  tools/*/tool.json   給模型看的說明（OpenAI function 物件去掉 name；工具名＝資料夾名）
```

一題的流程：think 把題目接成一則 user、問腦；腦要叫工具，act 就跑工具（`arguments` 從 stdin 進、stdout 整段是結果，小格 `$AOS_STACK/<名>/`）、把結果接回 history、退 0 回 idle；題目還在 `cur/`，所以 think 帶著 history 再問一次；腦不叫工具了，act 才把回答寫進 `out/<題名>`、題目搬 `done/`。trace 是 `idle think act idle think act idle`。對話在 `$AOS_STACK/history.jsonl`（一行一則 OpenAI message，只附加）。

**假腦**（沒設 `AOS_BRAIN_URL`，demo 與測試用）：history 最後一則是 user 且有 `clock` 工具就叫一次 `clock`，拿到結果後回 `FAKE ANSWER to: 題目`——不連網也走得完「想 → 工具 → 想 → 答」。

**真腦**：`AOS_BRAIN_URL=http://localhost:4000/v1 aos-exec --ws <工作區> proto8/demo/agent-dan`（家機的 LiteLLM，不用 key；PATH 照上面放好）。模型名在 `.env`，要換就在那一行前面加 `AOS_BRAIN_MODEL=…`。真跑的工作區放 `~/code/try/agent-dan/`（使用者 10-23「試驗場放在~/code/try」）。

**錯**（都是 stderr 一行 `agent-dan: 代號 原因`、退 1、state 不動、history 不接；修好再跑一次從同一格接著做）：`BrainFailed`（腦連不上、HTTP 非 2xx）、`ReplyBad`（回覆不是 OpenAI 的形狀）、`ToolUnknown`（叫了 `tools/` 裡沒有的工具）、`ArgumentsBad`（`arguments` 不是 JSON）、`ToolFailed`（工具退非 0）。

## daemon（一個 daemon 同時管 bob、ann，10-20）

`daemon/_entry`＝`exec aos-daemon daemon.json`；`daemon.json` 是 `{"max": 10, "interval_ms": 200, "ctl", "state", "loops": {"bob": …, "ann": …}}`（`loops` 10-23 統合前叫 `children`），每個子項是一份 loop 設定：`{"exec": "daemon.json#/loops/bob/body", "max": 1, "body": {"argv": ["aos-exec", "--ws", {"$env": "AOS_WS", "$path": "bob"}, "../agent-bob"]}}`（ann 同樣；10-21 起子項的 `exec`（當時叫 `run`）是 aos-exec 的目標，內嵌單子放在那個子項自己的 `body`，路徑從 daemon 的 cwd＝`demo/daemon/` 算——10-21 傍晚起子 loop 經 aos-exec 起、cwd 是小格，daemon 寫小格時把 `exec` 轉成絕對路徑，所以照樣指得到）——子 loop 跑一次那隻 agent，工作區是 `$AOS_WS/bob`、`$AOS_WS/ann`。`run.sh` 最後一段建暫時工作區、在 `bob/new/`、`ann/new/` 各放一題、`aos-exec` daemon：它跑 10 次（約 2 秒）就結束、結束前收掉子項。stack 樹：`.stack/state.json`（daemon 的 state，`loops` 表）、`.stack/bob/`、`.stack/ann/`（各子項的小格：daemon 寫的 `loop.json`（`exec` 已轉絕對、帶 `_entry`）、子 loop 的 `state.json`、`stderr.txt`，以及那隻 agent 自己的 `state.txt`、`current.txt`、`plan.txt`、`trace.jsonl`…——agent 的 stack 就是小格，因為 `AOS_STACK` 已經有值、aos-exec 沿用）。子 loop 結束後不重起，所以表上兩項最後都是 `done`（子 loop 自己結束；daemon 收掉的才是 `stopped`，10-23 統合前兩種都叫 `exited`）、`code` 0。state.json 長這樣：`{"kind": "state", "phase": "done", "runs": 10, "max": 10, …, "loops": {"bob": {"pid", "started_at_ticks", "phase": "done", "code": 0, "signal": null}, …}, "code": 0, "pid", "started_at_ticks", "boot_id", "at": "2026-10-23T02:46:30.317+00:00"}`；各 agent 的 `trace.jsonl` 一行 `{"at": "…T02:46:27.633+00:00", "state": "idle", "code": 0, "signal": null, "elapsed_ms": 14}`。

## tick（時鐘，10-21 晚）

`tick/_entry`＝`exec aos-loop loop.json`；`loop.json`＝`{"exec": "loop.json#/body", "body": {"argv": ["aos-tick", {"$env": "AOS_STACK", "$path": "tick.txt"}]}, "max": 5}`——loop 跑 5 次，每次 `aos-exec -- loop.json#/body`，那張單子跑 `aos-tick $AOS_STACK/tick.txt`，所以跑完工作區的 `.stack/tick.txt` 是 `5`（C-44：tick-tock 就是一個時鐘；N-01 大家抬頭讀這個檔）。節奏、停交給 loop：要隔多久走一格就在 loop.json 加 `interval_ms`，要能暫停就加 `ctl`、寫 `{"paused": true}`。程式見 [bin/README 的 aos-tick](../bin/README.md)。

## 測試

`python3 -m unittest discover -s proto8/tests`（10-23 起跑 impls 的 C++ 四支＋bin 的 aos-tick，先建 impls）：`test_loop.py`（直接叫 aos-loop：訊號、PATH、`interval_ms`／`ctl`／`state` 窗、命令列（10-21 傍晚：設定檔是唯一的位置參數、`exec` 陣列、`檔#/指標`））、`test_daemon.py`（aos-daemon）、`test_exec.py`（aos-exec、aos-loop、兩隻 agent 與 cathy／stamp 巢狀）、`test_exec_rules.py`（aos-exec 的新規則：命令列旗標（10-21）、找入口、`#/`、四種入口、`AOS_CF`／`AOS_CD`）、`test_inst.py`（inst 單子：經 aos-exec 跑；10-23 前另直接叫 Python 的 aos_inst 庫）、`test_fsm.py`（aos-fsm）、`test_tick.py`（aos-tick 與 demo/tick）、`test_dan.py`（agent-dan，10-23：用一支假 server 照劇本回 `tool_calls`／答案；連真模型的案例在 LiteLLM 不在時 skip）。

舊的 demo（daemon、fsm、paint、kernels、tasks、tick、once、`aos-demo`）10-19 進 git 歷史（daemon 10-20、tick 10-21 晚照新做法重做，見上），見 git 5546be29（刪除前的最後一個樣子）。
