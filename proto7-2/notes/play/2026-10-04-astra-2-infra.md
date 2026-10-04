# proto7-2 第二輪基礎設施回歸：回歸與故障注入

日期：2026-10-04。任務原文：[task.md](2026-10-04-astra-2-infra-evidence/task.md)。測試對象為目前副本；副本沒有可用的 Git repository，不能獨立核對題述五個 commit 的祖先關係。本輪只新增這份報告及同名 evidence，不修改產品、既有測試或其他文件，沒有呼叫模型服務。

## 摘要

**修復有實效，正常運作已相當穩定，但剩餘問題仍包含控制意圖與生命週期的結構性缺口，尚不建議直接把 kernel 接上來承擔排程／額度決策。** 既有 **219 項全過，83.927 秒**，其中固定矩陣確為116項。上一輪13項的原始反例都已有對應改善；A2-09只能確認規格模型已換掉，不能說尚未實作的 kernel 已通過測試。A2-05、07、13 在延伸組合仍只能判部分修復。

最重要的新增實證：同一 restart 的控制檔若刪除失敗，正常 keep 換 run 後會忘掉已完成意圖，再殺掉新 run 重起；environ 真 EACCES 加上 runner 死於 pid 發布前會雙開；把 birth.json 換成 FIFO 也會被當空槽而雙開。後兩項與規格刻意接受的例外有關，不能宣稱它們仍符合原本「觀測不到不當不存在」的完整保證。

矩陣不是假測試，但綠燈有界線：healthy `/proc` 12案中 **9案指定故障命中次數為0**；EACCES 的孤兒程序組合被刻意排除；restart只測單次崩潰後順利消費，沒測完成證據跨 run 消失。另有控制ID／owner編碼碰撞、掛載子目錄暫存漏清及重播通知失敗被吞。

真daemon長跑完成 **50 node × 1000空任務回合**及 **10 node × 1000含任務回合**，檔數分別固定456／183，未發現卡住。含任務有42筆「剛起」uncertain取樣，都是正常交接暫態，不能宣稱uncertain完全為零。量測限制見第五節；完成清場與來源異動核對見[最終稽核](2026-10-04-astra-2-infra-evidence/final-cleanup.json)。

## 一、方法與 A2-01～A2-13 回歸

共四條工作線。沿用上一輪 evidence 的 worker、故障位置與副作用觀察；只調整與新版契約不相容的探針：tick前先收開著回合、原本等待錯誤第二份出現改為檢查不再出現、A/B倒數案加入正確停在A後再resume、history提交前通知改成可不存在。未把舊測試腳本失配當產品失敗。

一次性執行以槽外副作用、真PID、birth／exit交叉核對。SIGKILL都作用於實際子程序；EIO／ESTALE用低層讀取注入，EACCES另用uid1000的真chmod及真不可ptrace程序驗證。沒有模擬斷電／fsync耐久性。重跑次數不加總成更多獨立測試。

主要證據縮寫：**R**＝[regression.json](2026-10-04-astra-2-infra-evidence/regression.json)；**O**＝[once-regression.json](2026-10-04-astra-2-infra-evidence/once-regression.json)；**D**＝[daemon-review.json](2026-10-04-astra-2-infra-evidence/daemon-review.json)；**X**＝[matrix-extra.json](2026-10-04-astra-2-infra-evidence/matrix-extra.json)。JSON key可直接搜尋。表中「已修」限定原故障；新增故障與契約縮限另列，不把它們藏在原案綠燈後面。

| 編號 | 判定 | 舊重現的本輪結果／延伸限制 |
|---|---|---|
| A2-01 `/proc`未知流失 | **已修（原EIO案）；保證有縮限** | O/three_state：stat EIO、all EIO、birth壞＋environ EIO均不起第二份、原PID活、tock有errors；identity.runner_before_pid正常可讀孤兒先收再起。真environ EACCES例外仍雙開，見A3-02。 |
| A2-02 round半寫／缺open | **已修（原JSON案）** | O/rounds.round_bad、round_open_missing、round_eio：tick/tock都Unknown、原bytes不動，last-round留r1，不覆蓋開著的r2；D/manual-round驗證daemon診斷與修復。FIFO被當不存在是新增A3-03。 |
| A2-03 birth半寫使once重跑 | **已修（原半寫案）** | O/once_corrupt_birth：刪once前SIGKILL，run1已完成後birth寫成`{`；tock報o#1/code0，下tick不起、表項刪掉，槽外副作用仍只有`[1]`。沒exit/pid證據時改停該槽。 |
| A2-04 node變symlink | **已修** | D/A2-04-same-inode、outside：missing、原任務已收，連結目標不建立`.aos`。R另驗上層symlink及登記拒絕。所有「root外」目標仍在副本內的測試空間。 |
| A2-05 restart重播 | **部分** | O/restart.original_append_sigkill：追加後真SIGKILL，恢復前後都只有一項，執行`[1,2]`。但ctl unlink失敗＋keep換代讓同一意圖再執行，A3-01。 |
| A2-06 owner倒數互蓋 | **已修** | D/A2-06-and-A2-13：A=1/B=3，r1由A pause，B還有2；resume A後r3由B pause，兩份倒數都保留。 |
| A2-07 dot tmp累積 | **部分** | [原腳本重跑](2026-10-04-astra-2-infra-evidence/storage-crashes-rerun.json)：20次rename前SIGKILL後最多留最後1檔；健康恢復＋10回合為0。mount-req/mount-done仍漏清10檔，A3-07。 |
| A2-08未知診斷／長路徑截尾 | **已修（原案）** | O/proc_starttime_none的summary.errors有unsure原因；D/manual-birth的status.uncertain有槽與提示；R在本副本深路徑執行的既有持鎖者測試與matrix kind前綴測試皆過。歷史last_error不等於目前仍故障。 |
| A2-09槽重建用量少算 | **已修於規格；無kernel可驗** | [舊反例](2026-10-04-astra-2-infra-evidence/slots-design-rerun.json)仍是run1/100→刪槽→run3/150；[新規則核對](2026-10-04-astra-2-infra-evidence/usage-spec-review.json)以兩run相加得250。精確cap明確不保證，詳第三節。 |
| A2-10事件history無上限 | **已修** | 同一slots-design原案max_lines=3、10次取樣，node歷史與daemon-events現在各3行。 |
| A2-11回合中wake留到idle | **已修** | D/A2-11原early／2500ms／sleep0.7案，running內wake到下一tick約2.439秒，未再約0.7秒直接開；R另驗idle wake仍即時。 |
| A2-12通知早於總結 | **已修（原順序案）** | [真history＋提交前延後200ms](2026-10-04-astra-2-infra-evidence/slots-extra-rerun.json)：r1提交前無通知，r2提交前仍通知r1，最後history含r1/r2。[SIGKILL後正常重播](2026-10-04-astra-2-infra-evidence/history-replay.json)也補通知成功。重播再遇I/O失敗的漏診斷另見A3-08。 |
| A2-13不同owner待辦互蓋 | **部分** | D原A/B＋相同by：路徑不同、兩份pause均生效。X/owner_encoding_collision：甲／乙都成`@_.json`，最終只乙；A/B與A+B也同名。A3-06。 |

O/once_boundaries保留上一輪8個真SIGKILL位置：before/after-launch、before-birth、before/after-runner、before/after-delete均恰執行1次；after-birth為0次且誠實報lost。這仍是已揭露的at-most-once取捨，不是「保證不漏起」。

## 二、固定矩陣審查

| 檔案 | 項數 | 真正覆蓋的故障／不足 |
|---|---:|---|
| test_matrix_faults.py | 52 | `/proc` healthy/orphan/deadboth/brokenbirth；birth/exit/pid、round/last-round、列槽與node stat錯誤。涵蓋主要EIO/ESTALE傳播；healthy部分未命中指定讀取，且明確排除關鍵EACCES組合。 |
| test_matrix_docs.py | 24 | round五種壞內容、last-round三種不完整、birth三種壞內容×四種證據。真正驗schema；未涵蓋FIFO／目錄型別、複合證據損壞或人工恢復的副作用取捨。 |
| test_matrix_once.py | 24 | once/keep的18個啟動交接組合及6個restart崩潰組合。真SIGKILL、真程序；沒有ctl消費失敗跨多run、ID截斷、同mtime與跨槽查重。 |
| test_matrix_misc.py | 8 | symlink兩位置、tmp兩案、診斷兩案、history上限與通知順序。tmp路徑覆蓋不全；通知只記函式呼叫順序，未驗失敗重播。 |
| test_matrix_daemon.py | 8 | 真daemon的symlink、owner倒數、owner檔名、tmp、wake。主要正常多控制者案有效；owner只用A/B，未驗編碼碰撞。 |
| **合計** | **116** | 另103項既有測試，共219項，不把本輪定向重跑另加進去。 |

**注入位置大致正確，但需要證明有打中。** `_read_proc`在真正open的同一try內呼叫inject，read_json3、list_slots、node lstat亦在相同錯誤處理邊界，適合驗證errno傳遞。`tmp:*`位於關閉暫存檔後、replace前；本輪攔真os.replace再SIGKILL得到一致結果。runner-before-pid在真Popen後，故能保留真孤兒。這些都比偽造「程序已死」的回傳有說服力。

但AOS7_TEST_FAULT並非涵蓋所有OS故障：它不注入write／rename／unlink，runner的read_birth也不走read_json3；規則在動作中生效，不會全部傳給任務。讀取開始前errno可驗傳播，不能涵蓋已開fd後讀取失敗、短讀、回讀與檔案替換競態，或斷電後持久化順序。

[matrix-hook-audit.json](2026-10-04-astra-2-infra-evidence/matrix-hook-audit.json)包住現有inject計數後重跑healthy12案：proc-stat三案各命中6次；proc-list／environ／cmdline各三案全為0次，仍全部通過。原因是已知pid/runner活著的捷徑不必掃環境。這9案能證明「有故障設定也不影響已知健康路徑」，不能證明指定讀取失敗已處理。orphan/deadboth仍有實際掃描覆蓋，不能因此否定整個矩陣。

本輪補的矩陣外組合：

| 組合 | 結果 |
|---|---|
| 真environ EACCES＋runner-before-pid死亡 | **失敗**：lost後兩PID同活，D，A3-02。 |
| 真ctl unlink EACCES＋restart已完成＋keep正常換run | **失敗**：同一意圖再kill/restart，O，A3-01。 |
| 不同完整ID同64字前綴／保留mtime的新檔／跨槽同key | **失敗**：新意圖遭去重，O，A3-04/05。正常新mtime控制組成功兩次restart。 |
| 非ASCII或編碼後同名owner | **失敗**：待辦被覆蓋，X，A3-06。 |
| 真FIFO取代birth／開回合round | **失敗**：雙開／同r2再開，X，A3-03。 |
| mount子目錄原子replace前連續SIGKILL | **失敗**：健康回合未清10個tmp，A3-07。 |
| 總結提交SIGKILL→正常重播 | **通過**：真history補收到r1。 |
| 總結提交SIGKILL→birth讀EACCES／通知寫EACCES、EISDIR | **失敗**：關回合卻未通知，也未留下失敗說明，A3-08。 |

下一輪應把上述反例固定下來，對每個fault要求命中計數大於0，並把「原故障解除後恢復」與「恢復期間再遇第二故障」分成不同矩陣軸。無須為湊項數遍歷所有組合；優先保住不雙開、同意圖不重做、未知不當不存在三條不變條件。

註解也仍有需收斂之處：`aos7_proc`檔頭把同uid的EACCES寫成未知，實際binary environ/cmdline卻略過；`kill_node`說掃描不完整時只收記住的群組，實作若env_procs先丟ProcUnknown則直接回False，沒有那段補收。這兩項是靜態文件／控制流核對，未另做獨立故障測例，不列成額外已實測A3。

## 三、與原約定不同處

**environ EACCES視為不是任務。** 這確實能避免掃到桌面上不可ptrace程序便令所有掃描停住，但代價不是單純少一個警告。D的任務只呼叫`prctl(PR_SET_DUMPABLE,0)`，沒有改uid或清掉AOS7環境；uid1000讀environ真的得13。正常pid紀錄仍可辨識它活著；runner死亡後，環境掃描卻看不見它，kill可假成功，缺pid的出生窗口更可雙開。不同uid／setuid未在本輪實跑，不能把這次結果寫成已實測所有跨uid程式；但「不可ptrace」這個共同機制已驗證。spec §11把這些算脫離管理，因此要把承諾限定為可持續讀取身分的合作式程序，不能用healthy EACCES綠燈證明更廣保證。

**tick拒絕open回合。** 合理且沒有發現因此永久卡住。D/manual-round：第二次tick退出3、檔案不動，daemon可自動tock原回合再向前；O也驗直接tock可收尾。真正需要人工的是round證據壞掉、持續I/O或不能核對持鎖者。status的error／round_open:null／round-unknown清楚，但文件只說「確認收完後寫回N/false」，沒有說N從哪裡核實、哪些未提交結果會被跳過。不要照矩陣的人工寫false當通用恢復方法。

**ctl_id＝內容＋mtime。** 普通原子重寫的兩次相同內容restart有不同mtime，兩件都成功（執行1、2、3）；不存在「同內容必然只做一次」的問題。真正限制是mtime不等於意圖：保留mtime複製／還原的新inode會被誤認重播；跨槽同內容同mtime還會互吃。低時間解析度檔案系統有同類風險，本輪沒有掛載那些檔案系統測試。CLI目前也不產生獨立id。明確id則另有靜默截64字的實作bug。識別契約及去重保存期限需一起修，不能只換hash演算法。

**root取realpath。** 就node登記以實際路徑為身分的模型而言合理：root別名被折成實際根，並非允許node登記後追symlink。這是靜態契約核對；本輪真symlink回歸重點在node／上層目錄，未把它宣稱成所有root別名切換的競態證明。

**after-popen時runner活著便當活。** 合理。PID尚未發布不等於任務不存在；O舊8點與R新矩陣都確認這個窗口恢復不重複執行。代價是runner真的卡住仍占槽；目前沒有runner自身啟動交接逾時，與單次tick/tock的action_timeout不同。正常短暫unsure不是人工停點。

**§8用量按run記。** 新模型修正了舊「看到usage下降才算重建」反例，並誠實降為已觀測下界。將來kernel還須把node識別納入鍵的作用域：不同node都可能有job#1。保留state與usage檔不等於usage仍屬當前run；讀者應依`usage.json.run`識別，不能只讀birth後把舊usage歸給新run。這是接kernel前的契約測試要求，不是聲稱現有kernel已犯此錯。

## 四、停在不知道／要人工的情況

以下依目前程式分支及spec整理，包含需要外部修復才會解除的狀態。**整node停開回合、單槽保留、單請求等待三者不同；uncertain非空不等於要人工。** 真實操作驗證見D/manual-round、manual-birth，其他列為程式／文件審查，不冒稱逐項故障都實跑。

| 情況 | 停止範圍與看得到的證據 | 合理性／恢復與文件缺口 |
|---|---|---|
| round半寫、缺欄、型別錯、I/O | 時間線error，round_open=null，kind=round-unknown | 保守合理；修I/O或還原可信round。文件有格式範本，缺核實N與是否已提交的步驟。 |
| round不在，last-round不能用 | tick3/error；round_open可能false，但last_error說明接號失敗 | 不猜回合合理；保留證據再恢復編號。兩檔都不在會當新空間，並不保護誤刪兩檔的情況。 |
| 明確open，但last-round讀不到、列槽失敗、總結寫入／回讀／收尾失敗 | open與recovery_pending，last_error，0.5～8秒退避 | 修檔案系統／權限後重試tock；只壞last-round內容通常能重建，不必人工。通知失敗可關回合是另一條分支，見A3-08。 |
| gen.json I/O或格式壞 | daemon動作3/error，gen不能用 | 需修存取或確認現役世代；不可猜gen放行舊動作。缺獨立恢復指引。 |
| node/root無法stat、open fd或辨識位置 | node的errno kind；root頂層last_error | 修存取後重試；保留現役程序合理。不是一律停整個daemon。 |
| action.lock持有者不能核對pid/starttime/舊世代 | stale-holder-unverified、人工提示 | 合理；用fuser/lsof核對再收確定的舊動作，或補可信owner；不能unlink鎖檔。這類提示最完整。 |
| birth/exit/pid I/O或列槽I/O | 單槽UNKNOWN＋uncertain/errors；整個槽列表失敗則擋動作 | 原因解除可自動恢復，不應用猜測換run。 |
| birth壞、沒有活身分，也沒有帶run的exit/pid | 單槽k#?、uncertain有刪birth提示，其他回合繼續 | 不重做合理。刪birth是重新授權執行，僅確認「現在沒活程序」不能證明once未產生外部副作用；提示應補這層後果。 |
| 活pid讀不到stat/starttime，或原記錄starttime=null | LIVE＋unsure，該槽不重用 | 暫時讀錯可恢復；歷史null不會因/proc恢復便自動補身分，需可信證據或等程序結束。現提示未分清兩者。 |
| 疑似lost但掃描不完整、SIGKILL後仍活、最後exit重讀失敗 | 單槽UNKNOWN／errors，ctl留著 | 必要保守；解除I/O、權限或程序阻塞後重試。不能為了進度直接判lost。 |
| ctl讀不到或目標槽UNKNOWN | 該請求保留，last-round.ctl有錯 | 合理重試；status缺待處理控制詳情，要另外讀ctl與last-round。 |
| daemon ctl處理例外、ctl-failed或ctl_stuck | 單份請求停止；last_ctl_error | 需核實效果是否已發生再重送；重啟不是無條件安全的通用解法。 |
| tasks表I/O／壞掉、表鎖逾時、項目不合法 | 回合繼續，該項不起；tasks_error/skipped | 隔離合理，但status只看round前進不足以發現沒工作，需讀總結。 |
| subroot停止標記／現役子daemon鎖／重複認領 | 單項准入擋下，tasks_error | 正常防雙開；stopped需明確刪標記或重開子daemon，已有規則。 |
| pause／rounds歸零、missing／symlink、取消登記、正常stop | paused_by/steps_left/missing/stopped | 明確控制或實體變更；resume對應owner、恢復真目錄／重新登記或起daemon，不是unknown故障。 |

正常birth→runner→pid交接的「剛起」，以及能找到活runner的after-popen恢復，另屬短暫保守觀察。它們會進uncertain，應看持續時間及run是否前進，不能一看到便叫人處理。last_error保留最近錯誤也不代表故障尚在；恢復後應合看phase、round及時間。

整體沒有看到全面停止導致的正常可用性崩退；單槽隔離有效。可改善的是診斷層次與復原文件，而非退回「不知道就重跑」。若要安全復原，至少需先保存round/last-round/槽證據、讓會寫檔的動作停止競爭，再依同回合完整總結與現役程序核對。只有明確open且內容完整時可直接tock；證據不完整時不能盲寫false或刪birth。README／spec尚未提供這套完整流程。

## 五、長跑與負載

本輪採真daemon及真tick/tock子程序，16個邏輯CPU，interval_ms=0以測吞吐。每個checkpoint透過resume --rounds跑到指定回合再pause採樣，避免把瞬間tmp當檔案累積；採樣r10／100／250／500／750／1000。腳本：[load-probe.py](2026-10-04-astra-2-infra-evidence/load-probe.py)，以`--long`執行正式規模。

| 工作負載 | 已關node回合 | 經過時間／平均吞吐 | CPU秒 | 檔數／邏輯bytes | uncertain |
|---|---:|---|---|---|---|
| [50 node空任務](2026-10-04-astra-2-infra-evidence/load-long-empty.json) | 50,000 | 330.520秒／約151.3回合/秒 | daemon72.06＋已wait子程序4844.80＝4916.86 | 各checkpoint456檔；79,709→80,109 bytes | 1643次輪詢未觀察到 |
| [10 node各一keep sleep＋一each true；n00另history](2026-10-04-astra-2-infra-evidence/load-long-tasks.json) | 10,000 | 83.242秒／約120.1回合/秒 | daemon10.30＋已wait子程序786.10＝796.40，屬下界 | 各checkpoint183檔；32,843→39,975 bytes | 417次輪詢共42筆，全為「剛起」，含重讀同一status |

每次checkpoint均無dot tmp、summary.errors或tasks_error；status輪詢沒有last_error。含任務最後每node keep仍run1，each已到run1000；history以max-lines25保留25行，末筆r1000、保留範圍無gap。bytes會隨回合數位數、history填滿及任務資料內容改變，不能把固定檔數說成嚴格固定bytes，也沒有推翻既知out.log可無界的限制。

延遲只取各checkpoint最後一回合的tick_at→tock_at：空任務各批中位數約77～107.5ms、最大198ms；含任務各批中位數34.5～43ms、最大55ms。不是所有回合的p99，也不是設定1000ms正常節拍的偏差測試。各node完成checkpoint時間已存JSON，可看負載下的離散程度；未觀察到某條時間線永久落後。

CPU取daemon的/proc/stat自身與已wait子程序累計；含任務未完整計入脫離tick父子關係的runner與其子任務。空任務平均約用14.9個CPU核心，每個node回合約98ms累計CPU，顯示每回合兩個Python程序的成本仍高。這是本機零間隔壓力測試，不能拿吞吐直接承諾別台機器或重型任務的延遲。

**uncertain並非故障誤判。** 42筆都是each出生交接時的LIVE＋unsure「剛起」，之後正常前進；未見持續未知或人工卡點。但若監控把uncertain非空就當告警，會產生正常流程的雜訊。200ms輪詢與status自身快取也表示「空任務零觀察」不等於所有瞬間都無未知。短跑校準另保留[50×100](2026-10-04-astra-2-infra-evidence/load-empty.json)及[10×100含任務](2026-10-04-astra-2-infra-evidence/load-tasks.json)，不混入正式長跑數字。

這是千回合／數分鐘量級的負載驗證，不是數日耐久性測試；足以確認目前固定工作集合不隨回合加檔，不能證明所有故障路徑有界。A3-07正是健康負載看不出的反例。

## 六、A3 新問題

### A3-01〔bug，高〕restart完成證據隨普通keep換run消失，同一意圖再殺再起

`aos7_task.run_ctl`只查目前birth及pending once的ctl_id；寫回條後unlink失敗被吞，ctl-done不參與去重。O/restart.ctl_unlink_denied_birth_reused在ctl-done提交後暫chmod槽0555，讓**真os.remove回EACCES**，再還原權限。這是精準時序注入，不是偽造回傳；原始碼未改。

唯一請求id:one-request先使run2由run1重起。run2完成後，tick3在去重後正常起keep run3，新birth沒ctl_id；tock3又讀到未能刪掉的同一請求，真殺run3，再起run4。run2與run4都帶同一ctl_id，後者restart_of=o#3。run3刻意是sleep60，證明它是被舊意圖中止，不能用「keep本來就會重起」解釋。

應保存不隨普通run覆寫的完成意圖證據，並讓消費失敗可觀察；矩陣需覆蓋完成後仍留ctl、跨一次以上槽重用。這是A2-05核心保證仍未封口。

### A3-02〔技術選型，高影響〕environ EACCES例外使不可ptrace任務脫離不雙開保證

D/real-environ-eacces-before-pid：任務保留AOS7環境、真EACCES13；runner在Popen後／pid.json前真SIGKILL，tock報k#1 lost，next tick起k#2，兩PID同活。spec §11雖已接受此範圍縮限，§5.4「舊的一定收掉、不會雙開」必須帶同樣限定。

目前只適合持續可辨識身分的合作式任務。若未來要支援會降低dumpable或變更credentials的工具，需更可靠的出生／所有權機制；不能靠跳過EACCES完成廣義不雙開承諾。無須把正常主機所有EACCES一律升成全域UNKNOWN，但必須分清無關程序與自己尚未完成交接的程序。

### A3-03〔技術選型，高影響〕非一般檔一概視為不存在，繞過round／birth的新保護

X/nonregular_birth_live_task以真FIFO取代健康keep的birth，judge直接EMPTY，tick起k#2，舊k#1與新k#2都活。X/nonregular_open_round以FIFO取代開著的r2；tick從last-round r1接號，重新開r2並覆寫原回合。

根因是`read_json3`把非regular檔回MISSING，birth與round再把MISSING當空／新空間。這是既有明定契約的代價，不是假裝原JSON半寫修復沒有效。防FIFO阻塞應保留，但「能非阻塞拒絕讀取」不等於「檔案不存在」；生命週期檔應把錯誤型別帶成BAD/UNKNOWN，與可忽略的控制垃圾分開。矩陣只擴JSON內容種類仍抓不到這一類。

### A3-04〔bug，中〕明確請求id靜默截64字，不同意圖變同一件

O/restart.long_ids：`x×64+0`與`x×64+1`是兩個不同id，`ctl_id_of`卻都回同一個64字前綴。第二次restart回已處理、未執行；不是SHA1機率碰撞。規格沒有64字限制。應保留／雜湊完整id，或明確拒絕超長，不能靜默截斷。

### A3-05〔技術選型，中影響〕內容＋mtime不是唯一意圖，且去重作用域未定

O/restart.same_mtime的兩份不同inode新請求，在保留mtime後被當重播，只有第一次生效。cross_slot_ids同內容同mtime的兩槽請求只重起o；p回條ok:true稱已加過，實際沒有p的once。pending查重只比cid，不比slot。使用相同explicit id跨槽也有相同結果，但規格尚未界定id須node全域唯一，不把那一項單獨放大成額外bug。

應明定「新請求／重送原請求」的id契約，CLI主動產生新id、重播保留原id，並界定node/slot命名域。新mtime控制組正常，不能籠統禁止同內容連續restart。

### A3-06〔bug，中〕owner到檔名的有損編碼仍可覆蓋不同控制者

X/owner_encoding_collision：甲與乙均寫成`cli.pause.a@_.json`，daemon未起前送兩份，最後paused只有乙；A/B與A+B、x?與x!也碰撞。新`@owner`只修ASCII安全字元的原案。應使用可逆編碼或對完整owner加入穩定雜湊；同理檢查by/node編碼，而非逐一補特例。

### A3-07〔bug，中〕mount子目錄的dot tmp漏清，長命run仍累積

[storage-nested-crashes.json](2026-10-04-astra-2-infra-evidence/storage-nested-crashes.json)：真keep run1內，mount-done回條replace前殺5個tick、官方mount.request的replace前殺5個寫者，10次rc=-9；後續健康10回合仍留10個tmp。現sweep只到`.aos`、槽頂層與daemon幾個目錄，沒到mount-req/mount-done。

把這兩個已知基礎設施子目錄納入死寫者清理即可；不建議遞迴刪任務自有檔。正常長跑檔數固定不能證明所有故障路徑無累積。

### A3-08〔bug，中〕重播通知失敗被吞，關回合後無法補同一通知

X的兩個replay_*真EACCES案：tock提交總結後SIGKILL，重播時讓birth讀不到或槽不可寫；回0/replayed、round.close，卻無tock.json、notify_errors與summary.errors。恢復權限後再tock只回already closed；counter仍活、count0，直到r2才加到1。另[真EISDIR對照](2026-10-04-astra-2-infra-evidence/notify-replay-error.json)證明正常收尾有notify_errors，重播卻沒留下。

正常路径已接受通知寫失敗仍關回合，因此本項不要求無損歷史或一律停整個node；至少重播應留下與正常路徑一致的失敗紀錄。若要提供重試，需定義尚欠通知的持久狀態，不能宣稱只要權限恢復就會自動補同一回合。

### A3-09〔bug，中〕已知任務仍活、群組身分無法核對，kill卻回成功

D/real-environ-eacces有有效pid/starttime的活任務，runner死亡後，kill_identity不承認其pgid便不送訊號；groups空時仍回True。回條同時寫ok:true與「pgid不是這個任務的群組，沒動它」，tock.alive仍k#1。即使接受A3-02的管理範圍限制，回條也應回無法確認／未完成，不能說收乾淨。

**本輪不新增「要使用者決定」條目。** 明確bug已有可驗證的修復方向；EACCES、非regular與mtime屬既有技術契約的代價，已把選型與實作缺陷分開。若要擴大到跨uid／不可ptrace任務，再另定支援範圍，不把每個bug改成政策投票。

## 七、重跑與清場

從副本根目錄執行；各腳本把TMPDIR放在本evidence自己的工作目錄，finally按記錄PID／PGID收程序再刪空間。沒有使用pkill，也沒有建立副本外/tmp測試目錄。代表性入口如下；其餘補測腳本亦可直接以同樣環境執行：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-2-infra-evidence/regression.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-2-infra-evidence/once-regression.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-2-infra-evidence/daemon-review.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-2-infra-evidence/matrix-extra.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-2-infra-evidence/matrix-hook-audit.py
```

清場明細：[once-cleanup.json](2026-10-04-astra-2-infra-evidence/once-cleanup.json)、D/_cleanup、各storage/load結果cleanup欄，以及[final-cleanup.json](2026-10-04-astra-2-infra-evidence/final-cleanup.json)。最終稽核包含程序、殘留目錄、證據JSON/Python語法、報告連結及指定產出以外的異動；執行環境自動更新的既有log.txt另行辨識，不當成測試腳本改產品。

## 總評

正常路徑、原EIO傳遞、JSON schema、owner倒數、登記symlink與history順序已經收斂。未知也大多正確限制在相關槽，不是處處把整條時間線停死。這輪確實比上一輪穩定，不需要退回更重的核心歷史設計。

但A3-01的完成意圖會被槽重用抹掉、A3-03把錯誤檔案型別當空、A3-02的身分可見性例外，仍會直接改變執行次數與程序生命週期。它們不是只補提示的邊角。應再做一輪聚焦回歸：先修控制完成證據及ID、修生命週期檔案的非regular判定，明確框住可管理程序範圍；把本輪失敗組合固定後再接kernel。kernel的純用量契約／取樣下界測試可以先寫，但正式排程與cap不宜建立在目前這些仍可雙開或重播的路徑上。
