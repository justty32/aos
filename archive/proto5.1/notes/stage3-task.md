# proto5.1 第 3 段任務書：aos-run／aos-daemon／aos-kernel 的 proto5 版（2026-09-22）

接 [stage2-task.md](stage2-task.md)；先讀 [findings.md](findings.md)（#1～#26）、`stage2-report.md`。一樣只動 `proto5.1/`；問題接第 27 條記進 findings。
**原則：保持 KISS**——能少一個欄位就少、能少一個子命令就少；proto4-3 有的不代表要搬。

材料：`proto5/notes/2026-09-22-daemon-kernel-summary.md`（§1 三層是什麼、§2 六個坑、§3 怎麼分、§4 六題全採建議 A）、
細節看 `proto5/notes/2026-09-22-daemon-kernel-report-astra.md`；舊程式在 `proto4-3/`（`aos_run*.py`、`aos_daemon*.py`、`aos_kernel*.py`、`docs/`）可以抄、
但要照 proto5.1 的規範與風格重寫，不要 import proto4-3。

## 要做的（三支程式、五份規範）

### aos-run（程式規範 `spec/aos-run.md`、`lib/aos_run.py`、`cli/aos-run`）
反覆叫 `aos_exec.run_target()`。旗標只留：`--interval-ms`（預設 1000，從完成後算）、`--timeout-ms`（每次；預設 0）、`--max-runs`、`--stop-exit CODE`（可重複）、
`--status-fd N`（事件 `ready`／`start #n`／`done #n exit=C kind=K`／`stop REASON`，一行一個）。**砍到底**：第一次 SIGTERM 就把正在跑的子程式 group 一起 TERM（走 aos_exec 的逾時砍法：TERM→2 秒→KILL），
跑完這次就停；不做 `--from-start`／`--time-limit-ms`／`--stop-on-error`／第二次訊號那套。退出碼 0（正常停）／2（用法）。

### aos-daemon（格式 `spec/daemon-home.md`、程式 `spec/aos-daemon.md`、`lib/aos_daemon.py`、`cli/aos-daemon`、`cli/aos-daemon-ctl`）
家＝`AOS_DAEMON_HOME`（預設 `~/.aos-daemon`）：`requests/<名>.json`→處理→**先寫** `requests/done/<名>.json`（原請求＋`ok`＋`result`）**再刪原單**；請求檔名＝`<epoch ns>-<pid>-<random 4 hex>.json`；
`state.json`（`pid`、`runs{key: entry}`；entry 只留 `pid`／`target`／`args`／`state`／`ready`／`running`／`runs`／`last_exit`／`last_kind`）；`daemon.pid`；`daemon.log`。
op 只留 **`add`／`remove`／`ls`／`stop`**（不做 pause／resume／restart／get；`ls` 由 ctl 直接讀 state）。狀態只有 `running`／`stopping`。
停：TERM aos-run（它會自己砍到底）→5 秒→KILL group。ctl：`add FILE.json [aos-run 旗標]`、`rm FILE.json`、`ls`、`stop`；等 done 最多 10 秒；退出碼 0／1／2。
錯誤代號：`NotAHome`／`ReadFailed`／`JsonSyntax`／`FieldTypeMismatch`／`NotRunning`／`AlreadyRunning`，stderr `aos-daemon: <代號>: <白話>`。

### aos-kernel（格式 `spec/kernel-home.md`、程式 `spec/aos-kernel.md`、`lib/aos_kernel.py`、`cli/aos-kernel`）
家 `K/`：`info.json`（`_metainfo._type`＝`kernel`、`_version`＝1；`ncpu`、`interval_ms`、`timeout_ms`、`quantum`、`done_exit`＝100、`wait_exit`＝101、`bad_after`＝10；解指示詞）、
`inst.json`（kernel 自己的 tick）、`state.json`（`cpus`、`queue`、`waiting`）、`procs/`（＋`done/`、`bad/`）、`cpus/`、`syscalls/`（＋`done/`；**只有 `rm`**）、`kernel.log`。
子命令：`aos-kernel init K --ncpu N`、`boot K`（把自己 add 進 daemon）、`tick`（cwd＝K；一格）、`add K INST [--name]`（用 `aos_inst.load()` 解完再驗，吃完整 proto5 inst）、
`rm K NAME`、`ls K`。**沒有 module**（llm cpu／tool cpu 就是普通行程：把它們的 inst add 進來）。
一格 tick 照 4-3 的 12 步，但：
- **擋重疊**：換人前看 daemon entry 的 `running`，還在跑就這輪不換；一個行程同時只能出現在一個 `cpus/<n>.json`。
- `bad_after` 計數跟著行程走（換下去存 `state.waiting` 旁邊，不丟）。
- 錯誤代號同上（`NotAHome`…），stderr `aos-kernel: <代號>: <白話>`。
退出碼 0／101（tick 沒事做也是 0，這個不用 101）／1／2。

## 測試、真跑、文件
- `test_run.py`、`test_daemon.py`、`test_kernel.py`（真開進程；暫存家；砍到底要驗孫進程真的死了；擋重疊要驗；done 先寫再刪原單）。全套綠。
- 真跑：`K` 一顆 kernel＋`ncpu 3`，add 三個行程：第 2 段 demo 的 agent（`engine.cpu`＋一個 `_run: "cpu"` 工具）、llm cpu、tool cpu；`aos-daemon` 起來、`aos-kernel boot`，
  丟 `input.json`，等到 agent 回話；貼 `aos-kernel ls` 幾次的輸出與最後記憶。然後 `aos-daemon-ctl stop`，驗證沒有殘留進程（`pgrep -f aos-`）。
- 文件：`lib/README.md`、`README.md`（分段表第 3 段「做完」、規範表加五份、程式表加三支）。
- 只動 `proto5.1/`；不 commit／push／stash／checkout。回報：檔案清單、測試數字、真跑紀錄（含 ls 輸出、stop 後 pgrep）、findings 新增幾條＋最重要 5 條。
