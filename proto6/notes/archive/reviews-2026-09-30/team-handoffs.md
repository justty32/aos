> 封存 2026-10-02：09-30 審稿與第十八～二十批（含 cgroup／git）改寫計畫、交接、核對報告，批次已結束；結論已由 proto6/spec（settled/ 與 settled/deferred/）與裁定紀錄 proto6/notes/verdicts/09～11 吸收

← [審稿索引](README.md)

# 第二階段各隊回報的交接（主對話彙整）

## T6（完成）
- 交 T3：P-205 補 `aos-tick unclaimed` 的 commit 訊息格式（建-5 另一半）；裁定14 若 P-716 要把 `.stdout` 納入清理，句子交 T6。
- 交 T2：P-105 寫出 `once.clear` 的回應形狀（CLI 目前印 `cleared N`）。
- 交 T1：H-004 總數 57。V-03 驗收句：
  - `aos node tick` 經 daemon：送 wake 後看到 `tick_seq` 變大才回 0；逾時回 101；paused 回 1 不等。
  - `aos work trace` 用請求 ID 或 attempt ID 都查得到同一件工作；讀不到的站標「看不到」不回錯；全找不到回 1。
  - `aos once clear N` 只清 N 整棵子樹下已結束且呼叫者有權清的 once 紀錄，在跑的不動。
  - 帶 `in_reply_to` 的回話過保留期被清，仍有引用就保留，agent 序號不倒退。
  - agent 任務表任一項帶 `user` 整份拒收；agent 設定多一個不認得欄位照樣讀進。
- 疑點：aos-clean 範本 kind 仍是 custom（A 改 system／B 維持、只靠 B-626 算基底）；`aos migrate` 形狀（A `aos migrate N`／`--daemon-config F`／`--dry-run`；B 拆 `migrate node`／`migrate daemon`）；預設鬧鐘 agent 看不到（歸 Q26 延後）。

## T4（完成）
### 交 T3
B-203（取消的行為正本）建議全文：
「只適用 once；kernel／agent／custom 類任務的取消延後（P-008）。入口 `work.cancel`（格式見 P-411）。
核權：取消請求檔的擁有 UID 等於下列任一就收：原請求檔的擁有 UID（接件時記下）；node 根目錄的擁有 UID；該 node inst 的執行帳號 UID（接件時記下；once 自己 inst 的 user 不算）。都不是就回 `cancel_not_authorized` 並丟掉這份取消。在 T-08 之下這只是防手滑，不是安全界線。
排隊中（還沒建 launch-started）：直接拿掉，原請求回 canceled、`started:false`，不開 once。
在跑：本格只記 `canceling` 並提交；下一格才請 daemon 對那個 once 收尾（B-604），那一格可同步等到全空，上限 `shutdown_grace_ms`；等不到記 unknown、保留占用。
三個窗口：(a) unregister 回 `not_registered` 時，要有 S-401 的可信「從未開始」證據（marker、`.err`、result）才回 canceled，否則 unknown；不靠會被淘汰的 once 診斷紀錄。(b) 記 canceling 與 unregister 分兩格。(c) 以「記 canceling 那格提交」為界：之前已有完整結果照原結果回；之後正常結束、完整發布的也照原結果；之後因 TERM 才寫出的 signal 結果記 canceled。
已結束或已回過結果的不動。」
其他：驗收沿用原 P-411 另加「兩種主人帳號不同時各送一次都收」；P-306 表取消列縮成一句連 B-203；P-606「unknown 估計占用隨清理」改「釋放時間依 S-304，資料保留依 P-606」。
### 交 T5
- S-401 吸收從 P-402 移出的證據句：已有 marker 先查證不重派；讀到 `.err` 先核對本次目標與可信 daemon 寫入來源再合成 `started:false`／failed／`start_failed`，不把自報旁檔當證據；LLM wrapper 沒啟動可合成 failed／`not_sent`；其他只看 result.json——wrapper exec 126／127、崩潰、自回 125 卻無結果，都不能只靠登記消失推定內層沒跑，缺可信證據就 unknown；兩份證據矛盾都保留並報事項。
- kernel-work-state schema 加可選欄 `attempt_allocator`（NodeId，省略＝材料 node_id）、`owner_exec_uid`（接件時記下的 inst 執行帳號 UID）。
- kernel-llm-limits 每個 scope 加可選欄 `unknown_hold_ms`（省略＝該請求 timeout_ms，0＝unknown 不占份額）。
- P-505、P-809、P-811、P-814「估計占用隨 P-606 清理」改「釋放依 S-304」；P-505 末段改「上層份額只對經上層轉交的請求有效」（裁-13）；P-505、P-813 兩條路線表縮成一句連 S-301；P-814 註明只裝 pool 不裝 forward 時 pool 要宣告 `llm.chat`（S-307）；P-806 取消句連 B-203、「殺掉」改「收尾」、前綴改「配出者」；S-102 取消段連 B-203。
### 交 T2
runner-report 的 signal 改 1～64；B-606 保持 P-402 的登記參數語意。
### 交 T1
T-03「attempt ID 由發起 node 自己配」改「由配出它的 node 配：一般是發起 node，LLM 池限流重試由池配（P-402）」；P-008 裁-5 那列補下一輪要加的欄位（forward-state 與 agent 請求的 `submitter_uid`、`canceling` 階段）；P-009 llm-work 列正本改 S-301～307。
V-03：取消兩種主人各送一次都收、他人回 cancel_not_authorized 原工作照跑；記 canceling 那格不 unregister；not_registered 無可信證據記 unknown、canceling 前已完整照原結果；純池 node 宣告 llm.chat 直投收得到、無人宣告回 -32601 原件被清鬧鐘不響、投給沒被 tick 的 node 堆著鬧鐘到期報錯；下層自建池不扣上層份額；斷線後本機名額立刻還、unknown 份額到 timeout_ms 才還、池狀態兩數分開、工作仍 unknown 不重送；池重試第二次目錄前綴是池的雜湊、request.json node_id 仍是發起者；改 llm-pools.json 後已派出嘗試仍用 W/llm-config.json；llm-config 帶 api_key 拒收、多欄位照收；work-result signal 65 拒。
### 交 T6
`aos work cancel` 說明註明目前只有 kernel work 支援、行為連 B-203；llm-messages 放寬後 agent-history 也收未知欄位。
### 疑點
unknown 份額預設何時還（a timeout_ms 暫定／b 固定時間／c 預設不占），欄位放 kernel-llm-limits（暫定）或 llm-config；池 HTTP once 的 parent_id（a 池 node 自己／b 維持發起者／c 池所屬 kernel 決定）；messages 未知欄位（a 忽略不送 HTTP 暫定／b 原樣轉）；重試 attempt ID 格式（a 池自訂／b 固定 `<原ID>.r<n>`）；取消同步等收尾超時（a 記 unknown 暫定／b cleanup_failed）；`W/llm-config.json` 為新加布局檔（建議預設）。

## T3（完成）
### 交 T1
P-010 可縮殘根；P-004「壞件怎麼處理見 tick」改「壞件只報一次見 B-623」；C-03 補「重送與補投見 B-503」；P-008 延後清單 Q26 列「標在哪」加 B-624；P-009 node 列行為正本加 execution（B-202）。
V-03：daemon 框外直接跑 `aos-tick` 回 2、不取鎖不改檔不開任務，經 `node.wake` 那格看得到 `tick_seq` 前進；同一壞收件連跑多格只一件事項、過保留期由 aos-clean 刪、期內留著；同 ID 重送補投的回應是 git 歷史裡原待送回應的原 bytes；本地動作回應 `stdout.path` 指向存在的 `.stdout`；根目錄擁有者與 inst 執行帳號不同時兩者取消都收、once 自己 user 被拒；任務吃滿 node 記憶體、tick 被 OOM 殺後 daemon 仍能清空 `tick` 與 `task-*`；斷電模擬 commit 成功後才刪原件、重開後物件與 ref 都在；沒人宣告的 method 回 -32601、有宣告但未授權回 -32000。
### 交 T2
B-605：git 2.35→2.36；「任務層」段縮成一句連 B-202；加逃生口段；「沒 quota 就定期掃資料夾」改「由磁碟資源任務定期量（B-304、S-203）」。B-603「逃生口以後再設計」改指 B-605。B-604「具體收尾見 B-203」改「取消在跑的 once 也用這套收尾（B-203）」。P-107「收尾程序留在成員限額外」改成只指 daemon 與 helper。B-609 清單要有「刪殘留框」（B-303 已列）。`node.show` 的 `last_tick` 要有 `tick_seq`、`registration_id`（B-627 靠它）。建議 P-601「每 1000 ms 批次寫出」搬進 B-607。
### 交 T4
P-411 核權與處理縮成一句連 B-203；接件時記下的執行帳號要有欄位存（與 T5 的 P-806 協調）；P-403 本地動作 stdout 不填 null，指向 `state/messages/requests/<id>.stdout`；P-400～403 行為句改引用 B-101／B-103。
### 交 T5
P-814 範本 check 從 system 改 kernel；清理遍歷納入 `.stdout` 與過期壞收件；P-806 取消改引用 B-203；S-202 加「失聯多久算、失聯時做什麼由父 kernel 自定，預設寫一件事項，不跨層代管孫輩」；P-804 寫清掃描間隔是資源任務的設定。
### 交 T6
H-004 第 17 列 `aos node tick N` 改送 `node.wake` 等 `tick_seq`（B-627），alias 一起改；P-716 清理遍歷納入 `.stdout` 與過期壞收件；H-034 連 P-008；H-036、A-201、H-030 分別改指 B-202、B-623／B-624、B-501；建-5 在 commands.md 的部分（任務表摘要補 methods、布局補兩檔）。
### 疑點
aos-clean 範本 kind（a 維持 custom 排最後、程式認定是基底 暫定／b 改 system 會排最前）；壞收件事項格式（a issue_id `bad-request-`＋檔名雜湊、reason `bad_request`、新欄 `reported_at_ms` 暫定／b 用原件 mtime 起算不加欄）；`.stdout` 位置（a 跟請求副本放 `state/messages/requests/` 暫定／b 另開目錄）；接件時記下的執行帳號存哪（a 工作狀態加 `owner_uid`／b 旁檔）；B-627 讓原型 test_tick.py 13 案例失敗（a 測試專用隱藏旗標／b 全改經 daemon）。

## T3 第二次回報補充（已落 B-203、P-205 unclaimed 格式）
- 交 T6 追加：P-716 清理遍歷加「本地動作 `state/messages/requests/<id>.stdout` 跟同 ID 請求副本一起清；過保留期的壞收件原件（有 `bad_request` 事項、從 `reported_at_ms` 起算）也列入候選」；P-704「手動跑完整一格用 `aos node tick N`」連 B-627；H-034 git 歷史回收標延後；P-706／P-715 每個請求預設帶鬧鐘。
- 交 T5 追加：S-202 或 P-803 補「aos 只提供 `observed_at_ms` 與 `last_tick`；多久沒更新算失聯、怎麼處理由父 kernel 自定，預設寫一件事項，不跨層代管孫輩」；P-506、P-804 沒 quota 時由磁碟資源任務定期量，間隔是該任務設定，只量直接成員。
- 交 T4 追加：P-403 註明本地動作 `result.stdout` 指 `.stdout` 檔、不填 null。
- 交 T1：V-03 另加「範本任務表沒有 system 類也能正常跑；kind:"agent.review" 照收、`system.x` 或帶 `user` 整份拒收」。
- 疑點追加：補投時 git 歷史已被合併提交整理掉（a 當證據已清照保留期 暫定／b 合併提交必須保留待送回應）；任務表壞了的事項 reason（a `config_invalid` 暫定／b 新增 `tasks_invalid`）；壞件保留期起點多一個選項 c 永遠不刪只報一次。

## T2（完成）
### 交 T3
B-303 helper 動作清單改指 B-609；B-202 驗收加「node 自開子框不算任務殘留，照 `kill_escape_cgroups`（B-605）」；B-302 加「改 cgroup 限制值不算中途換資源範圍（B-609）」；P-208「群組由有權者配置」改指 B-609 的 `group_create`、`group_add_member`、`chgrp`；P-601 批次寫出句縮成連 B-607；`registration_id` 在 node.show 回應最上層、不在 `last_tick` 裡；判斷新格做完加條件「`outcome` 不是 `running`」，並以 wake 回應裡的值為起點（B-627 相應修正）。
### 交 T5
P-803 與 `kernel-schedule-state`：wake 時記下 wake 回應的 `registration_id` 與 `tick_seq`，取代 `wake_after_end_ms`，判定照 B-607；P-802「不自動殺工作」改「kernel 移除成員時不對忙碌成員主動發解除、留待維護」，換父時舊父先把成員拿掉；P-504、P-804 刪「全空才改」改指 B-609，調低上限紀錄寫 kernel 資源狀態檔（Q17）；P-501、P-801 加「頂層額度檔只是分配政策」（B-605）；P-813 多帳號群組改指 B-609；P-806、P-800 取消時同步等解除到全空，上限 `shutdown_grace_ms`；P-812、P-814 重啟句改指 B-603；排空時新 once 被拒回 `stopping`，那件工作留在待派出。
### 交 T6
H-004 第 11 列「排空」改「收尾」指 B-606；pause 批存刪「每秒」指 B-603；新增 `aos once clear N`；`aos node tick N` 用 wake 回應的 `tick_seq` 當起點；熱重載只在說明寫 `kill -HUP`；H-036 與走查的 git 2.35 改 2.36。
### 交 T1
P-008 已裁定段「照 daemon P-104／110」改「B-606、P-110」；V-01 第 05 列收尾範圍加 `once-*`。
V-03：不同 socket 指向同一或重疊 `cgroup_root`／`state_dir`，後啟動的回 125 拒絕、先啟動的不受影響；`stop_mode:"drain"` 收 SIGTERM：新 once 被拒、已登記 node 照常開格、在途做完回 0，超 `drain_timeout_ms` 或再按 Ctrl-C 改立即停；SIGHUP 後改 `interval_ms`、加只用通用 user 的 root 立即生效，改 `socket_path` 或其他帳號額度時其餘照套、這些回報要重開，壞設定整份不套、舊設定照跑；換父：子樹沒停或新父在被搬子樹裡被拒、只是一方父 owner 被拒、搬好後框在新父下且 `registration_id` 換新；取消在跑 once 寬限後被殺、框被刪，重啟逐層重建完仍沒人登記的空框被刪、重建途中不先刪；node 自開子框預設重啟與解除後程序還在，`kill_escape_cgroups:true` 被清空；多帳號下兩 node 帳號靠 `group_create`、`group_add_member`、`chgrp` 交接檔案，有程序在跑時也能調低記憶體上限且立即生效；前綴規則比不中 UID<1000，子額度寫了父沒有的前綴或更大範圍被拒；已解除 once 紀錄超容量或保留期消失，`once.clear` 帶父 node 清整棵子樹已解除紀錄、別人的不動；git 低於 2.36 啟動報錯。
### 疑點
加列舉值算不算升版（a 本輪未發布維持 version 1 暫定／b 升 2）；多帳號建框缺口（a helper 建框再把上限檔交 daemon 暫定／b 委派時框設群組可寫）；wake 回應多 `registration_id`、`tick_seq`（a 保留暫定／b 拿掉只用 node.show）；沒 helper 時改 provision（a 一律重開暫定／b 沒 helper 時即時改）；「逐層重建完」判準＝所有沒暫停、非 once 的 node 自本次啟動都至少跑完一格（建議預設）；排他鎖（a 對目錄 flock 再上下試鎖、同時啟動互為祖孫可能都拒需重試 暫定／b 中央鎖檔）。

## T5（完成）
### 交 T2
`registration_id` 假設為 common 的 `ID` 字串（型別若不同告訴 T1 對齊）；`node.wake` 回應帶 `registration_id` 與 `tick_seq`；若補 `RegistrationOpen` 定義，`kernel-sync-state` 可改引用（目前內嵌開放版）。
### 交 T3
B-620／B-621 不再說範本用 needs 串任務（範本 needs 已全清）；B-302 補「改上限值不算中途換資源範圍」；B-404 列入 `state/kernel/sequence.json` 不清；P-601 行為句可縮成連 S-405。
### 交 T4
P-811 的窗口與 token 估算規則搬到 S-302／S-303，搬好後 T5 縮 P-811（主對話會處理）。
### 交 T1
P-009 resources、kernel-tasks 兩列正本補 S-205、S-206、S-406；P-008 延後表「agent 之間的問答」「標在哪」加 S-406。
V-03：工作在途弄壞父配額或資源任務失敗，仍收結果、接受取消、不開新工作；有程序在跑時調低記憶體上限直接寫入不等全空、資源狀態檔留 `over_limit`；頂層額度改到小於已分出合計不自動收回、記 `over_allocated`、寫事項、停新派工、在跑照跑；上層收小身分額度，重登被拒的成員只隔離那一項並記事項、其他照常；成員跑完一格摘要沒變牆鐘倒退，kernel 仍靠 `tick_seq` 認出新格，daemon 重啟 `registration_id` 換了 kernel 重新核對不空等；中間 kernel 停格，父 kernel 過 `member_stale_ms` 寫一件事項不重複、不碰孫輩；投給 kernel 的 `agent.say` 記進 kernel history、序號遞增、listen 讀得到、kernel 不回話、清理後序號不倒退；兩 kernel 各登記自訂資源名，上層不認得不報錯、配額檔帶自訂資源照收；範本任務表一項帶 `user` 整份拒收、kernel 持久檔多欄位照收；乾淨停機後 once 仍登記且 `last_tick` null 可第一次叫醒，意外重開無結果無 `.err` 記 unknown 不再啟動；父配額公開檔在期望配額提交後下一格才發布。
### 疑點
範本 needs 拿掉多少（A 全拿 暫定／B 保留 resources、schedule 對 members 的依賴）；Q8 超分擋什麼（A 整個 kernel 暫停增加占用的新派工 暫定／B 只擋配額增加的成員／C 只寫事項不擋）；失聯判斷（A 只看被叫醒後格次有無前進、預設 10 分鐘 暫定／B 也看有週期成員／C 預設不判斷）；自訂資源名格式（A 不限、只禁拿範本六類名字換形狀 暫定／B 比照任務種類「前綴.名稱」）；調低上限 `over_limit` 記哪些（A 只記憶體與 pids 暫定／B 三種都記）。

## 主對話追加給 T1（收尾）
- P-009 對照表：kernel-tasks、resources 列正本補 S-205、S-206、S-207、S-406；llm-work 列正本改 S-301～307（S-302 新增「份額扣在誰身上」「池的共享窗口」）。
- T6 的 H-004 總數 57。
- B-627 已對齊 B-607（registration_id 換了＝重新核對、不再等）。
- 若 V-01 正本表與實際落點不符（例如 P-809、P-810、P-502、P-811 已縮成連結、S-207 新開），更新表。
