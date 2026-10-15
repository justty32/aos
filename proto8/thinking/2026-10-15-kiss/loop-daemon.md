# KISS 審視：loop 與 daemon（稿，10-15 深夜）

範圍：NORMS [04 loop 與 daemon](../../NORMS/04-基礎設施-loop與daemon.md)（N-10、N-28、N-31、N-44）與 [05 窗](../../NORMS/05-基礎設施-窗.md) 裡 loop／daemon 讀 ctl、寫 state 的那幾條（N-06～N-08、N-11、N-17、N-32、N-33）；程式 `aos_loop.py`、`aos_daemon.py`、`aos_daemon_table.py`、`aos_daemon_folder.py`、`aos_proc.py`、`aos_ctl_state.py`（共用）；說明 `loop.md`、`daemon.md`、`ctl_state.md`；`demo/daemon.json`、`demo/run.py`；`tests/test_loop.py`、`tests/test_daemon.py`。CONCEPTS 不審。

> **只是稿，程式、規範、說明一個字都沒改。** 每條一個推薦，不攤方案。先砍、再併。別的 agent 正在處理的（daemon 不驗 inst；TARGET 全拿掉→children 內嵌、`id` 必填；命令列零引數、`-` 退場；`run()` 只收 dict）這裡不重提，只在最後一段說它們還能怎麼更簡。

## 一、砍（daemon）

**D1. 控制資料夾與九條指令（N-10、`aos_daemon_folder.py`、`Table` 九個方法）**
- 現況：daemon 掃資料夾收 `add／set／pause／resume／add_times／remove／state／get／list`，大半是「daemon 替你寫子 loop 的 ctl 窗、替你讀子 loop 的 state 窗再轉述」，還要等子 loop 的 `ctl_seq` 趕上才回 `.done`。
- KISS：**基礎實作不做控制資料夾**。要暫停、停掉、改哪個子 loop＝直接寫那個 loop 的 ctl 窗（N-06 本來就說誰都可以寫）；要看它＝直接讀它的 state 窗。daemon 只管「起 children、顧到它們結束、收工」；要動態多一個 loop＝再起一個 daemon。
- 動到：`aos_daemon_folder.py`（整檔刪）、`aos_daemon_table.py`（指令方法、`acked()`、`update_ctl()` 刪）、`aos_daemon.py`、`daemon.md`、N-10（移到待定「標準實作」）、`demo/run.py`、`demo/README.md`、`test_daemon.py` 大半。
- 風險：現在沒有任何東西在用動態 add（kernel demo 用靜態 `children`，agent 不用 daemon）；代價是沒有「等它真的停了才回」這種回執，要自己輪詢 state 窗。這是使用者 10-12 自己定的設計（「daemon 這塊才是資料夾」），要他點頭。

**D2. table 窗、`load` 接回、子項六態 `phase`、/proc 認領孤兒（N-28 後半、暫定 d、N-17 六態）**
- 現況：每個子項六態寫進 table 窗，daemon 死了重起可以靠 pid＋啟動時間認領孤兒；約 120 行，Linux 專屬。
- KISS：全刪。daemon 自己的 state 窗多一欄 `children: [{id, pid, state(alive|exited), last_code}]` 就是表；daemon 死了子 loop 照跑是你的事（本來就這樣），要收乾淨送 SIGTERM；重起不接回。
- 動到：`aos_daemon_table.py`（`_Entry.row/gone/status`、`load()`、`write()`、`phase`）、`aos_ctl_state.proc_started()`（沒人用了）、N-28、N-17 六態那句、待定裡的「清舊格子」、`daemon.md`、`ctl_state.md`、`test_table_window_and_load`。
- 風險：當機復原沒了；N-18 說基礎實作本來就不顧這種邊緣，要復原＝標準實作再加。

**D3. 策略格 `policies.child_exit`、退避、`MAX_EXITS`、`policy.in/out.json`**
- 現況：子 loop 結束時 daemon 寫兩個檔、起一張 inst 問「要不要重起」，格出錯當 leave，連崩 5 次強制 leave。
- KISS：刪。子 loop 結束＝記 `last_code`、留在 children 表上，沒了。要「掛了重來」＝loop 自己的 `times` 就是重來次數；要更聰明的監工＝標準實作。
- 動到：`aos_daemon_table.py`（`_exit_policy`、`backoff`、`retry_at`）、`aos_daemon.check()` 的 policies 驗證、N-28 的 `policies` 那句、`daemon.md`、`test_children_policy_inst_body`。
- 風險：沒有 supervisor 式自動重起；現在也沒人設過這格。

**D4. `work_dir/N/`：daemon 替子 loop 補 ctl／state 窗、接 `err.json`**
- 現況：子 loop 設定沒寫窗，daemon 替它在 `work_dir/N/` 生 ctl.json、state.json，stderr 落 `err.json`，remove 時刪格子、收工留格子。
- KISS：刪 `work_dir`。N-19 說 loop 的窗必填，所以 children 每項自己寫好 `ctl`、`state`（內嵌設定，路徑從 daemon 的 cwd 算）；daemon 不替下層發明路徑。子 loop 的 stdout／stderr 都丟掉：loop 跑起來之後的錯都在它自己的 state 窗，起不來＝children 表上 `last_code: 1`，想看細節就自己手動跑一次那份 loop 設定。
- 動到：`aos_daemon_table.py`（`add()` 的格子邏輯、`_spawn()` 的 err.json）、`aos_daemon.check()` 的 work_dir 預設、N-28、待定第 5 條（方案 B 那段）、`daemon.md`、`demo/README.md`。
- 風險：子 loop 設定錯時只看得到結束碼 1，debug 要多一步；這正是 C-53「你丟給我的就該是正常的」。

**D5. daemon 的 `inst` 身體、`times`、「daemon.json 是 loop.json 的嚴格超集」（N-28 前半）**
- 現況：daemon 繼承 `Loop`，靠六個掛鉤（`beat／idle／extra／error_now／warning_now／finish_up`）把「每拍跑一次 inst」和「掃資料夾、收屍」疊在一起；同名 key 預設不同（`times` null vs 1、`interval_ms` 200 vs 0、`grace_ms` 10000 vs 5000），`check_config()` 要帶 `defaults／need_inst／err` 三個參數讓兩邊共用。
- KISS：daemon **沒有身體、沒有 `times`**。daemon 要每拍做一件事＝children 裡放一個 loop（組合得到，不用內建）。daemon.json 只剩 `children`、`interval_ms`（多久看一次子項，固定一個就好）、`ctl`、`state`。daemon 不再是 `Loop` 的子類，跟 loop 共用的只剩 ctl／state 窗那一層（`aos_ctl_state`）和 `aos_proc`。
- 動到：`aos_daemon.py`（`Daemon(Loop)` 改成自己 30 行的小迴圈）、`aos_loop.py`（掛鉤、`extra()`、`need_inst`、`_PATHS` 裡 daemon 的 key 全拿掉）、N-28、N-31「daemon 沒 inst 就不吐」那句、`daemon.md`、`ctl_state.md` 的表、`test_loop_json_runs_as_daemon`、`test_no_inst_only_summary`、`test_times_one_shot`。
- 風險：「一份 loop.json 丟給 daemon 也能跑」這個性質沒了（10-14 使用者拍板的候選 g）；換到的是 loop 不再知道 daemon 的 key、兩支程式各自一眼看完。

**D6. `ctl_dir` 衝突檢查、`MkdirFailed`、`ScanFailed／ReplyFailed／given_up` 三層補救**
- 現況：ctl 不能放 ctl_dir 裡（Conflict）、建不了 ctl_dir 是錯、回覆寫不了就改名、改名也不行就記住不再讀。
- KISS：D1 做了就整段消失。D1 若不做，至少改成「讀→刪→做→寫 `.done`」一條路：讀到就刪指令檔，`.done` 寫不了只記一次 `last_error`，不會重做、不用 `given_up`；衝突、建資料夾都不檢查（誤用不歸組件管，N-18）。
- 動到：`aos_daemon_folder.py`、`aos_daemon.py`、`daemon.md`。
- 風險：`.done` 寫不了＝那條指令沒回執；本來就是檔案系統壞了的狀況。

## 二、砍（loop）

**L1. `interval_mode: "fixed"`、`skipped`、anchor／tick 對拍數學**
- 現況：兩種節奏模式，fixed 要算錨點、跳拍、對齊，state 多 `skipped`，ctl 也能蓋。
- KISS：只留「跑完再隔 `interval_ms`」。要準時＝aos-tick 自己看時鐘（它本來就是為此存在的），不是 loop 的事。
- 動到：`aos_loop.py`（`due()／start()` 砍一半、`skipped`）、`aos_ctl_state.py`（`_MODES`）、N-07／N-11 的 `interval_mode`、`loop.md`、`ctl_state.md`、N-31 總結裡的 `skipped`、`test_fixed_skips_missed_ticks`、proto8-1 `aos_tick.py` 檔頭那句。
- 風險：沒人用 fixed（demo、agent、kernel 全是 after）。

**L2. `error_wait_ms`、`ctl_poll_ms`、loop 的 `grace_ms` 三個旋鈕**
- 現況：三個獨立數字：aos_inst 出錯後至少隔多久、多久看一次 ctl、收身體時等多久再 SIGKILL。
- KISS：三個都刪。出錯後就照 `interval_ms`（出錯不是特殊節奏）；ctl 每圈都看（檔只有幾十 byte、已經是比 bytes 不比 stat，一圈 20 ms 讀一次沒成本；demo 裡到處寫 `ctl_poll_ms: 100` 只是為了測試快）；收身體＝對 aos_inst 送 SIGTERM 然後**等它**（aos_inst 自己保證過 `grace_ms` 會收掉子程式並結束，C-53 出口保證），loop 不再疊一層計時；daemon 同理等 loop。「巢狀 grace 慣例」（待定最後一條）跟著消失。
- 動到：`aos_loop.py`（`DEFAULTS`、`due()`、`serve()` 的 next_poll、`kill()` 改成 SIGTERM＋wait）、`aos_proc.py`（`kill()` 不帶 grace）、`aos_daemon*.py`、`loop.md`、`daemon.md`、demo 四份 loop.json 與 proto8-1 三份、N-28（daemon 預設那句）、`test_error_wait`。
- 風險：下層卡死 loop 就跟著卡（卡死不防護，已是原則）；`interval_ms: 0` 又一直出錯會空轉，那是設定的人的事。

**L3. ctl 窗只剩 `paused`、`stop` 兩個布林（N-07 後半、N-11「節奏類可蓋」、`want()`、`seq`）**
- 現況：ctl 還能蓋 `times／interval_ms／interval_mode`，沒寫的要「回初始值」（`initial`＋`want()` 一整套）；旗子是 `{"val", "now"}` 雙形要 `expand()`；還有流水號 `seq` 給 daemon 回執用。
- KISS：ctl＝`{"paused": bool, "stop": bool}`，沒了。改節奏＝停了重起（N-11 對位置類 key 本來就這麼說，節奏類跟著走）。`now`（當場收掉）刪：要當場收＝對 loop 送 SIGTERM（pid 在 state 窗，見 L5）。`seq／ctl_seq` 只有 D1 的回執在用，D1 砍了就一起砍（N-33 整條、N-14 的「回音以序號為準」那句留給別的窗）。
- 動到：`aos_ctl_state.py`（`parse_ctl` 剩兩個 key、`_flag`、`want()`、`CtlFile.seq` 刪）、`aos_loop.py`（`initial`、`stopping` 判斷簡化）、N-07、N-11、N-33、`loop.md`、`ctl_state.md`（四組表剩一行）、`test_want_reverts_to_initial`、`test_ctl_seq_and_heartbeat`、`test_ctl_now_kills_current`、`test_stop_now_and_bad_ctl`。
- 風險：跑到一半不能改次數與間隔（demo 的 add_times 那段沒了）；`now` 是使用者 10-12 親自寫的形狀，要他點頭。C-55 雙形還在，之後真要 `now` 再長回物件。

**L4. `stop_on_end` 認的是 fsm 的那行（N-44）**
- 現況：loop 讀身體的 stdout 檔，找 `{"from", "to", "end": true}`——loop 知道 fsm 長什麼樣（跨層）；還分「inst 有寫 stdout 檔就記 offset 讀那段／沒寫就接暫存檔」兩條路。
- KISS：留 key，改成 loop 自己的規矩：「**這次身體 stdout 的最後一份 JSON 帶 `"end": true`** 就不再起下一次」，不認 `from／to`、不知道 fsm。讀法只剩一條：有 stdout 檔就讀整份取最後一份（append 也成立，不用記 offset），沒有就接暫存檔。fsm 要配合的只是把 end 那行放最後（那是 fsm 那邊一行的事，N-40 的「結束時把格的結果當最後一份交出去」要翻成「end 那行最後」）。
- 動到：`aos_loop.py`（`_payload()` 的 offset、`_saw_end()` 的三條件）、N-44、`loop.md`、`aos_fsm.py` 一行（別人的範圍，只提）、`test_stop_on_end`。
- 風險：身體的結果自己帶頂層 `end: true` 會被當成結束——規矩寫明「`end` 是 loop 的 key，身體的結果別用」。

**L5. 訊號：loop 退 1＋`signal` 欄 vs daemon 退 0，兩套**
- 現況：loop 收到 SIGINT／SIGTERM／SIGHUP＝退 1、state 窗與總結多 `signal` 欄；daemon 收到＝退 0；`LoopError.exit` 屬性永遠是 1。
- KISS：loop、daemon 同一條：**SIGTERM／SIGINT＝`stop` 當場版**（收掉身體、寫最後一份 state、退 0），`signal` 欄刪，SIGHUP 不接，`LoopError.exit` 刪。這條也讓 L3 砍 `now` 站得住：當場停＝送訊號。
- 動到：`aos_loop.py`（`_CAUGHT`、`self.signal`、`run()` 的 Signaled）、`aos_daemon.py`（`run()` 吞 Signaled 那段）、N-43 裡「loop 被訊號停掉退 1」那句（總則，別人的檔，只提）、`loop.md`、`daemon.md`、`ctl_state.md`、`test_sigterm_clears_group`。
- 風險：分不出「跑完」跟「被停」——看 `runs` 與 `times` 就知道；10-15 晚才定的「loop 退 1」要翻回來。

**L6. 退出碼看「最後一次 aos_inst 有沒有錯」、`inst_exit`、`last_warning`**
- 現況：loop 結束時若最後一次是 aos_inst 自己出錯就退 1（中途錯後來好了不算），為此存 `inst_exit`、`last_err`；另有 `last_warning` 記 ctl 壞檔三種代號（`CtlBad／CtlMissing／CtlReadFailed`）、daemon 再疊四種。
- KISS：**loop 退 1 只有「起不來」和「state 窗寫不了」兩種**，身體怎麼錯都只在 state 窗 `last_error`（C-52：身體是下一層）。`last_warning` 刪：ctl 壞檔＝維持上一次、不記（N-13 的「安靜」）；daemon 那四種隨 D2～D4 消失。state 窗剩一個 `last_error`。
- 動到：`aos_loop.py`（`inst_exit`、`run()` 末段、`warning_now()`）、`aos_ctl_state.py`（`CtlFile.warning`、`_say`）、N-08（「原因記進 last_warning」那句）、N-29 的例子、`loop.md`、`daemon.md`、`ctl_state.md`、`test_inst_error_not_inherited`、`test_policy_failed_goes_to_state_not_stderr`、`test_state_last_error_scan_failed`。
- 風險：寫壞 ctl 沒人告訴你（寫的人自己驗）；aos_inst 一直起不來的 loop 退 0——看 state 窗。N-08 的 last_warning 是 10-15 晚使用者「都按照推薦」定的，要翻。

**L7. state 窗七態 → 三態**
- 現況：`starting／waiting／running／paused／done／stopping／stopped`，`starting` 只有 daemon 替子 loop 答、`stopping` 是收尾那幾十毫秒、`done` 與 `stopped` 都是終局。
- KISS：`running`（活著，不管身體此刻有沒有在跑）、`paused`、`stopped`（終局；是不是跑滿看 `runs`／`times`）。
- 動到：`aos_ctl_state.STATES`、`aos_loop.status()`、N-17 七態那句、`ctl_state.md` 狀態表、`demo/README.md` 樣本輸出、`test_paint_demo` 與 `test_agent_frame` 斷言 `"done"` 的兩處、`test_daemon.py` 多處。
- 風險：「身體正在跑」看不出來——要就看 `beat` 與 `runs` 變化；沒人靠 `waiting`。

**L8. stdout 兩種形狀（N-31）**
- 現況：每跑一次吐 `{run, code, ms}`，結束再吐 `{end, runs, skipped, last_code, signal}`；daemon 把子 loop 的 stdout 丟 /dev/null、demo 直接印。
- KISS：stdout 只在結束時吐**一份＝最後那份 state 窗的內容**（同一個形狀，不另定）。每拍那行刪。
- 動到：`aos_loop.py`（`record()` 的 emit、`serve()` finally 的 emit）、N-31、`loop.md`、`daemon.md`、`test_stdout_stream_stdin_flags`、`test_times_and_last_code`。
- 風險：想看每拍耗時＝身體自己寫；沒人讀過那行。

**L9. 心跳欄 `started`、`boot_id`（N-32）**
- 現況：state 窗帶 pid、/proc 啟動時間、開機 id、`beat`，每秒碰一次；啟動時間與 boot_id 唯一的讀者是 D2 的認領孤兒。
- KISS：D2 砍了就只留 `pid`、`beat`。
- 動到：`aos_ctl_state.py`（`_proc()`、`proc_started()`）、N-32、`ctl_state.md`。
- 風險：pid 重用誤判——基礎實作不顧（N-18）。這條在「窗」的範圍邊上，只提。

## 三、併

**M1. `aos_loop` 的 re-export 相容層**
- 現況：`aos_loop` 把 `aos_ctl_state`、`aos_proc` 的名字再 export 一遍（「既有的 import 照用」）。
- KISS：刪，誰要就從原檔 import。
- 動到：`aos_loop.py` 的 import／`__all__`、`aos_daemon_table.py`、`aos_daemon_folder.py`、`aos_fsm.py`（借 `write_json`）、lib README 相依那行。
- 風險：零。

**M2. `run(x)`／`load_config`／`check_config`／`main`／`Loop.run`／`serve` 六層入口**
- 現況：路徑或 dict 都收、`check_config(ident, doc, defaults, need_inst, err)` 五個參數、`_ok()` 一張驗證表裡混著 daemon 的 key。
- KISS：loop 剩 `main()`（stdin → dict）與 `Loop(cfg).run()`；驗證表只列 loop 自己的 key（D5 做了 daemon 自己驗自己的）。`run(dict)` 留一個給 Python 用（v3 的 J）。
- 動到：`aos_loop.py`、`aos_daemon.py`、`loop.md`、`daemon.md`、`test_run_api_and_ref`、`test_target_pointer`（兩檔）。
- 風險：零（v3 已經要動這裡）。

**M3. daemon 收工兩條路（`stop` 寫子項 ctl 等它們跑完 vs `now`／訊號整群 SIGTERM＋grace＋SIGKILL）**
- 現況：`shutdown(now, grace_ms, got)` 三個參數、兩段迴圈。
- KISS：一條：收工＝替每個活著的子 loop 寫 `stop: true`、等它們結束（loop 的出口保證）。要當場＝自己對子 loop 送訊號（L5）。
- 動到：`aos_daemon_table.shutdown()`、`daemon.md`、N-28、`test_sigterm_clears_loops`、`test_own_ctl_pause_and_stop`。
- 風險：daemon 收工會等子 loop 跑完這一次；fsm 一拍很短（C-25），可接受。

**M4. `aos_proc.py`：`_exited`、`_killpg`、`reap`、`kill` 四個**
- 現況：loop 與 daemon 各自組合這四個，加 `start_new_session` 的約定散在兩處。
- KISS：L2 之後剩兩個：`stop(proc)`＝整群 SIGTERM、等、整群補 SIGKILL 清孫、收屍；`reap(proc)`。檔頭一句「誰起在新 session、誰收整群」。
- 動到：`aos_proc.py`、兩個用它的檔。
- 風險：零。

## 四、demo 與測試

**T1. `demo/daemon.json` 與 `demo/run.py`**
- 現況：demo 的主角是控制資料夾（12 條指令一條條印回覆）。
- KISS：`daemon.json`＝`{"children": [once 的 loop 設定, tick 的 loop 設定], "ctl", "state"}`；`run.py` 剩：起 daemon → 印 daemon state 窗的 children → 往 tick 的 ctl 窗寫 `paused: true` 等它 paused → 寫回 → 寫 `stop: true` 看它 stopped → SIGTERM daemon 退 0。沒有 `$env` 也行（路徑從 daemon 的 cwd 算，run.py 把暫存資料夾當 cwd）。
- 動到：`demo/daemon.json`、`demo/run.py`、`demo/README.md`、`once/loop.json`、`tick/loop.json`（補 ctl／state、拿掉 `ctl_poll_ms`）。
- 風險：demo 變短、變無聊，但它示範的就是最小核心。

**T2. 測試**
- 現況：loop 23 個、daemon 20 個，一半在測旋鈕與指令。
- KISS：隨上面砍：loop 留 times／stop_on_end／ctl 兩旗／窗必填／起不來退 1／state 寫不了退 1／SIGTERM 整群收乾淨／孫程式清掉，約 9 個；daemon 留 children 起得來／子項結束記 last_code／stop 等子項／SIGTERM 退 0／窗必填／設定壞退 1，約 6 個。`helpers.leftovers()` 照留（它抓的正是「切不乾淨」）。
- 風險：零。

## 五、別人在處理、還能更簡的（只提一句）

- **daemon 不驗 inst**（principles 第 2 條）：D4 之後 daemon 連子 loop 的設定都不看內容，只原樣灌 stdin——比「驗自己收的那份」更乾淨。
- **children 內嵌、`id` 必填**（v3 的 H）：D2 之後 `id` 只拿來放進 children 表當名字，沒別的用；可以再退一步「沒寫 id＝用位置 0、1、2」，少一個必填錯。
- **命令列零引數、`-` 退場**（v3 的 I）：loop／daemon 的 `main()` 剩「讀 stdin 一份 JSON」，M2 自然成立。

## 最小核心（從零重寫只留這些）

- **loop**：設定 `{inst, times, interval_ms, stop_on_end, ctl, state}`；ctl `{paused, stop}` 兩個布林；state `{id, state(running|paused|stopped), pid, runs, times, interval_ms, last_code, last_error, beat}`；每次起 `aos_inst`、灌 stdin、等它結束、整群補 SIGKILL；stdout 結束時吐最後一份 state；退 0，只有起不來與窗寫不了退 1；SIGTERM＝當場 stop。約 150 行。
- **daemon**：設定 `{children: [loop 設定…], interval_ms, ctl, state}`；起每個 child（`aos_loop`，新 session，stdin 灌設定，stdout／stderr 丟掉）；每 `interval_ms` 收屍、寫 state `{state, pid, children: [{id, pid, state, last_code}], beat}`；ctl `{paused, stop}`；stop／SIGTERM＝替子項寫 stop、等它們、退 0。約 80 行，不繼承 loop。
- **共用**：`aos_ctl_state`（讀 ctl 比 bytes、state 暫存改名＋每秒心跳、`write_json`）、`aos_proc`（`stop`、`reap`）。
- **不留**：控制資料夾與指令、table 窗與接回、策略格、work_dir、daemon 的身體與 times、fixed 節奏、三個 ms 旋鈕、ctl 蓋節奏、`now`、`seq`、`signal`、`last_warning`、`skipped`、每拍 stdout 行、七態、`started`／`boot_id`、re-export、路徑／dict 雙收。

---

不在範圍（CONCEPTS，只讀不審）：C-36「daemon 自己也是一個 loop」與 D5 相衝、C-04 的 daemon 兩義——由使用者看 D5 時一併決定要不要改字。
