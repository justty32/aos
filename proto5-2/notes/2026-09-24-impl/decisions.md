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
