# proto8/demo — 兩隻 agent 跑一遍

← [proto8](../README.md)｜程式：[bin/README](../bin/README.md)｜慣例：[CONVENTION](../CONVENTION.md)

```
sh proto8/demo/run.sh      # 在 WSL／Linux 跑
```

`run.sh` 各建一個暫時工作區、放一題 `inbox/q1.txt`、`cd` 進去跑 agent-bob 與 agent-ann（慣例用法 `aos-exec <agent資料夾>`），最後再跑一次 daemon（見下），印工作區內容（`out/`、`done/`）與整棵 stack 樹（每檔印內容），最後把暫時資料夾刪掉，repo 裡不留東西。**PATH 由 `run.sh` 自己放**：aos 的程式都不動 PATH（ideas § 24，使用者「也套用，都不動path吧」），agent 裡寫的 `aos-loop`、`aos-fsm`、`aos-exec` 要呼叫端事先把 `proto8/bin` 放進 PATH——`run.sh` 開頭就這麼做；自己手動跑也一樣（`PATH=$PWD/proto8/bin:$PATH aos-exec --ws <工作區> proto8/demo/agent-bob`）。預設假腦；`AOS_BRAIN_URL`（OpenAI 相容 base URL，另可設 `AOS_BRAIN_MODEL`、`AOS_BRAIN_KEY`）指到遠端才用真腦。**這台電腦不要跑本機模型**（10-19 LM Studio 讓整台 Windows 當機，使用者定「放棄跑本機模型」，[ideas § 6](../thinking/2026-10-19-ideas.md)）。

## agent-bob（混合範本，叫 cathy、cathy 叫 stamp：四層）

入口 `_exec`（預設 `$AOS_ENTRY`；10-19 晚改，原 `.aos/exec`）＝`exec aos-loop loop.json`；`loop.json` 內嵌單子 `{"run": {"argv": ["aos-fsm", "fsm.json"]}, "max": 20}`；`fsm.json` 一份看完整張表：idle／act 是子資料夾 `idle/`、`act/`（shell），think 是內嵌單子（`python3 brain.py`、stdout 導到 `$AOS_STACK/plan`、逾時 120 秒）。idle 在 inbox 空時回 10 讓 loop 停。`brain.py` 挑 inbox 第一題、題名寫 `current`、答案印到 stdout。

act 把 plan 當題目交給 `act/tools/cathy/`（另一隻完整 agent，同一套範本；P-32、P-33）：在她的小格 `$AOS_STACK/cathy/` 裡備 `ws/inbox/<題名>`、`AOS_STACK=$sub aos-exec --ws "$sub/ws" tools/cathy`、從 `$sub/ws/out/<題名>` 拿答案寫進 `$AOS_WS/out/`、題目搬 `done/`；cathy 失敗（非 0）bob 的 act 說「cathy 失敗」並退 1。cathy 的 act 再經 `act/tools/cathy/act/tools/stamp`（工具，自己的 stack 在 `$AOS_STACK/stamp/`，前面加一行 UTC 時間戳、`runs` 計次）寫她的 out。一次跑完是四層：bob 的 loop／fsm → act → cathy 的 loop／fsm → 她的 act → stamp；`aos-exec --ws <工作區> proto8/demo/agent-bob/act/tools/cathy` 也能單獨跑 cathy。

stack 樹＝呼叫樹：`.aos/{state,current,plan,trace.jsonl}`、`.aos/cathy/{…,ws/,stamp/runs}`（P-38）。

## agent-ann（全內嵌對照）

跟 bob 做同一件事（一題一答），零子資料夾：入口 `aos-loop loop.json`，`loop.json` 內嵌 `aos-fsm fsm.json`，`fsm.json` 三格全是單子，各指一支小腳本——`idle.py`（inbox 空退 10）、`brain.py`（同 bob 的那份，複製）、`act.py`（plan 寫 out、題目搬 done）。資料夾裡只有 `_exec`、`loop.json`、`fsm.json` 和三支 `.py`。適合「格全是一行、不叫工具」的小 agent；要叫工具、要用 sh 搬檔，就回到 bob 的混合寫法。

## daemon（一個 daemon 同時管 bob、ann，10-20）

`daemon/_exec`＝`exec aos-daemon daemon.json`；`daemon.json` 是 `{"max": 10, "interval_ms": 200, "ctl", "state", "children": {"bob": …, "ann": …}}`，每個子項是一份 loop 設定：`{"run": {"argv": ["aos-exec", "--ws", {"$env": "AOS_WS", "$path": "bob"}, "../agent-bob"]}, "max": 1}`（ann 同樣）——子 loop 跑一次那隻 agent，工作區是 `$AOS_WS/bob`、`$AOS_WS/ann`。`run.sh` 最後一段建暫時工作區、在 `bob/inbox/`、`ann/inbox/` 各放一題、`aos-exec` daemon：它拍 10 拍（約 2 秒）就結束、結束前收掉子項。stack 樹：`.aos/state.json`（daemon 的 state，`children` 表）、`.aos/bob/`、`.aos/ann/`（各子項的小格：daemon 寫的 `loop.json`、子 loop 的 `state.json`、`stderr`，以及那隻 agent 自己的 `state`、`trace.jsonl`…——agent 的 stack 就是小格，因為 `AOS_STACK` 已經有值、aos-exec 沿用）。子 loop 結束後不重起，所以表上兩項最後都是 `exited`、`code` 0。

## 測試

`python3 -m unittest discover -s proto8/tests`：`test_loop.py`（直接叫 aos-loop：訊號、PATH、`interval_ms`／`ctl`／`state` 窗）、`test_daemon.py`（aos-daemon）、`test_exec.py`（aos-exec、aos-loop、兩隻 agent 與 cathy／stamp 巢狀）、`test_exec_rules.py`（aos-exec 的新規則：命令列旗標（10-21）、找入口、`#/`、四種入口、`AOS_CF`／`AOS_CD`）、`test_inst.py`（aos-inst）、`test_fsm.py`（aos-fsm）。

舊的 demo（daemon、fsm、paint、kernels、tasks、tick、once、`aos-demo`）10-19 進 git 歷史（daemon 10-20 照新做法重做，見上），見 git aa2fec1f（刪除前的最後一個樣子）。
