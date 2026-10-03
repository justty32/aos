# astra-7：proto7-1 第七輪基礎設施回歸與可靠性測試

**原修補的正常路徑有效，但仍不能把可靠性需求全數關閉。** `test_astra5`、`test_astra6`、`test_owner_reload` 共 **55／55 通過**；上一輪 G-01～G-10 的原案例重跑後，按涵蓋新邊界的保證判為 **6 項已修、4 項部分**。本輪提出 **7 個 bug、2 個技術選型邊界**，沒有新增「要使用者決定」的方向問題。優先處理 **H-01 回合恢復、H-02 子根認領、H-05／H-06 任務啟動交接**。

**正式長跑觀測 600.05 秒，20 線合計 6,003 回合**；穩態活程序 45、daemon fd 5～7，沒有觀察到持續增加的程序或 fd。歷史檔與磁碟則持續成長。stop＋kill 後 1.029 秒完成觀察（含 0.3 秒尾端等待），daemon rc0、產品活程序零殘留；所有測試暫存根與程序已清除。

全程只操作這份副本及本輪建立的 `/tmp/astra7-*`；沒有呼叫 LLM，沒有啟動 LM Studio、ollama 或 lms，沒有改產品程式、其他文件、commit 或 push。namespace／ledger 僅使用探針內固定結果的本機模擬服務。F-11 的 agent 測試只有無信、無 goal 的 idle 通知計數。

這份副本沒有 `.git`、`wf/` 或 CMake 根建置環境；因此不能驗證 `94ad4168`、`5a3d97fb` 的版本祖先關係，也沒有宣稱跑過 CMake。依實際來源與 SHA-256 驗證：[來源及範圍](2026-10-03-astra-7-infra-evidence/verification.json)。依據：[核心 S- 規格](../../../proto7/spec/core.md)、[細部規格](../../spec.md)、[infra-needs](../infra-needs.md)、[上一輪報告](2026-10-03-astra-6-infra.md)。[重跑入口與量測說明](2026-10-03-astra-7-infra-evidence/README.md)。

## 一、回歸判定

「已修」只涵蓋列出的重現；「部分」表示原案例通過，但相同承諾仍有可重現的失敗入口。故障掛鉤用來固定先後順序，不當作自然發生率。G-09／G-10 的修補目標本來就是文件或診斷，不把保留的合作式協定誤判成未修。

| 編號 | 判定 | 本輪重現、觀察與證據 |
|---|---|---|
| G-01 壞 daemon 回條擋 stop | **部分；原案例已修** | 原本兩件控制檔、第一件回條為目錄：stop 已收到成功回條，daemon rc0，pending 空；未修障礙前已退出。另有 `ctl-failed` 無法建立時的排序測試通過。但隔離檔的第二層名稱衝突會覆蓋歷史，見 H-07。[原案](2026-10-03-astra-7-infra-evidence/G01-ctl.json)、[55 項測試](2026-10-03-astra-7-infra-evidence/regression.json) |
| G-02 搬移中起任務留下 born／鬼目錄 | **部分；原兩案已修** | 在原 round replace 前 barrier 搬 n：rename＋mount、symlink＋task 都留下 exit 127，state=ended，新位置 tick 起 x-r2；other 未被寫入。`G02-rename` 的 `old_path_exists:false` 是被打斷那次的結果；其中 `ghost_files:[inbox]` 是後續在新位置重跑、仍宣告 `n/inbox` 所建，不能誤算原案失敗。更晚的啟動窗口與 out.log 失敗仍有缺口，見 H-05／H-06。[rename](2026-10-03-astra-7-infra-evidence/G02-rename.json)、[symlink](2026-10-03-astra-7-infra-evidence/G02-symlink.json) |
| G-03 父 node 搬家、子 daemon 建回舊根 | **已修** | 原 parent_move：舊子 daemon 已死，n 未重建；新位置 owner.node=m，由 child-r2 接手。root 被替換成另一 inode 時也 stop＋kill，狀態寫到 held root。[原案](2026-10-03-astra-7-infra-evidence/G03-parent-move.json)、[root 替換](2026-10-03-astra-7-infra-evidence/root-symlink-other.json) |
| G-04 失敗啟動者改現役 owner | **部分；既有鎖主的原案例已修** | 跨 node／同 node 新請求遇到已持鎖子 daemon，owner 與 PID 都沒變，記 tasks_error；外部 stop 仍拒絕。**兩個啟動者都還沒持鎖**則可重現同一錯誤，見 H-02；無掛鉤批次 12 次中 9 次 owner 與真正執行者不符。[跨 node](2026-10-03-astra-7-infra-evidence/G04-collision.json)、[同 node](2026-10-03-astra-7-infra-evidence/G04-same-node-existing.json) |
| G-05 reload 漏驗排程型別 | **已修** | 原 mode=nonsense、from_round=bad、max_live=bad 三案均回 ok:false、不 kill，原任務存活，沒有新 started。[mode](2026-10-03-astra-7-infra-evidence/G05-mode.json)、[from_round](2026-10-03-astra-7-infra-evidence/G05-from_round.json)、[max_live](2026-10-03-astra-7-infra-evidence/G05-max_live.json) |
| G-06 宣告接管掛載後仍標 dyn | **已修** | 原兩次 reload：n/dyn → n/static 後已無 dyn；刪掉宣告再 reload，mounts={}，diff 正確列移除。未被宣告接管的 dyn 保留對照也通過。[原案](2026-10-03-astra-7-infra-evidence/G06-dyn.json)、[測試](2026-10-03-astra-7-infra-evidence/regression.json) |
| G-07 atexit 遺失 group／grace | **已修** | 原獨立 helper 正常 interpreter exit，登記 group=true、grace=.1；約 .163 秒退出，忽略 TERM 的 parent／child 都已死，並非測試控制器事後代收的結果。[原案](2026-10-03-astra-7-infra-evidence/G07-atexit.json) |
| G-08 半行總結永久漏 ended | **部分；原半行重播已修** | 原 append 前 24 字元後 SIGKILL：原版重跑保留壞行、補獨立 r1，ended 標 r1，後續 r2 不重報。手動 tock 讀回失敗也保留 open、可重播。但 daemon 遇該錯誤直接開下一回合，見 H-01；其他 JSONL 見 H-03／H-04。[原案](2026-10-03-astra-7-infra-evidence/G08-partial.json)、[手動讀回失敗](2026-10-03-astra-7-infra-evidence/readback-direct.json) |
| G-09 owner／stopped 是合作式協定 | **已修（文件）；限制仍在** | 規格已明載合作式檔案協定。原任務改 allow_stop 後能 stop；子任務刪 stopped 後父 keep 起 gen2；壞 owner 拒絕、刪 owner 當頂層。這些行為仍在，符合本次只釐清界線的修法；不能當身分驗證。[改 owner](2026-10-03-astra-7-infra-evidence/G09-owner-edit.json)、[刪 stopped](2026-10-03-astra-7-infra-evidence/G09-delete-mark.json)、[壞／缺 owner](2026-10-03-astra-7-infra-evidence/G09-syntax.json) |
| G-10 身分不可驗時拒殺、欠說明 | **已修（診斷）** | 原 starttime=null 的持鎖者仍安全保留；補回正確身分後自動收舊者並到 r2。`G10UnverifiedHolder` 另驗 status/log 的 `stale-holder-unverified`、原因及 action.lock 恢復提示。錯 starttime、proc stat 讀不到的 sleeper 均未被殺。[持鎖](2026-10-03-astra-7-infra-evidence/G10-unverified.json)、[PID 身分](2026-10-03-astra-7-infra-evidence/G10-reuse.json)、[proc 故障](2026-10-03-astra-7-infra-evidence/G10-proc-error.json)、[診斷斷言](2026-10-03-astra-7-infra-evidence/regression.json) |

第五輪仍列部分的三項：

| 項目 | 本輪結論 |
|---|---|
| F-05 摘要後中斷／重播 | **仍部分**。完整 append 後 kill 的同回合與 timeout 重播通過；半行原案也已修，但新讀回失敗在 daemon 路徑重報／缺回合，H-01。[同回合](2026-10-03-astra-7-infra-evidence/F05-replay.json)、[timeout](2026-10-03-astra-7-infra-evidence/F05-timeout.json) |
| F-09 中途搬移／刪除 | **仍部分**。suite 的 tick／tock × delete／rename 四案、原 tock symlink 案通過；G-02／G-03 原問題改善，但較晚交接窗口仍把任務導向舊 AOS7 路徑，H-05。[tock](2026-10-03-astra-7-infra-evidence/F09-tock-symlink.json)、[suite](2026-10-03-astra-7-infra-evidence/regression.json) |
| F-11 測試／demo 收尾 | **原三個缺口已修**。agent 延遲啟動成功且無殘留；demo stop 寫入 EIO 後約 10 秒 fallback，daemon rc0、無活後代；G-07 atexit 群組已修。只驗上述路徑，不外推所有探針的所有中斷點。[agent](2026-10-03-astra-7-infra-evidence/F11-agent-delayed.json)、[demo](2026-10-03-astra-7-infra-evidence/F11-demo-eio.json) |

## 二、新修補的邊界矩陣

| 操作 | 看到的結果與界線 |
|---|---|
| root 一開始是 symlink | 可正常啟動、r1→r5，任務存活；fd 比的是最終目錄身分。[證據](2026-10-03-astra-7-infra-evidence/root-initial-symlink.json) |
| root chmod 000，再還原 | 權限不可觀測期間 daemon／任務仍活；恢復後進到 r4，io_errors=60。沒有誤當 root-gone；這不保證權限不足期間仍能持續寫狀態。[證據](2026-10-03-astra-7-infra-evidence/root-chmod.json) |
| 啟動後 root 換成指回原 inode 的 symlink | 持續跑到 r4，沒有 root-gone。若改指其他目錄則 daemon／任務退出，other 只有原 sentinel，沒有 `.aosd` 污染。[同 inode](2026-10-03-astra-7-infra-evidence/root-symlink-same.json)、[另一 inode](2026-10-03-astra-7-infra-evidence/root-symlink-other.json) |
| rename 後還原 | 暫停 daemon 主程序、完成來回 rename 再放行：同 inode、繼續跑；讓掃描先看見消失，再搬回：停機仍完成、任務已死。判定依實際觀測，已進入 stop 不會自動撤回，符合 Q4。[沒觀測到空窗](2026-10-03-astra-7-infra-evidence/root-rename-return.json)、[已觀測到](2026-10-03-astra-7-infra-evidence/root-return-observed.json) |
| 真 bind mount | 在私有 user＋mount namespace bind src→dst，真 daemon／任務跑到 r2。普通 umount 因 held fd／cwd 回 EBUSY（rc32）；lazy detach 成功後 root 身分變了，daemon rc0、root_gone=true、任務已死、裸 dst 空。初版測試把普通 umount 失敗當成已卸載而等待逾時，已修正測試器重跑，未算產品 bug。[實跑](2026-10-03-astra-7-infra-evidence/bind-daemon.json)、[直接身分檢查](2026-10-03-astra-7-infra-evidence/root-bind.json) |
| aos7-run 舊式單參數／有效 fd | 都 rc0、exit code0；既有 runner 搬移測試證明 pid／exit 寫到 held taskdir。[矩陣](2026-10-03-astra-7-infra-evidence/runner-fd.json)、[suite](2026-10-03-astra-7-infra-evidence/regression.json) |
| aos7-run 無效、非數字、一般檔 fd | 三案 rc1、沒有 stderr／exit，傳入路徑上的 birth 保持 born；不回退到可能已被替換的字串路徑。見 H-09 的內部介面界線。[矩陣](2026-10-03-astra-7-infra-evidence/runner-fd.json) |
| aos7-run fd 指到別的 taskdir | 用 a 的字串＋b 的 fd，實際跑 b 的 argv，exit 寫 b；a 保持 born。fd 是權威，沒有驗證二者一致；不把這個可信任內部 ABI 說成隔離機制，見 H-09。 |
| ctl-failed 同名累積 | 100 次同名壞回條保留 100 份、sequence 無遺失、stop 成功；次級 suffix 碰撞則覆蓋舊檔（H-07），沒有保留上限（H-08）。[證據](2026-10-03-astra-7-infra-evidence/ctl-failed.json) |
| G-04 啟動窗口 | barrier 固定先檢查空鎖、另一者拿鎖、再續跑：敗者 owner 覆蓋、外部 stop 被放行；另無掛鉤同 tick 12 次有 9 次 owner 指錯。見 H-02。 |
| G-08 讀回確認失敗 | 手動重跑同 round 可恢復；daemon 路徑會進新 round，完整摘要的 ended 重報、短寫摘要的舊 round 缺號，H-01。 |

其他 JSONL 用**真正寫入入口**檢查：daemon.log、kernel.one_round、agent_tools.do_tool(send)、Python audit hook。kernel 只替換純規則的輸出讓它產生一筆 decision，沒有啟動 LLM。[逐檔結果](2026-10-03-astra-7-infra-evidence/jsonl-writers.json)

| 檔案 | ASCII 半行後新紀錄 | UTF-8 尾端少一 byte 後新紀錄 |
|---|---|---|
| log.jsonl | 補換行，新紀錄可讀 | 有補換行；tail_jsonl 可讀新紀錄，read_jsonl 例外 |
| decisions.jsonl | 同上 | 同上 |
| sent.jsonl | 同上 | 同上；agent memory 使用 tail_jsonl，未在本案被拖垮 |
| writes.jsonl | **未補換行**；兩次真寫入只讀到第二次 | 第一筆仍黏壞行；read_jsonl／audit.scan 例外，tail 僅讀到第二筆 |

namespace **19／19**、ledger **30／30** 通過，程序也由探針收完。這支持 reload／mount 與帳本復原的正常整合路徑；不外推成能抵抗上述 torn UTF-8 或 audit 漏記。[namespace](2026-10-03-astra-7-infra-evidence/probe-namespace.json)、[ledger](2026-10-03-astra-7-infra-evidence/probe-ledger.json)

## 三、長跑

正式資料：[longrun-clean.json](2026-10-03-astra-7-infra-evidence/longrun-clean.json)，腳本 [longrun_clean.py](2026-10-03-astra-7-infra-evidence/longrun_clean.py)。一個頂層 daemon 管 **20 條時間線**，每線 interval 2000 ms、一個持續 keep；前五線加 each true；n19 另以任務啟動一個子 daemon，子根再有一條 keep 時間線。表的回合總數只加總父的 20 線，程序／fd／磁碟含子樹。

每分鐘另加一次 spawn，對前五線輪替 plain restart／reload，n10 動態加掛，對 n18 下 wake／pause／resume。啟動當下尚未 live 的任務不硬塞 ctl，因此實際動作以 JSON 的 events、restart_receipts、mount_count 為準。`keep_ended_rounds=3` 讓每回合短任務持續歸檔。0 分鐘是冷啟動快照；1～10 分鐘才用來看穩態。

| 分鐘 | 父線回合總數 | 活程序／Z | daemon fd／全樹 fd | 檔案數 | 邏輯 MiB／配置 MiB | log MiB | ctl-done | tasks-old |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 20 | 29／5 | 5／127 | 191 | 0.024／0.562 | 0.004 | 0 | 0 |
| 1 | 600 | 45／0 | 7／185 | 990 | 0.329／3.312 | 0.258 | 3 | 132 |
| 2 | 1,200 | 45／0 | 5／183 | 1,756 | 0.637／5.953 | 0.515 | 6 | 284 |
| 3 | 1,800 | 45／0 | 5／183 | 2,522 | 0.944／8.594 | 0.772 | 9 | 436 |
| 4 | 2,401 | 45／0 | 5／183 | 3,288 | 1.255／11.289 | 1.031 | 12 | 588 |
| 5 | 3,001 | 45／0 | 5／183 | 4,054 | 1.565／13.930 | 1.291 | 15 | 740 |
| 6 | 3,601 | 45／0 | 5／183 | 4,820 | 1.877／16.570 | 1.551 | 18 | 892 |
| 7 | 4,202 | 45／0 | 5／183 | 5,586 | 2.188／19.262 | 1.811 | 21 | 1,044 |
| 8 | 4,802 | 45／0 | 5／183 | 6,352 | 2.499／21.906 | 2.070 | 24 | 1,196 |
| 9 | 5,403 | 45／0 | 5／183 | 7,118 | 2.810／24.551 | 2.331 | 27 | 1,348 |
| 10 | 6,003 | 45／0 | 5／183 | 7,884 | 3.121／27.242 | 2.590 | 30 | 1,500 |

`檔案` 是 os.walk 的非目錄項目（包含符號連結）；`配置` 是這些項目的 st_blocks×512 加總，不含目錄自身的 block；`log` 合計所有 `.log`／`.jsonl` 的邏輯 bytes；`ctl-done` 是 daemon 控制回條數，不含任務單檔 ctl-done.json。fd 合計是讀得到的活程序 `/proc/<pid>/fd`；取樣與短命程序退出非原子，缺口另記 `fd_unreadable`，不把瞬間變動當成洩漏。

1～10 分鐘活程序均為 45、Z=0；第 1 分鐘 daemon fd=7／全樹185，之後回到 5／183，沒有持續上升。0 分鐘冷啟動的 5 個 Z 是程序退出與取樣之間的瞬間狀態，後續已回收。全程取樣 io_errors=0、fd_unreadable 空。第 10 分鐘每線至少 300 回合，n18 因 wake 到 303；子線最後收尾到 r301。10 次 restart 控制皆有成功回條（plain／reload 各 5）、10 個動態掛載均在 birth，完成 stop 後無活後代。

第 1→10 分鐘檔案增加 6,894 個，約 **766 個／分鐘**；配置量增加 23.93 MiB，約 **2.659 MiB／分鐘**；log 增加 2.333 MiB。最後 tasks-old 有 1,500 個任務。這是保留歷史造成的持續成長，不能把歸檔等同磁碟回收（H-08）。接近結束時另讀已提交歷史，20 線均未見 round 重複／缺號、ended 重報、summary errors 或 action／I/O 錯誤：[完整性取樣](2026-10-03-astra-7-infra-evidence/longrun-invariants.json)。

先前另一份同負載也已完成 600 秒觀測：[初跑](2026-10-03-astra-7-infra-evidence/longrun.json)。它啟用測試控制器 subreaper，但只在離開 Space 時 waitpid，因而累積控制器名下的 zombie；[PPID 核對](2026-10-03-astra-7-infra-evidence/longrun-reaper-audit.json)證明歸屬。初跑活程序仍穩定 45、daemon fd=5，收尾全部 reap；本表改用每 200 ms 收養後回收的完整重跑，沒有把控制器的 Z 程序當成產品洩漏。初跑同時進行回歸與故障探針；正式重跑開始時與初跑短暫重疊，之後仍有少量補測，同宿主也可能有他人工作，這是可靠性觀察，不是隔離環境的效能 SLA。

## 四、H- 新問題

### H-01 tock 讀回失敗後，daemon 沒先恢復舊回合〔bug〕

**重現：** `edges.py:readback`，one-r1 結束後總結已完整 append，但讓第一次讀回確認回 None；同時做直接 tock／真 daemon 兩個入口。`followup.py:readback_torn` 再注入只 append 24 bytes 就返回，讀回器實際找不到完整總結。

**看到：** 直接 tock rc1、open=true、沒有 ended；重跑同 r1 就 replayed、只留一行，修法本身有效。daemon 卻只對 timeout（rc=-9）補 tock；這次 rc1 後直接 tick r2。完整 append 案 one-r1 同時出現在 r1、r2 的 ended，ended.json 最終標 r2。短寫案最後合法總結只有 r2、r3，r1 永久缺失。`round_done` 也會走到，不能把 failed tock 當成成功關回合。

**需要：** 開下一次 tick 前確保先處理 open 回合；非零退出、讀回不確定、恢復再失敗都要涵蓋。持續 I/O 故障時應保留可診斷狀態，不能以增加 round 遮掉未完成提交。位置：`aos7_daemon_timeline.Timeline._loop/close_unclosed`。**S-06、S-08、S-11；N-20、N-22、N-23。** [直接重播](2026-10-03-astra-7-infra-evidence/readback-direct.json)、[daemon 重報](2026-10-03-astra-7-infra-evidence/readback-daemon.json)、[daemon 缺號](2026-10-03-astra-7-infra-evidence/readback-torn-daemon.json)

### H-02 子根的試鎖不是認領，正常同批啟動也能指錯 owner〔bug〕

**重現：** `edges.py:claim_race` 將 second 的 `subroot_running` 停在回傳 false 之後；先讓 first 真 daemon 拿鎖，再放行 second。另 `claim_batch.py:batch` 不注入，單一 tick 的 tasks 宣告 first／second 指同一 subroot，allow_stop 分別 false／true。

**看到：** barrier 案真正 PID 沒變、second exit1，owner 卻改成 second／true，外部 stop 成功。無掛鉤 12 次有 **9 次 owner=second，實際 daemon=first**；其餘 3 次由 second 贏鎖。這是這批小樣本，不是普遍發生率，但證明不需要兩個 tick 真正並行，更不需要修改合作式 owner 檔。

**需要：** 讓認領與取得 daemon 執行權成為一致交接，敗者不能發布現役 owner；同步測同 tick 多項與跨 node 競爭。無須重定義 Q5，這是產品自己寫錯歸屬。位置：`aos7_task.subroot_running/start_task`、`aos7_daemon.run`。**S-06、S-15、S-21；N-75、N-47、N-66。** [固定競態](2026-10-03-astra-7-infra-evidence/claim-race.json)、[未注入 12 次](2026-10-03-astra-7-infra-evidence/claim-natural-batch.json)

### H-03 writes.jsonl 繞過半行修復，第一筆復原後寫入被吞掉〔bug〕

**重現：** 先放 `{"broken":` 在任務 writes.jsonl，載入產品原版 audit hook 的 Python 任務依序寫 first.txt、second.txt。

**看到：** hook 直接 `os.open(O_APPEND)`／`os.write`，沒有補換行。first 紀錄與半行黏成壞行，read_jsonl／audit.scan 只剩 second：兩次寫入記成一次。這不是「壞半行本身無法恢復」，而是**之後完整的新紀錄也丟了**。

**需要：** 稽核寫入也處理尾段，避免 audit hook 遞迴並考慮多個 Python 後代同時寫入；至少不能宣稱所有 JSONL 已受共用修復保護。位置：`lib/audit_site/sitecustomize.py:record`。**S-01、S-06、S-10；N-22、N-23、N-49。** [ASCII 子案](2026-10-03-astra-7-infra-evidence/jsonl-writers.json)

### H-04 UTF-8 半字元讓全檔 JSONL 讀取直接失敗〔bug〕

**重現：** 尾端放 `{"text":"` 加中文 UTF-8 字元的前兩個 bytes `e4 b8`，再透過真寫入入口追加合法行。

**看到：** log／decisions／sent 有正確補換行，但 `read_jsonl` 在文字解碼時拋 UnicodeDecodeError，還沒進入逐行 json.loads 的錯誤邊界；`tail_jsonl` 則能跳過壞 byte 行。writes.jsonl 的 audit.scan 同樣直接失敗。它不是 JSON 語法壞行而已，與「跳過壞行、後面照讀」的共同約定不符。

**需要：** 每行的 UTF-8 解碼失敗也局部隔離、保留原始損壞證據；不能遇到不可讀歷史就默默回空清單，否則帳本／去重服務可能誤當沒執行過。此處實驗只證明讀取例外，沒有宣稱已測到 ledger 重複扣帳。位置：`aos7_fs.read_jsonl`；`tail_jsonl` 是通過的對照。**S-01、S-06；N-21、N-22、N-23。** [UTF-8 子案](2026-10-03-astra-7-infra-evidence/jsonl-writers.json)

### H-05 runner 已綁 fd／cwd，但新任務仍收到搬移前的 AOS7 路徑〔bug〕

**重現：** `jsonl_edges.py:late_move` 在 same_dir 檢查已過、即將 Popen aos7-run 時 rename n→moved。任務只照正常介面，對 `$AOS7_TASK/progress.json` 建父目錄並寫狀態。

**看到：** runner cwd 是 moved，exit0 寫在 moved 的 held taskdir；但 AOS7_NODE／AOS7_TASK 還是 n，任務因此把舊 n/.aos/tasks/x-r1/progress.json 建回，moved 沒有 progress。原 G-02 提前檢查抓不到此窗口。這是新任務啟動交接，不是要求任意長命任務在整個生命期都自動追隨 rename；實驗是直接 tick，不把 daemon 日後的 Q4 收尾算成已阻止這次寫入。

**需要：** 最後交接階段的 taskdir、cwd、AOS7_*、argv 展開、掛載 metadata 必須一致，或在搬移後受控拒絕啟動。不能只驗 true 任務的 pid／exit 就認為一般任務也拿到一致的路徑。**S-06、S-10、S-13、S-14；N-24、N-26。** [晚期窗口](2026-10-03-astra-7-infra-evidence/late-node-move.json)

### H-06 runner 開不了 out.log，仍可永久停在 born〔bug〕

**重現：** `followup.py:out_poison` 使用合法 keep true、合法 taskdir fd，在 runner 啟動前將 out.log 建成目錄。tick 後等 runner 退出，再 tock／tick。

**看到：** tick started=[x-r1]，runner rc1，沒有 pid／exit、也沒有 stderr；下一輪 started=[]，x-r1 仍 born，keep 不會重起。這條例外返回在 G-02 新增的「讀不到 birth 寫 exit127」之後，仍漏掉 open out.log 失敗。直接 fd 矩陣中的 out-dir 也得到同樣結果。

**需要：** 任務目錄仍可寫時，起程序前的 I/O 失敗也要寫受控 exit／可追蹤錯誤；沒有狀態檔可寫時，應有啟動交接的故障出口。另測 exit.json 本身是目錄時只留 tmp、讀不到 code，這屬 N-23 尚未完成的恢復範圍，不冒稱本輪已解。**S-06、S-10；N-21、N-22、N-23、N-59。** [完整 keep 重現](2026-10-03-astra-7-infra-evidence/runner-out-poison.json)、[runner I/O 矩陣](2026-10-03-astra-7-infra-evidence/runner-io.json)

### H-07 ctl-failed 的時間 suffix 也碰撞時，隔離檔會被覆蓋〔bug〕

**重現：** `edges.py:ctl` 先建立同名失敗檔，再預放 `x.json.42`，將 time_ns 固定為 42，送下一份 x.json。這是命名碰撞故障注入，**沒有聲稱自然時鐘曾重複該奈秒值**。

**看到：** 100 份正常同名隔離都保留；但次級 suffix 已存在時，程式直接 `os.rename` 覆寫 `x.json.42`，原 sentinel 消失，被 sequence=100 取代。stop 仍成功，所以此案是證據／請求保留失敗，不是 G-01 飢餓重現。

**需要：** 隔離目的地保證不覆蓋，碰撞時再取新名字或使用排他建立；時間字串只能降低碰撞機率，不能當 no-clobber 契約。位置：`aos7_daemon.ctl_failed`。**S-01、S-06；N-19、N-22。** [正常累積與碰撞對照](2026-10-03-astra-7-infra-evidence/ctl-failed.json)

### H-08 活集合有界，但歷史、回條與失敗隔離仍無界〔技術選型〕

**重現／看到：** 長跑 each 不斷產生新 tid，`keep_ended_rounds=3` 已歸檔，活程序／fd 沒有隨回合累積，但 tasks-old、rounds／daemon log、ctl-done、總檔案與磁碟仍持續增長。另 100 次壞回條留下 100 份 ctl-failed，障礙移除不會自行消耗歷史。具體斜率見長跑表。

**需要／界線：** N-40 的「目前 tick／tock／status 不被舊任務拖慢」與「總磁碟容量有界」必須分開。這符合既定 Q3 只搬不刪，不要求改成自動丟歷史；要持續運行時需有容量可見性、保留／匯出入口，尤其新增 ctl-failed 要納入。刪除政策仍尊重擁有者，不藉本案新增自動刪檔授權。**S-01、S-06；N-40、N-19、N-22、N-41。** [長跑](2026-10-03-astra-7-infra-evidence/longrun-clean.json)、[失敗累積](2026-10-03-astra-7-infra-evidence/ctl-failed.json)

### H-09 aos7-run 的 fd 是可信任內部交接，字串參數不是身分約束〔技術選型〕

**重現／看到：** 舊單參數與正確 fd 成功；錯 fd rc1、沒有解釋／exit；a 路徑＋b fd 時，b argv 照跑、exit 寫 b，a 留 born。這是 fd 作為權威的行為，也避免錯誤回退去污染舊路徑。正常 tick 用 pass_fds 傳自己的 taskdir，本輪沒發現它自然傳錯 fd。

**需要／界線：** 文件或錯誤訊息明確表達「第二參數是繼承而來的目錄能力、cwd 亦由呼叫者保證」；非法呼叫應能診斷，但不能為了補 exit 就盲寫第一參數。不把此入口宣稱成驗證／隔離任務身分的邊界。這不需要重開權限方向決策。**S-01、S-06、S-10；N-13、N-21、N-49。** [六種參數](2026-10-03-astra-7-infra-evidence/runner-fd.json)

## 五、對 infra-needs 的建議

僅建議，**沒有改需求檔**。

| 項目 | 建議狀態與下一個驗收 |
|---|---|
| N-20 | 從「已做」改 **部分**；保留完整／半行重播成果，補真 daemon 非 timeout 的 tock 失敗，不重報 ended、不越過 open 回合。 |
| N-75 | 明列 **部分**；現役鎖主衝突已擋，認領窗口未閉合。驗收加同 tick 雙宣告，不只先拿好鎖的對照。 |
| N-24／N-26 | 保留 root fd 的成功結果；N-24 整體列 **部分**，補 last-mile runner 環境一致性（H-05）。Q4 不需再決定。 |
| N-21／N-22／N-59 | N-21 的全涵蓋宣稱改 **部分**；runner out.log I/O 失敗不能永遠 born；UTF-8 解碼也需局部錯誤邊界。N-22 維持部分。 |
| N-19 | 維持 **部分**，加 no-clobber 隔離命名驗收。不要把「移到 ctl-failed」等同可靠保存／已完成執行。 |
| N-23 | 維持 **沒做完整恢復清單**；半行 JSON 與半個 UTF-8 字元分測，涵蓋 writes audit、runner tmp／缺 exit。 |
| N-40 | 活集合掃描成本的既有驗收仍成立；總磁碟、log、ctl-done／ctl-failed 保留量另列，不要把搬到 tasks-old 解讀成容量受控。 |
| N-31／N-55 | 維持目前已做；本輪 reload 完整驗證／dyn 來源、atexit 與 demo 收尾均通過。 |
| N-17／N-41 | 本輪 20 線混合負載沒有控制面失聯；不推翻前輪 200 線容量／公平性限制，也不改使用者接受慢的選擇。 |
| N-77／N-78 | namespace／ledger 正常探針通過；合作式身分、舊服務在途請求仍是原有界線，沒有新增方向決策。 |

## 六、收尾與可信範圍

來源比較覆蓋原有 proto7／proto7-1 的 **1,348 份檔案**，前後集合與內容聚合 SHA-256 相同，沒有新增／刪除／改動任何非交付檔案。47 份案例 cleanup 全數成功；核對時本輪記錄的暫存根、`/tmp/astra7-*` 資料夾、指向本輪 root 的產品程序均為 **0**，沒有 harness_error。[收尾 JSON](2026-10-03-astra-7-infra-evidence/verification.json)。交付只保留本報告與同名 evidence 目錄的腳本及精簡 JSON，沒有保留長跑原始空間、大型 log 或子程序。

本輪未測斷電持久性、真磁碟耗盡、NFS／FUSE，也未以失敗注入推估發生機率。真 bind mount 僅在私有 namespace 內；時序、短寫、讀回失敗、時間 suffix 皆明標注入方式。量測點的同步不代表整棵檔案樹的原子快照。報告的「沒有活程序殘留」取測試控制器介入之前的產品 stop 結果；最後清場另核對控制器的已退出後代，兩者不混算。
