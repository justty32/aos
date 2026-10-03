# astra-4：daemon／tick 基礎設施實驗（2026-10-03）

這輪只評 daemon、tick、tock、aos7-run、掛載與控制檔。**最需要補的是可靠的任務歸屬、重啟後的寫入權交接、可恢復的檔案協議，以及負載增加時仍可操作的控制面。** kernel／agent 都沒有參與；沒有跑 real.py、示範場景或真 LLM。

入口依序為 [README](../../README.md) → [試做 spec](../../spec.md)，才沿連結讀[核心 spec](../../../proto7/spec/core.md)、problems 分檔與前三輪報告。主線加五個 subagent，共六條工作線；只新增本報告與[證據](2026-10-03-astra-4-infra-evidence/)，未改產品。故障／時間／巢狀探針可並行；正式規模測量另外序列執行，重測最小規模以排除本輪其他探針干擾。不是隔離主機基準測試，也不是數天耐久測試。

## 一、數字

### 1. 規模：一個 daemon、10／50／100／200 條時間線

每條設定 **100 ms、每回合三個 each `/bin/sleep 0.01`**，各級目標跑 15 秒；200 條因採樣器自身也遲到，視窗實際 18.959 秒。AMD Ryzen 7 9800X3D、16 邏輯 CPU、Linux 6.18.49、Python 3.14.7。主表採 10 條的獨立重跑；外部宿主負載未隔離。含冷啟動及歷史逐漸累積，不是固定歷史的穩態測量。[完整方法](2026-10-03-astra-4-infra-evidence/scale/fragment.md)、[環境](2026-10-03-astra-4-infra-evidence/scale/environment.json)、[分析](2026-10-03-astra-4-infra-evidence/scale/analysis.json)

| 時間線數 | 視窗秒 | 每線完成 tick 最少／中位／最多 | daemon CPU（單核%） | 全組粗略等效核 | daemon RSS 峰 KiB | daemon fd 峰 | 全組活程序採樣峰 | 最終普通檔數 | 任務目錄數 |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 10 | 15.085 | 122／123.5／124 | 34.03 | 9.68 | 21,240 | 25 | 17 | 18,650 | 3,720 |
| 50 | 15.032 | 31／33／36 | 21.97 | 14.23 | 26,992 | 107 | 92 | 26,125 | 5,073 |
| 100 | 15.832 | 14／18／21 | 18.78 | 14.00 | 32,388 | 208 | 115 | 28,491 | 5,454 |
| 200 | 18.959 | 5／11／18 | 13.84 | 13.54 | 42,552 | 406 | 205 | 35,457 | 6,660 |

CPU／RSS／fd 指 daemon 本身，**不含**其動作與任務。全組 CPU 是 harness `RUSAGE_CHILDREN` 收集 daemon、tick、tock、runner、sleep 的累積 CPU 秒，除以含停機與離線整理的 wall time，只是粗略等效核，不能當精確利用率或 CPU profile。程序、RSS、fd 約每 250 ms 採樣，短命程序可能沒被抓到，峰值是下界；採樣本身在過載時會更慢。檔數是停機後普通檔，已扣三個探針檔；視窗末尚在飛的任務可能在停機期間才補全檔案。

**延遲表，單位 ms；各格為 P50／P95。** 主回合間隔用 tick **完成→下次完成**，符合 S-08；另列呼叫起點間隔供比較。tick／tock wall 包含完整 subprocess 啟動、工作、排程與等待，沒有用 log 差值冒充。

| 線數 | tick wall | tock wall | 回合間隔（完成→完成） | tick 起點→起點 | status 更新間隔 | rescan 回條 RTT |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 42.590／58.050 | 34.487／51.432 | 121.261／144.510 | 120.948／144.897 | 37.021／61.992 | 22.357／41.883 |
| 50 | 212.183／321.981 | 202.240／322.125 | 444.830／605.027 | 442.144／598.277 | 103.069／266.130 | 82.939／164.667 |
| 100 | 341.948／855.777 | 331.347／881.738 | 788.248／1,512.145 | 785.054／1,496.099 | 207.319／428.537 | 181.589／551.591 |
| 200 | 458.507／2,301.136 | 455.203／2,438.912 | 1,226.618／3,707.099 | 1,192.963／3,650.120 | 401.021／702.302 | 214.400／3,669.784 |

設定 100 ms，回合間隔中位落差依序 **+21.261／+344.830／+688.248／+1,126.618 ms**，即設定的 1.21／4.45／7.88／12.27 倍。200 條 tock 呼叫相對本輪預定 deadline 的遲到 P50／P95 為 **399.685／2,239.247 ms**；首份 status 要 4.671 秒，最晚一條首 tick 完成要 7.181 秒。表中的 status 更新間隔不包含這段首次等待。首次 status／首 tick 的延遲以第一筆 OS 採樣時點近似起算，晚於 Popen 啟動，故也屬下界，不是精確 exec 起算延遲。回條樣本僅 7／7／6／5 筆，P95 等於各組最大值，不能當 SLA。

全部 tick／tock rc=0、daemon 正常退出，未碰 fd／程序硬上限（fd 524,288；RLIMIT_NPROC 246,988；當前 cgroup pids.max 74,096）。**最先失去的是回合節奏、發現新線的公平性與控制反應，並非先 OOM、耗盡 fd 或程序額度。** daemon RSS 約 21→42 MiB 本身不足以解釋整組成本，也不能代表全部任務的記憶體。

為了避免把瓶頸一律歸給短任務 runner，再做 200 條、100 ms、**空 tasks** 對照：

| 空任務對照 | 視窗秒 | 視窗內曾完成 tick 的線 | tick／tock P50 ms | 回合間隔 P50 ms | 首 status | ctl 結果 |
|---|---:|---:|---:|---:|---|---|
| 第一次 | 10.117 | 121／200 | 46.316／46.971 | 377.420 | 10.225 秒，已送 stop 後 | 視窗內無回條 |
| 第二次 | 15.382 | 200／200 | 451.826／464.593 | 1,322.091 | 4.354 秒 | 最大 2,671 ms |

空任務也會失去可預期性，兩次差異很大；第二次全組粗略等效核約 6.91，比 each 的 13.54 少，回合卻沒變快。因此證據支持**多程序啟動／執行、掃描、排程與協調的合計成本**先壓垮節奏，並確認控制面沒隔離；沒有 CPU profile／固定歷史消融，不能宣布唯一瓶頸是 Python 啟動或磁碟 I/O。空任務第一次 79 條尚無完成 tick 的統計也有截尾，不能以它較低的 P50 說比第二次健康。

首次 10 條的回合間隔 P50 是 101.951 ms，獨立重跑是 121.261 ms，亦顯示宿主／排程變異。原始數據兩份皆保留，沒有選較漂亮的一份。P-12 已知歷史全掃；本輪短窗有數萬檔，但沒有把所有退化都歸給歷史增長。

### 2. 時間與延遲控制組

量測用外部 wrapper 的 `time.monotonic()`，仍呼叫原本獨立的 tick／tock 程序，包含啟動與排程等待。下表的「起點間隔」特指 tick **呼叫起點**，S-08 的回合開始則是 **tick 完成**；兩者不能混用。完整起訖在 [time/](2026-10-03-astra-4-infra-evidence/time/)。

| 實驗 | 設定／樣本 | 看到的延遲或間隔 |
|---|---|---|
| 極短 interval、空任務 | 1 ms，33 次 tick | 起點間隔中位 32.086 ms，範圍 30.657–34.176 ms |
| 零／負 interval | 0／−10 ms，各 33 次 tick | 靜默夾成 1 ms；實際中位 32.134／32.218 ms |
| 一般 interval、空任務 | 100 ms，11 次 tick | 起點間隔中位 100.056 ms |
| 極長 interval | 一天，觀察 1.05 秒 | 只起 1 回合；空任務照樣提早 tock，未實等一天 |
| 修改 interval | 1,000→100 ms，r1 tock 後改 | 下個 tick 仍等 1,000.060 ms；其後 100.060、100.070 ms |
| 很長改極短 | 一天→10 ms，再寫 rescan | 300 ms 內仍 r1；SIGTERM 後 31.33 ms 可退出 |
| 模擬繁忙造成 tick 遲到 | 100 ms；首 tick SIGSTOP 350.87 ms | tick 全程 367.11 ms；完成後 0.093 ms 進 tock，tock 15.628 ms 完成；下次 tick 距首起點 382.83 ms，其後約 100.08 ms |
| 模擬牆鐘跳動 | 0→+1 h→−1 h→0；11 次 tick | 起點間隔中位 100.062 ms，範圍 100.005–100.079 ms；檔案時間戳確實倒退兩小時 |

本次 uid 1000、effective capabilities=0，沒有 CAP_SYS_TIME；時鐘案改的是全部相關 Python 程序的 `datetime.now()`，沒有改 host 時鐘；遲到案以 SIGSTOP 精準模擬拿不到執行時間，實際 CPU 壅塞另由規模組覆蓋。原型使用 monotonic 排程，沒有補起無界回合或因牆鐘倒退卡住。S-08 本就容許不準時，**32 ms 跑不到 1 ms 並非核心違約**，但應能從檔案看出實際節奏。

提前 tock 的控制組設 500 ms，各跑三回合：空任務在 tick 完成後約 0.10 ms 呼叫 tock；每輪一個 10 ms 新任務約 40.3 ms；keep sleeper 首輪約 483 ms，之後約 0.1 ms，舊 sleeper 仍活著。這只是 P-16 的新數字：判斷集合確實是「本回合新起的」，不另報「常駐任務被排除」為新問題。[early.json](2026-10-03-astra-4-infra-evidence/time/early.json)

### 3. 任務型態覆蓋

所有 payload 是自寫 Python 或 `/bin/sleep`，負載有界；表內「剩餘」是產品停機後、探針額外清理前的觀察。最後都由探針清乾淨。普通任務型態測試可與其他小探針重疊，不能拿這裡的短窗數字推論整機飽和容量。

| 任務型態 | tick／tock／runner／daemon 的反應 | 證據 |
|---|---|---|
| 每輪 20 個、各 10 ms | 連續五個有負載回合，100 個任務全部 code 0；回合 tick 本體起點間隔約 99–102 ms。tick 本體首個時間戳到 daemon 收結果約 24–31 ms，至 tock 本體約 79–85 ms；這兩欄不是完整 subprocess 耗時 | [short.json](2026-10-03-astra-4-infra-evidence/tasks/short.json)、[summary.json](2026-10-03-astra-4-infra-evidence/tasks/summary.json) |
| 不理 SIGTERM | task kill 請求至回條 1,230.14 ms，最後 SIGKILL、exit −9；可收掉，但阻塞該次 tick，驗證 P-17 | [ignore.json](2026-10-03-astra-4-infra-evidence/tasks/ignore.json) |
| fork 後主程序先退出 | runner 寫 exit 0；同 PGID 與另 setsid 兩案，kill 都回 `already ended`，孫程序在 daemon stop 後仍活 | [fork.json](2026-10-03-astra-4-infra-evidence/tasks/fork.json)、[forksetsid.json](2026-10-03-astra-4-infra-evidence/tasks/forksetsid.json) |
| 一個吃滿單核的任務 | 有界忙迴圈正常 exit 0；200 ms 時間線照跑七回合，tick 完成間隔中位約 200 ms。這不是 16 核全滿測試 | [cpu.json](2026-10-03-astra-4-infra-evidence/tasks/cpu.json) |
| 大量 stdout | 8 MiB 全進 out.log，exit 0、沒有 pipe 塞死；無截斷／輪替。只保存大小，未把大檔帶入證據 | [output.json](2026-10-03-astra-4-infra-evidence/tasks/output.json) |
| 任務自行 chdir | 改到 `/` 後仍可用絕對 AOS7_TASK 路徑、runner 正常寫 exit 0；不影響 daemon cwd | [chdir.json](2026-10-03-astra-4-infra-evidence/tasks/chdir.json) |
| 刪自己的 taskdir | status 變 live=[]，task＋runner 仍活；keep 補驗三輪累積三個 task＋三個 runner，正常 stop 都略過 | [delete.json](2026-10-03-astra-4-infra-evidence/tasks/delete.json)、[deletekeep.json](2026-10-03-astra-4-infra-evidence/tasks/deletekeep.json) |
| birth.json 改成 `[1]`／壞語法 | `[1]` 使後續 tick 的 live_names 持續 AttributeError；壞語法被當空出生資料，keep 連起三份而舊任務仍活 | [birtharray.json](2026-10-03-astra-4-infra-evidence/tasks/birtharray.json)、[birthsyntax.json](2026-10-03-astra-4-infra-evidence/tasks/birthsyntax.json) |
| tock.json 壞語法／變目錄 | 語法壞掉會被下一次正常原子寫覆蓋；變成目錄則 tock 反覆失敗。雙任務補驗中四輪無摘要，排序較後的健康任務一次 tock 都收不到 | [tocksyntax.json](2026-10-03-astra-4-infra-evidence/tasks/tocksyntax.json)、[tockdirpeer.json](2026-10-03-astra-4-infra-evidence/tasks/tockdirpeer.json) |

### 4. 崩潰與重啟覆蓋

七組、各一條 200 ms 時間線。用 `sitecustomize` 在指定 `os.remove`／`os.replace` 前後 SIGSTOP，再由控制器 kill -9，精準放大真實的中斷窗口；重開 daemon 不帶 hook。這些是確定性的故障注入，沒有估算自然發生機率。[方法與完整快照](2026-10-03-astra-4-infra-evidence/crash/fragment.md)

| 窗口／故障 | 重開後各檔是否一致 |
|---|---|
| tick 刪 spawn 後，kill tick | 到 r5 仍無請求、birth、任務或回條；log 只知道 tick 曾 −9 |
| tock 寫 ended 後，kill tock | ended 指 r1；r1 摘要不存在，r2/r3 摘要也不再列該任務結束 |
| runner 寫完 exit 暫存、rename 前，kill runner | 正式 exit 是 `lost:true/code:null`，旁邊完整 tmp 卻有 code 23；沒有半截正式 JSON |
| tick 最後 round rename 前，kill daemon | 新 daemon 完成 r2；放行舊 tick，round.json 變回 r1/open，status 仍 r2 |
| tock 最後 round rename 前，kill daemon | 新 daemon 完成 r2；放行舊 tock，round.json 變回 r1/closed，status 仍 r2、摘要已有 r2 |
| 執行中 `.aosd` chmod 0555 | daemon exit 1，sleep 任務仍活；恢復權限、重開後接得回並能 TERM 收掉 |
| status rename 注入一次 ENOSPC | daemon exit 1、留下 status tmp，沒有產品 error／stop 記錄；移除注入重開可繼續 |

唯讀是非 root 帳號的真實 EACCES；ENOSPC 僅模擬 metadata rename 失敗，**沒有填滿實體磁碟，也沒有做斷電／fsync 耐久性驗證**。探針收集的 stderr 與 fault-marker 不是產品原本會留下的狀態檔。

### 5. 三層路一、兩 daemon 路二成環

路一為 A tick→B daemon→C daemon→leaf；每層 150 ms，經 task mount 啟動、預建子 `.aosd` 排除 P-11 首次掃描重疊。[nested/results.json](2026-10-03-astra-4-infra-evidence/nested/results.json)

| 對最上層 A 的操作 | A 退出耗時 | A 退出再等 1.4 秒 | 性質 |
|---|---:|---|---|
| SIGTERM，一個正常 leaf | 113.50 ms | 0 活程序，三份 status 均 stopped/live=[] | 正常路徑通過 |
| SIGTERM，四個忽略 TERM 的 leaf | 1,114.91 ms | B exit −9；C＋其 runner、兩個 leaf＋其 runner 共 6 活程序 | P-04 三層新證據；C 還在逐個善後，未宣稱永久孤兒 |
| SIGKILL，一個正常 leaf | 1.08 ms | 7 活程序：B/C、三 runner、一 leaf、一個當時正在跑的 tick；B/C 已到 r12 | P-04 新增深度與範圍量測 |

路二用兩個純 writer 任務，**只經各自 `mnt/peer/ctl` 寫對方 pause**。一般巢狀 root，A→B 掛載可用，B→A 的 `../.aosd` 與根內指向父的 symlink 均被拒；B 停在 r1，A 在 400 ms 觀察窗 r4→r7。另場先明示配置 `A/.aosd → child/.parent-aosd`，讓控制目錄的實體在兩邊可達範圍內：雙向掛載成功，兩邊都 pause 在 r1，400 ms 不前進；外部寫 JSON resume 後都到 r3。**有前置配置的成環成功**；S-22 已說成環風險由使用者承擔，雙方互停不是 bug。

## 二、新問題（含明確標示的既知問題新證據）

下列重現腳本都在證據目錄；在 workspace 根執行各目錄的 `probe.py`，nested 用 `reproduce.py`，scale 命令另列於其說明。每一項的錯誤責任都落在基礎設施，沒有把 kernel／agent 的規則當前提。

### I-01 舊動作能覆寫新 daemon 的回合〔bug〕

**重現：** `crash/probe.py` 的 stale-tick／stale-tock：停在 r1 最後 round rename 前，kill daemon；同 root 重開至 r2，pause 新時間線，再放行舊動作。

**看到：** 兩案 round.json 都由 2→1，新的 status 繼續報 2；tick 案還把回合改回 open。flock 只防第二個 daemon，不防舊 tick／tock 繼續提交。這超出 P-08「中斷回合缺號」：已提交的新進度被舊執行者倒寫。若不介入，依磁碟 round+1 的邏輯還可能再次使用舊編號；這是程式推論，本案直接證據止於倒退。

**牽涉：** S-01、S-03、S-06、S-08。核心沒指定世代鎖方案，但同一條線重啟接手後不能讓舊動作覆蓋新進度。[stale-tick](2026-10-03-astra-4-infra-evidence/crash/stale-tick.json)、[stale-tock](2026-10-03-astra-4-infra-evidence/crash/stale-tock.json)

### I-02 spawn 在啟動前先刪，崩潰會無痕丟工作〔bug〕

**重現：** 放 `spawn/once.json = {"name":"once","argv":["/bin/true"]}`；tick 刪檔後、start_task 前 kill -9；原 daemon 到 r3，再重開到 r5。

**看到：** 零 birth、零任務、零請求／回條。log 有 tick −9，卻沒有可重送的工作身分。細部 spec §4 是「起完就刪掉」，實作順序相反；不只是尚未定義 exactly-once 語意。

**牽涉：** S-01、S-06、S-09、S-10。[spawn-loss.json](2026-10-03-astra-4-infra-evidence/crash/spawn-loss.json)

### I-03 ended 標記與回合摘要分岔，後續 tock 也不自然補回〔bug〕

**重現：** 任務 `/bin/true` 已 exit 0；tock 寫 ended.json 成功後被殺；清空任務表避免干擾，再起 daemon 跑到 r3。

**看到：** ended 指 r1，但 r1 摘要沒寫成；r2/r3 因已見 ended 標記而永久略過這次結束。exit 原檔仍有 code 0，全盤掃可找回；只讀 rounds 會漏事件。新點是**消費標記先落盤**，不是重報 P-08 的缺回合。

**牽涉：** S-01、S-06、S-08；細部 spec §3／§7。[ended-loss.json](2026-10-03-astra-4-infra-evidence/crash/ended-loss.json)

### I-04 主程序正常結束後，仍活孫程序退出管理視野〔技術選型〕

**重現：** tick 起 Python 任務，fork 子程序睡 12 秒，主程序約 80 ms 後正常退出；分別測孫程序留在原 PGID 與 setsid。等 exit 0，寫 task kill，再正常 stop daemon。

**看到：** 兩案 kill 都回 `ok:true/msg:already ended`，status live=[]；孫程序在 stop 後仍活。同 PGID 也失敗，故不只是 P-05「另一 session 漏訊號」或 P-04「daemon 被強殺」：判定 ended 後根本不進群組清理。細部 spec §6 同時寫了「已結束任務 kill 當成功」，所以這個分支符合現行試做規則，不能稱它違反既定 kill 行為；缺口是「主程序已結束」與「所有歸屬資源已結束」沒分開。後代是否可脫離、需管理多久可以另定，但結果檔必須明說涵蓋範圍。

**牽涉：** S-01、S-03、S-06、S-10、S-17；細部 spec §6。[fork](2026-10-03-astra-4-infra-evidence/tasks/fork.json)、[forksetsid](2026-10-03-astra-4-infra-evidence/tasks/forksetsid.json)

### I-05 任務可寫的管理資料，會令自己失蹤或拖垮同線其他任務〔bug〕

**重現與觀察分三種，不能都歸成「壞 JSON」：**

| 操作 | 看到什麼 | 新增的基礎設施後果 |
|---|---|---|
| 任務刪掉自己的 taskdir，繼續睡 | status live=[]，task＋runner 仍活；keep 三輪補出三對程序，stop 全漏 | 任務清單依賴任務自己能刪的 birth 檔；沒有獨立歸屬清冊 |
| 任務把 birth 改 `[1]`／寫壞語法 | 前者 r2 起 tick 反覆 rc1；後者 keep 舊實例未死卻連起三份 | 格式驗證與保留有效定義不足；不能把「無法讀」一律當「沒有活實例」 |
| 任務把 tock.json 改成目錄，另放健康 task | 四輪 tock 全失敗；健康 task 一次 tock 檔都沒有 | 一個任務通知位置不能寫，阻斷整條線後續通知與摘要 |

這輪沒有要求先上安全 sandbox；即使完全信任程式，同 UID 任務誤刪、錯寫管理資料也是 S-06 要承擔的故障。單純 chdir 正常、單純 tock 語法損壞可被覆寫，對照組已排除「改 cwd 必壞」等過度結論。

**牽涉：** S-01、S-06、S-09、S-10、S-11。[deletekeep](2026-10-03-astra-4-infra-evidence/tasks/deletekeep.json)、[birtharray](2026-10-03-astra-4-infra-evidence/tasks/birtharray.json)、[birthsyntax](2026-10-03-astra-4-infra-evidence/tasks/birthsyntax.json)、[tockdirpeer](2026-10-03-astra-4-infra-evidence/tasks/tockdirpeer.json)

### I-06 interval 格式錯誤會永久停掉該迴圈，修檔＋rescan 不恢復〔bug〕

**重現：** 正常對照設 100 ms；其他 node 設 null、`"bad"`、10^309，另補 Python JSON 擴充 NaN／Infinity。起 daemon 後全部修成 100 ms，寫 rescan，再觀察 300 ms。

**看到：** 五條都在 r0/stopped/paused:false，good 從 r3→r6；rescan 回成功，status 無 last_error，只有 log 的 ev:error 記型別／溢位例外。合法 JSON 的 null、字串已足以重現，不靠非標準 NaN 才成立。已死 Timeline 仍佔在 daemon 字典，scan 不會重起它；「不會自動恢復」另有此程式路徑支持，沒有把 300 ms 當無限時間證明。

**牽涉：** S-01、S-05、S-06。[invalid.json](2026-10-03-astra-4-infra-evidence/time/invalid.json)

### I-07 status 一次 I/O 例外就讓 daemon 無清理退出〔bug〕

**重現：** keep sleeper 已寫 pid 後，實際 chmod `.aosd` 為 0555；另一案只對 status rename 注入一次 ENOSPC。

**看到：** 都 exit 1；唯讀案 task 仍活，產品 log 沒有 error／stopping／stop，舊 status 留著。0555 目錄下既有 log 檔仍可 append，因此本案有記錄機會卻未走降級路徑。traceback 只在啟動者接走的 stderr；恢復權限後重開能接續。與 P-04 強殺無法善後不同，這次是可捕捉的普通 OSError。

**牽涉：** S-01、S-03、S-05、S-06。不是要求磁碟壞仍保證服務，而是必須明示降級／停止和剩餘程序處置。[readonly](2026-10-03-astra-4-infra-evidence/crash/readonly.json)、[enospc](2026-10-03-astra-4-infra-evidence/crash/enospc.json)

### I-08 設定檔的新 interval 與正在生效的 deadline 不同，但沒有檔案能看出來〔技術選型〕

**重現：** r1 tock 後改 1,000→100 ms；另場一天→10 ms，寫 rescan。

**看到：** 前者下個 tick 仍等滿舊 1,000 ms；後者 300 ms 仍 r1。實作只在下一輪前讀設定，最久可能等舊 interval 是讀碼推論，未實等一天。這符合目前實作邊界，核心未定 hot reload；缺的是 effective interval／生效回合／deadline，以及何種控制可以要求重算。rescan 成功只代表掃過 node。

**牽涉：** S-01、S-06、S-08。[change](2026-10-03-astra-4-infra-evidence/time/change.json)、[longchange](2026-10-03-astra-4-infra-evidence/time/longchange.json)

### I-09 路二跨 daemon 的控制端點，缺少明文的匯入配置方法〔技術選型〕

**重現：** A root 包 B child；A 掛 `child/.aosd`，B 掛 `../.aosd`，或掛 child 內指向父控制目錄的 symlink。

**看到：** 反向的兩種都拒絕；先將 A 控制目錄實體 re-export 到 B root 內再掛載，雙向 pause 才成功。這不是 M-13 越界檢查退化，也不建議撤掉檢查；新證據是 S-21 路二與 S-23 在多 root 組合時需要 bootstrap 匯入步驟，README/spec 沒有可照做的流程。S-22 允許環，本輪也已真正跑成環。

**牽涉：** S-01、S-07、S-21、S-23。[results.json](2026-10-03-astra-4-infra-evidence/nested/results.json)

### I-10 其餘只算新證據，不另創舊問題

| 分類／既知項 | 本輪重現與新增觀察 | 牽涉 |
|---|---|---|
| 〔技術選型〕P-07 lost／runner 失聯 | 任務 exit 23；runner 在 exit tmp 寫完未 rename 被殺，重開正式 exit 補 lost/null，完整 tmp 23 原樣留著。原子寫保住格式，恢復規則未決定 tmp 的權威性 | S-01、S-03、S-06；[runner-exit](2026-10-03-astra-4-infra-evidence/crash/runner-exit.json) |
| 〔技術選型〕P-04／P-17 清理與一秒寬限 | 三層、僅四個忽略 TERM leaf 就讓 B 被升級成 −9；父停機後 1.4 秒還有六個活程序；見一-5 的步驟與正常對照 | S-01、S-03、S-06、S-21；[nested](2026-10-03-astra-4-infra-evidence/nested/results.json) |
| 〔技術選型〕P-12／P-17 歷史與程序成本 | 每條三個 each、100 ms，逐級 10→200，量到的節奏／CPU／控制延遲見一-1；P-12 的「全掃會長」升級成容量與操作延遲證據，不把容量下降直接列 bug | S-04、S-05、S-06、S-09；[scale](2026-10-03-astra-4-infra-evidence/scale/) |
| 〔技術選型〕牆鐘記錄與延遲判讀 | 同一調度過程注入 +1h→−1h，實際間隔仍 100 ms，rounds 的時間戳卻倒退兩小時；只靠現有 at 無法重建經過時間 | S-01、S-03、S-08；[clock](2026-10-03-astra-4-infra-evidence/time/clock.json) |

沒有重新開列 P-06 pause 時 task ctl 等待、P-09 keep 被 kill 後補起、P-10/P-11 接管重疊、P-16 提前 tock 等已知語意決策。本輪的工程需求可以先做；不需要把這些舊問題再交使用者回答一次。

### I-11 大量新 node 的發現流程，會延遲首次 status 與控制回條〔技術選型〕

**重現：** `scale/scale_probe.py --repo "$PWD" --seconds 10 --counts 200 --tasks 0 --tag=-empty`；另以 15 秒重跑確認。200 個全新空 node，沒有任務歷史。

**看到：** 第一次視窗 10.117 秒只有 121 條完成過 tick，沒有 status／ctl 回條，送 stop 後 10.225 秒才首 status；第二次首 status 4.354 秒、ctl 最慢 2.671 秒。產品主迴圈先 handle_ctl，再同步 scan 一次啟動全部新 Timeline，之後才 write_status；忙碌的發現過程阻住了後續控制與首份快照。沒有量 mutex 等待，不能限定某一把鎖是根因。這是零任務歷史即可發生的**冷啟動控制面飢餓**，不同於 P-12 的歷史全掃。

**牽涉：** S-01、S-05、S-06、S-18；核心未定延遲上限與排程方案，故不把「超過幾秒」自行升為核心 bug。[analysis.json](2026-10-03-astra-4-infra-evidence/scale/analysis.json)、[空任務重跑 status](2026-10-03-astra-4-infra-evidence/scale/daemon-200-empty-confirm-00-status.json)

## 三、daemon／tick 需求清單（重點）

「必要／應該／可以」是本輪依實驗提出的**工程驗收優先度**，不是聲稱核心已新增這些條款。S-06 給 daemon 責任；S-08 不承諾硬即時；核心未定的檔案格式、恢復與隔離方法仍可選。表中「原則有、細則無」表示能從核心責任推導需求，但不能把建議實作當作現有 S 條款。

### A. 先補可靠性與可管理性

| ID／優先度 | 一個合格的 daemon／tick 應提供什麼；最小驗收 | 本輪證據 | 核心對應 | proto7-1 現在做到沒有 |
|---|---|---|---|---|
| R1 **必要** | **接管後撤銷舊動作的提交權。** 每次 daemon 接手可辨識世代；kill/restart 之後再放行舊 tick／tock，不能倒寫已提交的回合 | I-01 | S-03、06、08 原則有；世代／鎖細則無 | **未做**。只有 root daemon flock，動作無世代檢查 |
| R2 **必要** | **請求不能無痕消失。** spawn／ctl／加掛共用可追蹤 request id、接受／處理／結果狀態；任意中斷點重開後，至少能回答待處理、已產生哪個 tid、失敗或結果未知 | I-02；runner-exit | S-01 直接，S-06／10 原則；交易協議無 | **部分**。task／daemon ctl 與加掛有回條；spawn 無結果、且先刪 |
| R3 **必要** | **回合關閉與通知可恢復。** tock 的任務通知、ended 消費、summary、round 關閉之間能重做／校對；不因局部完成永久漏事件；未完成者可讀為 incomplete／aborted／unknown | I-03、I-05 tockdirpeer | S-08／11 有回合與通知；S-01／06 有責任；提交方案無 | **部分**。單 JSON rename 原子；多檔沒有一致性／恢復協議 |
| R4 **必要** | **任務資源歸屬獨立於任務可刪的目錄與主 PID。** tick 交付後即有基礎設施保管的 owner／task 身分；主程序退出、fork、setsid、taskdir 刪除後，仍能盤點與清理已納管資源；允許脫離者須明示解除歸屬 | I-04、I-05 deletekeep；三層 TERM/KILL | S-03／06／10 直接相關，S-21 要可組合；資源域機制無 | **未完整做**。pid/pgid 加即時後代走訪；exit 或 birth 消失就失管 |
| R5 **必要** | **故障限制在可處理的最小範圍。** 一個 task 的 birth／tock 壞掉，不能令其他 task 永久無通知；格式與I/O錯誤要附目標、階段和後果。壞設定修好後有恢復途徑 | I-05、I-06 | S-05／06、S-11 原則有；恢復細則無 | **部分**。timeline thread 可隔離；task 內錯誤仍連坐、死 thread 不再起 |
| R6 **必要** | **一般 I/O 失敗有受控路徑。** 停止接新工作、重試／降級／停機可選，但要處理在飛動作和任務；尚可寫處記結構化原因，不能裸 OSError 退出 | I-07 | S-03／05／06；具體策略無 | **未做**。status 一次失敗退出，無清理；stderr 需啟動者另接 |
| R7 **必要** | **「成功／停止」說清涵蓋範圍。** 回條分 accepted／applied，停機另有 direct-task／resource-domain 完成或 remaining/unknown；不以父 live=[] 暗示整個子樹已收完 | I-04；三層六個殘存；I-08 rescan | S-01 直接；S-06／17／18／21 相關；結果語意細則無 | **部分**。有 ok/msg；沒有階段、清理範圍、未收完資源 |
| R8 **必要** | **控制面在所有線 pause、或工作面壅塞時仍有可用入口。** daemon ctl 的處理不能依賴任務收到 tock；公開並測量受理／套用延遲，過載要有狀態可看 | 路二互 pause 後外部 resume 成功；I-11 首 status／ctl 延遲 | S-18／21 直接，S-22 不替使用者解環；延遲上限無 | **部分**。pause 全部仍讀 ctl 已做到；冷啟動 scan/status 與 ctl 共主迴圈，負載會拖延 |
| R9 **必要** | **時間調度與牆鐘分離，遲到後有界前進。** 單調 deadline；tick 很晚時不補起無界回合，也不讓牆鐘倒退造成倒回合；這不要求準點 | 時鐘 ±1h；350.87 ms 停頓 | S-08 容許遲到，S-06；具體 clock 無 | **已做到本輪範圍**。monotonic 等待、遲到後循序前進；診斷欄位待補 |
| R10 **必要** | **可配置跨 daemon 端點，仍走掛載。** 明示外部 ctl 如何匯入／re-export、可達範圍、身份與拒絕理由；新操作者能照文件完成路二雙向配置 | I-09，兩種反向拒絕、re-export 成環成功 | S-07／21／23 直接；bootstrap 形式與權限細則未定 | **部分**。root 內 symlink mount、拒絕理由有；外部端點須手排實體目錄 |

R1–R3 不一定需要重型資料庫。可選動作鎖、世代 token、可重放紀錄、冪等請求 ID、提交指標等；驗收的是中斷後不倒退、不失蹤、能判別結果。R4 的後代歸屬、允許脫離的登記方式與整棵 kill 語意仍需明定，核心尚未要求遞迴收掉一切程序；表內是對已納管資源的工程建議。可選 cgroup、監督者加持久清冊等，**subreaper 單獨並不自動解決 owner 身分與所有清理語意**。路一的子 daemon 可以沿用普通任務資源域，無須把父子角色寫進 daemon 核心。

### B. 容量、時間設定與資源收尾

| ID／優先度 | 能力與驗收 | 本輪證據 | 核心對應 | proto7-1 現況 |
|---|---|---|---|---|
| R11 **應該** | **公開容量與過載策略。** 以時間線數、工作量、實際 cadence、tick/tock duration、ctl 延遲評估；限制同時在飛的動作／出生量，過載可排隊或明示拒絕；保持各線公平前進 | 10→200 規模表、tick/tock 全 rc0 但 cadence 下降 | S-04／05／06／09 原則有；沒有 200 條或 100 ms 的 SLA | **未做容量管理**。一線一 thread、每動作獨立程序；沒有過載狀態／配額 |
| R12 **應該** | **活動工作集成本有界。** 歷史任務不應每次 status／tick／tock 都全讀；有活動索引、歸檔／保留策略，保留 S-01 可讀查詢 | 本輪檔數與控制更新延遲；P-12 新規模證據 | S-01／05／06；保留與演算法無 | **部分**。rounds 已合 JSONL；任務目錄仍全掃、一直累積 |
| R13 **應該** | **CPU、程序數、輸出空間可設限並記結果。** 有總量與每任務政策，out.log 輪替／截斷有明示；以全部後代計資源，不只看 daemon RSS/CPU | 8 MiB output；單核忙迴圈；規模總CPU；I-07 ENOSPC | S-03／06 相關；S-17 允許上層定策略；具體配額無 | **未做**。任務直接輸出檔，無基礎設施配額或輪替 |
| R14 **應該** | **設定變更可判讀。** schema／範圍驗證；configured/effective interval、config revision、生效回合、下次到期或剩餘量；明示何時重算已存在 deadline | I-06、I-08 | S-01／06／08；hot reload 細則無 | **未完整做**。負值靜默夾 1 ms；錯型別停線；有效設定只在下一輪讀 |
| R15 **應該** | **多任務與多層停機使用可組合的總 deadline。** 批次通知、統一等待或傳遞剩餘期限；超時回報未收完，不讓祖先一秒先殺掉還在收尾的中間層 | 四個 stubborn leaf 的三層 TERM；單 task kill 1.23s | S-06／09／21；超時與整棵終止語意未定 | **未做**。每 task 串行一秒、外層也一秒，彼此衝突 |
| R16 **應該** | **啟動恢復清單。** 盤點未完回合、runner lost、遺留 tmp、缺 birth／失效 mount；逐項給 recovered／aborted／unknown 與證據來源，不能任意信任 tmp | I-01–03；runner-exit；deletekeep | S-01／06；恢復政策無 | **部分**。只補 lost；無恢復報告、tmp 無判讀規則 |
| R17 **可以** | **不改程序邊界的執行成本最佳化。** 在保留 S-04 每動作 POSIX 程序的前提，改善啟動／掃描與資料讀取，提供可重跑 benchmark | 極短空線約32ms；規模測量 | S-04／09 有約束；語言／演算法無 | 現用 Python CLI；是否改語言、批次內部 I/O 都可選，不能據此直接改成 thread action |

### C. S-01：新讀者只看檔，究竟能回答什麼

另外請一位**尚未讀任務組結果與 OS 存活資料**的既有 subagent，只讀三份實驗快照回答四個問題；它已讀 README/spec，並非全新上下文的 LLM，也沒有額外呼叫真模型。快照是循序採集，不是多檔同時定格。原始回答在 [file-only-review.md](2026-10-03-astra-4-infra-evidence/readability/file-only-review.md)，擷取來源在 [provenance.json](2026-10-03-astra-4-infra-evidence/readability/provenance.json)。

| 快照 | 只看檔案的回答 | 與獨立 OS 觀察核對 |
|---|---|---|
| A：fork 主程序已結束 | 一條 n；r5 已開、最後完成 r4，status 還是 r4 的較早觀測；協議列零活任務。額外 grandchild 檔只證明曾記 PID，孫程序現在是否活 **unknown**；不能因 kill ok 斷言全清 | 孫程序確實仍活。產品檔缺資源域存活與清理結果，讀者保持 unknown 是正確的 |
| B：taskdir 消失 | 一條 n，r4 已完成；live=[]，但歷史有 started、無 ended，資料夾缺失。只能說追蹤缺尾段，任務是否真死 **unknown**；任務自寫 deleted 檔不是可信死亡證明 | task＋runner 確實仍活；只讀產品 live 欄會漏掉它們 |
| C：birth 非物件 | 一條 n，r4 已完成；最後觀測 birtharray-r1 活。r2–r4 tick 的 `.get` AttributeError 可從 last_error/log 定位，tock 仍成功；round 遞增不代表 tick 成功 | 判讀吻合。這案的檔案足以指出錯誤元件，但無法知道誰何時改了 birth |

時間線數、已開／完成回合在 **3／3** 快照都能合讀回答；目前真正存活的 Linux 程序／後代不能完整回答。C 的故障可直接定位；A 無足夠產品證據宣稱故障，B 能識別追蹤缺口。A/B 中任務自寫 grandchild/deleted 證詞比標準產品檔多，不能假定每個任務都會幫基礎設施留下這些線索。

**R18〔必要〕：狀態輸出要是一份有觀察範圍、有版本、能表達 unknown 的檔案契約。** 核心直接對應 S-01，並受 S-13／14／21 的空間與身份約束；下列欄位是本輪建議，核心沒有規定名稱。proto7-1 已有局部 status、birth、exit、round、回條，做到基礎可讀；尚缺世代、一致性判讀、完整資源歸屬和恢復結果。

| 要回答的問題 | 現有檔案可回答的部分 | 最小還缺什麼；驗收方式 |
|---|---|---|
| 空間有幾條時間線？ | 單 daemon 的 status.nodes、各 timeline.json | `daemon_id/session`、管理的 canonical root 與子空間／端點索引、snapshot 範圍；沿三層只讀檔能區分「本 daemon 1 條」與「合計 3 條」，不因 mount alias 重複計數 |
| 各在第幾回合？ | round.json、status.round、rounds.jsonl | `generation`、`current_action/attempt`、最後已提交 tick／tock 的 round 與 commit 序號、incomplete/recovery 狀態；I-01 三份檔衝突時能指出權威來源，不靠取最大值猜 |
| 哪些任務活著？ | birth/pid/exit，daemon 提供當時 live 快照 | 獨立 task registry、主程序狀態與資源域狀態、observed_at、unknown／orphan／missing-metadata；fork／deletekeep 不能被說成零剩餘資源 |
| 剛剛哪裡出錯？ | task out/exit、daemon log、部分 last_error | 所有錯誤路徑一致的 `component/node/tid/request_id/phase/error_kind`、可恢復性與下一步、recovery report；I-06 thread 例外也要在近期錯誤入口，I-07 stderr 要有已知去處 |
| 這些狀態新不新、能否相互比較？ | wall-clock at 與各 node round | daemon session、單調事件／snapshot sequence、duration 與明示新鮮度；多檔讀到不同版本能察覺。時鐘跳動不影響排序／耗時判讀；重啟或跨主機不能直接比較裸 monotonic 絕對值 |
| ctl／掛載已生效嗎？ | ok/msg、birth.mounts、mount-done | 目標 owner/session、受理／套用／完成階段、effective round/config revision、端點有效性與失敗原因；成功回條不可被誤讀成整個子樹已停 |

「只看檔」不可能讓一份已凍結的快照證明此刻 Linux 程序必然活著；即使增加 heartbeat，也必須容許 **unknown／過期**，並約定以什麼可信時間或外部觀察者判斷新鮮度。需求是 daemon 將 Linux 觀察轉成有時間、範圍與可信程度的檔案，LLM 不需自己翻 `/proc` 才能知道這些限制。這比替每個上層 agent 補猜測規則更應先做。

R1、R2、R3、R4、R5、R6、R18 可作第一批故障驗收；R8、R11–R15 用規模與三層停機表驗收。先保證接受的工作有去向、仍活的資源不失蹤、重啟不倒寫，再優化吞吐。這些要求不依賴任務是否叫 kernel 或 agent。

### 重跑、證據與清理

各組腳本、原始計時切片、JSON 快照及方法限制都在[證據目錄](2026-10-03-astra-4-infra-evidence/README.md)。probe 的 subreaper 只讓實驗控制器接住並 reap 自己的孤兒；產品 daemon 沒有因此獲得該能力。故障後「仍活」先記證據，再由 probe 額外 kill／wait 清理，不能把探針清理當成產品通過。

最終核對：`/tmp/astra4-*` 實驗空間全數刪除，沒有本輪殘留程序；證據單檔最大 179,999 bytes，全部嚴格小於 200,000 bytes。JSON／JSONL 可解析，主報告與證據入口連結有效。詳 [final-check.json](2026-10-03-astra-4-infra-evidence/final-check.json)；可用同目錄 `verify.py` 重查。
