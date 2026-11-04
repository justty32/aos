# astra-5：daemon／tick 基礎設施回歸與再攻擊（2026-10-03）

**這批修補有實效，但需求清單多個「已做」仍只涵蓋正常路徑。** 原本 spawn 無痕丟失、ended 標記超前、壞 birth／tock 連坐、主迴圈遇一般 I/O 直接退出，都有改善；主要缺口轉到中斷後接管、跨檔提交、搬移時讀取一致性、消失判定與程序收尾。kernel／agent 僅用作檔案讀者或長駐探針，沒有跑 `real.py`，沒有呼叫真 LLM。

依據：[核心 spec](../../../proto7/spec/core.md)、[試做 spec](../../spec.md)、[N-01～N-54](../infra-needs.md)、[astra-4](2026-10-03-astra-4-infra.md)。主線加五個 subagent，不超過六條；只新增本報告與[證據](2026-10-03-astra-5-infra-evidence/README.md)，沒有改產品、核心 spec 或直接改需求清單。規模組在其他負載探針結束後序列執行。故障注入固定競態順序，不代表自然發生率；網路掛載用 ESTALE／EIO 模擬，沒有實架 NFS。

**Q1(a)、Q3(a)、Q4(a) 都視為既定決定。** 故意清環境並脫離管理、刪 taskdir 的代價不重新要求 cgroup；真實 rename 被掃到就 kill，不要求自動復活舊任務。下列無須新增〔要使用者決定〕：修正均可在現有語意內做；掃描錯誤如何暫緩判定屬技術選型，並明確指出原清單已記錄其風險。

## 一、I-01～I-11 回歸表

舊腳本已複製到本輪證據後重跑，未覆寫第四輪證據。必要相容調整及舊 harness 的失效等待條件見[證據入口](2026-10-03-astra-5-infra-evidence/README.md)。**原案例修好，不等於同名需求全部完成。**

| 編號 | 判定 | 本輪重現與證據 |
|---|---|---|
| I-01 舊動作倒寫新回合 | **原倒寫已擋；接管仍不完整** | 舊 tick／tock 在拿鎖前停住，新 daemon 可前進，放行舊者不倒退。舊者已持鎖時，新 daemon 卡在 r1，.25 秒 timeout 只殺等鎖的新動作；放行舊者才恢復。原腳本「先等新 r2，再放舊者」因此 timeout，不能拿它直接判失敗或通過。見 [crash/fragment](2026-10-03-astra-5-infra-evidence/crash/fragment.md)、第二節 F-04。 |
| I-02 spawn 起前先刪 | **原窗口已修** | 原 remove-after 注入點已經有 once-r1 birth／已啟動的工作，不再零請求零任務。至少一次仍容許重播，不宣稱 exactly-once。毒 batch 的永久飢餓另見 F-06。[spawn-loss](2026-10-03-astra-5-infra-evidence/crash/spawn-loss.json) |
| I-03 ended 有、摘要無 | **原窗口已修；N-20 僅部分** | 原 ended-after 注入點已有 r1 ended 摘要；改在 append 後中斷，則同回合重做 tock 寫兩行 r1，timeout 後下一輪也重報同一 ended。前者已防漏，尚未防重／統一提交。[ended-loss](2026-10-03-astra-5-infra-evidence/crash/ended-loss.json)、[same-round-replay](2026-10-03-astra-5-infra-evidence/crash/same-round-replay.json) |
| I-04 主程序結束後漏孫程序 | **部分** | 原 fork／setsid 案先下 task kill 都成功；移除此步、直接正常 stop，兩案各剩一個孫程序。同 PGID、原環境完整的普通 fork 也漏，不屬 Q1 故意脫離。[tasks/fragment](2026-10-03-astra-5-infra-evidence/tasks/fragment.md)、F-01 |
| I-05 任務壞資料連坐／失蹤 | **承諾修的原子案通過；刪目錄屬已接受邊界** | birth `[1]`／壞語法不再連起 keep；壞 tock 目錄有局部 errors，健康同伴收到 r4。deletekeep 仍累積三對 task／runner，stop 後六活程序，但 Q1 已明列刪 taskdir 自負，不把它重新算違約。更廣的單項隔離仍缺，見 F-06。[tasks/fragment](2026-10-03-astra-5-infra-evidence/tasks/fragment.md) |
| I-06 壞 interval 永久停線 | **部分** | null／字串／NaN／Infinity 改用1000ms，有 last_error；修檔會恢復。但原 10**309 仍在 math.isfinite 丟 OverflowError，r0/error，未走預設；修100ms後477ms到r3。[time/fragment](2026-10-03-astra-5-infra-evidence/time/fragment.md) |
| I-07 唯讀／ENOSPC 令 daemon 退出 | **原兩案已修；N-22 仍部分** | 真 chmod .aosd 0555、status rename 一次 ENOSPC，daemon 都活著，有 io_errors，解除後恢復且正常 stop rc0。舊 harness 等 daemon 崩潰而 timeout，補驗改看恢復；未測滿碟／斷電。[readonly-recovery](2026-10-03-astra-5-infra-evidence/crash/readonly-recovery.json)、[enospc-recovery](2026-10-03-astra-5-infra-evidence/crash/enospc-recovery.json) |
| I-08 interval 生效不可見／催不動 | **最小修復通過** | status 顯示 effective interval；一天改100ms後 wake，約152ms到r3。只改檔＋rescan 仍不催回合，符合分工；1000→100ms的第一個間隔仍約1000ms。deadline/config revision 尚未有。[time/extra](2026-10-03-astra-5-infra-evidence/time/extra.json) |
| I-09 路二匯入配置缺文件 | **未修，原限制確認** | 原生反向 `../.aosd`／symlink 仍拒；明示 re-export 後互 pause 成環與外部 resume 成功。不是越界檢查該撤掉，仍缺可照做的配置流程。[nested/results](2026-10-03-astra-5-infra-evidence/nested/results.json) |
| I-10 既知限制的新證據 | **多數仍在，分項判讀** | runner fd-relative exit hook 修正後：tmp code23，正式 lost/null；三層正常 TERM 後0活程序，頑固／SIGKILL 案在1.4秒窗各6活程序；牆鐘跳動排程仍約100ms，但事件排序缺序號。歷史搬移已做，新增讀競態見 F-02；程序成本見下表。不是把整項一概當未修。[crash/runner-exit-fd](2026-10-03-astra-5-infra-evidence/crash/runner-exit-fd.json)、[nested/fragment](2026-10-03-astra-5-infra-evidence/nested/fragment.md)、[time/fragment](2026-10-03-astra-5-infra-evidence/time/fragment.md) |
| I-11 冷啟動阻塞首次 status／ctl | **部分：首份 status 修好，後續公平性未完成** | SCAN_BATCH=20 使首 status 數十毫秒出現；但200空線首測15秒只167線完成過 tick，ctl 最大8.317秒，status 更新最大間隔4.318秒。首份快照不代表全部 node 已發現。重跑及四級負載詳下表。[scale/analysis](2026-10-03-astra-5-infra-evidence/scale/analysis.json) |

### 規模補表：沿用 astra-4 方法，單獨執行

每線100ms、每回合三個 `/bin/sleep .01`，每級目標15秒；另跑兩次200空線。wall 包含獨立程序啟動與等待。回合間隔取 **tick 完成→完成**，依 S-08；原 summary 的 actual_interval_ms 是起點差，本表另由原始資料重算。首測 empty 的首 status 以第一個 OS sample 作起點，是稍低估的值；其餘記實際啟動前 monotonic。P95 的 ctl 樣本只有數筆，表中直接列最大值，不當 SLA。

| 情境 | 視窗秒 | 有完成 tick 的線 | 每線完成 tick 最少／中位／最多 | 首 status 秒 | 完成間隔 P50／P95 ms | ctl 最大 ms（樣本） |
|---|---:|---:|---|---:|---|---|
| 10線、三短任務 | 15.031 | 10／10 | 130／131.0／133 | 0.017 | 107.7／155.7 | 23.3（7） |
| 50線、三短任務 | 15.427 | 50／50 | 27／30.0／34 | 0.033 | 501.7／748.3 | 68.8（6） |
| 100線、三短任務 | 15.737 | 100／100 | 12／15.0／20 | 0.045 | 875.0／1725.5 | 633.7（5） |
| 200線、三短任務 | 15.859 | 200／200 | 3／8.0／15 | 0.077 | 1218.1／3488.2 | 1318.1（5） |
| 200線、空任務首測 | 15.029 | 167／200 | 0／20.5／38 | 0.049 | 459.5／687.8 | 8316.9（3） |
| 200線、空任務重跑 | 15.116 | 152／200 | 0／14.5／30 | 0.086 | 576.1／839.9 | 6850.3（3） |

全部動作 rc0、daemon rc0。這些是短窗觀測、含冷啟動、未隔離宿主，不宣告穩定吞吐或唯一瓶頸。Q3 預設保留20回合：低線數跑得較多，會進入歸檔；高線數不少尚未達門檻，不能把差異全歸給歸檔。**使用者已接受「慢就慢」：N-41 不再升級成改架構要求；N-17 的控制面可操作性仍須另驗。**

## 二、新問題與再攻擊

### F-01 stop 不經已修的 ended 清理分支〔bug〕

**重現：** [stop_only.py](2026-10-03-astra-5-infra-evidence/tasks/stop_only.py) 沿用原 fork／forksetsid payload，只拿掉先下 task kill 的步驟。主程序約80ms退出、孫程序睡12秒；650ms後正常 SIGTERM daemon。

**看到：** 普通 fork 同 PGID、未改環境、taskdir 完整，daemon exit0、status stopped:true/live:[]，孫程序仍活；setsid 對照也剩一個。原腳本先下 task kill 則全收。`kill_if_stopping()` 只列 live_tasks，ended 任務根本不進 `kill_task()` 新增的殘留掃描；Q3 搬走後亦不能只掃 active taskdir。

**需要：** stop 對已接管 node 做 Q1 範圍內的群組／環境收尾，或同等完整的候選枚舉；回條區分任務主程序 ended 與程序群組仍活。不需要 cgroup／subreaper，也不用重問 Q1。S-01、S-03、S-06、S-10、S-17；N-09、N-25。[普通 fork 證據](2026-10-03-astra-5-infra-evidence/tasks/fork-stop-only.json)

### F-02 Q3 搬移時，兩處都找仍會讀成「沒有」〔bug〕

**重現：** [archive_probe.py](2026-10-03-astra-5-infra-evidence/tasks/archive_probe.py) 建 ended worker-r1，用量1234、agent state act/r2/steps9、kernel-state 有 sentinel；讀者列到舊路徑、尚未開檔時加 barrier，讓獨立原版 tock 在 r3、keep=0 完成 rename，再放行讀取。沒有假造讀取回傳值。

**看到：** agent 前任 state 被當缺失，回 fresh idle/r0；kernel 回 empty_state；usage_total **1234→0→1234**，中間還把已 ended 任務判 alive:true。搬前、搬後靜態控制組都正常。這是路徑清單和後續開檔間的競態；檔案未毀損，先 open 的 fd 在搬後仍可讀。[agent](2026-10-03-astra-5-infra-evidence/tasks/agent-archive.json)、[kernel](2026-10-03-astra-5-infra-evidence/tasks/kernel-archive.json)、[usage](2026-10-03-astra-5-infra-evidence/tasks/usage-archive.json)

**需要：** 基礎設施提供穩定 tid 讀取協議：directory fd／openat，或路徑失效後重定位並重讀整份任務快照；尚未讀齊要表達 unknown，不能無條件折成新狀態／零用量。用量跳動可能影響上層調度是推論，本案沒有宣稱已發出錯誤 pause。Q3 搬移政策維持；S-01、S-06，S-17／S-19 僅為探針顯示後果；N-40。

**撞號對照通過：** 正常 new_tid 同查 tasks-old，worker-r1 已歸檔時給 worker-r1-2。人為 restore 同 tid 至 active 造成非空目的衝突，tock 記 errors、兩份用量都保留、健康同伴仍收通知；沒有證據顯示正常 tick 自己撞號覆蓋。[collision](2026-10-03-astra-5-infra-evidence/tasks/archive-collision-archive.json)

### F-03 Q4 把 I/O 觀測失敗當 node 消失〔技術選型〕

**重現：** [node/repro.py](2026-10-03-astra-5-infra-evidence/node/repro.py) 在真 sleeper 已登記 pgid 後，對 `scandir(n)` 單次注入 ESTALE，或對 timeline stat 注入 EIO，再呼叫原 Daemon.guard(scan)。node 與 timeline 實體從未刪除。

**看到：** 兩案都 kill 現役 sleeper，log 是 node-／node-gone-kill，**io_errors 增量0**。os.walk 忽略掃描錯誤，isfile 把 stat 失敗變 False，guard 接不到例外。[結果](2026-10-03-astra-5-infra-evidence/node/results.json)

**定位：** infra-needs 文末已明記「一次掃不到就 kill，網路掛載斷一下先不處理」，所以這是**已知取捨的確證與診斷缺口**，不冒充新的未答 Q4。建議將「找到／確定不存在／無法觀測」拆開；對 ESTALE／EIO／EACCES 保存既有 node 與 pgid，記 scan error、恢復後重掃，再依確定消失執行 Q4。沒有要求真 rename 搬回就免死。S-01、S-03、S-06、S-07；N-12、N-22、N-26。

| Q4 其他對照 | 結果與界線 |
|---|---|
| n→.hidden、掃一次、立刻搬回 | 舊任務照樣被 kill；符合已答 Q4，不當 bug。 |
| timeline 原子替換 | 1000次 write_json/os.replace 與500次 scan 並行，沒有 node-，task 存活。本地 POSIX 同檔 replace 無 unlink 空窗；不能宣稱網路檔案系統也因此通過。 |
| 改環境但 pgid 已採樣 | 刪 node 後可收；光改環境不一定脫離群組管理。 |
| 清環境、在0.25秒採樣前刪 node | `_pids={}`、漏收；保持原環境的對照成功。屬 Q1 明示責任邊界，清單須揭露「記憶體清冊是週期採樣」，不寫成無條件保證。 |

### F-04 daemon 重開，timeout 收不到舊 action.lock 持有者〔bug〕

**重現：** [crash/extended.py](2026-10-03-astra-5-infra-evidence/crash/extended.py) 的 handoff-*-held：舊 tick／tock 已持鎖、停在最後 round replace 前；kill -9 daemon，原 root 重開，action_timeout_s=.25。另測舊動作尚未 flock 的對照。

**看到：** gen2 已寫，但1.15秒窗 round 一直1，新 tick／tock 連續 timeout -9；只有放行舊者才恢復到r4。未拿鎖的舊者放行後退出且不倒寫。安全性有了，但鎖內舊動作不再受活 daemon 的 timeout 管理。無限不恢復是程式路徑推論，實測是有界窗口與放行對照。[tick held](2026-10-03-astra-5-infra-evidence/crash/handoff-tick-held.json)、[tock held](2026-10-03-astra-5-infra-evidence/crash/handoff-tock-held.json)

**需要：** 可驗身分的動作 owner／世代／PID 啟動身分紀錄，重開後有界回收舊 action，再交接同一把鎖。不可用 unlink lock 解卡，否則新舊程序可能鎖到不同 inode。S-03、S-06、S-08；N-18、N-23、N-54。

### F-05 總結、ended、closed 與 timeout 不是同一提交〔bug〕

**重現：** tock 的 append_jsonl 已完整寫入後停住，分別讓 daemon 的 .25秒 timeout 殺它，或直接 kill 後在同回合再執行 tock。[extended.py](2026-10-03-astra-5-infra-evidence/crash/extended.py)

**看到：** timeout 案 r1、r2 兩份摘要都報 one-r1 ended；r1 摘要像正常完成、無 incomplete，daemon log 同回合卻記 incomplete:true／rc−9。直接重做案 rounds.jsonl **兩行 round:1**。closed 最後才寫，不能替前面的 append 去重。[timeout-after-summary](2026-10-03-astra-5-infra-evidence/crash/timeout-after-summary.json)、[same-round-replay](2026-10-03-astra-5-infra-evidence/crash/same-round-replay.json)

**定位與需要：** 細部 spec 已明說中斷可能重報 ended，故不把重報本身冒充違反 exactly-once；但 N-20「可恢復、不重複總結」的已做宣告不成立。需有 round／attempt 提交身份、可重放去重／恢復規則，並讓只看 rounds 的讀者知道哪份未完成。N-54 的殺動作與 log incomplete 都符合現行 spec；只有 tick 被切斷才明訂 summary 的 incomplete 欄位。tock 摘要與跨檔提交的一致判讀是 N-20／N-12 需補的驗收，不能據此宣稱現行 N-54 違約。S-01、S-06、S-08、S-11；N-20、N-12、N-54。

### F-06 單項隔離仍漏起任務、控制回條與讀取入口〔bug〕

| 重現 | 看到什麼 | 證據 |
|---|---|---|
| tasks 第一項 name:123，第二項正常 true；連三輪 | tick 全rc1，正常工作從未出生；new_tid 的 re.sub 拒絕 int，should_start 未驗 name，start_task 又在 try 外 | [robustness](2026-10-03-astra-5-infra-evidence/robustness/numeric-name.json) |
| batch=[合法prefix、name:7、合法suffix]，另有 regular | 兩輪各起一份 prefix，suffix／regular 都沒起；poison 檔一直在，round.started 卻空 | [controls](2026-10-03-astra-5-infra-evidence/controls/results.json) |
| 某 ended 任務 ctl-done.json 變目錄，提交未知 op | 三輪 tick/tock 全rc1，正常工作不出生、無總結；run_all_ctl 在兩個動作的局部保護外 | [ctl receipt](2026-10-03-astra-5-infra-evidence/robustness/ctl-receipt-dir.json) |
| interval=10**309 | 1.25秒仍r0/error，每0.5秒重試；不走預設，修檔後能恢復 | [time extra](2026-10-03-astra-5-infra-evidence/time/extra.json) |
| wait-tock 讀 tock.json=[1] 或2 | 立即 AttributeError／rc1，與 timeout 共用退出碼但不是正常等待到期；正常 round3、壞 round 字串對照符合預期 | [controls](2026-10-03-astra-5-infra-evidence/controls/results.json) |

**需要：** 完整 schema 與逐項錯誤邊界涵蓋 start_task／run_all_ctl／serve_mounts；拒絕壞項、保留可追蹤結果，讓健康項繼續。先做整數範圍檢查再 isfinite，wait_tock 先驗 dict。batch 至少一次已接受，但永久毒項導致健康項飢餓並非必要代價。S-01、S-06、S-09、S-10、S-11；N-13、N-21、N-34、N-51。

### F-07 加掛已生效，但請求與回條都消失〔bug〕

**重現：** fixture 任務向 inbox 加掛，故意令 mount-done/x.json 是目錄；跑原 tick。[mount-receipt-dir](2026-10-03-astra-5-infra-evidence/robustness/mount-receipt-dir.json)

**看到：** serve 先刪請求、symlink 與 birth.mounts 已更新，再寫回條失敗；第一輪 tick rc1，第二輪正常，但原請求沒了、正式回條也沒有。**不是掛載失敗或資料完全丟失**，而是無法從請求結果協議追蹤；還連坐當輪後續工作。

**需要：** 請求退休要在結果可追蹤之後，生效與回條具可恢復身份，寫回條故障局部隔離。N-19 本來就是部分，spawn 修好不代表整份請求協議完成。S-01、S-06、S-23；N-19、N-21。

### F-08 subroot 在 tick 才建，擋不住父 daemon 第一次搶管〔bug〕

**重現：** [subroot.py](2026-10-03-astra-5-infra-evidence/nested/subroot.py) 預備子樹 timeline/tasks，父任務已宣告 subroot，沒有另外預建 `.aosd`；三次冷啟動。

**看到：** 三次父 log 都先 node+ n/child/n，由父視角在子線 r1 起 leaf，birth.node=n/child/n；下一掃才 node-，子 daemon 從r2接手。subroot 最後確實有寫入 birth，不是漏宣告。scan 先取完 now_ids，tick 補標記來不及改掉這批候選。[subroot.json](2026-10-03-astra-5-infra-evidence/nested/subroot.json)

**需要：** 開線前先完成子根登記並在接管時複核 owner；或文件要求 bootstrap 先建標記，撤回欄位單獨足夠的承諾。本案證明誤接管／出生，不宣稱有 round 倒退。S-06、S-15、S-21；N-47。

### F-09 node 存在檢查過後仍能建回鬼目錄〔bug〕

**重現：** [gone_mid_action.py](2026-10-03-astra-5-infra-evidence/nested/gone_mid_action.py) 在 tick／tock 通過 timeline 檢查且已拿 action.lock 後、正式 round／summary 寫入前停住，分別刪除 node 或 rename，再放行。四種組合都跑。

**看到：** 四案 rc0 且重建舊路徑：tick 建 round.json，tock 建 round.json＋rounds.jsonl。rename 案新位置仍保留原 r1/open，舊位置卻寫新狀態。[四案](2026-10-03-astra-5-infra-evidence/nested/gone_mid_action.json)

**需要：** 動作對 node 目錄身分與提交位置要穩定綁定，不能只在入口 isfile 一次；可用目錄 fd／身分驗證，刪除後提交回受控失敗。單純提交前再查一次仍有 TOCTOU，unlink／重建 action.lock 也會破互斥。runner 經 fd 寫 exit 的修補有效範圍不能外推到 tick/tock。S-06、S-13、S-14；N-24。

### F-10 wake 洪水仍佔住主控制迴圈〔技術選型〕

**重現：** paused node 預排一萬 wake，第一份回條出現後再送 stop --kill。[controls/repro.py](2026-10-03-astra-5-infra-evidence/controls/repro.py)

**看到：** 此次整批排空約0.411秒，stop 回條等0.401秒，這段每0.1秒採樣 status.at 都沒變；不是死鎖。handle_ctl 會一次處理全部檔名快照，SCAN_BATCH 不管這條路。規模組另有數秒 ctl 延遲，兩者不能混成一個唯一根因。

**需要：** 每圈件數／時間預算、同 node wake 合併或等效公平性；保留控制順序，不能為插隊擅改 pause/resume 的排序語意。S-06、S-18；N-17，回條無界累積另屬 N-16。使用者接受低吞吐，不等於已有可操作控制面的證據。

### F-11 測試／demo 的失敗路徑確會留下指向已刪空間的程序〔bug〕

**重現 agent：** [node/repro.py](2026-10-03-astra-5-infra-evidence/node/repro.py) 執行原版 `test_agent.RoundsFlag.test_rounds_n_exits`，只把真 agent 啟動延後0.5秒、tmp 前綴換本輪。原測試在0、0.15秒覆寫 tock=1、2，agent 只看到2，只處理一次；`--rounds 2` 還等一次。5秒 communicate timeout 後，unittest 原 cleanup 只 rmtree。

**看到：** 空間已刪，0.7秒後 agent 仍活，AOS7_ROOT 明確指向已刪 `/tmp/astra5-node-*`。`--rounds N` 是處理 N 次通知，不是「round欄位達 N」，也沒有牆鐘期限；wait_tock 讀不到檔就繼續等。該測試直接 Popen，沒有 daemon Q4 替它收。**這可靠重現使用者所述現象，但未追溯使用者先前那兩個 PID，不能斷言它們一定出自此測試。**[結果](2026-10-03-astra-5-infra-evidence/node/results.json)

**demo 對照：** `demo/play.py` 正常末尾有 stop／清理，但整段沒 finally；在寫 stop 檔注入 EIO 後 run() 拋錯，daemon／任務尚活。刪 root 後 Q4 收任務，daemon 本身仍活，還把 `.aosd` 建回。這是生命週期 owner 沒善後，不應改 agent 去猜暫時缺檔是否該退出。

**最簡對策：** Popen 成功當下就註冊 cleanup：先 terminate，限時 communicate／wait，逾時 kill，再 wait，最後才 rmtree；覆蓋 assertion、TimeoutExpired、OSError、KeyboardInterrupt。測 `--rounds` 每送一輪等 state/progress 確認，取代固定 sleep。daemon／demo 的 owner 同樣用 finally 收自己的程序；保留 PID／身分，勿用廣泛 pkill。S-06、S-10、S-11；建議新增 N-55，連 N-09、N-26。

### 正面控制組：不要把已答語意當新問題

- **resume rounds／pause_pending：** running 中 pause 顯 pending，tock 完才 paused；停穩後 resume rounds2 恰再完成兩回合。pending 尚未停穩就 resume rounds1，當前回合 tock 即用掉一次，符合「第 N 次 tock 完」；要完整新 N 回合先等 paused。pause 不 kill，是已答 N-32。
- **edit_json 持鎖者 kill -9：** holder 已在 callback、尚未寫入時被殺；後續取得鎖約0.098ms，原值0→1。flock 隨程序退出釋放，遺留 `.lock` 檔不用刪。只驗該中斷點，不聲稱 callback 外部副作用具有交易性。
- **max_live／合法 batch／wait-tock：** max_live2 維持兩個 live；合法三件 batch 同回合啟動；正常 wait-tock 印新 round，沒有新通知正常 timeout。它們的壞輸入限制另列 F-06。

以上控制與原始結果見 [controls/fragment](2026-10-03-astra-5-infra-evidence/controls/fragment.md)。

## 三、對 infra-needs.md 的修正建議

### 先修「已做」的範圍，避免驗收清單過度樂觀

| 需求 | 建議現況／優先 | 應補上的驗收界線 |
|---|---|---|
| N-18 | **保留已做（防倒寫）／必要** | 原安全性驗收通過；重開後舊 action 持鎖的接管缺口另併 N-23，連到 N-54 的管理範圍。不能把新增的接管可用性要求當成倒寫仍未修。 |
| N-20 | **已做→部分／必要** | 原漏 ended 窗口修好；同回合重放去重、timeout 與摘要提交一致性未完成。明示目前可能重報，不能同時宣稱不重複。 |
| N-21、N-13 | **已做→部分／必要** | 已修 birth／tock 通知；仍缺 name／spawn、實際啟動、ctl-done 寫入、interval 超大整數、wait_tock 型別等入口。健康項持續運作與結構化錯誤需一起驗。 |
| N-24 | **已做→部分；應該→必要** | 入口檢查只擋動作開始前已消失；鎖內刪／搬四案仍建鬼目錄、分裂回合位置。 |
| N-26 | **已做→部分；建議升必要** | 確定刪／搬的回收可用；一次觀測錯誤觸發 kill 是已披露取捨，應加入 unknown／scan error 的近期驗收。週期 pgid cache 與環境 fallback 前提須明寫。 |
| N-40 | **已做→部分／必要** | 工作集搬移有效，正常撞號已防；缺搬移中的穩定讀取／重試／不完整標記。磁碟歷史總量依然無界，不能把「不掃歷史」寫成「歷史成本全有界」。 |
| N-47 | **已做→部分／必要** | subroot 太晚寫，三次冷啟動父都先接管子線；必須驗第一次 scan。 |
| N-54 | **保留當前動作逾時已做／必要，註明範圍** | 本 daemon 當下 action 逾時已驗；重啟遺留 holder 併 N-23，摘要提交一致性併 N-20／N-12。本輪 held-lock 案先放行舊者才 stop，未直接測持鎖中停機上界。 |
| N-34、N-51 | **已做→部分／應該** | 合法 batch／正常 wait-tock 通過；毒項隔離、非物件 JSON 防護併 N-21，不新增重複需求號。 |

### 保留已答決定，調整優先與文字

- **N-25 不重開 Q1。** 保留已答(a)，追加「正常 stop 也須履行同群組／相符環境的既有範圍」，列必要驗收。刪 taskdir、清環境再脫離等是明示代價；不能用它們掩蓋 F-01 普通 fork 的漏收。
- **N-09／N-12 維持必要且部分，提前實作。** stopped/live=[] 仍不足以代表已收完整個保證範圍；unknown 不能只做外觀欄位，掃描失敗與搬移讀不全時也要進入決策。至少分 daemon 世代、node 實例、round／attempt、觀測範圍與結果新鮮度。
- **N-19、N-22 維持部分／必要。** N-19 補 F-07 已生效但無回條，以及毒 batch 的可追蹤失敗；N-22 補 walk/isfile 吞錯、不能只寫「尚缺降級」。I-07 的兩案通過不能外推成所有 I/O 安全。
- **N-17 保持必要／部分，N-41 保留已接受慢。** N-17 一併驗 scan、控制洪水、首 status 之後的更新間隔與全部 node 發現進度。主表必須區分「第一份快照」與「已發現全部」。本輪不建議為吞吐改 S-04 程序架構。
- **N-23 建議應該→必要，先限縮到接管與提交恢復。** 舊 holder、open 回合、已 append 未 closed、無主 runner 要有可讀處置清單。tmp 中 code23 是否可信仍需技術恢復規則，不能直接把任何 tmp 升成權威。
- **N-27 維持應該／沒做，排在近期。** 三層頑固任務仍有停機寬限互相搶；支援總 deadline／批次收尾後才聲稱巢狀停機完整。N-45 保持必要／部分，補 re-export 配置文件，不取消掛載邊界。
- **N-16 建議可以→應該。** 一萬 wake 就產生一萬 ctl-done，控制面與磁碟需各自的保留／整理規則；本輪沒有量長期滿碟，不把它宣稱已發生。
- **N-01／N-06／N-08／N-33／N-36 可保留已做的已測範圍。** N-02 保持部分；補 resume 在途回合計數例子、wake 的 idle 語意。N-03 early、N-30 name/by_ctl 的正常資料亦在結果裡。沒有本輪新證據的 N-04／05／07／10／11／14／15／28／29／31／32／35／37／38／39／42／43／44／46／48／49／50／52／53 不藉此宣稱全面重驗或任意改順位。

### 缺的需求：一條新增，其他併入原號

**建議 N-55〔必要〕：建立程序的測試／demo／探針，必須先回收程序，再刪空間。** 正常、timeout、assertion、I/O、interrupt 都驗 finally；每個 Popen 立刻登記 owner，清理有期限、能 reap、有剩餘清單。`--rounds N` 不是資源清理機制。這條直接對應此次孤兒重現，驗證工具也不能把自己的洩漏當產品結果。

其餘不膨脹編號：穩定歷史讀取併 **N-40／N-12**；scan 的 unknown 併 **N-26／N-22**；action owner 與世代接管併 **N-18／N-54／N-23**；總結提交身份併 **N-20／N-12**；node 目錄身分與中途刪搬併 **N-24**；完整單項隔離併 **N-21**。這些都是 daemon／tick 基礎設施能力，不把修補責任分散給每一個 kernel／agent。

### 證據與收尾

實驗空間均在 `/tmp/astra5-*`。每組先記錄產品操作後的殘留，再由 harness 額外清理；subreaper 僅用於實驗回收，不算產品能力。最終核對通過：實驗空間與匹配程序皆0，最大證據檔179,997 bytes（<200,000），JSON／連結有效，產品來源雜湊未變。程序／空間、檔案大小、JSON、連結與產品雜湊核對見 [final-check.json](2026-10-03-astra-5-infra-evidence/final-check.json)。重跑命令、腳本變更與限制見 [README](2026-10-03-astra-5-infra-evidence/README.md)。
