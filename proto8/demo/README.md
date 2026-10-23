# proto8/demo — 兩隻 agent 跑一遍

← [proto8](../README.md)｜程式：[bin/README](../bin/README.md)｜慣例：[CONVENTION](../CONVENTION.md)

```
sh proto8/demo/run.sh      # 在 WSL／Linux 跑
```

`run.sh` 各建一個暫時工作區、放一題 `new/q1.txt`（10-23 改名，原 `inbox/`）、`cd` 進去跑 agent-bob 與 agent-ann（慣例用法 `aos-exec <agent資料夾>`），再跑一次 daemon、最後跑一次 tick（見下），印工作區內容（`out/`、`done/`；跑完 `new/`、`cur/` 是空的）與整棵 stack 樹（`$AOS_WS/.stack/`，10-23 改名，原 `.aos/`）（每檔印內容），最後把暫時資料夾刪掉，repo 裡不留東西。**PATH 由 `run.sh` 自己放**：aos 的程式都不動 PATH（ideas § 24，使用者「也套用，都不動path吧」），agent 裡寫的 `aos-loop`、`aos-fsm`、`aos-exec` 要呼叫端事先把 `proto8/bin` 放進 PATH——`run.sh` 開頭就這麼做；自己手動跑也一樣（`PATH=$PWD/proto8/bin:$PATH aos-exec --ws <工作區> proto8/demo/agent-bob`）。預設假腦；`AOS_BRAIN_URL`（OpenAI 相容 base URL，另可設 `AOS_BRAIN_MODEL`、`AOS_BRAIN_KEY`）指到遠端才用真腦。**這台電腦不要跑本機模型**（10-19 LM Studio 讓整台 Windows 當機，使用者定「放棄跑本機模型」，[ideas § 6](../thinking/2026-10-19-ideas.md)）。

## agent-bob（混合範本，叫 cathy、cathy 叫 stamp：四層）

入口 `_entry`（預設 `$AOS_ENTRY`；10-19 晚改，原 `.aos/exec`；10-23 改名，原 `_exec`）＝`exec aos-loop loop.json`（10-21 傍晚：設定檔是 aos-loop 唯一的位置參數）；`loop.json`＝`{"val": "fsm.json", "max": 20}`（`val` 是 aos-exec 的目標，10-21；10-23 統合前叫 `run`）；`fsm.json` 帶 `"_entry": ["aos-fsm", {"$env": "AOS_CF"}]`（`AOS_CF`＝aos-exec 實際跑的那份檔），所以它本身就是 aos-exec 的入口、每拍 `aos-exec -- fsm.json`（10-21 計畫第 3 段）；表一份看完：idle／act 是子資料夾 `idle/`、`act/`（shell），think 是內嵌單子——`"val": "fsm.json#/states/think/body"`、單子放那格的 `body`（`python3 brain.py`、stdout 導到 `$AOS_STACK/plan.txt`、逾時 120 秒，aos-exec 當監工）。idle 在 `new/` 空時回 10 讓 loop 停。`brain.py` 挑 `new/` 第一題、搬到 `cur/` 認領（Maildir 的 new → cur）、題名寫 `current.txt`、答案印到 stdout。

act 把 `plan.txt` 當題目交給 `act/tools/cathy/`（另一隻完整 agent，同一套範本；P-32、P-33）：在她的小格 `$AOS_STACK/cathy/` 裡備 `ws/new/<題名>`、`AOS_STACK=$sub aos-exec --ws "$sub/ws" tools/cathy`、從 `$sub/ws/out/<題名>` 拿答案寫進 `$AOS_WS/out/`、題目從 `cur/` 搬 `done/`；cathy 失敗（非 0）bob 的 act 說「cathy 失敗」並退 1。cathy 的 act 再經 `act/tools/cathy/act/tools/stamp`（工具，自己的 stack 在 `$AOS_STACK/stamp/`，前面加一行 UTC 時間戳、`runs.txt` 計次）寫她的 out。一次跑完是四層：bob 的 loop／fsm → act → cathy 的 loop／fsm → 她的 act → stamp；`aos-exec --ws <工作區> proto8/demo/agent-bob/act/tools/cathy` 也能單獨跑 cathy。

stack 樹＝呼叫樹：`.stack/{state.txt,current.txt,plan.txt,trace.jsonl}`、`.stack/cathy/{…,ws/{out,done}/q1.txt,stamp/runs.txt}`（P-38）。

## agent-ann（全內嵌對照）

跟 bob 做同一件事（一題一答），零子資料夾：入口 `_entry`＝`exec aos-exec loop.json`，`loop.json` 是 `{"_entry": ["aos-loop", {"$env": "AOS_CF"}], "val": "loop.json#/body", "body": {"argv": ["aos-fsm", "fsm.json"]}, "max": 20}`——loop.json 自己帶 `_entry`，`aos-exec loop.json` 就把 loop 跑起來（10-21 傍晚；跟 bob 的 `exec aos-loop loop.json`、`"val": "fsm.json"` 對照，兩種都行），`fsm.json` 三格全是單子（`"val": "fsm.json#/states/<名>/body"`、單子放 `body`），各指一支小腳本——`idle.py`（`new/` 空退 10）、`brain.py`（同 bob 的那份，複製）、`act.py`（`plan.txt` 寫 out、題目從 cur 搬 done）。資料夾裡只有 `_entry`、`loop.json`、`fsm.json`、三支 `.py`，和一份 `.env` 範例（10-22，全是註解、不設任何東西：示範 API key 與 `PATH=${AOS_CD}/bin:${PATH}` 怎麼寫。10-22 起 `.env` 預設不蓋環境裡已有的名字，PATH 那行要從外面叫 `aos-exec --dotenv-override agent-ann` 才生效；旗標只管那一次，入口的 `aos-exec loop.json`、loop 每拍、fsm 每格三層照樣各讀一次這份檔但不蓋，所以格裡的 PATH 只多一份 `${AOS_CD}/bin`——原本是四份）。適合「格全是一行、不叫工具」的小 agent；要叫工具、要用 sh 搬檔，就回到 bob 的混合寫法。

## daemon（一個 daemon 同時管 bob、ann，10-20）

`daemon/_entry`＝`exec aos-daemon daemon.json`；`daemon.json` 是 `{"max": 10, "interval_ms": 200, "ctl", "state", "loops": {"bob": …, "ann": …}}`（`loops` 10-23 統合前叫 `children`），每個子項是一份 loop 設定：`{"val": "daemon.json#/loops/bob/body", "max": 1, "body": {"argv": ["aos-exec", "--ws", {"$env": "AOS_WS", "$path": "bob"}, "../agent-bob"]}}`（ann 同樣；10-21 起子項的 `val` 是 aos-exec 的目標，內嵌單子放在那個子項自己的 `body`，路徑從 daemon 的 cwd＝`demo/daemon/` 算——10-21 傍晚起子 loop 經 aos-exec 起、cwd 是小格，daemon 寫小格時把 `val` 轉成絕對路徑，所以照樣指得到）——子 loop 跑一次那隻 agent，工作區是 `$AOS_WS/bob`、`$AOS_WS/ann`。`run.sh` 最後一段建暫時工作區、在 `bob/new/`、`ann/new/` 各放一題、`aos-exec` daemon：它拍 10 拍（約 2 秒）就結束、結束前收掉子項。stack 樹：`.stack/state.json`（daemon 的 state，`loops` 表）、`.stack/bob/`、`.stack/ann/`（各子項的小格：daemon 寫的 `loop.json`（`val` 已轉絕對、帶 `_entry`）、子 loop 的 `state.json`、`stderr.txt`，以及那隻 agent 自己的 `state.txt`、`current.txt`、`plan.txt`、`trace.jsonl`…——agent 的 stack 就是小格，因為 `AOS_STACK` 已經有值、aos-exec 沿用）。子 loop 結束後不重起，所以表上兩項最後都是 `done`（子 loop 自己結束；daemon 收掉的才是 `stopped`，10-23 統合前兩種都叫 `exited`）、`code` 0。state.json 長這樣：`{"kind": "state", "phase": "done", "beats": 10, "max": 10, …, "loops": {"bob": {"pid", "started_at_ticks", "phase": "done", "code": 0, "signal": null}, …}, "code": 0, "pid", "started_at_ticks", "boot_id", "at": "2026-10-23T02:46:30.317+00:00"}`；各 agent 的 `trace.jsonl` 一行 `{"at": "…T02:46:27.633+00:00", "state": "idle", "code": 0, "signal": null, "elapsed_ms": 14}`。

## tick（時鐘，10-21 晚）

`tick/_entry`＝`exec aos-loop loop.json`；`loop.json`＝`{"val": "loop.json#/body", "body": {"argv": ["aos-tick", {"$env": "AOS_STACK", "$path": "tick.txt"}]}, "max": 5}`——loop 拍 5 次，每拍 `aos-exec -- loop.json#/body`，那張單子跑 `aos-tick $AOS_STACK/tick.txt`，所以跑完工作區的 `.stack/tick.txt` 是 `5`（C-44：tick-tock 就是一個時鐘；N-01 大家抬頭讀這個檔）。節奏、停交給 loop：要隔多久走一格就在 loop.json 加 `interval_ms`，要能暫停就加 `ctl`、寫 `{"paused": true}`。程式見 [bin/README 的 aos-tick](../bin/README.md)。

## 測試

`python3 -m unittest discover -s proto8/tests`：`test_loop.py`（直接叫 aos-loop：訊號、PATH、`interval_ms`／`ctl`／`state` 窗、命令列（10-21 傍晚：設定檔是唯一的位置參數、`val` 陣列、`檔#/指標`））、`test_daemon.py`（aos-daemon）、`test_exec.py`（aos-exec、aos-loop、兩隻 agent 與 cathy／stamp 巢狀）、`test_exec_rules.py`（aos-exec 的新規則：命令列旗標（10-21）、找入口、`#/`、四種入口、`AOS_CF`／`AOS_CD`）、`test_inst.py`（inst 單子：aos_inst 庫、經 aos-exec 跑）、`test_fsm.py`（aos-fsm）、`test_tick.py`（aos-tick 與 demo/tick）。

舊的 demo（daemon、fsm、paint、kernels、tasks、tick、once、`aos-demo`）10-19 進 git 歷史（daemon 10-20、tick 10-21 晚照新做法重做，見上），見 git 5546be29（刪除前的最後一個樣子）。
