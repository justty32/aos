# proto7-2 第一輪基礎設施測試：新設計的可靠性與故障注入

日期：2026-10-04。任務原文：[task.md](2026-10-04-astra-1-infra-evidence/task.md)。本輪只新增此報告及同名 evidence 目錄，未修改產品程式、規格或既有測試；沒有呼叫模型服務。

## 摘要

**新設計確實減少了正常運作的歷史負擔，但還不能判為穩定；剩下仍有生命週期的結構性缺口。** 登記、固定／提前 tock、單一任務表、槽重用、可選歷史都已做出實際行為。歷史關／開各跑到 500 回合，固定工作集合的 `.aos` 分別一直是 39／44 檔，`.aosd` 都是 8 檔。八個 once SIGKILL 邊界符合已揭露的 P2-02：birth 後尚未起 runner 的窗口零次執行但報 lost，其餘各執行一次。

最需要先修的是：`/proc` 讀取失敗可誤殺或 keep 雙開；round 半寫／缺欄位仍被當已關；birth 半寫可使已執行的 once 再跑一次；一次 restart 在提交中斷後可排入兩次重起。這些直接影響「確知才動作」與不重複執行。另有 node 符號連結繞過登記邊界、多 owner 的 rounds 倒數互相覆蓋、故障後暫存檔累積等問題。

既有測試 **103 項，102 通過、1 失敗**，耗時 53.122 秒。失敗是深路徑使 `last_error` 截尾丟掉 `stale-holder-unverified`，不是錯殺持鎖者；新增實測證明持鎖者仍活、`last_event` 有完整原因。另跑 16 項既有定向測試全過，與 103 項重疊，**不把它們加總成 119 個不同測試**。[完整結果](2026-10-04-astra-1-infra-evidence/regression.json)、[定向結果](2026-10-04-astra-1-infra-evidence/slots-targeted.json)。

## 方法、證據與判定界線

共四條工作線，皆在副本內隔離。新增測試包含 20 個 once／三態案例、11 個 daemon 探針、10 個文件操作案例及 2 個控制中斷／碰撞案例、兩次 500 回合長跑，以及容量／歷史／掛載補測。證據只保留腳本及精簡結果，不保留長跑空間或輸出日誌。

- **真程序／真訊號**：once 八個位置與 restart／原子提交窗口使用真正 SIGKILL；以任務副作用及實際 PID 是否存活交叉核對，沒有用假的成功回傳代替程序出生。
- **明確注入**：EIO／ESTALE 用執行時 monkeypatch 注入 open、listdir、stat；權限另有 uid 1000 的真 chmod EACCES。沒有修改系統 `/proc` 或產品原始碼。
- **狀態機整合與完整 daemon 分開**：`once-results.json/timeline` 執行真正 `Timeline._loop` 與 tick／tock，daemon 控制器用最小 stub；正常時間線、pause、重開、搬移、符號連結、長跑則使用真正 daemon。
- **kernel 未實作**：§8 只做設計反例與真槽刪建，不把用量模型模擬說成 kernel 程式測試。
- **成立＝本輪明列範圍成立**，不代表窮盡所有排程。固定八點每點一次，不能據此主張數學上的 exactly-once；不涵蓋斷電、磁碟持久化或故意改身分逃逸。

主要證據縮寫：**O**＝[once-results.json](2026-10-04-astra-1-infra-evidence/once-results.json)、**D**＝[daemon-probes.json](2026-10-04-astra-1-infra-evidence/daemon-probes.json)、**U**＝[docs-and-crashes.json](2026-10-04-astra-1-infra-evidence/docs-and-crashes.json)、**R**＝[regression.json](2026-10-04-astra-1-infra-evidence/regression.json)。表中反引號是 JSON key 或測試方法名稱，可直接搜尋。

## 一、承諾實測表

| 承諾 | 判定 | 證據與限制 |
|---|---|---|
| register／unregister、nodes.json 重開有效；不掃描 | **成立** | R 登記／取消／重開相關測試通過；U/D01 未登記 node 不起，register 後即使無 timeline.json 也跑、預設 1000ms。D/pause_owners 重開沿用 nodes 與 pause。 |
| node 刪掉／搬走／換成符號連結 → missing | **部分** | R 的刪除、搬移、換 inode 原案通過。D/symlink_same_inode：原址改成連回搬走目錄的 symlink，仍由 r2 跑至 r5、原 PID 活；symlink_outside_root 更在 daemon root 外的目標建立 `.aos/round.json`。目標仍在本副本的 evidence 暫存內。A2-04。 |
| node EACCES／EIO／ESTALE 不當消失 | **成立，診斷略有缺口** | D/stat_io_fault_injection 三種 errno 均保留時間線、沒有 missing／reaping；actual_eacces 真權限失敗時 PID 活，恢復後相同 PID 跑到 r4。但當下 status.live 可為空，不能單看空清單推定任務已死。 |
| early_tock=false 固定 interval | **成立** | D/timing_modes 設 1800ms，tick_at→tock_at 1.809 秒，early=false；短任務完成不提早。這是含程序開銷的近似節拍，不是精準牆鐘週期。 |
| early_tock=true 任務完成可提前 | **成立** | 同案 48ms 收回合、early=true；之後仍等 interval，直到 wake。 |
| wake 兩模式（P2-01） | **部分** | fixed 中途 wake 不改首回合；early idle 時 wake 到下一 tick 108ms。early 回合中 wake 卻留下 kick，2500ms 設定下 768ms 就進下一 tick，省掉其後 idle，與「回合中照舊」未完整一致。A2-11。 |
| once 純 SIGKILL 不重複、或誠實報 lost | **成立，限 P2-02 的 at-most-once** | O/once_boundaries 八點全退出 -9；詳下表。after-birth 沒跑但報 lost，不能稱「不漏起」。 |
| once 遇 birth 半寫仍不重複 | **不成立** | O/once_corrupt_birth：成功副作用 `[1]`、launch 未刪，birth 半寫後再起 run2，副作用變 `[1,2]`，且 run1 沒進 ended。這是複合故障，與純 SIGKILL 八點分開。A2-03。 |
| 槽檔數／bytes 不隨回合累積 | **部分** | 正常 500 回合檔數穩定，bytes 為小幅變動；有聲任務 out.log 仍無界，反覆 SIGKILL 留 dot tmp。詳容量表；A2-07。 |
| 歷史可選，核心只留上一回合 | **成立；module 有邊界問題** | 關閉無 history；開啟後多一個普通 keep 槽，500 回合後 node 歷史依 max-lines=50 留 r451～500，核心仍只有 last-round。事件歷史沒套用上限、通知先於總結造成最後回合漏取樣，A2-10／12。 |
| starttime 讀不到保守處理 | **部分** | O/three_state.starttime_none：helper 回 None 時 live＋unsure，不起新 run，恢復後正常；公開 errors／skipped 卻沒有原因。直接 `/proc/PID/stat` EIO 的更低層路徑會誤判 dead，A2-01／08。 |
| birth.json 讀不到、壞／半寫 | **部分** | I/O 時 UNKNOWN、不重起，恢復正常；半寫但真程序可見時 `o#?`、不雙開。程序不可見或已結束時被當 EMPTY，可雙開或 once 重跑，A2-01／03。 |
| round.json 讀不到、last-round.json 壞 | **部分** | EIO 阻止 tick／關回合、恢復後收原回合；只壞 last-round 且 round 健康可重建。兩份皆壞會要求人工，不會自行猜。可是 round 半寫／缺 open 被當關閉，A2-02。 |
| `/proc` 讀不到不做破壞性動作、恢復自動回正 | **不成立** | O/proc_stat_eio 誤殺健康 run1；proc_all_eio 誤報 lost、兩個真 PID 同活；解除注入後舊 run 仍活，不會自動回正。A2-01。 |
| 不變條件一：確知關回合才開下一回合 | **部分** | open=true／EIO 的收尾、退避、恢復後回頭看 pause／rounds 成立；半寫與缺 open 不成立。O/timeline，A2-02。 |
| 不變條件二：lost 前掃描、keep 不雙開 | **部分** | O/identity.runner_before_pid 真 runner 死於子程序出生後、pid.json 前：舊 sleep 先被收掉，才重起。觀測不完整仍會雙開，A2-01。 |
| 舊 run 的 pid／exit／身分不當成新 run | **成立，限本輪篩選案例** | O/identity.old_run_residue：birth run100、pid/exit run1 不被採用；RUN100 掃描不認 RUN1 程序，RUN1 仍找得到。R 的 stale run kill 拒絕亦通過。 |
| 不變條件三：刪槽不改累計 | **部分；模型不足** | 真刪槽、重建後 usage=150，先前最大100；§8 規則只算150而非250。無 kernel 可驗，只能判現設計不能可靠辨認重建世代。A2-09。 |
| pause owner 互不解掉，resume 順便 wake | **部分** | A/B 都 pause 後 A resume 留 B，重開仍留 B；B resume 84ms 到新 tick。帶 rounds 時 A=1 被 B=3 蓋掉，最後僅 B pause；尚未處理的 CLI 同 by 請求也可能覆寫。A2-06／13。 |
| 世代、action.lock、舊動作接管 | **部分：保護成立，診斷失真** | D/stale_generation 的 gen8 在 gen9 下 tick／tock 皆 stale、不建回合；R 接管舊動作、第二 daemon、動作逾時通過。無法辨身分的持鎖者不殺，但長路徑截掉 last_error 的原因，造成一項原測試失敗。A2-08。 |
| fd 寫入，搬家中途不寫回舊址 | **成立，限基礎設施與已接受界線** | D/fd_mid_move：tick 中途搬移，birth／exit127 寫在新址、舊址未重建；runner 執行中搬移，exit0 落新址。R/root 搬走亦過；任務自己用字串路徑重建鬼目錄仍是 spec §5.3 已接受的 K-06 界線。 |
| 控制檔洪水、壞檔、ctl-failed | **成立於現有固定洪水測例** | R 的每圈預算、壞檔、FIFO／目錄回條、單件失敗不阻 stop、固定名覆蓋等測試通過。沒有把有限批次推論為持續惡意灌入也有公平性保證。 |
| 子 daemon owner／daemon、allow_stop、stopped | **成立於本輪** | R/test_subdaemon_modules 全部通過：取鎖後更新現役 PID、人手重開保留 owner、未許可 stop 拒絕、允許 stop 留標記、父 tick 不擅自重起、清標記可續跑。 |
| restart／reload | **部分** | 正常同槽重起、保留 state、reload 不合不 kill、回條及 diff 均通過；在 append once 後 SIGKILL，恢復重播同一 ctl 會再 append，兩次重起。U/restart_crash_after_append_before_kill，A2-05。 |
| 掛載與執行中加掛 | **成立於本輪** | [slots-extra.json](2026-10-04-astra-1-infra-evidence/slots-extra.json)：allow 前綴內 accepted、外部 denied，寫回條後請求刪除；reload 換宣告掛載、保留 dyn，換 run 清 mount-done。16 個定向測試亦通過。 |

### once 中斷矩陣

每案都是獨立空間；恢復先收開著的回合，再 tick。執行次數以槽外副作用計數，避免槽清除把證據刪掉。詳細每回合結果見 O/once_boundaries。

| SIGKILL 位置 | 任務實際執行次數 | 恢復結果 |
|---|---:|---|
| launch 寫入前 | 1 | 下一 tick 起 run2，正常 ended |
| launch 寫入後 | 1 | birth 未寫，換 run2 正常起 |
| birth 寫入前 | 1 | 換 run2 正常起 |
| birth 寫入後 | **0** | 等兩回合，`o#1` 報 lost，不重試；符合 P2-02 |
| runner 記錄前（Popen 已完成） | 1 | 保留既有程序，正常 ended |
| runner 記錄後 | 1 | 不重起，正常 ended |
| once 項刪除前 | 1 | launch 比對後刪項，不重起 |
| once 項刪除後 | 1 | 項目已刪，不重起 |

### 500 回合容量

真 daemon；固定八槽：兩個長跑 keep、三個 each busy、each_fast、一組兩槽 keep_fast。開歷史時再加一槽。於 r10／50／100／250／400／500 收完回合後 pause 採樣，避免把原子寫暫存或正在清槽算成成長。以下 bytes 是檔案邏輯長度，非磁碟配置區塊；含隱藏檔。[關閉](2026-10-04-astra-1-infra-evidence/slots-off.json)、[開啟](2026-10-04-astra-1-infra-evidence/slots-on.json)。

| 模式 | `.aos` 檔數 | `.aos` bytes | `.aosd` 檔數 | `.aosd` bytes | 歷史輸出 |
|---|---:|---:|---:|---:|---|
| history 關 | 每點39 | 5,229～5,263；r100後5,263 | 每點8 | 1,666～1,725 | 無 |
| history 開，max-lines=50 | 每點44 | 6,302～6,487 | 每點8 | 1,683～1,751 | 最後 node 50行、r451～500、無gap；事件9行，兩檔共28,063 bytes |

所以「固定工作集合的健康回合不累積核心歷史」成立，**嚴格 bytes 常數不成立**：計數位數、狀態內容會改變；更重要的是 W10 已接受的單次 run 日誌及任務自存資料本來就不受限。[slots-output.json](2026-10-04-astra-1-infra-evidence/slots-output.json) 的同一 keep run 到 r1／5／10 仍11檔，但 out.log 為 4,096／20,480／40,960 bytes。新檔名控制回條亦可累積，W3 已揭露。另有未揭露的故障累積：提交前 SIGKILL 20次留下20個 dot tmp、5,240 bytes，再健康跑10回合仍保留，A2-07。

## 二、proto7-1 K-01～K-10 對照

| 舊問題 | 本版分類 | 判斷 |
|---|---|---|
| K-01 round 讀不到仍開下一回合 | **換了形式** | EIO 原案已修；schema 壞／缺 open 仍當已關，能漏回合或覆蓋同號回合。A2-02。 |
| K-02 恢復漏看 pause／rounds 多一輪 | **已修** | O/timeline.recovery_pause_count：失敗→退避→成功 tock，done一次、paused=true，沒有再 tick。新多 owner 倒數碰撞是 A2-06，非同一條恢復分支。 |
| K-03 tick／runner 都死，永久 born | **已修** | 無 runner 的 birth 兩回合後進身分掃描／lost，after-birth 可恢復為可讀失敗。代價是 P2-02 零次執行，不是至少一次。 |
| K-04 runner 死於 pid 發布前，keep 雙開 | **換了形式** | 原出生窗口已修，真殘留子程序先被收掉；但 `/proc` 不完整仍當空，雙開重現。A2-01。 |
| K-05 starttime 不可讀當 PID 重用 | **換了形式** | proc_starttime=None 原案保守 live；更下層 pid_alive 的 stat EIO 仍當 dead。A2-01／08。 |
| K-06 最後啟動窗口搬移重建鬼目錄 | **仍在，已接受界線** | fd 基礎設施保護有效；spec 明確接受任務死前用字串路徑重建舊址，不以新增 stat 宣稱消失。本輪未重放舊版最後一指令窗口，只確認中途搬移 fd 行為及文件界線；新 symlink 問題另列 A2-04。 |
| K-07 清歷史造成 kernel 額度回退 | **換了形式** | tasks-old／purge 觸發消失；kernel 尚未實作，§8 用槽最大值＋看下降辨重建仍少算跨生命週期用量。A2-09，屬設計反例。 |
| K-08 owner 混合歷史權限與現役 PID | **已修** | owner／daemon 分塊，手動重開更新 daemon、保留 owner；R 子 daemon 測試通過。 |
| K-09 容量掃描卡 daemon 主迴圈 | **消失（設計上不存在）** | 無 disk 容量掃描與核心歷史 purge，程式未把此工作換個名字留在主迴圈。500 回合仍跑同一組固定檔。 |
| K-10 「1～2ms發現新 node」不合實作 | **消失（設計上不存在）** | 不再掃描，也沒有該時限承諾；register 由控制迴圈處理。未登記不跑的黑箱結果合新模型。 |

## 三、使用者建議落實與複雜度

| 建議 | 落實判定 | 程式／行為，以及新增成本 |
|---|---|---|
| 1. node 一開始登記，可中途 ctl 登記 | **已落實** | nodes.json 成為持久清單；無 timeline 亦可啟動，重開續用。省掉樹掃描／rescan，但每次使用路徑仍須重驗身分與邊界；目前 symlink 例外漏掉。 |
| 2. 提前 tock 可選，有固定 interval | **已落實** | false／true 的 1.809s／48ms 真節拍有差。新增等待的兩個階段，讓 wake／resume／kick 語意更容易不一致，P2-01 與 A2-11 需明確化。 |
| 3. 任務盡量統一 tasks.json | **已落實** | 沒有 spawn 佇列，once、batch、restart 都用該表；U/D07 原子加兩項並保留頂層 mount_allow。代價是鎖、launch、刪項、restart append 各有交接窗口；A2-03／05 不是檔案少了就自動解決。 |
| 4. 任務資料夾同名重用 | **已落實** | max_live 八槽長跑500回合，名稱固定；state 留、out.log 等基礎設施換 run 清。省掉找前任／tasks-old，換成 run 身分比對、seen_round、reaped、重建世代的成本。 |
| 5. 不要持續產垃圾、原建議定期清理 | **依追加意見落實，容量僅部分** | 正常核心歷史覆寫、孤立已結束槽延一回合刪；不再用保留上限／輪替管理核心歷史。尚有 SIGKILL dot tmp 真垃圾未清，及已接受的 out.log／自存資料／自取新回條名。 |
| 追加：歷史可選 module，核心只留上次 | **已落實** | history 是普通 keep 任務、可關，核心不依賴它；last-round 同回合重播可恢復。複雜度轉給取樣缺口、module 輪替與上層累計；A2-09／10／12 顯示轉移出去後仍要寫清保證。 |

這版概念較少，操作面的設定也較少；沒有必要把前版歷史機制搬回來。真正增加的難度在「可覆寫資料的身分與提交順序」：同一槽不等於同一次執行，沒有舊 birth 也不能代表沒有執行過。

## 四、新使用者文件一致性：10 項實測

以下預期只取 README／spec 的公開操作與承諾，操作腳本走公開 CLI；故障反例在右欄交叉對照，不把內部原始碼當成使用者應先知道的前提。U 的 D01～D10 保存正常黑箱結果。

| # | 文件宣稱 | 實測與一致性 |
|---|---|---|
| D01 | README、§1：只跑登記 node；timeline 可無，預設1000ms | **一致**：未登記不開；register後r1、1000ms。後續路徑換 symlink 的邊界另不一致，A2-04。 |
| D02 | §4.4／5.1：once 一次、刪項、交付物應放槽外 | **正常一致，故障部分**：o#1一次、r2不再起且刪槽；birth半寫後重複，A2-03。「不漏起」標題也需帶 at-most-once 限定，正文才說P2-02。 |
| D03 | §4／5：keep補滿、each每回合一個、滿槽跳過 | **一致**：r1起k/k.1/e，r2只e.1，r3不再起、each列busy。 |
| D04 | §5.1：同槽保留state、清本次基礎設施 | **一致**：x#2保留counter=71，舊out.log清空。 |
| D05 | §4.1：單項欄位錯誤不影響其他項 | **一致於測例**：max_live=0的bad被跳過、記tasks_error，ok#1正常起。 |
| D06 | README、§5.5：cwd=node、AOS7_*、PATH使用proto7-2/bin | **一致**：team/n 的cwd、NODE_ID、TASK、TID、RUN及PATH首項逐一相符。 |
| D07 | §10：ctl add 多項一次入表，保留其他設定 | **一致**：同一次add a/b，下一tick同時起兩項，mount_allow未丟。 |
| D08 | §2.4：A/B各自pause；resume只清自己且順便wake | **基本一致，延伸不一致**：A resume留B、B resume後續跑；帶rounds時互相覆蓋，A2-06；owner不同而by相同的待處理CLI會碰撞，A2-13。 |
| D09 | §2.2／7：同回合總結可恢復，確知關閉才下一回合 | **重播一致，壞檔不一致**：強制恢復open後tock replayed=true、summary原bytes不改且關閉；缺open卻直接跳回合，A2-02。 |
| D10 | §2.3／10：CLI固定檔名，回條同名覆寫 | **一致**：兩次pause寫同一路徑，只一個pause回條。W3「意思相同」的解釋不適用不同owner／rounds，A2-13。 |

**篇幅與易懂度：** proto7-1 spec 350行／34,778字元／58,592 UTF-8 bytes；proto7-2 356行／20,659字元／35,177 bytes。字元少約40.6%、bytes少約40.0%，行數略增，標題由12增至31；README則35→72行，但bytes 6,160→6,138，主要是切分說明。數據見 U/spec_size 與 [slots-metadata.json](2026-10-04-astra-1-infra-evidence/slots-metadata.json)。

新文件較容易找到登記、槽、once、歷史各自的規則，少了前版大量歷史典故。仍有三個閱讀陷阱：§0「半寫＝不知道」與§5.4「birth壞且掃不到＝空槽」互相衝突；§2.2的「確知已關」沒有完整寫出欄位驗證；§4.4「不漏起」標題比P2-02承諾強。另§2.3 unregister正文仍寫收完才移除登記，P2-10實作是先移除；只看README／spec的使用者不一定會再追problems，應將最終規則直接寫回正文。這個先後差異本輪列文件／程式核對，沒有另加 daemon 中途死亡實測，故不當作新的實測bug。

## 五、A2 新問題

### A2-01〔bug，高〕程序觀測不完整被當成沒有，造成誤殺或雙開

`lib/aos7_proc.py` 的 `pid_alive` 把讀stat的OSError變False，`all_pids` 把listdir失敗變空清單，`env_procs` 沒有回報掃描是否完整；`aos7_task.resolve` 據此判lost。O/three_state 的 `proc_stat_eio` 收掉健康run1再起run2；`proc_all_eio` 則兩個真sleep PID同時活，解除注入也未收舊run。birth半寫＋environ EIO另可直接EMPTY→雙開。

**應修方向：** 掃描結果包含完整性；只有「確知掃完且無匹配」能支持lost／清槽／重起。UNKNOWN必須一路傳過pid_alive、掃描、kill確認及槽判定，不能只在read_json3包一層。涉及S-06、S-10及不變條件二。

### A2-02〔bug，高〕回合半寫／缺open仍當已關，可跳過或覆蓋未提交回合

`aos7_daemon_timeline.Timeline.check_round` 只有IO回None，其餘不是`open is True`便False。O/timeline.round_open_missing先完成r1、開r2，再移除open：直接tick r3，last-round由1跳3、last_error=null。round_bad則把r2半寫成`{`，又開一次r2覆蓋原狀態。

**應修方向：** schema不完整同樣UNKNOWN；明確的`open:false`才可作已關證據，新空間的真正不存在另定規則。`next_round`能接號不等於舊回合已完成。這是K-01的新入口，不是一般JSON解析小問題。

### A2-03〔bug，高〕birth半寫使launch無法辨認已執行，once可重跑且漏報

O/once_corrupt_birth：tick被殺在刪once前，run1副作用已完成且exit code0存在；等runner退出後寫半份birth。tock的ended與errors皆空，下一tick改launch並起run2，副作用由`[1]`變`[1,2]`。**需要SIGKILL加檔案損壞，沒有否定八點純SIGKILL結果。**

`judge` 的「壞birth＋無活程序＝空槽」無法區分未執行與已執行完成。應使已有launch但無法證實birth身分的項目停在待恢復狀態；掃不到活程序不是「從未執行」證明。§0／§5.4規則也須一致。

### A2-04〔bug，高〕登記後追蹤symlink，node不missing且能沿新目標寫出daemon根

D/symlink_same_inode原址連回搬走目錄，stat追連結而inode相同，任務保持活、r2→5；symlink_outside_root改指另個目錄，時間線在目標建立`.aos`並起r1。測試目標在本副本的隔離空間，沒有碰副本外資料。

登記時realpath檢查不等於之後一直符合邊界。`Daemon.check_nodes`啟動／重啟時間線時應重驗路徑各段與daemon根規則；若要求「換symlink即missing」，需保留連結本身身分而非只看目標inode。這是合作式協定下的搬移／配置錯誤，不以惡意權限隔離作測試前提。

### A2-05〔bug，高〕restart追加once與消費ctl不具冪等性，一次請求可重起兩次

U/restart_crash_after_append_before_kill：`run_ctl`完成edit_json後SIGKILL（-9），表內一個`restart_of:x#1`且ctl仍在；恢復tock再執行同一ctl，表內變兩個同樣的once，後續tick實際起`x#2`、`x#3`，槽外副作用為`1,2,3`。

P2-07「先加後殺」避免殺了不重起，但沒有避免同一意圖重播成多項。應以控制請求／原run的穩定識別去重，或保存可恢復的處理階段；不能只靠once各自的launch，因為兩個once本來就是分開的項目。

### A2-06〔bug，中〕pause有owner，rounds倒數卻仍每node僅一份

`Daemon.steps`是`{node:{owner,left}}`。D/rounds_owner_collision：A/B先pause，A resume rounds=1仍被B擋住；B resume rounds=3覆蓋A，最後到r3只B pause，A的一回合上限消失。使用了不同by，與檔名碰撞無關。

應按node＋owner保存倒數，或明確拒絕衝突請求，不能接受兩筆卻無聲丟掉前一筆。正常A resume不解B的測試不足以驗證多控制者。

### A2-07〔bug，中〕原子寫被SIGKILL留下隱藏暫存檔，恢復後永久累積

[storage-crashes.json](2026-10-04-astra-1-infra-evidence/storage-crashes.json)：20個不同PID在last-round rename前SIGKILL，原5檔變25檔，新增20個`.last-round.json.tmp.<pid>`共5,240 bytes；成功恢復再跑10回合仍20個暫存。這是基礎設施垃圾，與W10任務日誌不同。

`write_json`／runner `write_at` 用PID命名，但沒有恢復清理。可在持有相應動作鎖、確認沒有現役寫者時清失效暫存；不要把「列目錄忽略點檔」當容量有界。

### A2-08〔bug，低〕保守判定的原因未完整顯示，長路徑還會截掉錯誤類型

O/starttime_none內部有unsure，但last-round的errors與tick的skipped皆空；只有alive看不出退讓原因。D/unverified_holder_diagnostic持鎖者確實未殺，`Timeline.err`只留最後300字卻截掉錯誤類型與根因，留下路徑尾端及人工提示。R唯一失敗可由此穩定解釋；last_event仍有完整ev/why，保護本身有效。

應將錯誤代碼、原因、路徑分欄；unknown／unsure進公開狀態，避免「保守停著但看似正常」。

### A2-09〔技術選型，高影響〕§8只憑usage下降辨認槽重建，無法可靠累計

[slots-design.json](2026-10-04-astra-1-infra-evidence/slots-design.json)/slot_recreated真實刪槽並重建：舊usage100、新生命首次看到150。規則未看到下降，retired=0、總量150；實際兩段合計250。即使記住舊槽曾消失，只要kernel漏看刪除那一刻，一樣分不出。尚未見到就刪掉的最後用量也無法靠最大值補回。

這不是已實作kernel的bug。**只增不減的顯示值可做到，但精確累計／cap不漏算尚不可承諾。** 需要跨run累計的槽生命週期ID與可靠退役交接，或明確限制為「已觀測用量下界」。單加run不夠，正常換run本來就應沿用usage。

### A2-10〔bug，中；可選module〕history的max-lines未套用事件歷史

[slots-design.json](2026-10-04-astra-1-infra-evidence/slots-design.json)/history_max_lines：`max_lines=3`，node歷史3行，`daemon-events.jsonl`卻10行。`modules/history.py.once`只在node分支trim，status分支直接append。應讓同一選項涵蓋事件檔，或清楚提供另一個上限；這不影響關閉module時的核心檔數。

### A2-11〔bug，中〕early回合中的wake被保留，會省掉之後的interval等待

D/wake_in_active_early_round：設定2500ms，在任務仍跑時wake，約768ms即下一tick；當回合沒有被截短，但後面的idle被kick略過。文件只說「回合中照舊」，未說會排下一次提早啟動。

若照現文字，應只在idle受理kick；若刻意讓回合中的wake延後生效，需直接修改規則及P2-01說明，否則呼叫者無法預期兩模式的差別。此項可依既定規格修正，無須擴張成新排程功能。

### A2-12〔技術選型，中影響〕history通知早於總結提交，快讀也可能漏最後回合

[slots-extra.json](2026-10-04-astra-1-infra-evidence/slots-extra.json)/history_notification_before_commit：只在寫last-round前延後200ms，真history任務已收到tock1卻讀不到總結，收到tock2時只讀到r1；最終last-round=r2、history僅r1、沒有gap。這比「module太慢漏取樣」多一個反方向的時序：讀者太早醒。

取樣遺漏已是§9接受代價，不將它列成核心無損歷史的bug。可讓module在收到本node回合通知後重讀到相應總結，或調整發布／通知順序；最少應補上停機／最後一回合可能未記的限制。初次從r100開始取樣也不會為1～99產gap，不能把沒有gap視為全歷史完整。

### A2-13〔技術選型，中影響〕CLI固定檔名未含owner，不同控制者會互蓋待處理請求

U/owner_cli_pending_collision：daemon未起前，依序`pause a --owner A`、`pause a --owner B`，預設by都是cli，兩次同為`cli.pause.a.json`；daemon起來只收到B。即使把A/B當不同控制者，owner隔離在進daemon之前已失效。

W3明確接受同名最後寫者勝，故不另稱未知產品bug；但「同一件事意思相同」不適用不同owner／rounds。使用者可用不同`--by`避開；文件應明講，或固定鍵至少納入owner。與A2-06已受理後覆蓋倒數是兩個獨立層次。

**要使用者決定的項目：本輪沒有新增。** 既有P2-01「固定interval時wake無效」及P2-02「once允許零次但報lost」仍維持原待決狀態。前者已有兩模式量測，後者八點純SIGKILL符合選定語意；不用把明確bug再交回使用者選政策。單純宣稱「不重起又絕不漏起」超出目前持久化交接能支持的範圍。

## 六、重跑與清場

在副本根目錄執行，所有腳本使用純標準庫及本版bin/lib，設定不產生bytecode：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-1-infra-evidence/regression.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-1-infra-evidence/once-probes.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-1-infra-evidence/daemon-probes.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-1-infra-evidence/docs-and-crashes.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-1-infra-evidence/slots-probe.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-1-infra-evidence/slots-extra.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-1-infra-evidence/slots-output.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-1-infra-evidence/storage-crashes.py
```

清場依各次建立的Popen／PID、程序身分與暫存根核對；沒有使用`pkill -f`。暫存皆位於副本evidence下（副本本身位於/tmp），程序先收再刪資料夾；沒有另建副本外/tmp空間。[once-cleanup.json](2026-10-04-astra-1-infra-evidence/once-cleanup.json)、D/_cleanup、各slots結果的cleanup欄與[最終清場](2026-10-04-astra-1-infra-evidence/final-cleanup.json)記錄零殘留；最後一份亦列本輪時間範圍內指定產出以外的檔案異動檢查：產品及文件無異動；唯一另有更新的是執行環境自動追加的既有 `log.txt`（Codex 會話逐字紀錄），測試腳本未寫入或清除它。

## 總評

proto7-2 已把「正常每回合一直長歷史」這個主要設計負擔拿掉，登記、槽、run、上一次總結也讓日常操作較清楚。K-02、K-03、K-08確實修掉，K-09、K-10的原問題從設計上消失；回退到前版沒有好處。但穩定性還差三件核心工作：讓**讀取與掃描的未知狀態一路保留**、讓**回合與槽生命週期都有足夠的有效身分證據**、讓**同一控制意圖在中斷後重播仍只生效一次**。A2-01～05仍屬結構性問題；owner倒數、暫存清理、module輪替與診斷才是其後可局部收斂的工作。先把這三類不變條件變成固定回歸矩陣，再談kernel接上去，才能避免將底層誤判放大成排程與額度錯誤。
