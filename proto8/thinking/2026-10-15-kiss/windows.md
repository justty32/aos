# KISS 審稿：窗（ctl／state）與時空

範圍：NORMS 02（時空 N-01～N-03）、05（窗 N-06～N-19、N-32、N-33）、沾到窗的 N-10／N-28；lib `aos_ctl_state.py`、`ctl_state.md`；loop／daemon／fsm／兩種 kernel 怎麼用窗；demo 與測試。只寫稿，不改任何檔。

每條：現況 → KISS 版；要動到哪；風險。直接給推薦。

## 一、刪（優先）

1. **ctl 的 `now`（`{"val", "now"}` 雙形）** — 現況：`paused`／`stop` 可以寫成物件，`now: true`＝當場收掉正在跑的那次；daemon 的 `pause`／`remove` 又多一個 `wait` 參數對應它。KISS：`paused`、`stop` 只收布林；要當場收掉＝送訊號給 loop（本來就會整群收）。要動：`aos_ctl_state.py`（`_flag`、`parse_ctl`）、`aos_loop.py`（serve 裡 stop／paused 的 now 分支）、`aos_daemon_table.py`（`wait`、`shutdown` 的 now）、N-07、`ctl_state.md`、`loop.md`、`daemon.md`、`test_loop.py` `test_ctl_now_kills_current`。風險：「暫停並殺掉這次、行程留著」這招沒了——沒人用過。

2. **ctl 的 `seq`／state 的 `ctl_seq` 回音（N-14 後半、N-33）** — 現況：寫 ctl 的人帶流水號，daemon 靠 state 的 `ctl_seq` 趕上才回指令。KISS：拿掉 seq；要知道「讀到了沒」看 state 回報的生效值（`times`、`paused`→`state` 那格）跟你寫的對不對得上，state 本來就回報生效值。要動：`aos_ctl_state.py`（`parse_ctl`、`CtlFile.seq`、`state_doc` 的 ctl_seq）、`aos_daemon_table.py`（`update_ctl` 加一、`acked`）、N-14、N-33、`ctl_state.md`、`test_loop.py` `test_ctl_seq_and_heartbeat`、`test_daemon.py` 的 ctl_seq 斷言。風險：寫了跟現值一樣的值分不出「讀到了」還是「還沒讀」——結果一樣，不用分。

3. **心跳三欄 `beat`、`boot_id`、`started` 與每秒碰一下（N-17、N-32）** — 現況：state 沒變也每秒重寫、帶開機 id 與 /proc 啟動時間；「3 倍間隔沒動靜算疑似死亡」。查過：`beat`、`boot_id` 全 repo 沒人讀；`started` 只有 daemon `load` 接回時用。KISS：全拿掉，state 只在內容變了才寫；活著沒有看 `pid`（kill -0），Unix 本來的做法。要動：`aos_ctl_state.py`（`_proc`、`proc_started`、`StateFile` 的 beat 計時、`BEAT_MS`）、N-17、N-32、`ctl_state.md`、`test_loop.py` 心跳測試、`test_daemon.py` 骨架欄位集合。風險：pid 重用的誤判——原型期不管。

4. **daemon 的 `load: true` 接回孤兒（N-28 暫定 d）** — 現況：table 窗當存檔，重起時對 pid＋啟動時間認領、對不上走策略格、backoff 的重起；為此 `_Entry` 有「孤兒」一整套（`cfg=None`、`gone()` 兩條路、`retry_at`）。KISS：拿掉 `load`；daemon 被 SIGTERM 本來就會把子 loop 收乾淨，被 SIGKILL 的孤兒自己 `pkill`。table 窗只是給人看的表，不是存檔。要動：`aos_daemon.py`（`load` 設定、`start_table`）、`aos_daemon_table.py`（`load()`、`_Entry` 孤兒路徑、`proc_started`）、N-28、`daemon.md`、`test_daemon.py` `test_table_window_and_load`。風險：daemon 被 -9 後要人工清子 loop；推翻 10-14 暫定 d（使用者當時「全定」）。

5. **`interval_mode: "fixed"` 與 `skipped`** — 現況：兩種節奏，fixed 要算錨點、拍號、跳拍數，ctl 可蓋、state 要回報。查過：demo 只有 tick 的檔頭提一句「要準時就 fixed」，沒人寫。KISS：只有一種：跑完隔 `interval_ms` 再起。要動：`aos_ctl_state.py`（`_MODES`、parse、`state_doc`）、`aos_loop.py`（`due`、`start` 的錨點數學、`anchor`／`tick`／`skipped`、結束那份的 skipped）、N-07、N-11、N-31（結束那份少一欄）、`ctl_state.md`、`loop.md`、`daemon.md`、`test_loop.py` `test_fixed_skips_missed_ticks`、`test_daemon.py` 的 fixed 測試。風險：tick 時鐘會慢慢飄——時鐘本來就「不保證什麼」（C-44）。

6. **`error_wait_ms`** — 現況：aos_inst 自己出錯後下一次至少隔 1 秒，防 `times: null`＋`interval_ms: 0` 空轉。KISS：拿掉；要隔就寫 `interval_ms`。誤用不歸組件管（C-53 姿態 a）。要動：`aos_loop.py`（DEFAULTS、`due`、`last_err`）、`loop.md`、`daemon.md`、`test_loop.py` `test_error_wait`。風險：設錯的 loop 會空轉得很快——它自己的事。

7. **`ctl_poll_ms`** — 現況：多一個 key 定多久看一次 ctl；測試、demo 全都要寫 `20`／`100` 把它調快。KISS：每圈都讀（loop 本來每 10～20 ms 一圈；ctl 幾十 bytes，比 bytes 沒變就不重驗，已經是這樣）。要動：`aos_loop.py`（DEFAULTS、`next_poll`）、`loop.md`、`daemon.md`、所有 demo 的 loop.json／daemon.json、`test_loop.py`／`test_daemon.py` 的 ctl_poll_ms。風險：每秒多幾十次小讀檔，不痛。

8. **`policies.child_exit` 策略格、backoff、`MAX_EXITS`、`exits`** — 現況：子 loop 結束時 daemon 起一個 inst 問「怎麼辦」，stdin 塞子項的 state 窗內容（`last_state`）、退避重起、連崩 5 次強制 leave、`PolicyFailed`／`RestartFailed` 兩個警告代號、`policy.in.json`／`policy.out.json` 兩個檔。KISS：拿掉。子 loop 結束＝表上留著（`code` 有值）；要重起的人自己 remove＋add（一個外層 loop 或 agent 讀 table 窗就能做，可由組合得到）。要動：`aos_daemon.py`（`policies` 設定與驗證）、`aos_daemon_table.py`（`_exit_policy`、`MAX_EXITS`、backoff／retry_at、exits）、N-28、`daemon.md`、`test_daemon.py` 策略格測試。風險：基礎實作沒有自動重起——這本來就是「kernel／外層」該做的事，不是 daemon 的。另：把子項 state 窗內容整份塞給策略格，是把下層的東西往別處遞（C-52），刪了就沒這問題。

9. **子項六態 `phase`（N-17 後半、暫定 b）** — 現況：starting／running／exited／backoff／stopping／removed，跟 state 七態撞名「不改」。第 4、8 條做完，backoff 沒了、removed＝不在表上、starting／stopping 沒人需要。KISS：拿掉 `phase`；表上一列只有 `{id, ctl, state, pid, code}`，`code` 是 null＝還在跑。要看細節讀它的 state 窗。要動：`aos_daemon_table.py`（`_Entry.phase`、`row`、`exited`）、N-17 後半、`daemon.md`、`ctl_state.md`「撞名」那段、`test_daemon.py`。風險：無；撞名問題跟著消失。

10. **N-10 指令資料夾（`ctl_dir`、`.done` 一問一答、九個 op）整套** — 現況：daemon 有兩種控制：宣告式 ctl 窗，加上指令式資料夾（add／set／pause／resume／add_times／remove／state／get／list），為此一整個 `aos_daemon_folder.py`（掃、pending、`ready()`、回覆寫不了的三層退路、`given_up`、`ScanFailed`／`ReplyFailed`）、`CommandBad`／`OpUnknown`／`NotFound`／`Exists`／`Conflict`／`Internal` 一串代號。KISS：**daemon 的 ctl 窗多一個 key `children`＝「我要表上有誰」**（同 daemon.json 的 `children`，沒寫＝起來那份）。daemon 每圈比表：多的起、少的停掉等它結束再拿掉。這正是 N-06「ctl 寫的是我要它現在怎樣，整份就是全部期望」的本意。set／pause／resume／add_times 本來就只是替你寫子 loop 的 ctl——ctl 誰都可以寫（N-06），自己寫；state／get／list＝讀 table 窗與子項的 state 窗。要動：刪 `aos_daemon_folder.py`、N-10、`ctl_dir`（含「ctl 不能在 ctl_dir 裡」的檢查）；`aos_daemon.py`（ctl 認 `children`）、`aos_daemon_table.py`（只剩 add／stop／tick／write）、N-28、N-11（「位置／身體類不能從 ctl 改」要放行 `children`）、`daemon.md`、`ctl_state.md`、demo `run.py`（兩份）與 `daemon.json`、proto8-1 demo、`test_daemon.py` 大半。風險：起不了的子項沒有回覆通道——記在它那一列（`error`）。推翻 10-12 的 N-10。

11. **daemon 自己的 `inst` 身體（N-28「loop.json 的嚴格超集」）** — 現況：daemon＝loop 子類，自己每拍還能跑一個 inst，所以 daemon 有 `times`、`interval_ms`、`inst`、`last_code`、stdout 每拍一份。KISS：daemon 只顧表，沒有身體；它的 ctl 只認 `paused`（不比表）、`stop`（收工）、`children`；state 只有 `state`、`pid`、`last_error`、`loops`。要跑東西＝表上加一個 loop。要動：`aos_daemon.py`（不再繼承 `Loop` 的節奏與 inst；只借 ctl／state 那兩個類別）、N-28、N-31（daemon 那半句）、`daemon.md`、`test_daemon.py`。風險：推翻 10-14 候選 g；「一份 loop.json 丟給 aos-daemon 也能跑」這句沒了。

12. **N-19 窗必填** — 現況：N-09、N-13 說窗選填、沒給就不開；N-19 再開例外：loop／daemon 的 ctl、state 與 fsm 的 state 必填，為此 lib 有 `require()`、代號 `WindowMissing`。KISS：窗一律選填（一條規則，沒有例外）；loop 沒 ctl＝只能用訊號停、沒 state＝結果在 stdout，都成立。fsm 的 `state` 不是「窗」而是它的記憶（像 `start`），列在 fsm 的設定必填項裡（N-36 那邊），不用窗的規則管。要動：N-19 刪、N-09／N-13 的例外句刪、N-39 一句；`aos_ctl_state.py` `require`、`aos_loop.py`、`aos_fsm.py`（改成 FieldType）、兩種 kernel 的 `WindowMissing`、`loop.md`、`daemon.md`、`ctl_state.md`、`test_loop.py`／`test_daemon.py` 的 WindowMissing 測試。風險：推翻 10-14 夜使用者的裁定；daemon 替子項補 `work_dir/N/ctl.json`、`state.json` 照舊（它要讀，所以它自己給）。

13. **N-15 鎖、N-16 信箱兩形、N-14 的實作叮嚀** — 現況：N-15 鎖窗（mkdir、`holder.json` 租約、收屍）沒有任何實作（fsm 的 lock 已拿掉）；N-16 說信箱兩種都收，只做了 Maildir；N-14 還寫了 fsync 不強制、比內容不比 stat、inotify 加速、FUSE 效能、未拍板的 IPC 研究頁連結。KISS：N-15 整條刪（沒機制就別寫）；N-16 只留 Maildir 一種；N-14 瘦成一句：「窗＝設定裡給路徑的一個 JSON 檔（或資料夾），寫法照 N-05 先暫存再改名；沒給＝不開」。要動：NORMS 05。風險：鎖以後要做再寫一條，照當時的需求寫，不會比現在這條更難。

14. **N-01、N-02、N-03 時空三條** — 現況：N-01「大家都要看時鐘」沒有任何程式看（也跟 C-37「可看可不看」打架）；N-02「資料夾別亂弄」是口號，具體規則已經是 N-05；N-03 打包是 kernel 的事，已在待定【kernel】公告。KISS：02 檔只留一條「時鐘＝一個檔裡的回合數，aos-tick 加一，要看就讀它」；N-02 刪（N-05 的「細則之一」改成獨立一條）；N-03 原文併進待定【kernel】公告那條。要動：NORMS 02、N-05 的半句、08 待定。風險：三條都是使用者 10-12 原文，刪的是條文不是原文——原文留在 thinking。

15. **table 窗的 `kind`** — 現況：N-14 說「窗內自述種類 `kind`」，但只有 table 窗寫 `"kind": "aos-daemon-table"`，ctl、state 都沒有。KISS：刪 `kind` 與 N-14 那半句；檔名與設定裡的 key 就說明了種類。要動：`aos_daemon_table.py` `write`、N-14、`daemon.md`、`test_daemon.py`。風險：無。

16. **ctl 的「stop 是終點、改回 false 不復活」與「stop 壓過 paused」** — 現況：loop 有 `self.stopping` 閂鎖專門記「讀到過 stop」，另有一句規則說 stop 壓過 paused。KISS：ctl 純宣告，沒有記憶：stop 為 true 時不起新的、正在跑的跑完就結束；兩個都 true 自然是不起新的、跑完就走，不用另寫一句。要動：`aos_loop.py`（`stopping` 閂）、N-07 兩句、`loop.md`。風險：結束前一瞬改回 false 會繼續跑——那就是你寫的期望。

17. **`CtlMissing`（ctl 檔不見了＝維持上一次）與 daemon 替子項先寫一份 `{}` ctl** — 現況：N-08 說檔不見了維持上一次、記警告；為此 `CtlFile` 要記「有沒有讀到過」；daemon add 子項時先寫空 ctl。KISS：沒有檔＝沒有期望＝全部回初始值（跟「沒寫的欄位＝初始值」同一條）。要動：`aos_ctl_state.py` `poll`、N-08、`aos_daemon_table.py` `add` 那行、`test_loop.py` `test_stop_now_and_bad_ctl` 的 CtlMissing 段。風險：刪掉 ctl.json 會把暫停的 loop 放行——宣告式本來就該這樣。壞檔（`CtlBad`）照舊維持上一次（編輯器寫一半不該把它放行）。

18. **`aos_loop.py` 對 `aos_ctl_state` 的 re-export** — 現況：loop 把 ctl／state 那組名字全部再 export 一次，daemon、fsm 從 `aos_loop` 拿 `write_json`、`read_state`；README 還要解釋相依鏈。KISS：誰用誰直接 `from aos_ctl_state import`，loop 不轉手。要動：`aos_loop.py`、`aos_daemon_table.py`、`aos_daemon_folder.py`、`aos_fsm.py`、lib README 相依那段、測試裡的 `aos_loop.parse_ctl`。風險：無。

## 二、合併

19. **N-06、N-07、N-08、N-11 四條 ctl 規則 → 一條** — 現況：四條互相引用，N-11 還順便定義「設定檔」（那是 inst／命令列的事）。KISS 一條：「ctl.json＝整份期望，誰都可以寫、後寫的算、程式只讀；認 `paused`、`stop`、`times`、`interval_ms`（daemon 再加 `children`）；沒寫的＝設定檔初值、沒檔＝全部初值、壞檔＝維持上一次並記進 state 的 `last_error`；state 回報生效值。」要動：NORMS 05、`ctl_state.md`。風險：無，意思不變（除了第 16、17 條改掉的兩處）。

20. **N-09、N-13、N-14 三條「窗是什麼、放哪、要不要開」→ 一條** — 現況：三條都在講「位置由設定給、沒給不開、只有自己寫」，N-13 多了 Plan 9／FUSE 的比喻與「跟 stdio 無關」。KISS：併成第 13 條那句，加「state 只有被控的那個自己寫」。要動：NORMS 05。風險：無。

21. **state 的 `last_warning` 併進 `last_error`** — 現況：10-15 晚剛把 stderr 的警告改記 `last_warning`，於是 state 有兩格、程式要分「這個算錯還是算警告」（`error_now`／`warning_now` 兩個掛鉤、daemon 還要排「ctl 窗的優先」）。KISS：一格 `last_error`＝「最近一件自己遇到的不對」（代號: 白話）；退出碼由程式自己判（loop 本來就靠 `inst_exit` 判，不靠這格）。第 2、3、4、8、10 條做完，會進這格的只剩 `CtlBad`、aos_inst 出錯那行、kernel 回信寫不進去。要動：`aos_ctl_state.py` `state_doc`、`aos_loop.py`、`aos_daemon.py`、兩種 kernel、N-08、N-29 裡「`last_warning`」字樣、`ctl_state.md`、`aos_cli.py` 檔頭、測試斷言。風險：看的人靠代號分輕重；推翻今晚 S1 的欄位名（做法不變，只是少一格）。

22. **state 七態 → 五態** — 現況：`starting`（只有 daemon 替還沒寫 state 的子項答，第 10 條做完沒人答）、`stopping`（結束前一瞬寫一份，沒人來得及讀）。KISS：`waiting`／`running`／`paused`／`done`／`stopped`。要動：`aos_ctl_state.py` `STATES`、`aos_loop.py` serve 的 finally、N-17、`ctl_state.md`、`daemon.md`。風險：無。

23. **`write_json` 的「建一層、不 -p」（盤點 P3）** — 現況：特例規則，要解釋「只建一層、再上層沒有照樣寫不了」。KISS：`os.makedirs(exist_ok=True)`，一句「窗所在資料夾沒有就建」。要動：`aos_ctl_state.py`、`ctl_state.md`。風險：路徑打錯會多出資料夾——打錯是使用者的事。

24. **兩種 kernel 的 state 窗抄 loop 骨架** — 現況：kernel 是一拍一次的程式（跟 fsm 一樣由 loop 拍），卻寫 `state: "waiting"`、`pid`、`beat`、永遠是 null 的 `last_error`，說明寫「loop 骨架的…加 kernel 的…」；而 N-39 剛定 fsm 這種單次程式不寫時間、pid。KISS：同一把尺：單次程式的 state 只放自己的東西——LLM kernel：`runs`、`seen`、`budget`、`served`、`last_error`（回信寫不進去）；通用 kernel：`runs`、`queue`、`running`、`slots`、`budget`、`served`、`seen`、`judge_error`、`last_error`。活不活看拍它的 loop。要動：`aos_kernel_llm.py`、`aos_kernel_general.py`（`snap`）、`kernel_llm.md`、`kernel_general.md`、N-39 補一句「單次程式都這樣」、`test_gate.py`／`test_kernel_general.py` 斷言。風險：無。

## 三、跨層偷看／替別層做事

25. **daemon 把子項 state 窗整份塞給策略格** — 見第 8 條，策略格一刪就沒了。
26. **daemon 用 /proc 核對子項身分、替子項補 ctl／改 seq** — 見第 3、4、17 條；做完後 daemon 對子項只剩「起、寫它的 ctl、讀它的 state、收屍」四件事，全走窗。
27. **daemon 代寫子 loop 的 ctl 再等回音** — 見第 2、10 條；做完後 daemon 自己不代寫節奏類 key，只在收工時寫 `stop`。

（fsm 讀格 stderr、daemon add 先驗 inst：另一組人在處理，不重提。）

## 四、為了方便加、其實沒人用

28. `boot_id`、`beat`（第 3 條）、`interval_mode: fixed`（第 5 條）、`error_wait_ms`（第 6 條）、`seq`（第 2 條）、N-15 鎖（第 13 條）——全 repo 沒有人讀或沒有實作。
29. **`ctl_state.md` 的四組 key 大表** — 做完上面，「節奏／旗子／回音／位置」四組只剩兩組（能從 ctl 蓋的、不能的），表縮成兩行。要動：`ctl_state.md`。風險：無。

## 最小核心

從零重寫，窗這塊只留：

- **一條規則**：窗＝設定裡給路徑的一個 JSON 檔；沒給＝不開；寫法先暫存再改名；state 只有被控的那個自己寫、ctl 誰都可以寫。
- **ctl**：`paused`、`stop`、`times`、`interval_ms`（daemon 多 `children`），布林與整數，沒寫＝初值、沒檔＝初值、壞檔＝維持上一次並記 `last_error`。
- **state**：`id`、`state`（五態）、`pid`、`runs`、`times`、`interval_ms`、`last_code`、`last_error`、`signal`；內容變了才寫。
- **daemon 的 table 窗**：一列 `{id, ctl, state, pid, code}`，純給人看。
- **單次程式（fsm、kernel）的 state**：只放自己的東西，不抄 loop 骨架。
- **時鐘**：一個檔裡的回合數，aos-tick 加一。
- lib：`parse_ctl`、`want`、`CtlFile`、`StateFile`、`read_state`、`write_json`，六樣。

不在範圍：CONCEPTS（C-05～C-44 時空、C-36、C-48 雙形）照使用者「概念不用」不審；上面若提到概念只是用來對照。
