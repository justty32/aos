# proto5-2 實作的決定（2026-09-24）

← [實作總報告](README.md)｜規範：[spec/](../../spec/README.md)

編號規則：Q1～Q9 是 [proto5-2 README](../../README.md)「要使用者拍的」九題（隊長代使用者先定）；
D-n 是實作中撞到規範沒寫或矛盾、自己選的（一律選最保守的）。為了幾隊同時寫不撞號：隊長 D-1～D-19、kernel 隊 D-20～D-49、daemon 隊 D-50～D-69、cpu 隊 D-70～D-79、其他 D-80 起。
每條寫：撞到什麼、選了什麼、為什麼保守、翻案要改哪裡。

## Q1～Q9：九題

| 題 | 定成 | 可翻案？翻案要改哪裡 |
|---|---|---|
| Q1 帳本整份讀寫 | **先不動**，照 proto5 現況（一份 `K/state.json`）；目標先以「幾百到一千顆」為準，不拆帳本 | 可。要拆：`aos_kernel_ledger.py` 的讀寫、aos-agent 偷看 `procs` 的地方（`aos_agent_runtime.ledger`、`aos_agent_status`）、spec kernel-ledger／scale |
| Q2 agent 偷看整份帳本 | **先不動**，aos-agent 照舊每格讀 `K/state.json` | 可。要改：kernel 另維護一行程一小檔、aos-agent 改看它（proto5 aos-agent.md §10） |
| Q3 一顆 cpu 一支 Python | **先不動**，照 `aos-cpu` 現況；上限以千顆為準 | 可。要改：`aos_exec_cpu.py`（一支管多家）或換語言；daemon 的 fd 預算跟著變 |
| Q4 `cpu rm NAME` | **照草稿**：`NAME`＝`P/<i>`、永久退休該號（寫進 `skip`、`count` 減 1） | 可。只要「這次收哪一顆」：改 kernel 的 cpu rm 不寫 `skip`、改成換號 |
| Q5 既有池 `cpu add --env` | **照草稿**：拒絕（`PoolExists`，用法錯 2），改環境請編 info | 可。要允許：cpu add 改寫 `pools.P.envs`，tick 第 7 步第 4 小步本來就會重寫 `envs.json`；要活的一起換再加 `aos-daemon kill --all` |
| Q6 縮池要不要 `--now` | **照草稿**：沒有，一律做完再收；卡住用 `aos-daemon kill` | 可。要加：cpu rm 多一旗標、kernel 不等 busy 直接把號從 T 拿掉，並處理卡在 running 的行程 |
| Q7 拉不起來的號卡住的工作 | **照草稿**：不另訂放棄協定，唯一解是修家 | 可。要訂：新協定（確認沒人會跑那張單就回 Interrupted），動 kernel-pools §4 |
| Q8 daemon halt 後 boot 自動拉回 | **照草稿**：要；`pool.json` 留著 | 可。要不拉：daemon boot 不照 `pool.json` 排 pending，kernel 要改回每次 boot 重宣告 |
| Q9 退休 cpu 家的清理指令 | **照草稿**：家不刪、不做清理指令 | 可。要做：`aos-kernel cpu gc` 之類，先確認不在任何成員、daemon 看不到 |

## 隊長的 D-1～D-19

- **D-1 程式與入口**：`proto5/lib` 整份複製到 `proto5-2/lib`，`proto5/cli` 複製到 `proto5-2/cli`（任務書寫「含 cli/」，但 proto5 的 cli 在 lib 旁邊）。池模板的 `argv[0]` 指 `proto5-2/cli/aos-cpu`。
- **D-2 模組分工**：daemon 相關只在 `aos_daemon*.py`；kernel 相關只在 `aos_kernel*.py`；cpu 通知只在 `aos_exec_cpu.py`；`aos_home.py`／`aos_client.py` 只准**加**函式、不改既有函式的行為。
- **D-3 錯誤回音形狀**：沿用 proto5 `aos_home.error_response`：`{"code": -32000, "message": …, "data": {"code": "NameTaken"}}`；`-32602` 用 `params_error`（`data.code`＝`FieldTypeMismatch`、`data.position`）。kernel 判錯一律看 `data.code`，沒有 `data.code` 時用 `str(code)`。
- **D-4（＝ D-38 拍板）skip 一律保留不丟**：`cpu add／rm` 整理 `skip` 時只排序、去重，不丟大於最大成員號的項目，因為 Q4「永久退休」優先於 skip 長度；代價是 skip 只增不減，要清得手改 info。詳見下面 D-38。

## kernel 隊 D-20～D-49

- **D-20 帳本多出的格**：撞到——規範提到 `halting`、「每池記舊格數」、「帳本裡的 kernel 池」，但範例沒列欄位。選——`halting`（布林）、`stale`（`{池名: 舊格數}`）、`pools.kernel` 只有 `daemon`／`dpool`／`sent`／`pending` 四格（第 7 步不碰它）。保守：只加規範說要記的，`procs` 一字不改。翻案：`aos_kernel_info.new_state`、`aos_kernel_boot.boot` 第 3 步。
- **D-21 `want` 初值 null**：新池帳本格還沒處理過 info 時 `want`＝null（當空集合），第一格一定判成「變了」。翻案：`new_pool`。
- **D-22 舊格數怎麼數**：撞到——`delayed` 是全池共用的一個堆積，rm 時不知道那格在 ready 還是 delayed。選——記在行程的池名下；「舊格數 ×2 ＞ ready[P] 長度＋delayed 長度」就把 ready[P] 與整個 delayed 一起壓縮。行程已刪的 delayed 舊格被彈出時不減數（高估只會提早壓縮，不影響對錯）。翻案：`KernelLedger.mark_stale／compact`。
- **D-23 出錯後怎麼「不自動重試」**：`error` 不是 null 且沒設 `redeclare` 就不送單（連 draining 做完的重算也不送）；info 的 `count`／`skip` 變了（含進入停機縮池）才設 `redeclare` 再試；`Stopping` 到 `retry_at` 設 `redeclare`；boot 一律設。保守：錯誤的池不會每格狂送。翻案：`PoolsMixin.pool_step`。
- **D-24 新池解不出 daemon**：頂層與池都沒寫 `daemon` 的池，tick 不建帳本格、不送單，每格記一行 `pool_no_daemon` 事件；boot 照規範擋 `NoDaemon`。保守：不讓一個池讓整格退 1。翻案：`pool_step` 開頭。
- **D-25 scale 單重放前先看回音**：出貨時對方 `responses/` 已有同名回音就不再放（崩在「放完、清帳前」，避免 daemon 對同名單處理兩次）。同 proto5 `_daemon_call` 的做法。翻案：`flush_outboxes` 的 sends 段。
- **D-26 stop 控制檔進 `deletes`**：proto5 是當場存帳本再刪檔；四個提交點下改成「phase 改動進提交點 3、stop 檔名進 `deletes`、第 10 步刪」。崩在提交點 3 前＝下一格再看到 stop 檔，冪等。帶 id 的壞 stop 回音走 `replies`。翻案：`Kernel._stop_control`。
- **D-27 discard 且兩個檔都不在**：proto5 `collect` 會一直 `continue` 卡住那顆；這裡直接取消（拿掉行程、放回號碼），跟 rm 當下遇到同情況的處理一致。翻案：`Kernel.collect`。
- **D-28 boot 交接兩個 kernel 池**：帳本的與 info 的 kernel 池不同、又在同一個 daemon 家時，第二張縮 0 單叫 `k-<chain>-boot-scale-kernel-down-2.json`（規範檔名只有一張）。翻案：`boot` 第 2 步。
- **D-29 proto5 帳本不接手**：`K/state.json` 有 `cpus`、沒 `pools`＝`LedgerVersion` 退 1，請人先 halt 舊版、移走帳本（boot、halt 都擋）。保守：不猜舊帳本怎麼搬。翻案：`_ledger_version_check`。
- **D-30 boot 半途失敗的 ack**：第 2 步回錯或逾時時帳本還沒碰，已收到的回音當場放 ack（不留在 daemon 家）；第 5 步回錯時帳本已寫、ack 記進出貨箱，退 1，再 boot 即可。翻案：`boot`、`_ack_now`。
- **D-31 halt 的 not running 與「每個池」**：帳本沒 kernel 池、kernel 池的 daemon 不活、或 daemon 那邊 kernel 池摘要不在／`count 0`＝`not running`、不放單；`phase` 已是 stopped 就不再放單、直接等。等的「每個池」＝帳本 `pools` 每一格（含 kernel 池、搬池中的舊位置），按 (daemon, dpool) 去重。翻案：`aos_kernel_boot.stop／_halted`。
- **D-32 release 遇到 dirty 不放回 free**：那池本格要重算，重算會從頭算 `free`，先放回反而可能重複。翻案：`KernelLedger.release`。
- **D-33 envs 摘要與模板重寫**：摘要＝`json.dumps(envs, sort_keys, 無空白)` 的 SHA-256 前 16；`envs.json` 與池模板 `inst.json` 一起重寫（boot、envs 變了、新池）；每顆 cpu 的 `inst.json` 只在缺時寫。翻案：`aos_kernel_pools.write_pool_files`。
- **D-34 init 寫進 info 的預設**：`tick_ms`…`bad_after` 五格照 proto5 寫進去；`cpu`、`sweep` 不寫（讀時補）；`--config` 可以寫 `daemon`（proto5 禁止，proto5-2 規範允許，`--daemon` 優先）。翻案：`info_from_config`。
- **D-35 kernel.log 新事件**：`scale_send`、`scale_echo`（`result`＝ok 或錯誤碼）、`pool_new`、`pool_envs`、`pool_gone`、`pool_no_daemon`、`bad_notify`、`halting`、`stopped`；舊的 `dispatch`／`response`／`bad`／`tick_error` 不變，`cpu` 欄改成 `P/<i>`。
- **D-36 ls 只求不崩**：`aos-kernel ls` 印鏈、按池一行（want／sent／busy／idle／draining＋daemon 摘要）、行程、排隊數；health 仍呼叫 `aos_kernel_health.health`（還沒改，會回 `broken`）。按池的完整 ls、health、check 留給下一隊。`boot` 成功印 `booted N pools, M cpus`。

**kernel 指令隊（第二階段）D-37～**：

- **D-37 cpu add／rm 只改字面的格**：撞到——「指示詞原樣保留、只動 count／skip／新池那格」，但那格本身若是指示詞（`"count": {"$ref": …}`、`pools` 整個 `$ref`）就沒法「只改那格」。選——`pools` 不是字面物件、或既有池那格／它的 `count`／`skip` 不是字面值＝`NotLiteral` 退 1、不寫；新池不碰別格，照加。保守：絕不把人寫的指示詞換成展開後的值。原本沒有 `skip` 鍵又沒東西要寫就不加這鍵。翻案：`aos_kernel_cpu._literal_pool`。
- **D-38 skip 整理與「永久退休」衝突**：撞到——kernel-info §5「大於最大成員號的 skip 寫入時拿掉」（隊長任務書也這樣寫），但 `cpu rm P/<最大號>` 寫進去的那號當場就大於新的最大成員號，會被丟掉；之後 `cpu add` 會用回那號（家壞了的那顆又回來）。選——照規範字面丟掉（排序、去重、丟大於最大成員號的；count 0 時全丟）。保守的點在於不自己改規範；**這條建議隊長拍板**。翻案：`aos_kernel_cpu._set_count` 改成「本次退休的號不丟」或整條不丟。
  **隊長裁定：保留不丟，因為 Q4 永久退休優先於 skip 長度；代價是 skip 只增不減，要清得手改 info。**
- **D-39 cpu add／rm 參數邊界**：`--count` 在 add 可以是 0（新池先宣告 0 顆；既有池印 `A -> A`），負數＝用法錯；`--env` 要 `KEY=VALUE`，KEY 空、以 `$` 開頭（會被當指示詞）、同 KEY 給兩次＝用法錯；`--daemon` 轉絕對路徑；池名、`--dpool` 不合 kernel-info §5 規則＝用法錯 2（不等寫完再讀驗報 `FieldTypeMismatch`）；改完讀驗不過（例如 count 超過 1000000）＝退 1 不寫。`PoolExists` 走用法錯 2、代號照印 `PoolExists`。翻案：`cpu_add`／`cpu_rm` 開頭。
- **D-40 「kernel 沒在跑」怎麼判**：帳本 `phase` 是 `running`、帳本有 kernel 池、那個 daemon 活著、它那邊 kernel 池摘要 `running` > 0，四個都成立才算在跑；否則多印「kernel 沒在跑：下次 boot 生效（aos-kernel boot --target K）」。規範只說 add 要印，rm 也照印（同理）。翻案：`kernel_running`、`_report`。
- **D-41 cpu ls 的欄位來源**：`want`＝info 現在的 count（剛 `cpu add` 完就看得到）；`sent`／`busy`／`idle`（帳本 `free` 長度）／`draining` 取帳本；kernel 池只印 want／sent。info 有、帳本沒有＝`sent -`＋「還沒宣告」；帳本有、info 沒有＝「移除中」；搬池中印新位置。daemon 標籤：用的是頂層 `daemon` 就只印 dpool，否則印 `D dpool`。池列 kernel 排第一。`--pool` 每顆的狀態除了 idle／busy／draining 另有「待宣告」（在 W 不在 S）、「收掉中」（在 S 不在 W、沒在忙）；kids 檔沒有時：在 S＝`daemon pending`，否則 `daemon -`。有 draining 時池行尾印「收掉中 N 顆，等 <行程名>」（kernel-pools §3）。翻案：`aos_kernel_cpu.pool_row／row_line／cpu_rows`。
- **D-42 ls 的格式**：health 行之後保留 proto5 的鏈資訊，併成一行 `chain … phase … last_seq … kernel cpu kernel/0 current … requests N`（鏈斷了靠它看）；計數行固定 `queued／running／done／bad` 四格（有別的狀態接在後面）；預設只逐行印 `bad`（agent 的暫停標記只在 bad 行與 `--procs` 出現，第一行 health 仍會講）；`--json`＝`status()` 快照＋`health`，`--pool` 時 `pools`／`busy`／`procs` 只留那池；`--pool` 在 info 與帳本都沒有＝`NotFound` 退 1。翻案：`aos_kernel_cli._summary`。
- **D-43 health 的碼與順序**：dirs（`requests/`、`responses/`、`pools/`）→ stopped → daemon（先 kernel 池的 daemon，再其他已宣告池的 daemon）→ cpus（kernel 池摘要不在或 `running 0`）→ stall → pools（新碼：池 error、池不見了，可多池用「；」接）→ 停機收尾中到這裡就算 ok（池本來就在縮）→ recovering（搬池中、池少 N 顆）→ ok。「少顆」「搬池中」用 **recovering** 碼，讓 aos-agent status 照 fix-r5 當成「會自己好」不喊「kernel 家有問題」。縮到 0 的單在路上時摘要消失不算「池不見了」。提示裡的 `aos-daemon ls` 帶 `--target D`（規範原句沒帶，但 fix-r4 起不帶會找錯家）；停機中的提示拿掉 `--daemon-target`（boot 不收了）；daemon 沒在跑的提示照 handoff §2「每天重開機」改成「先 aos-daemon boot；之後 health 還不是 ok 再 aos-kernel boot」。翻案：`aos_kernel_health.health`。
- **D-44 check 的細節**：`--daemon-target` 保留（proto5 §6 有；池表以外多查一個 daemon，PATH 也取它的 `/proc` 環境），省略時 PATH 取 kernel 池那個 daemon 的；池解不出 daemon＝bad（boot 會 `NoDaemon`）；`cpus` 項只看 daemon 活著的已宣告池，一個都沒有就不印；`K/pools/<池>/envs.json` 跟 info 的 envs 不同＝warn；沒 `--agent` 時 envs 整個是指示詞（看不出有沒有 `AOS_LLM_CONFIG`）的池不查 llm，有 `--agent` 時它的 `llm.pool` 一律查；`tool_pool` 跟 `tick.pool`／`llm.pool` 一起查。翻案：`aos_kernel_check.check`。
- **D-45 `init --config` 內容是 JSON null**：`info_from_config(None)` 會當成沒給 `--config`、建預設家；CLI 先擋，`FieldTypeMismatch` 退 1、不建家（fix-r4 的既有行為）。翻案：`aos_kernel_cli._run` 的 init 段。
- **D-46 add 的池不在時的提示**：kernel 回 `-32602` 且 `data.position` 是 `params.pool` 時，CLI 在訊息尾補「先 aos-kernel cpu add --target K --pool P」。翻案：`_cli_request`。

## daemon 隊 D-50～D-69

- **D-50 fd 1 接 /dev/null 怎麼做**：規範要孩子只留 fd 0 一條 pipe，但 `aos_exec.spawn_target` 寫死 stdout=PIPE，`aos_exec.py` 不是 daemon 隊的檔。
  選：`aos_daemon_pools.spawn_child` 照抄 `spawn_target` 的流程（同樣讀目標、同樣的 SpawnFailed），只換自己的 launcher（stdout=DEVNULL），借用 `aos_exec._load_control_inst`／`_execute_inst`。保守：不改別隊的檔、讀驗行為一字不差。翻案：`spawn_target` 加一個 stdout 參數，`spawn_child` 改回呼叫它。
- **D-51 第 1 版 info 缺 `restart_max_ms`**：v1 常見 `restart_delay_ms` 大於 60000 就會撞「max ≥ delay」讀驗。選：缺的時候預設取 max(60000, `restart_delay_ms`)。保守：舊家照樣開得起來、不改舊鍵意思。翻案：`aos_daemon.load_info`。
- **D-52 `TooMany` 的上限**：protocol 寫「超過 `max_children`」，daemon-home §1 寫「實際上限再取 開檔上限 − 64」。選：兩者取小（＝fd 預算）。保守：宣告了卻永遠拉不滿的情況提早回錯。翻案：`aos_daemon_rpc.Requests.scale` 第 6 步改用 `info["max_children"]`。
- **D-53 沒給 `decl` 的 scale**：不擋（不算 Stale），`pool.json` 的舊 `decl` 留著不清。保守：CLI `--force` 改了 kernel 的池之後，kernel 下一張單的新鮮度照樣比得出來。翻案：scale 第 7 步。
- **D-54 池不在、count>0 卻沒給 `target`**：回 `-32602`（position `params.target`），判在第 5 步之後，所以「池不在、count 0、沒 target」照樣成功 ver 0（boot 的縮到 0 單可以不帶樣板）。
- **D-55 開機讀到壞的 `pool.json`**：整個不開（`ReadFailed`、退 1），在殺舊孩子、對帳之前就判。保守：不猜、不默默丟掉宣告；state.json 壞了 proto5 也是這樣。翻案：`aos_daemon._scan_pools` 改成記一行、跳過那池。
- **D-56 開機要殺哪些 pid**：只拿 kids 檔 `state` 是 `running`／`killing` 的 pid（加上舊版 `state.json` 的 `children`）。`dead`／`failed`／`pending` 的 pid 早就收過屍，再送訊號只會打到被重用的 pid。翻案：`_scan_pools`。
- **D-57 活滿 `stable_ms` 不寫 kids 檔**：規範列的寫檔時機沒有這條（閒著不寫），所以記憶體的 `streak` 歸 0、summary 的 `restarting` 減 1，但 kids 檔的 `streak` 要到下次寫（死、kill）才更新。`ls --pool` 可能看到舊的 streak。翻案：`aos_daemon_loop.run_timers` 的 stable 分支加 `pool.write_kid`。
- **D-58 halt 時的 kids 檔**：成員的檔改成跟開機一樣的 pending（pid null、streak 0，gen／exits 照留），非成員的刪掉。保守：下一任不會拿舊 pid 去送訊號（同 D-56）。停機後 `summary.json` 是 `count N`、各格 0（成員「拿掉」了），重開再算。翻案：`Daemon.forget`。
- **D-59 kill 到 `dead`／`failed` 的號**：算進 `killed`，`next_at` 改成現在、馬上排隊重拉，`streak` 不動。翻案：`Requests.kill`。
- **D-60 `restarting` 怎麼算**：拉起來那一刻 `streak > 0` 就算，活滿 `stable_ms` 取消。kill 重來的那顆若之前有 streak 也算；daemon 重開後 streak 歸 0，所以不算。
- **D-61 CLI scale／kill**：daemon 沒在跑就不放單、`NotRunning` 退 1（放了會在下次開機才生效，人看不懂）；`--skip` 省略＝沿用 `pool.json` 現在的（送 `[]` 會把退休的號叫回來）；池不在、count>0、沒 `--inst`＝用法錯 2；`--inst`／`--home` 相對路徑先轉絕對。`--force` 送的 owner 是池現在的 owner，不帶 `decl`。
- **D-62 CLI ls 的細節**：第一行的 `children`＝各池 running＋pending＋dead＋failed＋killing＋draining 的和；`busy` 欄：活著且忙＝`busy`、活著不忙＝`idle`、其他＝`-`；有 kids 檔的 pending 另印 pid／gen／exits；`--json` 多一格 `daemon: {running, pid}`，其餘形狀同 protocol §3 的 ls 回音。只看有 `summary.json` 或 `pool.json` 的池；`--pool` 兩個都沒有＝`NotFound` 退 1。
- **D-63 開機時沒有 `pool.json` 的池資料夾**（崩在拿掉池的中途）：裡面 kids 檔的舊 pid 照樣殺，然後整個資料夾刪掉。
- **D-64 fork 之後 kids 檔寫不進去**：不送 `go`、直接關 fd 0（孩子讀到 EOF 自己退），那顆照常收屍、當成死了（dead、加 streak）。同 proto5「表寫不進去就不 go」。
- **D-65 `waitpid(-1)` 跟 `subprocess.Popen` 共處**：收屍後把 `Popen.returncode` 補上，免得 Popen 之後自己再 waitpid 同一個（可能已被重用的）pid。

**規範有洞、daemon 端處理不了的（kernel 隊要知道）**：
1. 池縮到 0 收完就從 daemon 消失，連 `decl` 一起忘掉；之後才被處理的舊單（比現在的 decl 舊）會把池重建——Stale 只擋得住「池還在」的情況。同一圈裡先後處理的兩張不受影響（池在那圈結束才拿掉）。kernel 放單的檔名 `k-<chain>-<seq>-…` 的 seq 沒補零，照字典序處理時 `-10-` 會排在 `-9-` 前面，靠 decl 擋。
2. daemon `halt` 之後 `summary.json` 留著 `count N`、各格 0；kernel `cpu ls` 在 daemon 沒跑時會看到「宣告 N、0 顆」。
3. `TooMany` 的上限跟 daemon 開起來時的開檔上限有關（D-52）；同一份宣告換台機器可能被拒。
4. `pool_kid` 回 `None`＝還沒拉過（pending）或讀壞了，兩者分不出來（照約定表）。

## cpu 隊 D-70～D-79

- **D-70 `notify` 寫 `null` 算不算「有寫」**：cpu-notify §1 只講「有寫就要是絕對路徑字串」，沒講 `"notify": null` 算不算「有寫」。**選最保守**：鍵存在（不管值是什麼）就要通過型別＋絕對路徑檢查，`null` 通不過（型別不是字串）＝`FieldTypeMismatch`。理由：不想讓使用者以為 `notify: null` 等同「不寫這個鍵」而悄悄關掉通知——寫錯就直接報錯，比默默不通知安全。翻案要改：`aos_exec_cpu._validate_notify`，把 `value is None` 另外放行當「沒開」。
- **D-71 啟動補丟時哪些檔算「回音」**：cpu-notify §3 說「對 `responses/` 裡每一份回音補丟一次通知」，沒講要不要濾檔名。`responses/` 理論上只會有 `<name>.json`（放單用的 `.tmp` 半成品是 `requests/` 那邊的事，不會出現在 `responses/`），但**選最保守**：只認檔名以 `.json` 結尾的項目，其餘（含任何意外的 `.tmp`、目錄）一律跳過，不當回音處理。翻案要改：`aos_exec_cpu._notify_backfill` 的檔名過濾。
- **D-72 放通知的寫法**：直接重用既有的 `aos_home.link_json`（同目錄 `.tmp`→`link`→刪 `.tmp`，本來就是規則一那套放單寫法），`FileExistsError`（`aos_home.RequestExists`）當成功、其餘 `aos_home.HomeError` 才記 `NotifyFailed`。沒有另外重寫一套放單邏輯。理由：`aos_home.py` 只准加函式不准改行為，而 `link_json` 現成的行為完全對得上 cpu-notify §2／§3.1 的要求，重用比照抄一份更保守（少一套邏輯要保持一致）。若之後要讓通知內容允許覆蓋既有同名檔，要改 `aos_exec_cpu._send_notify`，不能改 `aos_home.link_json` 的行為（那是共用函式）。

## 其他 D-80～

### 整合測試隊（第二階段，D-80～D-89）

- **D-80 K 經過 symlink 時每則 resp- 通知都被當成壞通知**：現象——K 家的路徑裡有 symlink（例如 `/link/K`，`/link` 指到 `/real`）時，
  真 aos-cpu 丟來的每張通知都在 kernel.log 記一行 `bad_notify`（「home 不在 K/pools/*/cpus/ 底下」），回音只能等巡檢／`recent` 收，通知形同沒開。
  根因——cpu 的 `home` 是 `os.path.abspath(".")`＝它 `getcwd()` 的**實際路徑**（`/real/K/pools/…`），kernel 卻拿字面的 `self.home / "pools"`（`/link/K/pools`）比。
  修法——`aos_kernel_engine.Kernel._notified_cpu`：先照舊用 normpath 字面比，比不上再把通知的 home 與 `K/pools` 都 realpath 之後比；
  兩種都比不上才算壞通知。其他壞通知的判法不變（仍只刪、記 log、不退 1）。測試：`test_p52_e2e.Grow.test_notify_through_symlinked_kernel_home`。
  保守：只多接受「同一個實際位置」的寫法，不放寬 `P/<i>` 格式或 `busy` 檢查。翻案：刪 `_notified_cpu` 的第二組比法（那 symlink 的 K 就只靠巡檢收音）。

### agent 隊（proto5-2 實作隊第二階段，D-90～）

- **D-90 `_already()` 的 discard 怎麼查**：kernel-ledger.md 只說「`on[NAME]` 指的那格 `busy[...]` 的 `discard`」，沒講 `on` 剛好沒這個 NAME（帳本卡在中間狀態、或壞了）時要不要退回掃描。選：先查 `on.get(name)` 拿格子鍵，格子存在就直接看它的 `discard`；`on` 沒有這個名字（或格子不在 `busy` 裡）就退回掃一遍 `busy`，找 `proc == name` 且 `discard` 的格子。保守：跟 proto5 舊版「掃全部 slots」的行為完全相容，只是多了一條正常路徑的快路徑，帳本形狀有點走樣也不會直接判「查不到」。翻案要改：`aos_agent.py` 的 `_already()`。
- **D-91 `cpu_logs()` 不再列出每顆 cpu 名**：proto5 版本會把同池每顆 cpu 的名字都列出來（`K/cpus/l1/cpu.log、K/cpus/l2/cpu.log`）；kernel-home.md 的新家是 `K/pools/<P>/cpus/<i>/`，cpu 的號碼由 `count`／`skip` 算出來，不會再一顆顆列在 info 裡，要列全部得額外解 members()。選：直接印萬用字元 `K/pools/<P>/cpus/*/cpu.log`（池名不在 `info.pools` 就整段池名也用 `*`），不去解那個池實際有哪幾號。保守：不用另外 import kernel 的 `members()` 公式（agent 這邊不该碰 kernel 內部算法），使用者拿著萬用字元路徑自己 `ls`／`cat` 一样能找到。翻案要改：`aos_agent_results.py` 的 `cpu_logs()`；連帶改了 `test/test_agent_fix_storage.py`、`test/test_agent_tick.py` 裡照舊路徑斷言的測試。
- **D-92（測試修正，非規範決定）`test_agent_integration.py` 誤用舊參數名沒報錯**：`self.setup_running(cpus=self.cpus)` 傳的是舊 proto5 的 `cpus=` 關鍵字，但 `_kernel_util.py`（整合測試隊已改成 proto5-2 版）的 `setup_running(self, pools=None, **settings)` 不會因為多餘的關鍵字報錯——`cpus` 被 `**settings` 吃掉、原樣塞進 `kernel-config.json` 當一個沒人理的頂層鍵，而 `pools` 因為沒傳、退回預設 `POOLS`（`default`／`llm` 各 1 顆、都沒 `envs`）。後果是 llm 池 cpu 沒有 `PATH`／`AOS_LLM_CONFIG` 環境，`aos-llm` 顯示 exit 127（不是 kernel 的 bug，是我這邊測試沒跟著改參數名）。修法：把 `self.cpus =` 改成 `self.pools =`（值也從舊的 `{'k': {...}, '0': {...}, 'llm': {...}}` 換成新的 `{'default': {'count': 1, 'envs': …}, 'llm': {'count': 1, 'envs': …}}`，kernel 池不用另外寫），六處 `setup_running(cpus=self.cpus, …)` 一併改成 `setup_running(pools=self.pools, …)`。改完 6 條整合測試全線變綠。
