proto7-2 已承接多數舊能力，但生命週期與 once 去重仍未完全封閉；本次也找到巨大 interval 容錯、巢狀 subd 啟動及子根稽核三項明確的遷移退步，不能把 K 系列與第三波需求整批視為已解。

## 審查範圍與判讀方式

審查基準為 `6daebe2ef8227021745def649f4e3d86a3a8038c`。使用六條平行審查線，核對原始碼、規格、既有測試及探針，重要新發現再交叉複核。

**全程唯讀：沒有修改檔案、commit、push，也沒有執行測試、探針或匯入專案程式。** 下文的失敗結果都是附帶明確前提的靜態推導，不是本次實測紀錄。收尾時 HEAD 未變；工作樹另出現未追蹤的 `proto7-2/notes/reviews/`，不是本線建立，未納入判定。

來源正本：

- K-01～K-10：[astra-8 報告](../../../../proto7-1/notes/play/2026-10-03-astra-8-infra.md):103。
- 原修法：[生命週期三個不變條件](../../../../proto7-1/notes/decisions/2026-10-03-lifecycle-invariants.md):7。
- N-01～N-86：[infra-needs](../../../../proto7-1/notes/infra-needs.md):40，第三波從第 196 行開始。
- 現行承諾以 proto7-2 程式、[spec](../../../spec.md):7及各模組契約交叉判讀；舊「已修」紀錄不直接當驗收證據。

判定意義：

- **已解**：原需求已有對應實作；列出既有測試，覆蓋不足會明說。
- **部分解**：正常路徑成立，但仍缺一部分，或找到合法操作下的失敗路徑。
- **仍存在**：所需能力仍未提供；另註明原本未做或已接受限制。
- **因設計改變不適用**：舊機制消失或承諾明確撤回；不代表原現象在技術上被消除。

表內未加前綴的路徑均相對 `/home/guanyu/projs/aos/proto7-2/`；`P1/` 表示 `/home/guanyu/projs/aos/proto7-1/`。所有 `檔名:行號` 都指本次讀取的位置。

## 主要結論

K 系列中，**K-01、K-03、K-05 的原失敗條件已有實作防線**。K-02 尚有回合欠扣窗口，K-04 尚有官方 inst 子程序漏收窗口；K-07 的原 kernel 累計帳本沒有移植；K-08 只在 subd 包裝路徑更新身分。K-06、K-09、K-10 則主要靠改變範圍或移除舊機制處理。

第三波的最終判定是：

- **已解：N-80、N-81、N-84。**
- **部分解：N-79、N-86。**
- **仍存在：N-82、N-83、N-85。**

N-86 原本的「批次起一半被殺」已修，但交叉核對找到另一條合法反例：已啟動 once 尚未移項時，修改其排程門檻，讓同名 keep 先重用槽，之後原 once 仍可能再執行一次。詳見 R03。

N-01～N-78 中，最值得列為**遷移漏接**的是：

1. **N-21／N-62：巨大整數 interval 的容錯與舊精確回歸案例未承接。**
2. **N-66：移出核心後，`AOS7_SUBROOT` 的隔代清除／設定時序失去保護，正常三層配置會用到上一層路徑。**
3. **N-66：舊版「子根屬於擁有者的合法稽核範圍」沒有在 audit＋subd 組合接回。**

N-31 的第二次 reload 掉動態掛載、N-19 的失敗請求證據縮減、N-24 的啟動中搬移保護移除，則都有新版文件明說，應列為**已記載的能力退縮**。N-55 的中斷清場、N-38 的 node 世代識別等，是**原有未完成項延續**，不宜誤稱新版才忘記。

## 完整對照表

以下共 **96 列：10 個 K，加上 N-01～N-86，無省略編號**。「相關測試」表示覆蓋鄰近能力，沒有直接驗證整項需求。

| 編號／原需求 | 判定 | 程式與既有測試證據 | 差異、殘留與重現指引 |
|---|---|---|---|
| **K-01** 讀不到 round 卻開下一回合 | **已解** | `lib/aos7_fs.py:223`；`lib/aos7_daemon_timeline.py:184`；`lib/aos7_tick.py:246`。測：`tests/core/test_matrix_docs.py:39`、`test_matrix_faults.py:247`、`test_daemon.py:378`。 | daemon 與 tick 都拒絕 OPEN／UNKNOWN；不再把讀不到當已關。原「daemon 讀取失敗＋tock 持續 ENOSPC」完整組合未見同構測試。 |
| **K-02** 恢復後漏看 pause／rounds | **部分解** | `lib/aos7_daemon_timeline.py:190`、`:204`、`:260`；`lib/aos7_daemon.py:517`。測：`tests/core/test_daemon.py:211`、`test_errors.py:103`。 | 原 OPEN 恢復後已回迴圈頂端；但 CLOSED 後一次 UNKNOWN 會留下 `owe_done`，下一圈直接再 tick。**R01**。 |
| **K-03** tick／runner 交接雙死，永久 born | **已解** | `lib/aos7_task.py:92`、`:103`、`:118`、`:294`。測：`tests/core/test_ctl.py:161`、`test_once_threestate.py:51`、`test_matrix_once.py:66`。 | 無 runner／pid 的 birth 兩回合後須掃描，再判 lost；活 runner 仍會保守保留。once 可以零次執行是另行選定的最多一次語意。 |
| **K-04** runner 死於 pid 發布前，keep 雙開 | **部分解** | `lib/aos7_task.py:118`、`:134`；`lib/aos7_proc.py:176`、`:210`。測：`tests/core/test_matrix_once.py:66`、`test_matrix_faults.py:118`、`test_ctl.py:102`。 | 原普通任務案例已修；官方 inst 可在群組快照後生出新 session，漏收後仍發布 lost。**R02**。 |
| **K-05** starttime 讀不到被當 PID 重用 | **已解** | `lib/aos7_proc.py:29`、`:54`；`lib/aos7_task.py:92`。測：`tests/core/test_once_threestate.py:167`、`:182`；`test_matrix_faults.py:65`。 | runner、任務都比 PID＋starttime；未知保守當活。PID 重用測例是合成不同 starttime，非實際等待 PID 重用。 |
| **K-06** 啟動途中搬 node，產生鬼目錄 | **因設計改變不適用** | `notes/problems.md:196`；`spec.md:283`；`lib/aos7_task.py:311`、`lib/aos7_run.py:65`。相關測：`tests/core/test_daemon.py:113`。 | 鬼目錄明確接受；原決定仍要求的最後身分檢查也在精簡時刪除。原現象仍可能發生，不能稱技術修復。 |
| **K-07** 清歷史讓 kernel 忘記累計用量 | **部分解** | `lib/aos7_task.py:275`；`lib/aos7_tock.py:126`；`notes/problems.md:397`。測：`tests/core/test_tick_tock.py:58`；`packs/budget/tests/test_budget_step.py:180`。 | tasks-old／purge 已消失；同槽 state 保留，budget 有槽外帳。但原 kernel 累計仍只有設計，沒有原 cap 整合驗收。**R08**。 |
| **K-08** 手動重開子 daemon，owner 留舊 PID | **部分解；直接啟動改為不保證** | `modules/subd/aos7-subd:278`、`:295`；`lib/aos7_daemon.py:558`；`modules/subd/README.md:72`。測：`modules/subd/tests/test_subd_ownership.py:49`、`:88`。 | 經 wrapper 重開會更新；直接起核心 daemon 刻意不碰 owner。舊症狀仍在，現役 PID 要讀 status。 |
| **K-09** disk 掃描卡住 daemon 控制面 | **因設計改變不適用** | `lib/aos7_daemon.py:510`、`:582`；`notes/changes-from-7-1.md:18`。相關測：`tests/core/test_daemon.py:293`。 | disk／retention 計算已移除，不是改成背景計算。其他同步列目錄、status、tmp 清理仍無整體延遲上限，見 N-17。 |
| **K-10** 文件誤稱 1～2 ms 發現 node | **因設計改變不適用** | `spec.md:23`、`:37`；`lib/aos7_daemon.py:174`、`:400`。測：`tests/core/test_daemon.py:23`、`:36`。 | 改 register，不再掃 timeline；文件寫主迴圈約 20 ms，沒有硬延遲保證。 |
| **N-01** 外部催 node 立即開下一回合 | **已解** | `lib/aos7_daemon.py:257`；`lib/aos7_daemon_timeline.py:241`。測：`tests/core/test_matrix_a3.py:374`、`test_daemon.py:223`。 | 固定 interval 的 wake 可提前 tock；early 回合中 wake 不保留是明定語意。 |
| **N-02** interval 生效值可見、能立即重算 | **部分解** | `lib/aos7_daemon_timeline.py:59`、`:216`；`lib/aos7_daemon.py:528`。相關測：`tests/core/test_daemon.py:152`、`test_matrix_a3.py:374`。 | 有有效值及 wake；沒有 config revision，early 回合中仍須等。`tasks_rev` 不能代替 timeline 版本。 |
| **N-03** 任務知道 tock 是否提前 | **已解** | `lib/aos7_daemon_timeline.py:254`；`lib/aos7_tock.py:90`、`:102`。測：`tests/core/test_daemon.py:152`、`:162`。 | `early` 已到任務通知與總結；不是完整的提前原因分類。 |
| **N-04** 每回合任務 ACK／回報追蹤 | **仍存在；原本未做** | `lib/aos7_tock.py:90`；`modules/tools/aos7_taskside.py:30`。相關測：`tests/core/test_tick_tock.py:30`。 | 任務自行記收到幾次，核心不追 ACK；慢 reporter 仍會漏回合。 |
| **N-05** 漏掉的回合可補回 | **因設計改變不適用；承諾撤回** | `spec.md:125`；`lib/aos7_tock.py:96`；`modules/history.py:73`。測：`modules/tests/test_modules_history.py:31`。 | 核心只留最新；history 也只記 gap，補不回內容。開啟 history 不等於原能力完整移植。 |
| **N-06** 只跑 N 回合就停 | **部分解** | `lib/aos7_daemon.py:128`、`:222`；`lib/aos7_daemon_timeline.py:260`。測：`tests/core/test_daemon.py:211`、`test_matrix_daemon.py:87`。 | K-02 可多跑；倒數只在記憶體，daemon 重開會丟。**R01、R07**。 |
| **N-07** 單調時間調度、不無界追趕 | **已解** | `lib/aos7_daemon_timeline.py:125`、`:217`。相關測：`tests/core/test_daemon.py:152`、`test_matrix_a3.py:387`。 | 使用 monotonic，逐回合前進。未見新版直接牆鐘跳動測例，不能把節拍測試當成該項實測。 |
| **N-08** 區分 pause 已要求／已停住 | **已解** | `lib/aos7_daemon.py:527`；`lib/aos7_daemon_timeline.py:210`。測：`tests/core/test_daemon.py:171`、`:199`。 | 有 phase、pause_pending、round_open；測試主要等 phase，未直接完整斷言 pending 轉換。 |
| **N-09** accepted／applied 與停機剩餘清單 | **部分解** | `lib/aos7_daemon.py:365`、`:501`；`lib/aos7_proc.py:225`。測：`tests/core/test_daemon.py:236`、`test_matrix_faults.py:63`。 | 回條仍只是接受；沒有 applied 階段、整棵 remaining PID 清單。stop-sweep 事件也不等於永久紀錄。 |
| **N-10** 控制送錯 daemon 應失敗 | **已解** | `lib/aos7_daemon.py:145`、`:164`。測：`tests/core/test_daemon.py:45`；`modules/subd/tests/test_subd_ownership.py:49`。 | 子根邊界拒收；尚不存在的 node 可預先 pause，是保留的合法用法。 |
| **N-11** 看檔案能分 daemon 死活 | **部分解** | `lib/aos7_daemon.py:534`、`:597`。測：`tests/core/test_daemon.py:236`、`:396`。 | 正常停止有 stopped；強殺或卡住都只呈現 at 停更，仍無法只靠檔案確診。 |
| **N-12** 世代、snapshot、範圍與 unknown | **部分解** | `lib/aos7_daemon.py:517`、`:534`；`modules/diag/aos7-diag:44`。測：`tests/core/test_daemon.py:378`；`modules/diag/tests/test_diag.py:53`。 | gen、三態有了；沒有跨檔 snapshot 序號、完整 orphan 盤點。uncertain 改由 diag 按需重算。 |
| **N-13** 錯誤有一致可定位入口 | **部分解** | `lib/aos7_fs.py:42`；`lib/aos7_tock.py:75`；`lib/aos7_tick.py:335`。測：`modules/diag/tests/test_diag.py:38`；`tests/core/test_tick_tock.py:90`。 | 常用錯誤已有位置；tasks_error、ctl、mount、last_error 仍分散，不是完整聚合入口。 |
| **N-14** 父層直接看下層 daemon 狀態 | **仍存在；原本未做** | `lib/aos7_daemon.py:514`；`modules/diag/aos7-diag:78`。相關測：`modules/subd/tests/test_subd_ownership.py:63`。 | 仍需另讀子根 status；subd 不提供 tree 聚合。 |
| **N-15** node 出生即停，不偷跑 | **已解；由操作順序組合** | `lib/aos7_daemon.py:211`、`:269`；`lib/aos7_daemon_timeline.py:210`。相關測：`tests/core/test_daemon.py:23`、`:171`。 | 先 pause 並等回條，再 register；不是 register 自帶原子 paused 選項，未見兩步整合專測。 |
| **N-16** ctl-done 不一直增加 | **部分解** | `lib/aos7_daemon.py:367`；`modules/tools/aos7_ctl.py:62`。測：`tests/core/test_daemon.py:285`、`:293`。 | 固定名字覆寫有效；持續換名字／by／owner 仍累積，無全域上限。 |
| **N-17** 負載下控制面仍可用 | **部分解** | `lib/aos7_daemon.py:302`、`:400`、`:510`。測：`tests/core/test_daemon.py:293`、`:324`。 | 有每圈控制處理預算；列舉排序、冷啟動、status 不全受它約束。舊每圈最多起 20 線已明文移除。 |
| **N-18** 舊動作不能倒寫新 daemon | **已解** | `lib/aos7_fs.py:259`、`:286`；`lib/aos7_daemon.py:579`。測：`tests/core/test_daemon.py:396`、`:415`、`:430`。 | 世代＋action lock 保留；無法驗證舊持鎖者時保守不殺，須人工恢復。 |
| **N-19** 請求不無痕消失 | **部分解** | `lib/aos7_tick.py:319`；`lib/aos7_mount.py:123`；`lib/aos7_task.py:241`；`lib/aos7_daemon.py:308`。測：`tests/core/test_once_threestate.py:68`、`test_daemon.py:324`。 | once／任務 ctl／加掛有交接；daemon 例外件改成刪請求、只留最新錯誤。跨 run 去重也縮限；另見 N-86。 |
| **N-20** 關回合中斷不漏、不重寫總結 | **已解於提交／重播範圍** | `lib/aos7_tock.py:60`、`:96`、`:139`。測：`tests/core/test_matrix_docs.py:121`、`test_daemon.py:370`。 | 同回合完整總結可重播收尾；K-02 是完成次數欠扣，不是本反例造成總結重寫。舊歷史與跨回合補通知不保證。 |
| **N-21** 壞任務隔離、壞設定能恢復 | **部分解；有遷移退步** | `lib/aos7_tick.py:138`、`:339`；`lib/aos7_daemon_timeline.py:68`。測：`tests/core/test_tick_tock.py:90`；舊精確案例 `P1/tests/test_astra5.py:334`。 | 一般隔離保留；巨大整數 interval 先 OverflowError，無法退回預設。**R04**。 |
| **N-22** 一般 I/O 故障受控 | **部分解** | `lib/aos7_fs.py:84`；`lib/aos7_daemon.py:408`、`:611`；`lib/aos7_daemon_timeline.py:133`。測：`tests/core/test_matrix_faults.py:359`、`:388`。 | 三態與退避已有；沒有整體降級／停止准入策略，初始化寫入也不都在運行中 guard 內。 |
| **N-23** 啟動恢復清單：回合、runner、tmp | **部分解** | `lib/aos7_daemon_timeline.py:190`；`lib/aos7_task.py:92`；`lib/aos7_fs.py:136`。測：`tests/core/test_daemon.py:396`、`test_matrix_misc.py:46`。 | 恢復動作有，無統一清單；完整但未 rename 的 runner exit tmp 仍會被清掉，結果變 lost。 |
| **N-24** 刪移 node 不建回鬼目錄 | **部分解；啟動中搬移保護撤回** | `lib/aos7_tick.py:221`；`lib/aos7_run.py:48`、`:102`；`notes/problems.md:196`。測：`tests/core/test_tick_tock.py:334`、`test_daemon.py:113`。 | fd 保護保留；晚期啟動的字串路徑使用不保，見 K-06。 |
| **N-25** 主 PID／taskdir 不在仍管得到程序 | **部分解** | `lib/aos7_proc.py:122`、`:176`、`:210`；`lib/aos7_task.py:189`。測：`tests/core/test_ctl.py:79`、`:102`、`:116`。 | 環境身分與後代群組有；持續盤點仍依槽，且官方 inst 有快照後出生窗口。**R02**。 |
| **N-26** node 消失／搬家收任務 | **已解於現行 node 定義** | `lib/aos7_daemon.py:403`、`:418`、`:446`。測：`tests/core/test_daemon.py:100`、`:113`、`:126`、`:136`。 | 不可見不當消失；missing 保留登記，新位置另 register。刪 timeline 已不等於刪 node。 |
| **N-27** 多層停機有總期限 | **仍存在；原本未做** | `lib/aos7_proc.py:176`；`lib/aos7_daemon.py:457`；`modules/subd/README.md:75`。相關測：`modules/subd/tests/test_subd_recover.py:128`。 | 重開前回收不等於停機即清空；父不再重開，前代任務可能一直留著。 |
| **N-28** keep 有正規停用方式 | **已解** | `lib/aos7_tick.py:150`、`:107`。測：`tests/core/test_tick_tock.py:152`、`:161`。 | `enabled:false` 保留項目及 state；exit 0／kill 本身不表示永久停用。 |
| **N-29** crash loop 退避／連敗可見 | **部分解** | `lib/aos7_tick.py:184`；`lib/aos7_task.py:163`。測：`tests/core/test_tick_tock.py:136`、`:278`。 | 有最新結束結果、槽不累積；沒有任務退避或連敗數。timeline backoff 處理的是動作失敗。 |
| **N-30** ended 說清任務與原因 | **已解；最低需求保留** | `lib/aos7_task.py:163`、`:174`。測：`tests/core/test_ctl.py:42`、`test_tick_tock.py:300`。 | `slot#run`、code、lost、by_ctl 可判讀；restart 現包成 kill，須另讀新 birth 才分清 restart 意圖。 |
| **N-31** 依新定義 reload | **部分解；有已記載退縮** | `modules/control/aos7_control.py:24`、`:71`；`lib/aos7_task.py:300`。測：`modules/control/tests/test_control.py:57`、`:69`、`:91`。 | 正常 reload 有；動態掛載第一次帶過後失去 dyn，第二次 reload 可能掉掛。**R09**。 |
| **N-32** pause 搶佔活任務 | **仍存在；已接受限制** | `lib/aos7_daemon.py:211`；`lib/aos7_daemon_timeline.py:209`；`spec.md:243`。相關測：`tests/core/test_daemon.py:171`。 | pause 只停新回合，活任務繼續；不是程序暫停或搶佔。 |
| **N-33** 多人安全修改 tasks.json | **已解；合作式** | `lib/aos7_fs.py:185`、`:205`；`lib/aos7_tick.py:313`。測：`tests/core/test_errors.py:36`；`modules/control/tests/test_control.py:180`。 | 共同 flock、原子換檔、壞表拒寫；不拿鎖的編輯仍不保。舊兩寫者各 100 次案例未見直接移入。 |
| **N-34** 批次任務一次交付 | **已解；改用批次 once** | `modules/tools/aos7_ctl.py:112`；`lib/aos7_tick.py:313`。測：`tests/core/test_tick_tock.py:192`。 | 原子發布表成立，不等於整批原子起動；後者是 N-85。 |
| **N-35** 有檔才起、每檔一次 | **部分解** | `packs/step/aos7_step.py:418`、`:478`、`:622`；`lib/aos7_tick.py:157`。測：`packs/step/tests/test_step.py:564`；`tests/core/test_tick_tock.py:174`。 | step 可 wait 指定檔再 run；glob 只是布林條件，沒有逐新檔認領與永久去重。 |
| **N-36** each 並行上限 | **已解** | `lib/aos7_task.py:33`；`lib/aos7_tick.py:134`、`:184`。測：`tests/core/test_tick_tock.py:119`、`:129`。 | max_live 由固定槽落實；不限制任務內 fork 的 OS 程序數。 |
| **N-37** 新 node 準備好的規則 | **已解；以登記取代出生檔** | `lib/aos7_daemon.py:174`、`:400`。測：`tests/core/test_daemon.py:23`、`:36`。 | 正確順序是準備完再 register。先登記缺席 node、再慢慢建內容，仍可能空跑。 |
| **N-38** 同名 node 重建有歷史世代 | **仍存在；原本未做** | `lib/aos7_daemon.py:418`、`:441`；`modules/history.py:69`。相關測：`tests/core/test_daemon.py:126`；`modules/tests/test_modules_history.py:31`。 | 無持久 epoch；history 會略過重建後未超過舊高水位的回合。**R10**。 |
| **N-39** tid／name 不誤解或碰撞 | **已解** | `lib/aos7_task.py:16`、`:294`；`lib/aos7_tick.py:68`。測：`tests/core/test_tick_tock.py:15`、`:81`、`:129`。 | 不再有損改名；name／slot／run 分開。多槽時 tid 仍不等於 name，要讀 birth。 |
| **N-40** 歷史目錄不使掃描越來越慢 | **已解；槽重用取代歸檔** | `lib/aos7_task.py:275`；`lib/aos7_tock.py:114`。測：`tests/core/test_tick_tock.py:278`、`:213`。 | 200 回合檔數測試有；不代表 out.log、開啟的事件 log 或任務自有資料有容量上限。 |
| **N-41** 每回合兩個 Python 程序成本 | **仍存在；使用者已接受** | `lib/aos7_daemon_timeline.py:37`、`:221`、`:257`；`spec.md:292`。相關測：`tests/core/test_daemon.py:152`。 | 架構保留；本次沒有新版吞吐量實測，不沿用舊數字當新結果。 |
| **N-42** 每任務 runner 太重 | **仍存在；原本未做** | `lib/aos7_task.py:316`；`lib/aos7_run.py:76`、`:89`。相關測：`tests/core/test_tick_tock.py:24`。 | 每個活 run 仍有等待中的 Python runner；無記憶體預算測試。 |
| **N-43** 大量起任務吃掉 interval | **仍存在；原本未做** | `lib/aos7_tick.py:339`；`lib/aos7_daemon_timeline.py:217`。相關測：`tests/core/test_tick_tock.py:15`、`:192`。 | 仍逐項建檔、掛載、Popen；小批功能測試沒有驗大量起動成本。 |
| **N-44** CPU／程序數／輸出容量上限 | **仍存在** | `lib/aos7_run.py:68`、`:76`；`spec.md:294`。相關測：`tests/core/test_tick_tock.py:129`。 | max_live 只是槽上限；budget 假 API 額度不是 OS CPU、fork 或 log bytes 限制。 |
| **N-45** 跨 daemon 控制端點可配置 | **部分解** | `lib/aos7_mount.py:35`、`:54`；`modules/tools/aos7_ctl.py:33`。相關測：`tests/core/test_ctl.py:182`、`:196`。 | 空間內跨 daemon 可掛；跨 root 匯入／re-export 仍無完整機制。直接寫外部絕對路徑不算掛載協定完成。 |
| **N-46** 路二起回 daemon、身分不隨路徑變 | **部分解** | `lib/aos7_daemon.py:49`、`:534`；`modules/tools/aos7_ctl.py:21`。相关測：`modules/subd/tests/test_subd_ownership.py:88`。 | realpath 修正別名拼法；仍無 start/restart daemon op、無搬家不變的 ID。 |
| **N-47** 子根標記避免父掃描搶 node | **因設計改變不適用** | `lib/aos7_daemon.py:400`、`:145`；`modules/subd/aos7-subd:53`、`:242`。測：`modules/subd/tests/test_subd_ownership.py:58`、`:106`。 | 父不掃描，原競態消失；顯式登記與 subd 認領仍有邊界保護。 |
| **N-48** 重掛失蹤目標不建鬼資料夾 | **仍存在；原本未做** | `lib/aos7_mount.py:43`、`:58`。測：`tests/core/test_ctl.py:182`，其中第 187 行正斷言缺席目標被建立。 | 搬走收件 node 後 restart 掛載者，仍可能重建舊 inbox，寄信成功卻無收件者。 |
| **N-49** audit 分清核心檔、外部寫入、runner | **部分解** | `modules/audit/audit_site/sitecustomize.py:95`、`:97`、`:135`；`modules/audit/aos7-audit:19`。測：`modules/audit/tests/test_audit_wrapper.py:20`、`:43`。 | root 外略過、未分類核心檔；audit 包住子 daemon 時 hook 仍可污染內層 runner 紀錄。後者舊版也有。 |
| **N-50** 父 node 自動管子時間線 | **仍存在；明確未採隱含權限** | `modules/audit/audit_site/sitecustomize.py:52`、`:62`、`:97`；`spec.md:239`。測：`modules/audit/tests/test_audit_wrapper.py:43`。 | 父須先掛載子 node；直接寫可生效但 audit 判越界，符合合作式限制。 |
| **N-51** 非 Python 任務等 tock、取回合 | **已解** | `bin/aos7-wait-tock:18`、`:28`；`modules/tools/aos7_taskside.py:30`。相關測：`tests/core/test_tick_tock.py:30`。 | helper 保留；未見新版直接 sh＋CLI 專測，仍是輪詢，不是事件通知。 |
| **N-52** tmp 不被當正式檔 | **已解** | `lib/aos7_fs.py:119`、`:136`；`lib/aos7_run.py:102`；`lib/aos7_mount.py:103`。測：`tests/core/test_matrix_misc.py:46`、`:65`。 | 點開頭＋rename＋讀者略過；另清死寫者 tmp。這不是對任意 glob 讀者的存取限制。 |
| **N-53** inst 預設輸出別丟掉 | **仍存在；原本未做** | `lib/aos7_run.py:17`；`lib/aos_exec_run.py:113`。相關測：`tests/core/test_tick_tock.py:314`。 | inst 不宣告 stdout 時仍到 `/dev/null`；現有測例明寫 inherit，不能證明預設已改。 |
| **N-54** 動作逾時、停機不被卡住 | **已解於動作範圍** | `lib/aos7_daemon_timeline.py:22`、`:28`、`:116`、`:255`。測：`tests/core/test_daemon.py:354`、`:361`、`:370`。 | tick／tock timeout、停機寬限及 incomplete 有；不等於 N-27 整棵停機總期限。 |
| **N-55** 測試先收程序再刪空間，含中斷 | **部分解；繼承舊缺口** | `tests/base.py:55`、`:89`；`tests/_proc.py:47`；`tests/run_all.py:52`。情境：`tests/core/test_tick_tock.py:278`。 | 正常 cleanup 有；純 tick 起的 runner 未 track，Ctrl-C 跳過 unittest cleanup 時可能殘留。**R11**。 |
| **N-56** JSON FIFO／非一般檔不堵塞 | **已解** | `lib/aos7_fs.py:84`；`lib/aos7_daemon.py:337`。測：`tests/core/test_errors.py:71`、`:88`；`test_daemon.py:306`。 | 非阻塞開檔並分類；生命週期檔 UNKNOWN，daemon 壞請求回 B。 |
| **N-57** 壞控制檔名／資料夾有回條 | **已解** | `lib/aos7_daemon.py:325`。測：`tests/core/test_daemon.py:306`。 | FIFO、dir.json、x.txt、壞 JSON、未知 op 有對應案例；同名只留最新。 |
| **N-58** 單 node 壞檔不拖垮 daemon | **已解** | `lib/aos7_daemon_timeline.py:160`、`:184`；`lib/aos7_daemon.py:611`。測：`tests/core/test_daemon.py:378`、`test_matrix_docs.py:39`。 | 壞 node 可停在 error，其他線不退出；不是保證壞 node 自動繼續。 |
| **N-59** 任務欄位驗證、毒丸不連坐 | **已解** | `lib/aos7_tick.py:66`、`:138`；`lib/aos7_run.py:71`。測：`tests/core/test_tick_tock.py:81`、`:90`；`modules/control/tests/test_control.py:69`。 | name、argv 型別有檢查；壞 once 可留表反覆報錯，但不拖垮其他項。部分舊精確型別案例未直接移入。 |
| **N-60** 壞 round 不重數／重號 | **已解；恢復方式改變** | `lib/aos7_tick.py:246`；`lib/aos7_daemon_timeline.py:184`。測：`tests/core/test_matrix_docs.py:39`、`:77`、`:87`。 | 壞內容停等人工修復；僅「不存在」可借 last-round 接號。沒有保留舊自動歷史恢復方式。 |
| **N-61** 重現／重開先補未關 tock | **已解於回合恢復** | `lib/aos7_daemon_timeline.py:190`；`lib/aos7_tock.py:139`。測：`tests/core/test_daemon.py:396`、`test_matrix_docs.py:121`。 | 未關回合先補；恢復後的倒數殘洞另見 K-02。刪 timeline 不再觸發 node 消失。 |
| **N-62** 負 interval 當壞值 | **部分解** | `lib/aos7_daemon_timeline.py:67`。相關測：`tests/core/test_errors.py:88`；舊直接案例 `P1/tests/test_wave2.py:93`。 | 一般負值回預設；巨大負整數會先在 `math.isfinite` 溢位，與 N-21 同缺口。**R04**。 |
| **N-63** pid.json 不能導致誤殺別人 | **部分解；保留基本防護** | `lib/aos7_proc.py:158`、`:210`、`:235`。測：`tests/core/test_ctl.py:88`。 | 單槽 kill 會驗群組身分；node 清場仍使用 cached pgid。惡意改核心檔／脫離身分已明列範圍外。 |
| **N-64** 一次性任務遵守槽／max_live | **已解；統一挑槽入口** | `lib/aos7_tick.py:126`、`:174`、`:184`。測：`tests/core/test_tick_tock.py:129`、`:145`、`:199`。 | spawn 目錄取消；once 和常駐項共用 free／used 判定。busy once 留表等候，不再直接丟棄。 |
| **N-65** 正規「做一次」寫法 | **已解於介面** | `spec.md:137`；`lib/aos7_tick.py:157`。測：`tests/core/test_tick_tock.py:174`、`:192`。 | `mode:once` 正式存在；不代表直到成功，也不消除 N-86 的組合缺口。 |
| **N-66** 子根範圍、路徑、稽核清楚 | **部分解；兩項遷移退步** | `modules/subd/aos7-subd:53`、`:295`；`lib/aos7_run.py:24`；`modules/audit/audit_site/sitecustomize.py:27`。測：`modules/subd/tests/test_subd_ownership.py:106`、`:129`。 | 一層位置檢查有；巢狀 SUBROOT 先展成上一層，合法子根寫入也可能 audit false。**R05、R06**。 |
| **N-67** stop 帶 node 要拒絕 | **已解** | `lib/aos7_daemon.py:275`。測：`tests/core/test_daemon.py:236`。 | 回失敗並指向 pause／unregister。 |
| **N-68** 看得出「正常但尚未開始」 | **已解；靠現有欄位組合** | `lib/aos7_daemon.py:575`、`:526`；`lib/aos7_daemon_timeline.py:105`、`:151`。相關測：`modules/tools/tests/test_tools_ctl.py:35`、`tests/core/test_matrix_docs.py:87`。 | 沒有 started 欄，但 round 0、round_open、phase、空 paused 表可判讀；未見完整專項斷言。 |
| **N-69** last_error 分得出新舊 | **部分解** | `lib/aos7_daemon_timeline.py:111`；`lib/aos7_daemon.py:529`。相關測：`modules/diag/tests/test_diag.py:38`。 | 有 round／at；沒有 last_ok_round 或 resolved，成功後仍留舊錯。 |
| **N-70** 逾時指出卡在哪 | **部分解** | `lib/aos7_daemon_timeline.py:45`、`:299`；`lib/aos7_fs.py:91`。測：`tests/core/test_daemon.py:354`、`:430`。 | FIFO、持鎖者原因可見；一般 timeout 仍無 wchan 或更細阻塞階段。 |
| **N-71** status 直接看到反覆任務失敗 | **仍存在；原本未做** | `lib/aos7_daemon.py:510`；`lib/aos7_tock.py:78`。相關測：`tests/core/test_tick_tock.py:136`。 | 沒有 last_task_fail／連敗數；須自行取樣 last-round 與 out.log。 |
| **N-72** 結束結果能撐過一次 LLM 思考 | **仍存在；保留政策已明確縮減** | `lib/aos7_task.py:275`；`lib/aos7_tock.py:114`；`spec.md:205`。測：`tests/core/test_tick_tock.py:58`、`:213`、`:225`。 | 無時間下限，once 報完再一回合可整槽刪；keep 新 run 覆寫。交付物須放槽外，不能說原使用痛點已消失。 |
| **N-73** 停著 daemon 的控制檔怎麼辦 | **已解；保留原選擇** | `spec.md:73`；`lib/aos7_daemon.py:582`。測：`tests/core/test_daemon.py:61`。 | 保留到下次啟動處理，沒有過期機制；舊 stop 也可能影響新啟動。 |
| **N-74** 別人改 daemon 專屬檔要報錯 | **因設計改變不適用；明列誤用** | `spec.md:281`；`lib/aos7_daemon.py:94`、`:101`、`:124`。相關測：`tests/core/test_daemon.py:171`。 | 不保證偵測手改 status／paused／gen；運行中修改 paused.json 不等於正式 resume。 |
| **N-75** 子 daemon stop 不被父 keep 抵銷 | **已解；需 subd 包** | `lib/aos7_daemon.py:280`；`modules/subd/aos7-subd:141`、`:179`、`:227`。測：`modules/subd/tests/test_subd_ownership.py:71`；`test_subd_recover.py:295`。 | 允許 stop 後留 stopped，擋子 daemon 重起；父 keep 仍可起失敗的 wrapper。直接繞包與三層起動問題另見 K-08、N-66。 |
| **N-76** 整檔讀工具能看最新摘要 | **已解** | `lib/aos7_tock.py:90`；`lib/aos7_daemon.py:534`。測：`tests/core/test_tick_tock.py:278`。 | 固定 last-round／last_event 已補；檔案大小隨任務數，不是固定 bytes。 |
| **N-77** 可信請求人身分／付費硬限制 | **仍存在；舊已裁定合作式** | `spec.md:290`；`packs/budget/aos7_budget.py:129`；`packs/budget/spec.md:96`。測：`packs/budget/tests/test_budget_ledger.py:33`。 | holder／環境身分仍可自報；budget 不是身分驗證層。不是新版遺忘，也不應誤列為本輪新增安全要求。 |
| **N-78** 換服務後收完舊服務在途請求 | **仍存在；原本未做** | `modules/control/aos7_control.py:24`；`lib/aos7_task.py:275`；`spec.md:186`。相關測：`modules/control/tests/test_control.py:57`、`:91`。 | 無自動 drain／保留舊目標至結清；仍須 model-prev、checkpoint 等上層協定。**R09**。 |
| **N-79** keep 共用准入、延後、停用、重啟政策 | **部分解** | `lib/aos7_tick.py:50`、`:150`、`:184`；`spec.md:294`。測：`tests/core/test_tick_tock.py:152`、`:161`、`:136`。 | from_round、enabled 有；always／on-failure／never 尚無。排程欄與已 launch once 的交互另見 N-86。 |
| **N-80** 看得出 tick 使用哪版 tasks | **已解於版本可見性** | `lib/aos7_tick.py:25`、`:313`、`:333`；`lib/aos7_tock.py:93`。測：`tests/core/test_tick_tock.py:15`。 | 雜湊是讀入快照，不是 tick 改表後的版本；不是取消在途起動的屏障。雜湊另一次讀取失敗可為 null，現測試僅驗非空／一致。 |
| **N-81** pause 帶 owner、各解各的 | **已解；合作式 owner** | `lib/aos7_daemon.py:94`、`:211`、`:222`；`modules/tools/aos7_ctl.py:62`。測：`tests/core/test_daemon.py:171`、`:188`；`test_matrix_daemon.py:87`。 | owner 清單持久化；all 才全清。不帶 owner 共用空字串，owner 不是權限驗證。rounds 故障不推翻 owner 隔離本身。 |
| **N-82** pause 中只做任務控制 | **仍存在；明確延期** | `lib/aos7_daemon_timeline.py:209`；`lib/aos7_tick.py:292`；`lib/aos7_tock.py:66`；`spec.md:243`、`:294`。 | task kill 仍等 tick／tock；未見 pause＋單槽維護專測。resume 一回合也會起其他工作。 |
| **N-83** 事件監看、idle_safe、wake reason | **仍存在；明確延期** | `lib/aos7_daemon_timeline.py:59`；`lib/aos7_daemon.py:510`；`spec.md:294`。相關測：`tests/core/test_daemon.py:223`。 | 顯式 wake 已有，自動目錄監看沒有；沒有 watcher 包接手。 |
| **N-84** resume 打斷上一 interval 睡眠 | **已解** | `lib/aos7_daemon.py:228`、`:242`、`:262`；`lib/aos7_daemon_timeline.py:125`。測：`tests/core/test_daemon.py:199`、`test_matrix_daemon.py:139`。 | 最後一個 hold 消失才 kick；既有 resume 測試未直接重現 early＋idle 尚有長睡眠的舊反例。 |
| **N-85** 批次全有全無准入 | **仍存在；明確延期** | `modules/tools/aos7_ctl.py:112`；`lib/aos7_tick.py:137`、`:174`、`:339`；`spec.md:294`。測：`tests/core/test_tick_tock.py:90`、`:192`、`:199`。 | 一次改表是原子交付，起動仍逐項；壞項／忙槽可造成部分成組。 |
| **N-86** tick 中斷後不重起已起項 | **部分解** | `lib/aos7_tick.py:150`、`:165`、`:171`、`:319`。測：`tests/core/test_once_threestate.py:86`；`test_matrix_once.py:42`、`:68`。 | 原批次案例已修；已 launch once 改排程後，同名 keep 可覆寫唯一完成證據，導致原 once 再跑。**R03**。 |

## 主要缺口的重現思路

以下是後續在可丟棄環境中驗證的設計，**本次沒有執行，也沒有建立重現腳本**。舊探針使用 proto7-1 協定，不能直接換 bin 路徑就當新版驗證；須同步改 register、固定槽、`slot#run`、once 與控制包介面。

### R01：K-02／N-06，回合已關但確認失敗，倒數漏扣

先 pause，再送 `resume rounds=1`。讓第一回合 tock 正常提交總結並寫成 CLOSED，只對 daemon 的最後確認讀取注入一次 EIO：

1. [timeline](../../../lib/aos7_daemon_timeline.py):258 可以正常讀到 False。
2. [](../../../lib/aos7_daemon_timeline.py):260 那次讀取回 UNKNOWN／None，設 `owe_done=True`。
3. 下一圈 [](../../../lib/aos7_daemon_timeline.py):184 恢復讀到 CLOSED，因此不進 OPEN 恢復分支。
4. 唯一補扣位置 [](../../../lib/aos7_daemon_timeline.py):204 被跳過，owner 尚未 pause，直接開第二回合。
5. 第二回合正常完成才扣到零；`owe_done` 還可能遺留，影響後來另一組倒數。

應檢查：第一回合已完整提交，卻在第二回合才 pause；不是把故障打到 tock，造成第一回合真的未關。

現有 [正常 rounds 測試](../../../tests/core/test_daemon.py):211與[未知回合測試](../../../tests/core/test_daemon.py):378分別驗兩側，沒有驗這個交接。舊 `P1/notes/play/2026-10-03-astra-8-infra-evidence/boundaries.py` 的 `error_rounds` 可作基底，但它主要測 OPEN 恢復。

### R02：K-04／N-25，官方 inst 在清場快照後出生

用合法 keep＋inst；inst 的程式是長睡眠，保留預設環境。讓 runner 在起了 `aos-exec`、尚未寫 pid.json 的 [runner-before-pid](../../../lib/aos7_run.py):85 點死亡。

固定以下順序：

1. 暫停官方 aos-exec，使它尚未執行子程序 Popen；例如利用合法 stdin FIFO 等待，或只在驗證副本加 barrier。
2. 讓 lost 恢復走到 [群組及後代快照](../../../lib/aos7_proc.py):183完成。
3. 在送 TERM 前放行 aos-exec，使它經[官方 `start_new_session=True`](../../../lib/aos_exec_run.py):130起出 inst 子程序。
4. 清場只向先前固定的 `allg` 送訊號；存活檢查也只查這些群組。
5. 舊群組消失後可回 clean，[resolve](../../../lib/aos7_task.py):134發布 lost，keep 起下一代。

应檢查：舊 run 的 inst 子程序與新 run 同時存活；舊程序的 NODE／TID／RUN 仍完整，沒有換 uid、清環境或自訂逃逸邏輯。

[現有 inst kill 測試](../../../tests/core/test_ctl.py):102先等至少兩個群組存在才 kill，只證明「快照前已出生」的情況。這個反例使用內建 inst 路徑，不能直接套用「任務自行改 pgid 屬誤用」排除。

### R03：N-86，已執行 once 的排程變更，使它再次執行

初始表使用合法的同名 once＋keep：

```json
{
  "tasks": [
    {
      "name": "w",
      "mode": "once",
      "argv": ["sh", "-c", "echo once >> \"$AOS7_NODE/effects.log\""]
    },
    {
      "name": "w",
      "mode": "keep",
      "argv": ["true"]
    }
  ]
}
```

重現順序：

1. 第一回合在[before-once-delete](../../../lib/aos7_tick.py):351殺 tick。等待 once 已追加一行、run 1 已結束，再恢復 tock。表內仍有 `launch.run=1`。
2. 合作式拿鎖修改表，**只把該 once 的 `from_round` 改為 3**；不改 launch、不新增項目、不重送 restart。
3. 第二回合，[排程門檻](../../../lib/aos7_tick.py):150先略過 once，同名 keep 重用槽，birth 改為 run 2。
4. 第三回合到達 from_round，原 launch 的 run 1 不等於目前 birth 的 run 2；[](../../../lib/aos7_tick.py):171將它誤認為「上次尚未寫 birth」，再起 once run 3。

應檢查：`effects.log` 從一行變兩行，而操作過程始終保留同一個 once 及 launch。`enabled=false → keep 重用 → enabled=true` 也是同型反例。

現行 [spec](../../../spec.md):144只禁止他人修改 launch，沒有禁止修改帶 launch 項的排程欄。現有矩陣的[once 案](../../../tests/core/test_matrix_once.py):42是單一 once，[keep 陪伴案](../../../tests/core/test_matrix_once.py):68使用不同名字，沒有覆蓋此組合。

### R04：N-21／N-62，巨大整數 interval 卡住 node

把 timeline 的 `interval_ms` 寫成合法 JSON 整數，值為 `10**309`；此處是數值說明，JSON 內須寫完整數字，不能寫 Python 算式。負 `-10**309` 也成立，且明確是不合法 interval。

[read_config](../../../lib/aos7_daemon_timeline.py):68先呼叫 `math.isfinite`，整數转浮點時即溢位，無法進入「預設 1000 ms 並記錯」分支。外層 [](../../../lib/aos7_daemon_timeline.py):167雖接住例外，下一次仍讀到同值，該 node 持續 error，不開回合。

應檢查：其他 node 繼續；壞設定 node 不採預設；改回正常值後恢復。

這是有舊防護及精確測例的退步：[舊 timeline](../../../../proto7-1/lib/aos7_daemon_timeline.py):115、[舊 test_astra5](../../../../proto7-1/tests/test_astra5.py):334。

### R05：N-66，README 的三層 subd 用法指回上一層

建立三層：

- D0 的 root 是 `R`，node `a` 經 subd 起 D1，子根 `S1=R/a/sub`。
- D1 的 node `n1` 再經 subd 起 D2，子根應是 `S2=S1/n1/sub`。
- 兩層都使用 [subd README 的 shell BOOT 寫法](../../../modules/subd/README.md):29，並把 wrapper 路徑寫成正確絕對路徑。

第一層 wrapper 設定 `AOS7_SUBROOT=S1`。D1、tick、下一個 runner 都保留該值。第二層 runner 在新 wrapper 執行前，已由 [expand](../../../lib/aos7_run.py):24把 shell 字串中的 `$AOS7_SUBROOT` 換成字面 S1。

第二個 wrapper 雖在 [](../../../modules/subd/aos7-subd):295設定 S2，命令字串仍指 S1，於是向 D1 註冊並企圖再起 D1，撞現役 daemon.lock；D2 沒起來。

這是遷移退步：[舊 task](../../../../proto7-1/lib/aos7_task.py):700原本先清繼承 SUBROOT／OWNER，再依本次 subroot 設定。新測試只涵蓋一層 subd；部分回收探針的「巢狀」只是手造深路徑身分程序，沒有經過第二次 runner＋BOOT。

### R06：N-66，audit＋subd 把合法子根寫入記成越界

在 node `lab` 使用以下合法項目；`<P>` 換成 proto7-2 絕對路徑，不加額外 mounts：

```json
{
  "name": "sub",
  "mode": "keep",
  "argv": [
    "python3", "<P>/modules/audit/aos7-audit", "--",
    "python3", "<P>/modules/subd/aos7-subd", "lab/sub", "--",
    "sh", "-c", "exec aos7-daemon \"$AOS7_SUBROOT\""
  ]
}
```

应檢查父槽 `lab/.aos/tasks/sub/writes.jsonl`：子 daemon 寫自己 `.aosd` 的紀錄會被判 `ok:false`。

原因是新 audit [只從 mounts 收允許目標](../../../modules/audit/audit_site/sitecustomize.py):27，又[排除巢狀 daemon 根](../../../modules/audit/audit_site/sitecustomize.py):62。subd 傳入子程序的 ROOT／NODE／TASK 仍是父任務，新增的 SUBROOT 沒有被 audit 納入範圍。

舊版不只有程式，還有整合測試：[舊 hook](../../../../proto7-1/lib/audit_site/sitecustomize.py):39、[舊 test_wave2](../../../../proto7-1/tests/test_wave2.py):168。新版 [audit 測試](../../../modules/audit/tests/test_audit_wrapper.py):20沒有這個組合。

另外，audit 環境沿 child daemon 傳入後續 runner，會混入內層 runner 的 pid／exit 寫入；這件事**舊版也存在**，應列 N-49 的繼承缺口，與本項新增誤報分開。

### R07：N-06，daemon 重開遺失剩餘回合數

先 pause，再 resume 若干回合；確認請求已接受、owner hold 已拿掉，但倒數尚未耗完時 SIGKILL daemon，再啟動同一 root。

[steps](../../../lib/aos7_daemon.py):65初始化為空；[resume](../../../lib/aos7_daemon.py):237只將倒數放在記憶體；[落盤](../../../lib/aos7_daemon.py):94只有 paused owners；[復載](../../../lib/aos7_daemon.py):101不還原 steps。

應檢查：新 daemon 看到沒人 pause，也沒有剩餘上限，繼續跑。這是現行復原限制，未見跨 daemon 重開的 rounds 測試；本報告不將它斷言為新版才引入。

### R08：K-07，上層累計的驗收仍未完成

不能直接把舊 cap 探針換路徑：新版沒有對應 kernel。舊基底在 `P1/notes/play/2026-10-03-astra-8-infra-evidence/followup.py` 的 `cap`。

現有證據分成三層：

- 核心同槽換 run 會保留任務自有 state，測試在 [test_tick_tock](../../../tests/core/test_tick_tock.py):58。
- 名字退役後仍會整槽刪掉，所以累計不能只留被觀測槽內。
- 新 budget 有槽外帳與[刪除 once 槽後仍能結算的測試](../../../packs/budget/tests/test_budget_step.py):180，但不等於原 token kernel 已移植。

而且文件尚有舊方案殘留：[changes-from-7-1](../../changes-from-7-1.md):29仍寫單槽跨 run 累加；[最新設計](../../problems.md):397改為每個 `slot#run` 的已見最大值相加，並明說 kernel 尚未做、總數只是已觀測用量下界。

### R09：N-31／N-78，第二次 reload 與舊服務在途工作

先動態掛載 `model-prev` 或 `z`，再 restart／reload 一次，確認新 run 可看到它。之後再 reload，且新 tasks 宣告不含該掛載。

[控制包](../../../modules/control/aos7_control.py):18只保留仍標 dyn 的掛載；新 birth 把第一次帶來的掛載當宣告，不保留 dyn。第二次就可能消失。[README](../../../modules/control/README.md):48已承認此限制；[現有測試](../../../modules/control/tests/test_control.py):91只驗第一次帶過。

再加一筆尚未回覆的舊服務請求，可驗 N-78：新版沒有自動保留旧服務到請求結清的協定。舊探針基底是 `P1/probes/namespace/probe.py:139`。

### R10：N-38，同名 node 重建後 history 靜默略過

讓獨立 logger 記來源 node 至第 100 回合；logger 本身保留。刪除並重建來源同名 node，使來源從第 1 回合重新開始。

[history](../../../modules/history.py):69只以 node id 記 seen，`round <= prev` 直接略過。應檢查：新來源第 1～100 回合都沒記，第 101 回合接到舊歷史後，沒有 reset／epoch 分界。

[現有 history 測試](../../../modules/tests/test_modules_history.py):31只驗遞增與向前跳號。adapt 的 round 倒退偵測沒有接入 history，也不是持久 epoch；觀測者停住期間來源重建且追過舊高水位時，單靠數值比較仍分不出。

### R11：N-55，Ctrl-C 跳過純 tick 測試的清場

以 [200 回合測試](../../../tests/core/test_tick_tock.py):278為基底，在常駐 k／runner 已起、迴圈尚未完成時 Ctrl-C。

應檢查：暫存根是否已刪，但獨立 session 的 runner／任務仍活著。

[base 的空間掃描清場](../../../tests/base.py):89只登記為 unittest cleanup；KeyboardInterrupt 可跳過它。[atexit fallback](../../../tests/_proc.py):47只收 `_proc.track` 清單，而純 tick 啟動的 runner 不在其中。

舊 [test_core](../../../../proto7-1/tests/test_core.py):55也是相同結構，故是原有「含中斷都安全」承諾尚未完整落實，不是本次遷移退步。

## 其他未解項目的驗證思路

下列較多屬原本未做或明確接受的限制；驗證目的在確認代價，不代表應一律加入核心。

- **N-79／N-29／N-71：重啟政策。** keep 工作使用 `false`，或正常 exit 0；觀察下一回合仍重起、status 無連敗数。對照 `lib/aos7_tick.py:184`、`lib/aos7_daemon.py:510`。舊基底：`P1/probes/supervisor/probe.py`、`P1/probes/lifecycle/probe.py:162`。
- **N-32／N-82：pause 中維護。** keep 長任務活著，等 phase paused 後送帶目前 run 的 kill。它會留待 resume；resume 一回合也會執行其他 eligible 任務。對照 `lib/aos7_daemon_timeline.py:209`、`lib/aos7_tick.py:292`。舊基底：`P1/probes/holds/probe.py`。
- **N-83／N-35：事件准入。** pause 閒置 node 後往 inbox 放信，不送控制檔，應不會自動醒；step 的 exists/glob 也不提供逐檔認領。對照 `lib/aos7_daemon_timeline.py:59`、`packs/step/aos7_step.py:418`。舊基底：`P1/probes/tickless/probe.py`。
- **N-85：全有全無。** 一次加 a／b／judge 三個 once，讓 judge.argv 不合，或它的槽正忙；a／b 仍可先起。對照 `lib/aos7_tick.py:137`、`:174`。舊 `P1/probes/gang/probe.py` 的 prepare／commit 可作應用層對照。
- **N-04／N-05／N-72：通知與結果留存。** 讓 reporter／history 慢數回合；另讓 once 結束後等待超過一回合才讀槽。前者只看到最新或 gap，後者槽可能已刪。對照 `modules/tools/aos7_taskside.py:30`、`modules/history.py:73`、`lib/aos7_tock.py:114`。舊基底：`P1/probes/longrun/probe.py`。
- **N-09／N-14／N-27／N-46：整樹生命週期。** 建三層 daemon、各層放多個慢收尾任務，停父且不再起 subd；逐層讀 status、盤點程序，不能只看父 live。為避開 R05，可用明確子根路徑建測試。對照 `modules/subd/README.md:75`、`lib/aos7_daemon.py:514`。舊基底：`P1/probes/nest3/probe.py`、`P1/probes/multid/probe.py`。
- **N-16／N-17：控制面容量。** 持續用新檔名送控制，並預登記大量 node 後冷啟動；量首份 status、stop 回條及累積回條數。對照 `lib/aos7_daemon.py:302`、`:400`。現有 3000 件有限批次測試不能證明持續洪水公平性。舊基底：`P1/probes/fleet/probe.py`、`P1/probes/sched/probe.py`。
- **N-41／N-42／N-43／N-44：執行成本與配額。** 分別增加空 node、長命 keep、單回合大量 once，再放 CPU 忙迴圈或持續輸出任務；量程序數、RSS、tick elapsed、out.log bytes。對照 `lib/aos7_daemon_timeline.py:37`、`lib/aos7_task.py:316`、`lib/aos7_tick.py:339`、`lib/aos7_run.py:68`。舊基底：`P1/probes/fleet/probe.py`、`P1/probes/swarm/probe.py`。
- **N-19／N-22／N-23：失敗後還剩哪些證據。** 連續讓兩件 daemon 回條寫失敗，觀察第一件只剩的 last_ctl_error 被後件蓋過；另在 runner exit tmp 完成、rename 前中斷，確認後續只報 lost。對照 `lib/aos7_daemon.py:308`、`lib/aos7_run.py:102`、`lib/aos7_fs.py:136`。
- **N-45／N-48：掛載與搬移。** 分別將掛載指向另一個 root，以及把原收件 node 搬走後 restart 掛載者；前者被 realpath 邊界拒絕，後者可能重建舊 inbox。對照 `lib/aos7_mount.py:35`、`:43`。舊基底：`P1/probes/multid/probe.py`、`P1/probes/rename/probe.py:107`。
- **N-49／N-50／N-77：合作式範圍。** audit 任務寫自己的核心檔、root 外檔、未掛載子 node；另以自報 holder 提交 budget 請求。對照 `modules/audit/audit_site/sitecustomize.py:95`、`:97`、`packs/budget/aos7_budget.py:129`。這些檢查現有契約，不把合作式系統誤當身分隔離。
- **N-53：inst 輸出。** inst 只寫 argv 執行 echo，不宣告 stdout；與 stdout inherit 對照，檢查 out.log。證據：`lib/aos_exec_run.py:113`；舊基底 `P1/probes/polyglot/probe.py:184`。
- **N-02／N-11／N-12／N-13／N-69／N-70：觀測完整性。** 回合中改 interval、讓 daemon 停更、修復一次動作錯誤，再逐份比較 status／round／last-round／ctl。可確認有效值與檔案設定延遲、跨檔無共同 snapshot、舊 last_error 不清、一般 timeout 無阻塞位置。主要入口為 `lib/aos7_daemon.py:510`、`lib/aos7_daemon_timeline.py:59`、`:111`、`:299`。

## 驗收證據目前缺在哪裡

现有測試的強項是單點故障與正常恢復；本次找到的主要殘洞集中在**兩項已存在機制交接的地方**：

- 已關回合＋最後觀測 UNKNOWN＋rounds 倒數。
- lost 清場＋官方 inst 尚在啟動。
- once 中斷＋合法排程變更＋同名 keep 重用槽。
- subd 拆包＋runner 提前展開環境。
- audit 拆包＋子根所有權。
- node 同名重建＋history 高水位。
- 純 tick 啟動＋KeyboardInterrupt＋測試暫存目錄回收。

這些組合不能由「各自已有測試」推導成已驗收。

最後，**程序 SIGKILL 恢復與斷電持久性是不同範圍**：核心原子寫主要是 close＋rename，沒有 fsync；[組件契約](../../component-contracts.md):51也明確排除斷電後的持久化順序。本報告的「已解」不延伸到斷電保證，也沒有把 README 記載的歷史測試結果當成本次通過紀錄。