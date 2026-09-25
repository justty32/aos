# daemon／kernel：精簡總結與 proto5 該怎麼寫規範（2026-09-22）

astra 唯讀調查了 proto4-3 的 aos-run、aos-daemon（＋ctl）、aos-kernel（＋module／syscall／llm module）
（原報告 1209 行：`2026-09-22-daemon-kernel-report-astra.md`）。這份是我的精簡版＋規範要怎麼分、哪些照抄、哪些要改；
決策由使用者做。跟 [llm cpu](2026-09-22-llm-cpu-summary.md)、[act](2026-09-22-act-summary.md)、[逾時](2026-09-22-timeout-summary.md) 一起看。

## 1. 三層各是什麼（事實）

| 層 | 一句話 | 家目錄／檔 |
|---|---|---|
| **aos-run** | 反覆叫 `aos_exec.run_target()`；`--interval-ms`（預設 1 秒，從完成後算）、`--timeout-ms`（每次）、`--time-limit-ms`（整體）、`--max-runs`、`--stop-exit`、`--stop-on-error`（只對 `kind=aos`）；事件寫 `--status-fd`（`ready`／`start #n`／`done #n exit=C kind=K`／`stop REASON`）；訊號第一次＝跑完這次就停、第二次＝KILL 子程式 group | **沒有**家目錄、沒有狀態檔；編號從 1 起 |
| **aos-daemon** | 管一堆 aos-run：`requests/<名>.json`（op：`add`／`remove`／`restart`／`get`／`ls`／`pause`／`resume`／`stop`，八種）→處理→刪原單、寫 `requests/done/<名>.json`（原請求＋`ok`＋`result`）；每支 aos-run 一個 entry 寫進 `state.json`（`pid`／`target`／`args`／`state` 五態 running／pause_pending／paused／stopping／restarting／`ready`／`running`／`runs`／`last_exit`／`last_kind`／`last_line`／`alive`）；停：TERM→5 秒→KILL group | `AOS_DAEMON_HOME`（預設 `~/.aos-daemon`）：`requests/`、`requests/done/`、`daemon.pid`、`state.json`、`daemon.log` |
| **aos-kernel** | 排程：`procs/<pid>.json`（等著跑的 inst）→拿一個 replace 到 `cpus/<n>.json`（該 cpu 的 aos-run 下一次就跑它）；一格 tick＝讀 daemon state→補 cpu→跑 syscall→跑 module tick→驗 queue→排程→存 state；退出碼 `done_exit=100`（完成→`procs/done/`）、`wait_exit=101`（在等；有人排隊就讓位）、其他非零累計 `bad_after=10`→`procs/bad/`；`quantum=5`＝完成 5 次就換人；syscall＝`syscalls/<名>.json`→`syscalls/done/<名>.json`（`{ok,msg}`）；module＝config 列的 Python 檔，`NAME`／`OPS`／`handle`／`tick`／`status`／`cli` 四個 hook 在 kernel 進程裡直接叫 | `K/`：`inst.json`（kernel 自己的 tick）、`config.json`（`ncpu`／`interval_ms`／`timeout_ms`／`quantum`／`done_exit`／`wait_exit`／`bad_after`／`modules`）、`state.json`（`cpus`／`queue`／`waiting`）、`procs/`（＋`done/`、`bad/`）、`cpus/`、`syscalls/`（＋`done/`）、`kernel.log` |

kernel 的 cpu ＝ daemon 管的一支 aos-run，反覆跑 `cpus/<n>.json`；換行程＝換那個檔。kernel 不知道 agent 在等什麼，只看到退出碼。

## 2. 最要緊的坑（會影響 proto5 怎麼寫）

1. **同一行程可能被兩顆 cpu 重疊跑**：kernel 換人只看「完成幾次」，不看 daemon 的 `running`；換下去的行程可能在上一次還沒跑完時被另一顆 cpu 拿走。agent 的前提是「同一資料夾不能同時跑兩份」→ **proto5 的 kernel 要保證**。
2. **砍不乾淨**：daemon→aos-run→inst 子程式各開一個 session；daemon 5 秒後 KILL 的是 aos-run 那組，inst 子程式（例如 agent 的工具）可能還活著。
3. **崩潰不對帳**：daemon 重啟 table 從空的開始、舊 aos-run 沒人收養；kernel 只看 daemon 的最新快照（runs 一次跳 5，5 次全算成最新那個碼）；request 刪了才寫 done（有失單窗口）；兩個 tick 同跑沒鎖。
4. **文件過強**：「主迴圈不等人」（其實 reap 會 join）、「每 0.5 秒存 state」（是門檻不是時鐘）、「kernel tick 一律 0」（有 1／2）、「v1 行程不會結束」（早有 done_exit）、README 的 add 範例名字對不上（自動名是數字）。
5. **kernel 吃的 inst 比 proto5 規範窄**：add／queue 要 raw 的 `argv` list、`argv[0]` 字串、`cwd` 字串（頂層 `$ref`、`cwd` 指示詞、`$opt:mkdir` 都進不去）；`argv[0]` 含 `/` 且不存在就事先拒收。
6. **沒有具名錯誤代號**：daemon／kernel 都是中文 msg＋退出碼 1／2；只有 inst 那層有代號。

## 3. proto5 規範怎麼分（我的建議）

照使用者定的「格式一份、程式一份」：

| 格式（協議） | 程式 |
|---|---|
| `spec/daemon-home.md`：家目錄、`requests/` 請求／回應檔（八個 op、欄位、`ok`／`result`）、`state.json` 的 entry 欄位與五態、`daemon.pid` | `spec/aos-daemon.md`：`aos-daemon [--home]`、每輪做什麼、停止流程（TERM→5 秒→KILL）、崩潰後怎樣；`aos-daemon-ctl add／rm／restart／get／ls／pause／resume／stop` 與等多久、退出碼 0／1／2 |
| `spec/kernel-home.md`：`K/` 逐檔、`config.json` 八欄、`state.json`（`cpus[n]` 的 `pid`／`since`／`runs_at`／`seen_runs`／`waiting`／`wait_runs`／`bad_runs`／`bad_exit`／`aos_ticks`；`queue`；`waiting`）、行程的六種去處（queued／running／waiting／done／bad／removed）、syscall 請求／回音格式、module 介面（`NAME`／`OPS`／四 hook） | `spec/aos-kernel.md`：`aos-kernel-init／boot／tick`、`aos-kernel add／rm／ls／<module>`、一格 tick 的 12 步、退出碼怎麼判（完成→觀察→aos 連敗→bad→waiting 讓位→quantum）、換人怎麼換檔、退出碼 |
| aos-run **沒有家**，只有命令列與 status 事件 → 不另開格式檔；`spec/aos-run.md` 一份程式規範（旗標、每格、退出碼、訊號、status-fd 事件格式） | |

**照抄 proto4-3 的**：三個家的長相、八個 op、五態、config 八欄、100／101／bad_after／quantum、syscall 同名回音、module 四 hook、status-fd 事件。
**要改的（列在各檔「跟 proto4-3 差在哪」）**：
- kernel 換人前**確認 daemon entry 不在 `running`**（擋重疊）；或更簡單：一個行程同時只能在一個 cpu 檔裡、且 daemon 回報 `done` 之後才換。
- 砍行程要砍到底：aos-run 收到 TERM 時轉送給正在跑的子程式 group（proto4-3 只在第二次 TERM 才砍）；或 daemon 記下子程式 pgid。
- daemon request 改「先寫 done、再刪原單」；request 檔名加隨機尾巴（現在同毫秒同 pid 會撞）。
- kernel 的 add／queue 用 `aos_inst.load()` 解完再驗（吃完整 proto5 inst），不看 raw。
- 錯誤給代號（沿用 agent.md 那套：`NotAHome`／`ReadFailed`／`JsonSyntax`／`FieldTypeMismatch`…）。
- `.json` 不存在＝125 那條已在 proto5 exec 定了，kernel 的 `aos_ticks>=2` 退件照舊。

**先不做**：pause／resume（agent 已有 `waits` 暫停）、restart、module 機制（llm cpu 改成普通行程，見 llm cpu 總結；kernel 不需要 module）、`ls` 的欄寬。

## 4. 要你拍板的

1. **module 機制要不要留**：**A** 不留，llm cpu／tool cpu 都是普通行程（一個資料夾＋inst，kernel 排它）／B 照 4-3 留 module（hook 在 kernel 進程裡跑，會拖住 tick）。建議 A。
2. **pause／resume／restart 要不要進第一版**：**A** 不要（agent 有 `waits` 暫停；重啟＝rm＋add）／B 要。建議 A。
3. **daemon 跟 kernel 要不要併成一支**：**A** 維持兩支（daemon 管 Linux 進程、kernel 管排程；各自的家）／B 併成一支（少一層檔案協議與 20 秒 ctl 等待，但 kernel 崩了 aos-run 全沒人管）。建議 A（照 4-3）。
4. **重疊執行怎麼擋**：**A** kernel 換人前看 daemon entry 的 `running`，還在跑就不換／B 每次執行給 invocation id、agent 自己加鎖。建議 A。
5. **砍到底怎麼做**：**A** aos-run 第一次 TERM 就把子程式 group 一起 TERM（現在要第二次）／B daemon 記子程式 pgid 自己砍。建議 A。
6. **錯誤代號**：**A** 三支都給具名代號、stderr `aos-xxx: <代號>: <白話>`（跟 agent 一致）／B 照 4-3 只有白話。建議 A。
