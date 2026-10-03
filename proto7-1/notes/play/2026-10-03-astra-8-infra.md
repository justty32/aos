# astra-8：proto7-1 第八輪基礎設施回歸與可靠性測試

**原修補有效，但這一層還不能判為穩定。** 既有 `test_astra5`、`test_astra6`、`test_owner_reload`、`test_astra7` 共 **72／72 通過**，其中 H 系列 17 項全過；上一輪直接重現也確認問題已有改善。把新邊界一起納入後，H-01～H-09 判為 **5 項已修、4 項部分**；G-01、G-04 可關閉原競態，G-02、G-08 仍部分。

本輪記錄 **8 個 bug、2 個技術選型邊界，沒有新增待使用者決定的產品方向**。優先處理：**讀不到回合狀態卻開新回合、runner 交接中斷造成永久 born 或重複活任務、清歷史讓 kernel 忘記用量**。這些影響回合完整性與任務管理，並非單純診斷文字或速度問題。

所有測試只操作副本與自建 `/tmp/astra8-*`；沒有呼叫任何 LLM，也沒有執行 LM Studio、ollama、lms。產品、既有文件與證據 **1,449 個檔案雜湊不變**；新增內容只有本報告與[本輪證據目錄](2026-10-03-astra-8-infra-evidence/)。最終核對：**46 份案例／suite 清場紀錄均成功，自己的暫存根與程序零殘留**。[驗證結果](2026-10-03-astra-8-infra-evidence/verification.json)

## 方法與判定範圍

依據：[核心 spec](../../../proto7/spec/core.md)、[細部 spec](../../spec.md)、[infra-needs](../infra-needs.md)、[上一輪報告](2026-10-03-astra-7-infra.md)。這份副本沒有 `.git`、`wf/`、根 `CMakeLists.txt`；無法獨立核對 `b3bd7f44` 的 ancestry，也不宣稱跑過 CMake。以實際原始碼與[來源雜湊](2026-10-03-astra-8-infra-evidence/baseline.json)為準，Python 3.14.7／Linux。

「已修」限定本表的失敗條件；「部分」表示原案通過，但同一保證仍有失敗入口。故障掛鉤只固定操作順序或指定 I/O 回傳，不修改產品檔；不是自然發生率。PID 重用用「活 PID＋不同 starttime」建構，**未宣稱真正等到核心重用 PID**。本輪沒有重跑十分鐘長跑、斷電或 fsync 耐久性測試，重點是新增交接點與組合故障。

[regression.py](2026-10-03-astra-8-infra-evidence/regression.py) 跑既有測試；[legacy.py](2026-10-03-astra-8-infra-evidence/legacy.py) 載入上一輪原探針，輸出改到本輪。同 tick 雙宣告現在只起一個，故移除舊腳本「等敗者 exit」的等待，保留 12 次批次與 owner／真 PID 比對。其餘新增腳本見末節。控制器設 subreaper 只為回收自己的 orphan；產品本身沒有改成 subreaper。

## 一、逐項回歸

| 項目 | 判定 | 原重現與本輪證據 |
|---|---|---|
| H-01 tock 失敗後先恢復回合 | **部分；原兩案已修** | 完整 append 後讀回失敗、24 bytes 短寫均恢復同回合；one-r1 的 ended 只在 r1，沒有原本的缺號／重報。[讀回](2026-10-03-astra-8-infra-evidence/H01-readback.json)、[短寫](2026-10-03-astra-8-infra-evidence/H01-torn.json)。持續 ENOSPC 也守住 r1；但 daemon 另讀不到 round.json 就再次跳號（K-01），恢復後 rounds 倒數會多跑（K-02）。 |
| H-02 子根 owner 認領 | **已修，限正常交接／搶鎖** | 原固定競態：敗者 exit 1、owner 前後相同、真 daemon PID 不變、未允許的外部 stop 被拒。[競態](2026-10-03-astra-8-infra-evidence/H02-race.json)。無注入 12 次皆只起 first-r1，owner 與真 PID **12／12 相符**。[批次](2026-10-03-astra-8-infra-evidence/H02-batch.json)。手動重開的歷史 owner 邊界另列 K-08。 |
| H-03 audit 半行修復 | **已修** | ASCII／UTF-8 半行後，真 audit hook 的 first、second 兩筆都可讀。[原入口](2026-10-03-astra-8-infra-evidence/H03-H04-jsonl.json)。另 8 個 Python 程序各寫 20 次，同一份 torn UTF-8 writes.jsonl 讀回 **160 筆、160 個唯一路徑、僅原半行 1 筆 bad**。[並行](2026-10-03-astra-8-infra-evidence/audit-parallel.json) |
| H-04 JSONL 半個 UTF-8 字元 | **已修** | log、decisions、sent、writes 真寫入入口之後，read_jsonl／tail 均讀到新紀錄，audit.scan 不再因解碼失敗退出。[四種入口](2026-10-03-astra-8-infra-evidence/H03-H04-jsonl.json)、[suite](2026-10-03-astra-8-infra-evidence/regression.json) |
| H-05 晚期 node 搬移 | **部分；原窗口已修** | 原「tick 最後檢查後、runner Popen 前搬移」：exit 127 寫到 moved，沒有舊根／ghost progress。[原案](2026-10-03-astra-8-infra-evidence/H05-late-move.json)。再晚到 runner 的任務 Popen 前，仍起出 cwd／環境路徑不一致的任務、建回舊根（K-06）。 |
| H-06 out.log／runner lost | **部分；out.log 原案已修** | out.log 是目錄時 exit 127、state ended，下次 keep 起 x-r2。[原案](2026-10-03-astra-8-infra-evidence/H06-out.json)。runner 身分已寫且尚未生任務時被殺，可正常 lost；但缺交接紀錄仍永久 born、子程序先出生則可能重複起（K-03～K-05）。 |
| H-07 ctl-failed 排他命名 | **已修** | 100 件同名失敗全保留；預置 x.json.42 再固定 time_ns=42，sentinel 不變，新件到 x.json.42.1，stop 成功。[碰撞](2026-10-03-astra-8-infra-evidence/H07-collision.json) |
| H-08 保留與容量觀測 | **部分；新增功能原測試通過** | `keep_old_rounds`、預設不刪、retention、status disk 四測均過。[suite](2026-10-03-astra-8-infra-evidence/regression.json)。0／負數／非整數照選定規則執行；但 purge 會破壞 kernel 累計用量（K-07），同步 disk 掃描會擋控制面（K-09）。未把「有選項」判成全系統容量已有界。 |
| H-09 runner fd 契約 | **已修（內部 ABI）** | 無效數字、非數字、一般檔 fd 均 rc2、stderr 清楚、a 無 exit；舊式單參數／有效 fd rc0。a 路徑＋b fd 仍執行 b，符合 fd 是權威的文件。[矩陣](2026-10-03-astra-8-infra-evidence/H09-fd.json) |
| G-01 壞控制回條擋 stop | **已修（原案與隔離命名）** | 原壞回條後面的 stop 成功，pending 清空、daemon rc0；H-07 的第二層衝突也不再覆蓋。[原案](2026-10-03-astra-8-infra-evidence/G01-ctl.json)、[命名](2026-10-03-astra-8-infra-evidence/H07-collision.json) |
| G-02 起任務中搬移 | **仍部分** | 原 rename＋mount、symlink＋task 皆受控 exit127；更晚窗口仍見 K-06，runner 交接另見 K-03／K-04。[rename](2026-10-03-astra-8-infra-evidence/G02-rename.json)、[symlink](2026-10-03-astra-8-infra-evidence/G02-symlink.json)。rename 案後續重跑建立宣告的 n/inbox，不算原次 ghost。 |
| G-04 敗者修改現役 owner | **已修（競態）** | 已持鎖的跨 node／同 node 新請求均拒絕、不改 owner；尚未持鎖的窗口也由 H-02 驗過。[跨 node](2026-10-03-astra-8-infra-evidence/G04-collision.json)、[同 node](2026-10-03-astra-8-infra-evidence/G04-existing.json) |
| G-08 半行總結漏 ended | **仍部分；半行原案已修** | 原半行中斷後重播保留壞行、補合法 r1、ended 標 r1，後續不重報；其他 UTF-8 入口也改善。但回合狀態無法觀測時仍漏整回合（K-01）。[原案](2026-10-03-astra-8-infra-evidence/G08-partial.json) |

## 二、新修補的邊界

### H-01：error 退避、控制與診斷

持續讓 tock 的 rounds.jsonl append 回 ENOSPC，round 一直停在 **1／open=true**；重試間距可見約 **1.04、2.04、4.04、8.04 秒**，符合加倍到 8 秒的行為（包含程序啟動成本）。pause 回條約 **20 ms**、resume 約 **10 ms**；在 8 秒退避期間下 stop＋kill，回條約 **20 ms**、daemon **52 ms** 內 rc0，原活任務已收完，無需控制器代收。[完整觀測](2026-10-03-astra-8-infra-evidence/error-controls.json)

status 的 error、round、last_error 有原因及嘗試次數，看得出哪回合卡住。**但 pause 後變成 phase=paused、pause_pending=false，磁碟 round 仍 open=true**；只照操作卡以為「本回合已收完」會誤判。`io_errors=0` 也只是 daemon 主迴圈沒有 I/O 例外，不能讀成所有動作正常。修復後 last_error 保留舊錯誤符合文件，應連同 round 判讀；它不是目前健康狀態的布林值。

### H-02：環境交接

| 邊界 | 觀察 |
|---|---|
| 子 daemon 由父 keep 重開 | child-r1 → child-r2，owner.tid、daemon_pid 更新成新執行者，allow_stop 保持 false。[證據](2026-10-03-astra-8-infra-evidence/owner-restart-manual.json) |
| 任務在 exec daemon 前改 OWNER／ALLOW_STOP | owner 依修改值變成 edited／edited-r99／true，路二 stop 成功。[證據](2026-10-03-astra-8-infra-evidence/owner-env-edited.json)。符合合作式界線，**不是新安全漏洞，也不要求帳號隔離**。 |
| 三層巢狀 | 第二層 owner=n:child-r1，第三層=m:grand-r1；leaf 環境沒有 OWNER 三欄及 SUBROOT 洩漏。頂層 stop＋kill 後產品活程序為零。[證據](2026-10-03-astra-8-infra-evidence/owner-nested3.json) |
| 人手在舊子根直接起 | stopped 標記確實清掉，但 owner 還記上一個已死 daemon_pid／tid；stop 沿用舊 allow_stop。這是 K-08 的歷史歸屬與現役身分混用。 |

### H-06：runner 的死亡位置

| SIGKILL 位置／身分條件 | 結果 |
|---|---|
| runner.json 已寫，runner main 前 | lost；tock 補 exit(lost)，keep 起下一份，符合預期。[證據](2026-10-03-astra-8-infra-evidence/runner-before-main.json) |
| 任務 Popen 後、pid.json 前 | runner 死了，任務仍活；tock 判 lost，keep 再起一份。兩個真任務 PID 同時存活；正常 daemon stop sweep 最後可把兩個都收掉（K-04）。[精確核對](2026-10-03-astra-8-infra-evidence/runner-duplicate.json) |
| pid.json 寫完，任務仍活 | runner 死後仍 live，不重起；符合跨回合任務仍存活的事實。[證據](2026-10-03-astra-8-infra-evidence/runner-after-pid.json) |
| 任務已結束、exit.json 前 | lost，結果碼 unknown，下一個 keep 可起。[證據](2026-10-03-astra-8-infra-evidence/runner-before-exit.json)。沒有捏造成功碼。 |
| tick 的 Popen 已回到掛鉤、runner.json 尚未寫 | 同時殺 tick／runner，留下 birth，後續 tock 仍列 alive，keep 不再起（K-03）。[真程序中斷](2026-10-03-astra-8-infra-evidence/runner-tick-crash.json) |
| starttime=null／runner.json 寫入 EIO | 也會 born 卡住。[null](2026-10-03-astra-8-infra-evidence/runner-null-start.json)、[EIO](2026-10-03-astra-8-infra-evidence/runner-record-eio.json)。null 案由測試器先 wait runner 固定「取身分時已不存在」的順序，主證據以上一列真中斷為準。 |
| 無 pid.json、活 PID 的 starttime 不同 | 判 lost，已補 PID 重用判別；但當前 starttime **讀不到**也判 lost（K-05）。已有 pid.json 時又只看 PID 是否存在，重用的活 PID 仍判 live。[身分矩陣](2026-10-03-astra-8-infra-evidence/runner-identity.json) |

### H-08：保留、讀者與成本

[型別矩陣](2026-10-03-astra-8-infra-evidence/retention-values.json)實測：

- `keep_old_rounds=0`：r3 刪掉 ended=r1 的 tasks-old；`0` 不是關閉清除。設定為 `2`，差值恰好 2 不刪（條件是 `>`）。仍需先符合 `keep_ended_rounds` 才搬入 tasks-old，兩個值不會互相取代。
- `ctl_done_max=0`／`ctl_failed_max=0`：全部清除；`log_max_bytes=0`：非空 log 輪替，保留 log.1，並不是完全不留 log。
- `-1`、`1.5`、字串 `"2"`、`true`、`null`：該選項忽略、不刪；沒有另外的設定警告。這與 retention 的文件一致，不算型別驗證失敗。

[輪替與讀者](2026-10-03-astra-8-infra-evidence/retention-reader.json)：真 `Daemon.log` 與 `retention` 搭配並行重開讀者，沒有 JSONL 解碼例外；持續拿舊 fd 的讀者只再看到輪替前同 inode 的一筆，之後不會自動跟到新 log。共發出 62 筆，最後當前＋一份舊檔只剩序號 60、59；快速重開讀者也只見部分資料。此測試直接多次呼叫 retention **加速輪替**，不是聲稱 daemon 正常每毫秒輪替。這是單備份輪替的既定資料保留界線，讀者不能當它是可靠事件佇列。

[disk 成本](2026-10-03-astra-8-infra-evidence/disk-cost.json)：每一階都是 `.aosd/ctl-done` 的 N 個小檔＋tasks-old 的 N 個空目錄，三次暖快取量測如下。**不是全空間 bytes**：disk 只報 `.aosd` bytes、各 node 任務項目數，任務 out.log／rounds.jsonl 的 bytes 不在其中。

| N | disk_usage 三次耗時（ms） |
|---:|---:|
| 1,000 | 1.53／1.41／1.40 |
| 10,000 | 18.32／14.29／14.10 |
| 30,000 | 59.47／55.62／47.79 |

不是每次 status 都重算，30 秒一次有節流；但重算在主迴圈同步做，慢儲存會直接拖住控制處理，見 K-09。初版成本探針少建 `.aosd` 父目錄而失敗；修正測試器後重跑，未列為產品 bug。purge 對 kernel 的作用則不是容量問題，見 K-07。

## 三、新使用者文件一致性：10 項實測

本表的操作預期只取 **README.md、spec.md、probes/llm_card.md**，不靠舊報告補齊操作步驟；由人類式讀檔／寫檔探針執行，沒有讓 LLM 代操作。這不是盲測：本輪另有原始碼診斷，但判定文件承諾仍以這三份文件為準。README 的 demo／real／LLM 入口沒有執行；README 所列整套測試數量與 35 秒也未當成本輪驗證結果。

| # | 文件承諾與操作 | 結果／不一致 |
|---|---|---|
| D01 | spec §1、操作卡：最後寫 timeline，1～2 ms 內撿到 | **不一致（時間承諾）**。不下 rescan 可自動發現；10 次建立到 node+ log 約 **10.30～20.94 ms**。另建到首份 round.json 為較長的端到端延遲，沒有混成掃描時間。[掃描](2026-10-03-astra-8-infra-evidence/docs-scan-latency.json)、[首回合](2026-10-03-astra-8-infra-evidence/docs-discovery.json)，K-10。 |
| D02 | spec §2：同 root 只能一個 daemon | **一致**。第一個在跑，第二個 rc1。[控制測試](2026-10-03-astra-8-infra-evidence/docs-controls.json) |
| D03 | spec §2、操作卡：pause 收完本回合才停，保留任務 | **部分**。正常 pause 後回合 closed、數字不動、任務存活；error 路徑 phase=paused／pause_pending=false 卻 open=true，K-02。[正常](2026-10-03-astra-8-infra-evidence/docs-controls.json)、[error](2026-10-03-astra-8-infra-evidence/error-controls.json) |
| D04 | 操作卡：resume rounds=N 精準再跑 N 回合 | **部分**。正常 N=2 從 r3 到 r5；故障恢復 N=1 從 r0 跑到 r2，K-02。[正常](2026-10-03-astra-8-infra-evidence/docs-controls.json)、[恢復](2026-10-03-astra-8-infra-evidence/error-rounds.json) |
| D05 | spec §4／§5、操作卡：keep 不重複起活任務，任務跨回合收 tock | **部分**。正常 stay-r1 跨回合、tock 到 r5，沒有多生；runner 死在 pid 發布前則兩份真任務同活，K-04。[正常](2026-10-03-astra-8-infra-evidence/docs-controls.json)、[失敗](2026-10-03-astra-8-infra-evidence/runner-duplicate.json) |
| D06 | spec §6、操作卡：任務 kill 等 tick／tock，pause 時等 resume | **一致**。paused 寫 ctl 後仍 pending／任務活，resume 後成功回條且任務死。[證據](2026-10-03-astra-8-infra-evidence/docs-controls.json) |
| D07 | 操作卡：spawn 一次、each 每回合，壞項目不連坐 | **一致**。三回合有 once-r1 一份、each-r1～r3 三份、stay-r1 一份；broken argv=123 每輪記 tasks_error，好項目照起，spawn 檔消耗。[證據](2026-10-03-astra-8-infra-evidence/docs-task-table.json) |
| D08 | README／操作卡：cwd=node，環境給 node／task，mount 在 taskdir/mnt | **部分**。正常 team/n 的 cwd、NODE_ID、TASK、peer 連結全合；啟動最後窗口搬移可產生 cwd=moved、環境仍 n，K-06。[正常](2026-10-03-astra-8-infra-evidence/docs-mounts.json)、[晚移](2026-10-03-astra-8-infra-evidence/H05-runner-late-move.json) |
| D09 | spec §2、操作卡：刪 timeline 等於 node 消失，活任務會被收 | **一致（本次正常掃描）**。真 sleeper PID 結束，有 node-／node-gone-kill。[證據](2026-10-03-astra-8-infra-evidence/docs-node-gone.json) |
| D10 | spec §7、操作卡：超過 keep_ended_rounds 歸檔，預設只搬不刪 | **一致**。設 keep_ended=0，r3 時 r1、r2 在 tasks-old，r3 還在 tasks，歷史可讀。[證據](2026-10-03-astra-8-infra-evidence/docs-archive.json)。可選 purge 與 kernel 用量的文件衝突另列 K-07。 |

整體閱讀上，三份文件已足以完成正常的 node 建立、啟停、任務與掛載操作。欠缺主要在**失敗狀態的語意**：paused 是否代表回合已提交、born 如何從未交接恢復、owner 是歷史權限還是現役程序、刪歷史會影響哪些上層狀態。操作卡也還只說「tasks 不在去 tasks-old 找」，開啟 purge 後可能兩邊都不存在，應補這個前提。

## 四、K- 新問題

### K-01〔bug，高〕讀不到 round.json 被當成已關閉，仍可永久漏回合

**重現：** daemon 的 `aos7_daemon_timeline.read_json(round.json)` 回 None（等同讀取 EIO 被共用 helper 吞成預設值），同時 tock 持續 ENOSPC；tick 本身讀寫正常。沒有刪檔、沒有把真 round 改成 closed。[證據](2026-10-03-astra-8-infra-evidence/round-read-unknown.json)

**結果：** 故障期間實際磁碟已到 r3/open；解除故障後合法總結只有 **[3,4]**，r1、r2 永久缺失。`round_open()` 把「無法確認」回成 false，原本的 tock rc1 也攔不住下一次 tick。

**建議：** 回合狀態至少分「已關／未關／未知」；未知不能解除恢復義務，應停在可診斷的 error 再試。這是 H-01／G-08 尚未完整的原因。**S-06、S-08；N-20、N-22、N-23。**

### K-02〔bug，中〕恢復完成後漏看 pause，限回合多跑一輪；paused 也掩蓋未提交回合

**重現：** node 預先 paused；resume rounds=1；第一輪 tock ENOSPC 到 error；移除故障。[證據](2026-10-03-astra-8-infra-evidence/error-rounds.json)

**結果：** r1 恢復後已記 `steps-done`，卻又 tick／tock r2，最後 paused 在 **r2**。原因是恢復分支 `round_done()` 已將 node 加入 paused，之後直接往下 tick，沒有重過迴圈頂部的 pause 判斷。

同一狀態機另有診斷不一致：持續故障時 pause 可停止重試，但 status 的 `pause_pending=false` 不代表舊回合已提交。[證據](2026-10-03-astra-8-infra-evidence/error-controls.json)。建議恢復計數後重新檢查控制狀態，並使 status 明示 open／recovery pending；不必讓 pause 為了不可完成的 I/O 永遠失效。**S-08、S-18；N-09、N-20。**

### K-03〔bug，高〕runner.json 的發布仍非完整交接，兩端死掉可永久 born

**重現：** tick 已 Popen runner、尚未寫 runner.json；先停住 runner main，然後 SIGKILL runner 與 tick。[證據](2026-10-03-astra-8-infra-evidence/runner-tick-crash.json)

**結果：** birth 留下、runner／pid／exit 全無；tock 把 x-r1 列 alive，下一個 keep `started=[]`。這是沒有活程序卻永久占住名額；不是故意脫離 Q1 管理的任務。runner 記錄 EIO、starttime null 也走相同保守分支。

**建議：** 啟動前就要有可恢復的啟動意圖／階段；未完成交接不能永久等同「活」。恢復要先辨認、收妥可能已生出的程序，再允許重試，不能只加 born 年齡逾時，否則會撞上 K-04。**S-06、S-10；N-21、N-23。**

### K-04〔bug，高〕runner 死於任務出生後、pid.json 前，lost 導致 keep 雙開

**重現：** runner Popen 真 Python sleeper 後，在 write pid.json 前停住；任務已寫自己的 PID 證據；SIGKILL runner，再 tock、tick。[證據](2026-10-03-astra-8-infra-evidence/runner-duplicate.json)

**結果：** 舊任務 **3240946** 尚活，tock 已報 lost，keep 起新任務 **3240958**；兩者同時存活。這些任務沒有 setsid、清環境或刪 taskdir。最後正常 daemon stop sweep 能收兩份，說明不是「完全收不到」，而是重起前沒有先處理殘留。

**建議：** runner 死亡與工作死亡必須分開；起下一份前，利用現有 cooperative NODE＋TID 掃描／已知身分完成辨認或收尾。驗收要包含任務副作用不能因這個窗口多執行一份。**S-06、S-10；N-21、N-23、N-25。**

### K-05〔bug，中〕runner starttime 讀不到被當成 PID 已重用

**重現：** runner.json 記著仍活程序的正確 PID/starttime，但當前 `proc_starttime(pid)` 回 None。[證據](2026-10-03-astra-8-infra-evidence/runner-identity.json)

**結果：** `None != recorded_starttime`，task_state 回 lost，與「確認另一個 starttime」混為一談；相同身分正常可讀時是 born。可使暫時觀測失敗觸發錯誤結束與重起。這裡只是 liveness 判定，沒有對無關程序發 kill。

**建議：** 當前身分無法確認應回 unknown／待恢復，不能當成已死。另本輪構造已存在 pid.json 的重用 PID，仍得到 live：新的 starttime 防線只涵蓋「尚未 pid.json」階段，不能宣稱整段任務生命週期都防 PID 重用。**S-06；N-21、N-22、N-23。**

### K-06〔bug，中〕多加一次路徑檢查只縮短搬移窗口，仍能重建舊 node

**重現：** runner 已通過 env_mismatch、開好 out.log，正要 Popen 真任務時，以 barrier 搬 n→moved，再放行；任務經 AOS7_TASK 正常寫狀態。[證據](2026-10-03-astra-8-infra-evidence/H05-runner-late-move.json)

**結果：** exit0，任務 cwd=moved，但 AOS7_TASK 仍 n/...；它建立舊 n，marker 內容正是 moved。exit／pid 經 held fd 寫到 moved，任務自己的狀態卻在 ghost 路徑，管理觀點分裂。原 H-05 窗口已修，這是下一個更晚窗口，沒有把原案例說成失敗。

**建議：** 要處理「檢查與任務使用字串路徑之間仍可搬移」的共同原因，而不是無限往後加 stat。可在既有路徑交接／任務初始協定內解決或收斂可保證的範圍；本報告不代定新架構。**S-06、S-10；N-24、N-26。**

### K-07〔bug，高〕清理 tasks-old 把已用額度也清掉，cap 會自動解除

**重現：** 歷史 ended 任務 usage=1000，kernel cap_tokens=500，實際 snapshot＋run_rules 先得到 cap pause；tock 按 keep_old_rounds=0 刪該歷史，再做下一次 snapshot／規則，設定不變。[證據](2026-10-03-astra-8-infra-evidence/retention-cap.json)

**結果：** usage_total **1000→0**，unknown 沒有標記；規則產生 **cap resume**，直接違反 spec §9「總額不會自動 resume，要人調高或拿掉 cap」。案例直接呼叫真 tock 與真規則，usage 是本機合成檔，不是付費模型測試；正常 daemon 已在途的 tock 與 cap pause 亦有交疊窗口，本輪沒有宣稱做過其自然競態頻率量測。

**建議：** 刪除可重建的歷史輸出前，要保留上層依賴的累計量／接續狀態，或明確阻止這組不相容設定。至少 kernel 不能把因 purge 消失的已用額度當成歸零。這是合作式預算算錯，與 N-77 的付費硬限制、惡意偽造無關。**S-17；N-12、N-40。**

### K-08〔技術選型〕人手重開保留歷史 owner，daemon_pid 不再代表現役

子 daemon 正常從 child-r1 重起成 child-r2，owner 更新正確；停掉它後，人手直接在同一子根起新 daemon **3235056**，owner 還記已死的 **3235055／child-r2**。stopped 清除，但 stop 因舊 allow_stop=false 被拒。[證據](2026-10-03-astra-8-infra-evidence/owner-restart-manual.json)

沿用原 node 的權限本身可以合理，不應擅自當成頂層、清掉 ownership；問題是文件的「owner 一定是真正在跑的那個」未限定環境交接條件。建議保留權限時，也分清歷史 owner／目前 daemon PID，操作卡說明手動重開後 stop 照誰。沿用 Q5 即可，沒有必要另開一題產品方向。**N-75、N-09。**

### K-09〔技術選型〕新增容量掃描在主迴圈同步做，控制延遲跟著儲存走

暖快取 30,000 個回條小檔＋30,000 個歷史目錄，disk 約 **48～59 ms**。另只對自己的 200 個回條 lstat 注入每次 10 ms，真 daemon 處理 stop 回條等了 **2.033 秒**，退出 **2.064 秒**。[注入](2026-10-03-astra-8-infra-evidence/disk-control-delay.json)

這不是把接受「回合慢」改寫成需要效能重構，也不是硬宣稱 30,000 就超載；風險是無關的診斷工作共享控制主迴圈。建議把 housekeeping 做成可分段／有時間預算，或明載採樣期間控制會延後。保留設定只清部分檔案，rounds.jsonl 等仍成長，disk 也不是全 root 容量表。**N-17、N-40；既有 N-41 的速度選擇維持。**

### K-10〔bug，低；文件〕新 node「1～2 ms 內撿到」與實作週期不合

新使用者只照文件建 node；記錄 timeline 寫出到 daemon node+ log，10 次為 **10.30～20.94 ms**，輪詢解析度 0.5 ms。spec §2 又明載主迴圈約 20 ms，兩處文字互相矛盾。[證據](2026-10-03-astra-8-infra-evidence/docs-scan-latency.json)

建議改為「自動在後續掃描發現，低負載約一個 polling 週期，重負載更久」，不要把非即時系統寫成 1～2 ms 承諾。功能確實自動發現，本項不要求改排程速度。

## 五、這一層離穩定還差什麼

**剩下的不全是邊角；核心概念沒有被推翻，但實作的生命週期交接仍有結構性缺口。** 正常路徑、單項隔離、JSONL 修復、搶鎖認領都顯著成熟；72 個舊測試全綠不是假象。但目前仍用「幾個檔案有／沒有」推定程序或回合事實，跨程序交接遇到不可觀測、中途死亡、清歷史，就會把 unknown 當 closed、把 runner 死當工作死、把歷史消失當用量 0。

**值得再回歸，但不值得只做第九輪同樣的案例重跑。** 下一輪應先修、再用固定中斷矩陣驗三個不變條件：

1. 舊回合未確認提交時，不開始下一輪；恢復成功仍遵守 pause／rounds。
2. 啟動交接的每一階段中斷後，都能區分「沒起／仍活／已死／無法確認」；不能永久占住 keep，也不能重複活任務。
3. GC 只改保留量，不能默默改變 kernel 已累計的用量或其他仍承諾可接續的狀態。

晚期 rename 的窗口應一次面對同一個交接問題；再加一個 stat 只會讓下輪把 barrier 往後移。完成上述後，再做較長負載與低速／失敗儲存下的控制延遲驗收，收益會高於持續增加正常路徑範例。這些修正都可沿既定 daemon→tick/tock→kernel 路線處理，不需要藉本輪重新決定 cgroup、帳號隔離或產品方向。

## 六、對 infra-needs 的建議（本輪未修改該檔）

| 需求 | 建議狀態／驗收補充 |
|---|---|
| N-20 回合關閉可恢復 | 從「已做」調為**部分**；加 K-01 的讀取未知與 K-02 的恢復後倒數測試。 |
| N-21／N-23 任務失敗與 crash 恢復 | 區分 out.log 已修與啟動交接未完；加入 K-03／K-04 各發布前後 kill，以及 K-05 身分讀取失敗。 |
| N-22 一般 I/O 失敗 | 維持部分；「看不到≠不存在」應一致套用回合與 runner，不只掃描 node。 |
| N-24／N-26 搬移 | 原 fd 保護有效，但仍部分涵蓋任務啟動最後窗口；補 K-06，不能只列早期 rename 通過。 |
| N-40 歷史成本 | 歸檔掃描改善仍成立；可選 purge 的整合應列部分，加 N-12／kernel 用量不倒退的驗收。 |
| N-17 控制面、N-09 回條／停機 | 保留部分；記 housekeeping 的同步延遲與 paused/open 診斷。不要用 status.io_errors=0 代表所有時間線正常。 |
| N-75／N-47 子根 | H-02 搶鎖認領可關閉；分開記 K-08 的手動重開 metadata，合作式環境改寫維持既有邊界，不重開 Q5／N-77。 |
| N-19／N-49 | ctl-failed 排他命名、audit 半行／並行可記已驗；不外推為可靠投遞、永久保存或安全隔離。 |
| N-55 測試清場 | 本輪 46 份清場紀錄及最終 /proc、/tmp 核對通過；維持既有要求。 |

## 七、重跑與證據索引

從副本根依序執行，全部加 `PYTHONDONTWRITEBYTECODE=1`，例如：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 proto7-1/notes/play/2026-10-03-astra-8-infra-evidence/regression.py
```

同樣依序跑 `legacy.py`、`boundaries.py`、`docs.py`、`followup.py`、`extra.py`，最後 `verify.py`。不要並行同一腳本，輸出檔名固定；`followup.py` 的 disk-cost 是正式重跑版本。腳本只 import 本副本產品／既有探針，暫存資料與程序在每案 finally 清掉。

| 腳本 | 內容 |
|---|---|
| [common.py](2026-10-03-astra-8-infra-evidence/common.py) | 自有暫存根、PID 清理、subreaper、逐案精簡 JSON；`recorded` 代表已記錄，不代表 pass。 |
| [regression.py](2026-10-03-astra-8-infra-evidence/regression.py)／[regression.json](2026-10-03-astra-8-infra-evidence/regression.json) | 72 個既有測試，每項結果與耗時。 |
| [legacy.py](2026-10-03-astra-8-infra-evidence/legacy.py) | H 原案、G 部分項目重現；依賴既有上一輪證據腳本。 |
| [boundaries.py](2026-10-03-astra-8-infra-evidence/boundaries.py) | error 控制、runner 各階段、owner 手動／巢狀、retention 型別／讀者／成本。 |
| [docs.py](2026-10-03-astra-8-infra-evidence/docs.py) | 文件十項行為的正常操作與 node 發現延遲。 |
| [followup.py](2026-10-03-astra-8-infra-evidence/followup.py) | 真 tick／runner 中斷、真雙活任務、runner 晚移、kernel cap、disk 控制延遲。 |
| [extra.py](2026-10-03-astra-8-infra-evidence/extra.py) | audit 8 程序並行、round.json 未知狀態組合故障。 |
| [verify.py](2026-10-03-astra-8-infra-evidence/verify.py) | 保護檔 hash 比對、所有清場、/tmp 前綴與 /proc 身分檢查。 |

輸出保留腳本、精簡 JSON；30,000 檔容量樣本與原始 taskdir 均已刪除，沒有把大目錄放進證據。程序先收、再刪空間；不使用 `pkill -f`。最終沒有殘留測試程序或 `/tmp/astra8-*` 目錄。
