# astra-6：proto7-1 第六輪基礎設施回歸與可靠性測試

**原修補的主要路徑有效，但不能把相關需求全部關閉。** 原版 `test_astra5.py` 與 `test_owner_reload.py` **37／37 通過**；沿用第五輪重現並擴充故障點後，F-01～F-11 判為 **8 項已修、3 項部分（F-05、F-09、F-11）**。本輪列出 **8 個 bug、2 個技術選型邊界，沒有新增要使用者決定的方向問題**。

優先修正的是：控制回條故障擋住 stop、搬移時 runner 與掛載仍沿舊路徑、半行總結導致 ended 永久漏報。Q5 的正常拒絕／允許與停住標記有效，但失敗的第二個啟動者能改掉在跑的 daemon 所有權；Q6 正常更新有效，但驗證與動態掛載來源仍有缺口。

本次僅測本機副本，沒有呼叫任何 LLM，沒有執行 LM Studio、ollama 或 lms。kernel／agent 只讀取狀態；唯一啟動的 agent 是無信、無 goal 的 idle 通知計數測試。沒有改產品或其他文件，也沒有 commit／push。副本沒有 `.git`、`wf/` 或 CMake 根建置環境，所以版本以實際檔案為準，不宣稱已驗證所述 commit 的祖先關係；[來源指紋與收尾](2026-10-03-astra-6-infra-evidence/verification.json)記錄本次檔案 SHA-256。

依據：[核心規格](../../../proto7/spec/core.md)、[試做規格](../../spec.md)、[需求清單](../infra-needs.md)、[第五輪報告](2026-10-03-astra-5-infra.md)。重跑入口：[證據 README](2026-10-03-astra-6-infra-evidence/README.md)。故障注入固定競態順序，不代表自然發生率。PID 重用以 starttime 不符模擬；跨檔案系統以 EXDEV 注入加實際 copy／delete 模擬，沒有測真實第二個檔案系統、NFS 或斷電。

## 一、回歸表

「已修」是原重現通過；有同一承諾下的新失敗路徑則列「部分」，不把基本測試全綠當成整個 N- 已完成。

| 編號 | 判定 | 本輪操作、看到與證據 |
|---|---|---|
| F-01 stop 漏 ended 孫程序 | **已修** | 直接重跑上一輪 `stop_only.run('fork'/'forksetsid')`，不先下 task kill。兩案 SIGTERM stop 均 exit 0，約 31 ms，孫程序零殘留。[原重現](2026-10-03-astra-6-infra-evidence/legacy-stop.json)。另驗原父任務已 ended、留下巢狀子 daemon：stop-sweep 收到子 daemon，子任務亦結束。[巢狀](2026-10-03-astra-6-infra-evidence/sweep-nested.json) |
| F-02 歷史搬移讀成沒有／零 | **已修** | 重跑 `archive_probe.race` 三案，barrier 均觸發，原版 tock 實際搬移；agent 保留 act／steps 9，kernel 保留 inherited-state，usage 前／中／後均 1234，ended 不變 alive。[重現](2026-10-03-astra-6-infra-evidence/legacy-archive.json)。找不到時 unknown 與預算基準不歸零的對照亦通過 `F02ArchiveRace`。 |
| F-03 ESTALE／EIO 當消失 | **已修** | 上輪 scandir ESTALE、timeline stat EIO 重現：既有 node 與 sleeper 保留，`io_errors` 各 +1，有 `scan-error`；真 rename 掃到消失仍收任務，符合 Q4。[原重現](2026-10-03-astra-6-infra-evidence/legacy-scan.json) |
| F-04 新 daemon 收不到舊鎖主 | **已修，限身分可驗證** | 舊 tick／tock 已持鎖、SIGSTOP，再 kill daemon、重開。1.15 秒後新回合已到 r6，舊持鎖者已死，有 `stale-holder-kill`，不用手動放行。尚未持鎖的對照亦不倒寫。[tick](2026-10-03-astra-6-infra-evidence/handoff-tick-held.json)、[tock](2026-10-03-astra-6-infra-evidence/handoff-tock-held.json)。身分不足的安全／恢復界線見 G-10。 |
| F-05 摘要後中斷、重播重報 | **部分：原兩案已修** | 完整 append 後 SIGKILL，再做同回合 tock：r1 只有一行、stdout／round 標 replayed；daemon timeout 案亦補 tock、不重報 one-r1。[同回合](2026-10-03-astra-6-infra-evidence/replay-same-round.json)、[timeout](2026-10-03-astra-6-infra-evidence/replay-timeout.json)。**append 中途只留半行**則仍會永久漏 ended，見 G-08。 |
| F-06 毒項連坐 | **已修** | `F06Isolation` 五案全部通過：numeric name、毒 batch、任務 ctl-done 目錄、10**309 interval、wait-tock 非物件。合法 suffix／regular 可起，壞請求局部記錯，wait-tock 正常 timeout 且無 traceback。[逐項結果](2026-10-03-astra-6-infra-evidence/regression.json)。daemon 控制回條另有 G-01；新 reload 入口另有 G-05。 |
| F-07 加掛無回條又刪請求 | **已修** | `F07MountReceipt`：回條位置是目錄時，掛載可已生效，但請求留下、有 receipt_error、其他請求成功；移除障礙後補成功回條，再刪請求。[逐項結果](2026-10-03-astra-6-infra-evidence/regression.json) |
| F-08 冷啟動搶子根 | **已修** | `F08SubrootFirstScan` 三次冷啟動，預建 child node 但無 `.aosd`；父只接管 n，未啟動子線任務。[逐項結果](2026-10-03-astra-6-infra-evidence/regression.json)。這不等於重複 subroot 所有權已仲裁，見 G-04。 |
| F-09 動作中途重建鬼目錄 | **部分：原四案已修** | tick／tock × delete／rename 四案全過，掛鉤匹配 fd 路徑；空任務下將舊 node 換 symlink，round／總結也仍寫入原 inode。[tick symlink](2026-10-03-astra-6-infra-evidence/fd-symlink-empty.json)、[tock symlink](2026-10-03-astra-6-infra-evidence/fd-tock-symlink.json)。**有掛載／起任務時仍建舊路徑或留下 born**，見 G-02；子 daemon 自己寫 status／log 的路徑見 G-03。 |
| F-10 wake 洪水佔住主迴圈 | **已修：控制檔批次預算** | `F10CtlFlood` 的件數、檔名順序、status 更新檢查通過。一萬 wake 已開始處理後送排序在前的 stop，約 **10.2 ms** 收回條，停止後剩 9601 個 wake；150 wake＋stop 的低負載組，自程序啟動起約 **40.9 ms** 收回條。[洪水](2026-10-03-astra-6-infra-evidence/ctl-flood.json)、[預算內](2026-10-03-astra-6-infra-evidence/ctl-budget.json)。預算不保證整個主迴圈有界，見 I-11、G-01。 |
| F-11 測試／demo 刪空間後留程序 | **部分：原兩案已修** | 原 agent 啟動延遲 .5 秒重現現在成功退出，刪空間後無 agent；demo 的 stop 寫入注入 EIO，約 10 秒後 fallback SIGTERM，daemon rc0、無活後代，再清目錄。[agent](2026-10-03-astra-6-infra-evidence/legacy-agent-delayed.json)、[demo](2026-10-03-astra-6-infra-evidence/legacy-demo-eio.json)。`_proc.track` 的 atexit 遺失 group／grace，仍漏孫程序，見 G-07。 |

第五輪列「部分」的 I- 現況：

| 編號 | 現況 | 證據／界線 |
|---|---|---|
| I-01 舊動作倒寫／持鎖交接 | **原案例已修** | tick／tock 的 waiting 與 held 四組皆恢復且不倒寫。正常 owner 身分可驗證時，第五輪持鎖卡住的缺口已補；owner 身分讀不到不能宣稱無條件接管（G-10）。 |
| I-03 ended 與總結提交 | **部分** | 完整摘要後 kill 的漏／重已修；半行 append 仍可 ended 有、有效摘要無（G-08），N-20 尚不能關。 |
| I-04 主程序結束漏孫程序 | **原案例已修** | 未先 task kill 的 fork／setsid 正常 stop，以及 ended 父留下正常巢狀 daemon 的收尾均成功。未把本結果外推到已知的頑固多層停機 N-27。 |
| I-06 壞 interval 永久停線 | **已修** | 真 daemon 遇 10**309 仍到 r1，effective interval 1000、有 last_error；改 100ms＋wake 到 r3，程序活著。[真 daemon](2026-10-03-astra-6-infra-evidence/interval-live.json) |
| I-11 首 status 後的公平性 | **仍部分** | 首 status 快，但 200 空線的後續發現、status 與 ctl 仍慢；下表為獨立負載組。維持使用者「慢就慢」的架構決定，控制面的可操作性另記 N-17。 |

### I-11 獨立補測

每 node 100ms、空 tasks、觀察 15 秒；20／200 線依序執行，期間沒有其他本輪負載探針。wake 回條從寫完請求到讀到回條計時；以約 10ms 輪詢，所以含觀測粒度。單機共享宿主，數字不是 SLA。

| 線數 | 首 status 秒 | 15 秒內觀察到 round>0 | wake 回條最大 ms／樣本 | status 最大觀測間隙 ms | 窗口後 stop 回條 ms |
|---|---:|---:|---:|---:|---:|
| 20 | 0.051 | 20／20 | 35.8／28 | 44.2 | 10.3 |
| 200 | 0.053 | 160／200 | 3322.1／6 | 3824.5 | 8389.0 |

兩組 daemon 都 exit 0。200 線最後在 stop 排空階段全部至少完成一次 tick；不能據此說全數在 15 秒內已服務。這次 stop 前面沒有一萬件控制檔，因此 **F-10 的 200 件／50ms 預算通過，不代表 stop 全路徑會在 50ms 內處理**。未把延遲歸因於單一瓶頸。[20 線](2026-10-03-astra-6-infra-evidence/scale-20.json)、[200 線](2026-10-03-astra-6-infra-evidence/scale-200.json)

## 二、G- 新問題與邊界

### G-01 daemon 控制回條壞掉，一件就能擋住後面的 stop〔bug〕

**重現：** `boundaries.py:ctl_poison`。paused node；`ctl-done/000.json` 建成目錄，排 `ctl/000.json` wake、`001.json` stop --kill，總共只有兩件。

**看到：** 0.7 秒內 daemon 活著、status 仍更新，但 `io_errors=34`；兩份請求都在，stop 沒回條。移除回條目錄後約 63ms 正常退出。`handle_ctl()` 的結果寫入沒有逐件錯誤邊界；外層 guard 每圈重試排序第一件，後面永遠輪不到。這和 F-06 已修的**任務** ctl 回條是不同入口，也不是吞吐不足。[結果](2026-10-03-astra-6-infra-evidence/ctl-poison.json)

**需要：** 失敗請求可保留、可追蹤，但必須能處理本圈其他請求，特別是 stop；避免重試同件造成永久飢餓。保持 pause／resume 的必要順序，對失敗項明確標示阻礙。位置：`aos7_daemon.py:handle_ctl`。**S-01、S-06、S-18；N-17、N-19、N-21、N-22。**

### G-02 node fd 只保住中繼檔，掛載與 runner 仍沿舊路徑〔bug〕

**重現：** `fd_sweep.py:fd_race` 在 tick 已抓 node fd、第一次 round replace 前 SIGSTOP，再 rename n→moved，放行。兩個子案：① 任務宣告 mount `box: n/inbox`；② 舊 n 改成指向同一隔離空間內 other 的 symlink，任務不掛載。沒有把 symlink 指到副本外。

**看到：** ① `aos7_mount.make` 沿 root/n/inbox 把舊 n 建回；birth 與 round 在 moved，但 runner 用舊 `$AOS7_TASK`，讀不到 birth 而退出。② 中繼檔不會寫到 other，卻同樣讓 runner 走 other 的任務路徑。兩案 tick rc0、started 含 x-r1，而 x-r1 **只有 birth、沒有 pid／exit，狀態 born**；新位置再 tick 不重起 keep，仍是 born。這不是「Q4 殺掉舊任務後 keep 正常重起」。[rename＋mount](2026-10-03-astra-6-infra-evidence/fd-rename-mount.json)、[symlink＋task](2026-10-03-astra-6-infra-evidence/fd-symlink-task.json)

**需要：** 起任務的 cwd、birth 交接、runner 的 taskdir 身分與掛載操作都要和 held node 一致；若偵測搬移而不能完成啟動，回受控失敗並留下 exit／可恢復狀態，不能永遠 born。不可只在 round 寫入處用 fd，就宣告整個動作完成綁定。位置：`aos7_task.py:start_task`、`aos7_mount.py:make`、`aos7_run.py:main`。**S-06、S-10、S-13、S-14；N-24、N-26、N-21。**

### G-03 父 node 搬家，子 daemon 仍沿舊根寫 status／log〔bug〕

**重現：** `ownership.py:parent_move`。n 以 keep／subroot 起 n/sub 的真 daemon；rename n→m，同步把新 tasks.json 的 subroot 改為 m/sub，等待父掃到 Q4。

**看到：** 舊子 daemon 確實被收掉，新位置以 gen2、owner.node=m 重起；但原本已不存在的 **n/sub/.aosd/status.json、log.jsonl 被舊子 daemon 建回**。這是 daemon 自己的絕對路徑寫入，和 G-02 的 tick 掛載分支各自獨立。[結果](2026-10-03-astra-6-infra-evidence/parent-move.json)

**需要：** 子 daemon 的 root／`.aosd` 生命週期也要綁定原目錄身分；搬移後依 Q4 收尾時不再沿舊路徑 makedirs。新位置重起、舊任務全死的既定語意不用改。位置：`aos7_daemon.py:log`、`write_status` 與 `self.aosd`。**S-06、S-14、S-21；N-24、N-26、N-75。**

### G-04 起不來的第二個 daemon，先把在跑的 owner 改掉〔bug〕

**重現：** `recovery_edges.py:owner_collision`。node n 的 first-r1 已起 n/inner/sub，allow_stop=false。再新增 node n/inner，由它的 second-r1 宣告同一 subroot、allow_stop=true。

**看到：** 第二個 daemon 因根的鎖已被持有而 **exit 1**；真正跑著的 daemon PID 完全沒換。然而 owner 已從 **n／first-r1／false → n/inner／second-r1／true**；外部 stop 隨即成功，回條還宣稱它屬於 n/inner。同 node 的第二個 task 指相同 subroot 也會重寫 owner。[跨 node](2026-10-03-astra-6-infra-evidence/owner-cross-node-collision.json)、[同 node](2026-10-03-astra-6-infra-evidence/duplicate-owner.json)

**需要：** 子根認領和實際取得 daemon 執行權要一致。已被占用的根不能讓失敗的競爭者先覆寫 owner；至少拒絕衝突並留可追蹤結果，或設計不會讓失敗啟動改掉現役 owner 的交接。這是落實「歸起它的 node」，不是要求再決定所有權方向。位置：`aos7_task.py:start_task` 寫 owner 早於 `aos7_daemon.py:run` 取得 daemon.lock。**S-06、S-15、S-21；N-75、N-47、N-66。**

### G-05 reload 先剝掉排程欄位，繞過「不合格就不 kill」〔bug〕

**重現：** `boundaries.py:reload_bad`。x 正在跑；tasks.json 的同名項改新 argv，分別填 `mode:"nonsense"`、`from_round:"bad"`、`max_live:"bad"`，提交 restart＋reload。

**看到：** 三案回條全部 `ok:true`、舊 PID 已死、新 x-r2 已起；**同一個 tick 的 tasks_error 卻說同一項目不合格**。reload 只呼叫 `validate()`，排程型別在 `should_start()` 才檢查；剝欄位後把錯誤藏掉。[mode](2026-10-03-astra-6-infra-evidence/reload-bad-mode.json)、[from_round](2026-10-03-astra-6-infra-evidence/reload-bad-from_round.json)、[max_live](2026-10-03-astra-6-infra-evidence/reload-bad-max_live.json)

**需要：** 先驗證原項目的合法性，再套用 restart 不受 mode／from_round／max_live 排程限制的規則。規格第 6 節明列「項目不合格（第 4 節的檢查）整個不執行、不 kill」，本案只要求這項保證；不要求合法的 max_live 約束 restart（合法值的對照見後表）。位置：`aos7_task.py:reload_item`。**S-06、S-17；N-31、N-21、N-59。**

### G-06 動態掛載被宣告覆蓋後仍標 dyn，下一輪 reload 刪不掉〔bug〕

**重現：** `boundaries.py:reload_dyn`。先動態加掛 n/dyn（名字 n_dyn）；tasks.json 宣告同名改指 n/static，reload；接著從 tasks.json 刪除此 mount，再 reload。

**看到：** 第一次目標正確改成 n/static，卻仍寫 `dyn:true`；第二次 n/static 被當作執行中加掛繼承，仍留在 birth.mounts，回條 `diff:{}`／「定義沒變」。新任務從未動態申請過 n/static。[完整兩次 reload](2026-10-03-astra-6-infra-evidence/reload-dyn.json)

**需要：** `mounts_dyn` 只帶「沒有被當前宣告接管」的名字。當同名以 tasks.json 為準時，來源也應變成宣告；後續刪除宣告能生效，diff 能看見它。位置：`reload_item` 合併 mount 後，`run_ctl` 又把舊 dyn 名字全放進 mounts_dyn，`start_task` 不分來源重新標記。**S-01、S-17、S-23；N-31。**

### G-07 `_proc` 的 atexit 忘了 group 與 grace〔bug〕

**重現：** `recovery_edges.py:cleanup_atexit`。獨立 helper 呼叫 `track(None, p, grace=.1, group=True)`；p 為自己 session 的程序，fork 一個同群組 child，兩者忽略 SIGTERM。helper 正常結束，讓它走 Ctrl-C fallback 也使用的同一個 atexit。

**看到：** helper 約 **3.07 秒**後 rc0；p 被殺，child **仍活著**。`track` 在正常 unittest cleanup 保存參數，但 `_live` 只留 Popen；atexit 只做 `reap(q)`，退回 group=false、grace=3。測試器在記錄漏收後才用 PID 收 child，然後刪空間。[結果](2026-10-03-astra-6-infra-evidence/cleanup-atexit-group.json)

**需要：** fallback 登記並沿用每筆程序的回收選項，和正常 cleanup 一致；加入確實走 interpreter exit 的驗收。原本 `F11ProcHelper` 只驗 `doCleanups()`，抓不到此分支。位置：`tests/_proc.py:track`。**S-06（測試工具）；N-55。**

### G-08 半行 rounds.jsonl 讓恢復後的完整摘要也變壞行〔bug〕

**重現：** `extra_faults.py:partial_summary`。one-r1 已結束，tock append 時注入「只寫 JSON 前 24 字元，flush 後停住」，控制器 SIGKILL，再跑原版 tock；下一個 tick／tock 也照跑。這是**append 中途的短寫狀態注入**，不是第五輪完整摘要後中斷，也不是斷電測試。

**看到：** 重試把完整 JSON 直接接在半行後，成為一條不合法的 JSON。tock 仍 rc0，round.open=false、one-r1 有 ended.json；`read_jsonl` 可解析行數卻是 **0**。下一回合有合法 r2 摘要，但 ended 為空；r1 的結束事件再也不報。[原始半行、重試輸出與下一回合](2026-10-03-astra-6-infra-evidence/partial-summary.json)

**需要：** 持鎖的恢復流程能處理未完成尾行，完整且可讀的本回合總結確認提交後，才寫 ended／closed；尾段修復可保留損壞證據。已有完整同 round 的去重仍保留。位置：`aos7_fs.py:append_jsonl`、`aos7_tock.py:logged_summary/_tock`。**S-01、S-06、S-08、S-11；N-20、N-22、N-23。**

### G-09 owner／stopped 是可寫檔案協定，沒有強制辨別操作者〔技術選型〕

**重現與看到：** 真正跑在子 daemon 下的任務把 owner.allow_stop 從 false 改 true，stop 就成功；允許 stop、但不 kill 的子 daemon 留下的任務自行刪 stopped，父 keep 隨即重開到 gen2。壞 JSON／[]／null／allow_stop 為 1 或字串都拒 stop；但 **刪除 owner** 會讓子 daemon 當自己是頂層，stop 成功而不留 stopped，父又起回 gen2。[任務改 owner](2026-10-03-astra-6-infra-evidence/owner-task-edit.json)、[子任務刪標記](2026-10-03-astra-6-infra-evidence/child-deletes-mark.json)、[壞檔／刪檔](2026-10-03-astra-6-infra-evidence/owner-syntax-missing.json)

**需要／界線：** 文件要說清楚 Q5 是合作式檔案協定；目前只能根據檔案值判斷，無法知道是 owner、子任務或人改的。「手動啟動清標記」也不能辨別真的是人。本輪不據此要求帳號隔離、FUSE、cgroup 或重新決定 Q5；G-04 那種產品自己在失敗啟動時寫錯 owner 則是可獨立修的 bug。

相同界線也見 stop-sweep：只給**不同 NODE**的外部探針、巢狀 node 探針及沒有 TID 的程序都保留；給相同 NODE＋TID、但不同 ROOT 的探針仍被收。判定式不檢查 ROOT，符合現有 Q1 以 NODE／TID 識別的界線，不能稱作完整的 daemon 身分驗證。[範圍對照](2026-10-03-astra-6-infra-evidence/sweep-isolation.json) **S-10、S-21；N-75、N-49、N-25、N-09。**

### G-10 action owner 無法驗身分時安全拒殺，但沒有恢復說明〔技術選型〕

**重現：** `stale_identity` 用真 sleeper 的 PID、錯誤 starttime 模擬 PID 已重用；另一案讓 proc_starttime 回 None。兩者都不殺 sleeper。再起一個真持鎖者，把 owner.starttime 設 null（模擬寫 owner 當下讀不到 stat），換新 daemon，action timeout .2 秒。

**看到：** 1.1 秒內反覆 tick／tock timeout，round 還沒建立，舊鎖主仍活著；補回正確身分後，自動收舊鎖主並到 r2。保守不殺是正確的，問題是 status/log 只看得到 timeout，不能直接區分「確認為舊者、即將回收」和「身分不足、無法安全回收」。[PID 不符](2026-10-03-astra-6-infra-evidence/stale-pid-reuse.json)、[讀不到 stat](2026-10-03-astra-6-infra-evidence/stale-unreadable.json)、[真持鎖恢復](2026-10-03-astra-6-infra-evidence/owner-starttime-missing-lock.json)

**需要：** 保留 PID＋starttime 防誤殺，不用猜 PID 強殺。記錄 owner 缺欄位／無法驗證／讀取失敗等原因與人工恢復所需資訊；把有界接管保證限定於 owner 可驗證的情況。這屬技術處置，不需改使用者方向。**S-01、S-03、S-06；N-18、N-23、N-54、N-70。**

### 指定新功能邊界的其餘對照

| 範圍 | 實測結果與證據 |
|---|---|
| Q5 allow_stop 型別 | tasks／spawn 分別測 null、0、1、字串、[]、{}；12 壞項全部跳過、兩個健康項照起，沒有建立壞項的子根。[矩陣](2026-10-03-astra-6-infra-evidence/allow-stop-types.json) |
| Q5 stopped 四種入口 | keep、each、spawn、restart 產生的 spawn 都不起、不占新 tid，四筆 tasks_error；restart 的 ok 只代表控制被處理，不代表子 daemon 已重起。[矩陣](2026-10-03-astra-6-infra-evidence/stopped-all-modes.json) |
| Q5 多層所有權 | 三層：middle owner=n 允許 stop；deep owner=x 不允許。deep 控制檔 stop 被拒；middle stop --kill 後 middle／deep／leaf 三 PID 都結束；只有被路二停的 middle 留 stopped。沒有把 n 當成 deep 的直接 owner。[結果](2026-10-03-astra-6-infra-evidence/nested-owner.json) |
| Q6 spawn＋reload | spawn-only 任務在 tasks.json 無同名項時，reload 回 false 且原任務仍 live；新增同名定義後可 reload。[結果](2026-10-03-astra-6-infra-evidence/reload-spawn.json) |
| Q6 keep／連續 reload／同名多項 | keep＋max_live=1 連續三次 reload 都只有一個 live、argv 更新、restart_of 串接；同名兩個合法 keep 項取第一項，第二項沒有再起。[結果](2026-10-03-astra-6-infra-evidence/reload-matrix.json) |
| Q6 合法 max_live | 原本有兩個 each 實例，配置改 max_live=1 再 reload 其中一個，結果仍兩 live。**符合第 6 節明訂 restart spawn 去掉 max_live**，不列 bug；max_live 非合法整數則屬 G-05。[結果](2026-10-03-astra-6-infra-evidence/reload-maxlive.json) |
| F-09 fd 數量 | 同一 Python 程序直接跑 300 組 tick／tock，fd 數 4→4，round=300，未觀察到漏 fd；不宣稱驗過所有 OSError 分支。[結果](2026-10-03-astra-6-infra-evidence/fd-count.json) |
| F-09 跨檔案系統 | 限定路徑內未架第二個檔案系統；注入 rename EXDEV，再真 copytree＋rmtree 舊 node。舊 fd 寫入回 ENOENT、動作回 gone、舊路徑不重建，複製目標沒有收到 fd 的寫入。**不是跨檔案系統無縫搬移通過證明**。[結果](2026-10-03-astra-6-infra-evidence/fd-crossfs.json) |
| F-01 巢狀與他人程序 | 真巢狀 daemon 的正常收尾成功；獨立、不相符 NODE 的程序沒被 sweep 誤收。相同 NODE／TID 的識別界線詳 G-09；沒有為測試打到任何非本次建立的程序。 |

## 三、infra-needs 的建議

只提出修訂建議，沒有直接修改需求清單，也不新增重複的 N- 號。

| N- | 建議現況 | 理由／驗收要補什麼 |
|---|---|---|
| **N-20** | **已做 → 部分** | 完整摘要重播去重通過；G-08 半行 append 後仍會 closed／ended 有、合法摘要無。加入短寫＋重試的提交驗收。 |
| **N-24** | **已做 → 部分** | 空任務動作的 fd 修復通過；G-02 掛載建回舊 node、G-03 子 daemon status／log 建回舊根。驗收不能只有 round／exit 檔。 |
| **N-31** | **已做 → 部分** | 正常 reload、spawn 缺名拒絕、keep 連續更新通過；G-05 必須先驗完整項目，G-06 要正確移轉 mounts_dyn 來源。 |
| **N-75** | **已做 → 部分** | 正常 allow_stop／stopped 行為通過；G-04 第二個啟動失敗不能奪走現役 owner。另註 G-09 是合作式檔案協定的能力界線。 |
| **N-55** | **已做 → 部分** | 舊 agent／demo 洩漏已修；G-07 atexit 未沿用 group／grace，需測實際 interpreter exit。 |
| **N-21** | **建議部分，或明列只完成任務側隔離** | F-06 舊項全部通過，但 G-01 daemon ctl 仍會永久阻擋其他項；新 reload 驗證 G-05 也未涵蓋完整 schema。不可用同一個「已做」涵蓋所有控制入口。 |
| N-17 | **維持部分** | 控制檔洪水與小批量 stop 已改善；G-01 兩件即可卡住，200 空線 stop 回條 8.389 秒。保留實測容量與控制延遲，不重新要求架構重寫。 |
| N-18 | **保留已做、加前提** | 原世代倒寫／持鎖接管已修；G-10 要說明 owner 身分可驗證前提，身分不足時不得冒險殺 PID。 |
| N-19／N-22 | **維持部分** | 加掛回條先提交的修復有效；daemon 控制回條與半行總結仍需恢復／局部隔離（G-01、G-08）。 |
| N-23 | **維持沒做（已有局部恢復）** | 已有完整摘要與可驗證持鎖者恢復，但無完整恢復清單；加入半行日誌與未知 action owner 的診斷。 |
| N-09／N-12／N-70 | **維持部分** | 分清已接受／真的停好、scope 與 unknown；G-10 應提供不能安全回收的原因。 |
| N-25 | **維持已答 Q1(a)** | 原 stop 孫程序與正常巢狀收尾已修；記清 NODE／TID 識別不含 ROOT，不擴張成隔離保證。 |
| N-26 | **保留核心行為已做，加關聯缺口** | 真消失會 kill、EIO／ESTALE 保留，符合 Q4；搬移後的鬼目錄／born 任務另連到 N-24（G-02、G-03），不要把熱搬整段宣告全好。 |
| N-40／N-47／N-34／N-51／N-59 | **保留已通過的修復範圍** | 歷史讀競態、冷啟動子根避讓、毒 batch 隔離、wait-tock 型別均通過；不因其他新入口有錯而撤銷原修復。N-47 另連 Q5 所有權衝突；N-59 另連 reload 的驗證缺口。 |
| N-27／N-41 | **維持原狀** | 頑固巢狀停機總期限沒做；使用者已接受目前程序架構的速度。本輪沒有以正常巢狀成功或單次容量樣本改寫既定決定。 |

**本輪收尾確認通過：** 所有 `/tmp/astra6-*` 與結果記錄的暫存根皆不存在，自建後代程序為 0。第一次全域 `pgrep -af aos7-` 無輸出；再次核對時，副本外的 `/home/lorkhan/repo/simple_tools/aos/proto7-1` 另啟動一批 unittest／demo／probe。最後證據保留全域輸出，另核對本副本執行路徑與本輪 `AOS7_ROOT`，沒有本輪殘留；**未終止或修改副本外的程序**。48 份結果 JSON 無 harness_error、無清理失敗，報告連結全部有效；單份結果最大約 9 KB。詳見 [verification.json](2026-10-03-astra-6-infra-evidence/verification.json)。產品的漏收均在測試器介入前記錄，之後才回收並刪空間。
