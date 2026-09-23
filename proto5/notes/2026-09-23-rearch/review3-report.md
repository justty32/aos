## 1. 總評

**還不能當完整實作契約；本輪有 9 條「擋」。**
chain 固定在 request、工作結果一次入帳、先查原單再查回音，確實修掉第二輪主要競態。
剩餘阻塞集中在：syscall 重掃、rm once、stop 跨世代重送、單主人交接，以及 daemon 的 spawn／restart 邊界。
「出貨箱可以重送」對一般回音成立，對停止另一個行程的 stop 不能直接套用。
全程唯讀；以下接受全部已拍板前提，為文件與時序審查，未執行會寫檔的測試。

## 2. A 驗收表

「已解」只表示該條原問題已解，不表示整條流程完全無洞。

### CPU、kernel

| 項目 | 判定 | 差異／剩餘問題 |
|---|---|---|
| C2-1 | 已解 | 明訂刪 response → 刪 ack，ENOENT 成功，可重入。 |
| C2-2 | 已解 | 禁止不同工作重用運輸名；唯一性由交件者負責。 |
| C2-3 | 已解 | 對帳表補 notification，改成「可能停在哪」。 |
| C2-4 | 已解 | 取單前重查停止旗標；自然完成與強停的截點已定。 |
| C2-5 | 已解 | 對帳失敗退 1；固定間隔、無上限重拉及永久故障行為已明訂接受。 |
| C2-6 | 已解 | 壞 JSON／壞信封與合法 notification 已分開。 |
| K2-1 | 已解 | chain／seq 固定在 tick request 的 args，不再經可變 tick.json。 |
| K2-2 | 已解 | 後繼取自本格 args 的 N+1，不會因帳本序號落後而撞自己。 |
| K2-3 | 部分解 | 停舊 CPU 的方向成立；daemon 快照、並行 boot、kernel CPU 熱改仍破壞交接，見 K3-4、K3-5、X3-1。 |
| K2-4 | 已解 | 正常跨 boot 的 tick／工作名不再因序號重設而重複。 |
| K2-5 | 已解 | 查檔順序符合 CPU 發布順序；ack 又受帳本提交約束。 |
| K2-6 | 部分解 | 單次 syscall 已原子化，但可被 rm 刪掉的 procs 不能充當完整去重紀錄，見 K3-1。 |
| K2-7 | 已解 | 政策、終局決定、pending、CPU ack 同次入帳，舊多檔提交縫已消失。 |
| K2-8 | 已解 | 已記未放可直接取消，不必再靠已刪政策補派；once 的取消回覆另見 K3-2。 |
| K2-9 | 部分解 | queued once 會回 Stopping；stopped 後新 request／ack 的接手仍未明訂，見 K3-6。 |
| K2-10 | 已解 | 工作 cpus 表排除 kernel CPU；tick 回音有獨立流程。 |
| K2-11 | 已解 | runs／fails 更新已逐列明訂，獨立 aos 計數已移除。 |
| K2-12 | 部分解 | boot 驗證點、空池及移除 worker 的在途處理已補；kernel 池身分熱改仍不安全，見 K3-4。 |
| K2-13 | 解法引入新問題 | 非 0 才 restart、stopped 與 stops 同次提交有效；但補送舊 stop 會停掉新 CPU，見 K3-3。 |

### 跨層、說明

| 項目 | 判定 | 差異／剩餘問題 |
|---|---|---|
| X2-1 | 已解 | args 未給就不存、不送；`[]` 與缺鍵仍區分。 |
| X2-2 | 部分解 | CPU 已明說收下不代表等待；aos-exec 仍宣稱缺檔日後出現會自然跑，與新 daemon 不符。 |
| X2-3 | 部分解 | spawn 已有 NameTaken；kernel 動態補 CPU 卻可能跳過 spawn，見 X3-2。 |
| X2-4 | 部分解 | CPU 承認 timed_out API 缺口，但仍只有「實作要補」，見 X3-4。 |
| X2-5 | 已解 | CPU 高位 fd 的 CLOEXEC、daemon 的端點隔離都已補。 |
| R2-1 | 部分解 | 正文 target／base 已改善；CPU 名詞表與 daemon 的 inst 用語仍有殘文，見 R3-1、R3-2。 |
| R2-2 | 已解 | 對帳表不再把觀測狀態說成唯一歷史。 |
| R2-3 | 部分解 | 原子提交點已展開；當格新增出貨箱的出貨時機與例外仍含混，見 R3-4。 |
| R2-4 | 部分解 | 前綴規定已統一；本輪已拍板內容仍混在待確認項，見 R3-5。 |
| R2-5 | 已解 | K 的 ack、工作 CPU ack、tick ack 已有各自入口。 |
| R2-6 | 部分解 | FIFO 誤稱已撤；ls 的讀取範圍仍不足以支撐所述斷鏈診斷，見 R3-6。 |

### 第二輪 D 清單

| 題 | 判定 | 差異／剩餘問題 |
|---|---|---|
| D-1 | 部分解 | flock 解決 daemon 重複啟動；接手仍漏未入表孤兒，見 D3-1。 |
| D-2 | 部分解 | 孩子表持久化已定；fork 成功至寫表之間仍可能完全沒有 PID 紀錄。 |
| D-3 | 部分解 | target 衝突已定；dir_target／restart 不同的等價規則未定，見 D3-3。 |
| D-4 | 已解 | 名字作用域明訂為整個 daemon。 |
| D-5 | 部分解 | spawn 的 running／dead／killing 分支已列；dead 收 kill 缺終局，見 D3-2。 |
| D-6 | 部分解 | 非 0 與主動停止優先已定；到期 dead 分支仍可能在 stopping 中重拉。 |
| D-7 | 已解 | 固定節流、永久故障、無退避／上限都已明訂。 |
| D-8 | 已解 | 每次重讀 target；重拉失敗記 log、等待再試。 |
| D-9 | 部分解 | 正常只 waitpid 自己的孩子；接手用 kill(pid,0) 尚未區分「PID 存在」與「仍在執行」，見 D3-5。 |
| D-10 | 已解 | daemon／孩子端點與跨孩子隔離已明訂。 |
| D-11 | 已解 | CPU 搬高位並 CLOEXEC，工作 exec 後拿不到控制端點。 |
| D-12 | 部分解 | 非 stop、回程丟棄、EPIPE 已交代；半行與 SIGPIPE／阻塞讀寫邊界仍缺，見 C3-1。 |
| D-13 | 部分解 | 並行階梯已定；總預算公式及接手 TERM 的「第二次」假設有誤，見 D3-5。 |
| D-14 | 部分解 | kill 撤銷 restart 已定；dead→killing 仍可能永久卡住。 |
| D-15 | 解法引入新問題 | 宣稱會等未入表孤兒死透，但接手流程找不到它，見 D3-1。 |
| D-16 | 已解 | 已明訂不支援改綁交接，須先停舊 daemon；不是自動交接功能。 |
| D-17 | 部分解 | 操作順序已定；反序停機被錯誤概括成一律 Interrupted，見 R3-7。 |
| D-18 | 已解 | 檔案協議可套 current／對帳／ack；遲到 request／ack 留待下次啟動。spawn 副作用另見 D3-1。 |

## 3. B 三份及底層的一致性

**互引與名詞。** 確定錯引是 [cpu.md:62](/home/guanyu/projs/aos/proto5/spec/cpu.md:62)：kernel 命名法應指 **§1.3**，不是 §1.2。`killing` 是 daemon 單一孩子狀態，`stopping` 是 daemon 全域旗標或 kernel phase，正文沒有混用；「偷看」也一致是唯讀，但不能因此推導資料仍新鮮。

**三個根因解法的有效範圍：**

| 機制 | 本輪核對結果 |
|---|---|
| 先查原單，再查回音 | 成立。原單還在便等待；原單不在時，CPU 已先發布回音。kernel 未提交收件決定前不會送 ack，所以不能自行把證據刪掉。 |
| 第 6 步一次入帳 | 成立。每則結果的計數、狀態、queue、pending 回覆、CPU ack 與清 req 必須是同一次原子替換，不能拆寫。 |
| 一般 replies 出貨重送 | 成立。link 後未清帳便崩，下格第 4 步先重放、清帳，第 5 步才處理客戶 ack；不會單因這個窗口復活已消費回音。 |
| acks 出貨重送 | 指向同一個永不重用的工作名時成立；CPU 刪不存在回音是 no-op。 |
| stops 出貨重送 | **不成立於 CPU 換代後**。名字含 chain 不代表 CPU 會檢查 stop 的 chain，見 K3-3。 |

**跨 chain 接手。** 保留完整舊 `cpus.req`、`pending.name`、`replies.name` 是正確的；新鏈仍按舊名收回音，ack 可以用新運輸名指向舊工作名。不可把這些目標名改成新 chain。旧 tick 的 args 固定，確實會自滅；其回音由第 4 步統一 ack。前提仍是 **chain 本身唯一**，`epoch ns＋pid` 是生成慣例，不是歷史唯一性的證明。

**daemon 自己的家。** [daemon §3](/home/guanyu/projs/aos/proto5/spec/daemon.md:130)套 CPU current／對帳／ack，在檔案協議層成立：已發布回音保留，未發布補 Interrupted。但「副作用先於回音」只描述發生順序，**沒有解決 fork 與持久登記的窗口**；CPU 對帳不會替 daemon 找回未知 PID。

**普通檔 tick。** 依 [aos-exec 三種目標](/home/guanyu/projs/aos/proto5/spec/aos-exec.md:25)及 [CPU fd 搬移](/home/guanyu/projs/aos/proto5/spec/cpu.md:248)：

| 項目 | 結果 |
|---|---|
| stdin／stdout／stderr | daemon 啟動的 CPU 下，tick 繼承 `/dev/null`、cpu.log、cpu.log，不會吃控制 pipe。 |
| 環境 | 繼承 CPU 的環境，沒有額外的 tick inst 環境設定。 |
| cwd | 普通檔所在資料夾；因此 K 必須先固定為絕對路徑。 |
| exit 檔 | 沒有，但不妨礙 CPU 發 response。 |
| 無執行權 | 回 child/126；tick 本體未開始，沒有機會接後繼，見 X3-3。 |

**另兩處契約落差：**

- [kernel boot 第 4 步](/home/guanyu/projs/aos/proto5/spec/kernel.md:274)說每顆 CPU 建家並寫 info／inst，但第 2 步只停 kernel CPU；仍活著的工作 CPU 不能按 [§1](/home/guanyu/projs/aos/proto5/spec/kernel.md:73)被重新初始化。應明訂既有家只驗證／補缺，哪些情況才可改寫。
- [aos-exec.md:38](/home/guanyu/projs/aos/proto5/spec/aos-exec.md:38)的「缺檔之後出現就自然跑」與 daemon 首次 SpawnFailed 不登記矛盾；[aos-exec.md:105](/home/guanyu/projs/aos/proto5/spec/aos-exec.md:105)也仍把反覆執行交給已退休的 aos-run。

## 4. C 新機制與剩餘漏洞

### K3-1｜syscall 去重憑據會被另一則 syscall 刪掉

**在哪：**[kernel §2](/home/guanyu/projs/aos/proto5/spec/kernel.md:167)。  
**時序：**`z-add` 建立 X、成功回覆入帳 → 刪原單前崩 → 下格先處理排在前面的 `a-rm X`，刪掉 X → 再掃 z-add，`procs.X.request` 已不存在 → 重新建立 X。另 rm 提交成功後若原單殘留，重掃又會產生同名 NotFound 回音。  
**後果：**已 rm 的工作復活；同一請求可能得到不同終局。未命名 add 還可能重新分配 NAME。  
**建議：**保存已提交 syscall 的決定與待刪原單，直到清理完成；不能只靠可被其他 syscall 刪除的 procs 去重。  
**嚴重度：擋。**

### K3-2｜rm 在途 once，會丟掉 add 的終局回音

**在哪：**[rm 三分支](/home/guanyu/projs/aos/proto5/spec/kernel.md:172)、[discard 判定](/home/guanyu/projs/aos/proto5/spec/kernel.md:225)。  
**時序：**once 已派 → rm 設 discard → 結果抵達 → §4 先命中 discard、刪行程，不進 once 分支。另一條：once 已記 req 未放檔 → rm 直接清 req、刪行程，也沒有回 pending。  
**後果：**兩條都遺失原 add 的終局；stopping 還會因 pending 已消失而認為收完了。queued once 的 Removed 分支則成立。  
**建議：**取消決定與 pending 的終局回覆同次入帳，例如 Removed；在途 discard 之後只負責收掉 CPU 結果。  
**嚴重度：擋。**

### K3-3｜boot 補送舊 stop，會停掉新 kernel CPU

**在哪：**[出貨](/home/guanyu/projs/aos/proto5/spec/kernel.md:195)、[停機](/home/guanyu/projs/aos/proto5/spec/kernel.md:215)、[boot](/home/guanyu/projs/aos/proto5/spec/kernel.md:272)。  
**時序：**持久提交 stopped＋stops → 放 k 的 stop → 清出貨箱前崩 → 舊 k 消耗 stop、退 0 → boot 看見仍欠 k stop，再放一次 → 拉起新 k → 新 k 先掃舊 stop，立即退 0。  
**後果：**新鏈首格無人執行。chain 避免了名字撞用，沒有讓 stop 具備行程世代判斷。  
**建議：**stop 綁定欲停止的那一代；確認該代已死便結清，不能再向新代將接手的家補送。  
**嚴重度：擋。**

### K3-4｜熱改 kernel 池，破壞「所有格都在同一顆 CPU」

**在哪：**[info 熱改](/home/guanyu/projs/aos/proto5/spec/kernel.md:106)、[接鏈與 spawn](/home/guanyu/projs/aos/proto5/spec/kernel.md:187)。  
**時序：**kernel 池由 k 改為 s → 尚排在 k 的格讀到新 info → 第 2 步把後繼放入 s → 第 7 步拉起 s → s 開始下一格，k 上這格還在派工／寫帳本。  
**後果：**兩格並寫 K；原子替換只能保證單份檔完整，不能防止互相覆蓋與重複派工。  
**建議：**每條鏈持久固定 kernel CPU 身分；更換必須交接已保存的舊 CPU，再開新鏈。  
**嚴重度：擋。**

### K3-5｜兩個 boot 能同時通過交接

**在哪：**[kernel boot](/home/guanyu/projs/aos/proto5/spec/kernel.md:267)、[不重疊宣稱](/home/guanyu/projs/aos/proto5/spec/kernel.md:291)。  
**時序：**B1、B2 都看到舊 k 已死 → B1 寫 chain A、spawn、放首格 → A1 開始並通過守門 → B2 再用自己的舊快照寫 chain B 與帳本。  
**後果：**boot 與 tick 並寫；入場時檢查 chain 擋不了已經入場的 A1。  
**建議：**明訂 boot 的獨占交接邊界。若依靠呼叫者序列化，就明寫此限制，不能宣稱現有流程已保證。  
**嚴重度：擋。**

### K3-6｜boot 逾時不是「什麼都沒改」；stopped 也沒有回覆者

**在哪：**[boot 第 2 步](/home/guanyu/projs/aos/proto5/spec/kernel.md:269)、[stopped 早退](/home/guanyu/projs/aos/proto5/spec/kernel.md:188)。  
**時序：**boot 已投 stop → 舊 tick 超過 30 秒仍未完成 → boot 退 1 → tick 日後完成，CPU 才掃 stop 退出。另一條：kernel 已 stopped → 客戶再投 add／ack → 沒有 tick 處理。  
**後果：**逾時後舊鏈可能稍後停止；新 add 只能留檔，沒有人立即回 Stopping。tick 沒 timeout，交接等待沒有工作時長上限。  
**建議：**明說失敗後 stop 可能仍生效、不得繼續換 chain；stopped 後新單與 ack 明訂留待 boot，並交代停止期間接受的單在重啟後如何處理。  
**嚴重度：要修。**

### D3-1｜未入表孤兒，接手流程根本找不到

**在哪：**[daemon spawn](/home/guanyu/projs/aos/proto5/spec/daemon.md:116)、[啟動接手](/home/guanyu/projs/aos/proto5/spec/daemon.md:191)。  
**時序：**fork 成功，CPU 已開始工作 → children 尚未寫入便崩 → CPU 收 EOF，只做溫和停 → 新 daemon 查舊表，沒有此 PID → 同名 spawn 拉出新 CPU。  
**後果：**同一家兩個主人；新 CPU 可補 Interrupted，舊 CPU 還在執行並可能回寫結果。「§6.1 先等孤兒死透」沒有可用資料。  
**建議：**補孩子開工前的提交邊界，例如父端持久登記 PID 後才放行；未放行便失去父端者直接退出。僅記 spawn 意圖仍不足。  
**嚴重度：擋。**

### D3-2｜dead 收到 kill／stop，沒有完整狀態轉移

**在哪：**[method](/home/guanyu/projs/aos/proto5/spec/daemon.md:125)、[主迴圈](/home/guanyu/projs/aos/proto5/spec/daemon.md:139)。  
**時序：**孩子非 0 退出、dead 等重拉 → kill 改 killing → 收屍只處理 alive，重拉只處理 dead，兩邊都跳過。另一條：已 dead → 全域 stopping → 到期 dead 分支仍照文字重拉。  
**後果：**名稱永久 Killing，或停止過程反而產生新孩子；「主動停止贏過 restart」尚未落到所有轉移。  
**建議：**dead 收 kill／stop 時取消重拉並直接移除；每次實際重拉前重查 stopping。重複 kill 不重設既有期限。  
**嚴重度：擋。**

### D3-3｜同名 spawn 的等價鍵不完整

**在哪：**[daemon §3](/home/guanyu/projs/aos/proto5/spec/daemon.md:125)。  
**時序：**spawn `target=/jobs, dir_target=a.json` → 再送同名、同 target、`dir_target=b.json` → 回舊 PID。`restart=false→true` 也沒有更新或拒絕規則。  
**後果：**呼叫者得到成功，實際啟動內容／重拉政策卻不同。  
**建議：**明訂 target＋dir_target 的等價比較，以及 restart 不同時是保留、更新還是衝突。  
**嚴重度：要修。**

### D3-4｜daemon 重啟後，通常沒有「下一格」補拉 CPU

**在哪：**[daemon 啟動第 3–5 步](/home/guanyu/projs/aos/proto5/spec/daemon.md:191)、[kernel 補拉](/home/guanyu/projs/aos/proto5/spec/kernel.md:206)。  
**時序：**daemon 崩 → 新 daemon 等所有舊孩子死透，包含 kernel CPU → children 清空 → 等客戶 spawn。  
**後果：**後繼 tick 雖在資料夾，卻沒有主人執行；不能拿「每格補拉」證明會自行恢復。  
**建議：**明訂 daemon 重啟後需外部 kernel boot。重生 worker 也不是一律 Interrupted：未認領原單照常執行、已發回音保留、只有 current 尚無回音才補 Interrupted。  
**嚴重度：要修。**

### D3-5｜接手 TERM 不保證是第二次；等待與總預算也需修正

**在哪：**[daemon 階梯](/home/guanyu/projs/aos/proto5/spec/daemon.md:164)、[接手](/home/guanyu/projs/aos/proto5/spec/daemon.md:191)。  
**時序：**父端已死，但 CPU 尚未處理 EOF → 新 daemon 立即 TERM → CPU 把它當首次停止，只設溫和旗標 → kill_wait 到便 KILL。另舊 PID 已成殭屍時，`kill(pid,0)` 仍不能代表它在執行。  
**後果：**不能承諾 TERM 必回 stopped；也可能把等待 PID 消失誤當等待工作停止。殭屍與存在性檢查的差異見 [Linux kill(2)](https://man7.org/linux/man-pages/man2/kill.2.html)。  
**建議：**區分「EOF 已發生」與「CPU 已處理」；明訂接手可能落到硬砍的結果。按現有時間表，KILL 在 stop_wait＋kill_wait，CPU 的 2 秒寬限位於第二段內，不能又直接加成總預算。  
**嚴重度：要修。**

### X3-1｜D/state 的快照不足以完成 boot 交接

**在哪：**[kernel boot](/home/guanyu/projs/aos/proto5/spec/kernel.md:268)、[daemon state](/home/guanyu/projs/aos/proto5/spec/daemon.md:89)。  
**時序一：**D 寫 pid 非 0、alive=true → D 被 KILL → 檔案永不更新；boot 仍認定 daemon 活著，等待不存在的更新。  
**時序二：**k 非 0 退出，D 表為 dead、alive=false，等待 restart → boot 跳過停機 → D 同時重拉 k，舊 tick 可在 boot 換帳本前開始。  
**後果：**前者誤判活性；後者沒有交接獨占，可能與新 boot 並寫。正常退 0 又會從表移除，boot「等 alive=false」還缺少 absent 的成功條件。  
**建議：**分開 daemon 活性、孩子最後觀測、等待重拉及已完成交接。從未 spawn／正常移除的 absent 可直接處理；dead 等重拉不能視為已放棄該家。  
**嚴重度：擋。**

### X3-2｜kernel 動態補 CPU，會繞過 NameTaken

**在哪：**[kernel 第 7 步](/home/guanyu/projs/aos/proto5/spec/kernel.md:206)、[daemon spawn](/home/guanyu/projs/aos/proto5/spec/daemon.md:125)。  
**時序：**K1 已有活孩子 c → K2 熱加同名 c → K2 只看到 `children.c.alive=true`，不呼叫 spawn → 工作投進 K2/cpus/c。  
**後果：**K2 的家沒有主人，工作永遠在途；已拍板的 NameTaken 根本沒有被觸發。boot 全部 spawn 的路徑則會報錯。  
**建議：**偷看時同時比對期望 target；不同家立即 NameTaken，不能只憑同名 alive 認定就緒。  
**嚴重度：擋。**

### X3-3｜普通檔 tick 缺執行檔定位與路徑閉合

**在哪：**[kernel tick request](/home/guanyu/projs/aos/proto5/spec/kernel.md:189)、[aos-exec 普通檔](/home/guanyu/projs/aos/proto5/spec/aos-exec.md:29)。  
**時序：**`boot ./K` 把相對 K 放入 args → 普通檔以 cli 所在目錄為 cwd → tick 找錯家。另一條：cli/aos-kernel 沒 +x → 回 126，tick 根本沒開始。  
**後果：**boot 可以成功投首格並退 0，鏈卻未啟動；CPU 沒死，daemon restart 不會救。  
**建議：**明訂 cli/aos-kernel 絕對路徑由何處取得；K／D 先正規化；boot 驗證執行入口。seq 放進 args 時亦須是字串。  
**嚴重度：要修。**

### X3-4｜timed_out 仍未形成跨層 API 契約

**在哪：**[cpu result](/home/guanyu/projs/aos/proto5/spec/cpu.md:178)、[aos-exec API](/home/guanyu/projs/aos/proto5/spec/aos-exec.md:95)。  
**時序：**工作自行退 143，或 timeout 後退 143 → 公開接口都只回 `(143,"child")` → CPU 卻須輸出不同 timed_out。  
**後果：**不能只靠已定接口實作；引用 run_inst 的欄位也未涵蓋普通檔。  
**建議：**在 aos-exec 定義三種 target 共用的真實終止資訊，CPU 引用同一契約。  
**嚴重度：要修。**

### C3-1｜pipe 端點隔離已補，讀寫邊界尚未閉合

**在哪：**[daemon pipe](/home/guanyu/projs/aos/proto5/spec/daemon.md:108)、[CPU 控制輸入](/home/guanyu/projs/aos/proto5/spec/cpu.md:202)。  
**時序：**控制行只抵達半行，讀端等待換行；或 daemon 向已關讀端寫 stop，先收到 SIGPIPE。若採阻塞讀回程，沒有輸出的孩子也可能卡住主迴圈。  
**後果：**poll／停機期限可能失效，或尚未執行 EPIPE 分支便退出。pipe 是位元組流；無讀端寫入涉及 SIGPIPE／EPIPE，見 [Linux pipe(7)](https://man7.org/linux/man-pages/man7/pipe.7.html)。  
**建議：**明訂增量組行、EOF 殘行處置、不中斷主迴圈的 I/O，以及 SIGPIPE 策略。EPIPE 只證明讀端關閉，不證明孩子已死。  
**嚴重度：要修。**

CLOEXEC 對正常 exec 工作的隔離已成立；純 fork 階段仍有 fd 副本，應在 fork／exec 路徑關閉。工作 exec 完再生的孫子不會重新取得控制端點。CPU 被 KILL 後仍活著的工作，已是規範明列保證外，本輪不另列阻塞。

## 5. D 說明清楚度：R3

| 編號 | 發現與建議 |
|---|---|
| **R3-1** | [CPU 名詞表 base](/home/guanyu/projs/aos/proto5/spec/cpu.md:28)仍一概說「目標所在資料夾」；資料夾目標應是自身。命名導引 §1.2 改 §1.3。 |
| **R3-2** | [request 定義](/home/guanyu/projs/aos/proto5/spec/cpu.md:21)把所有 request 說成執行工作；[daemon 一句話](/home/guanyu/projs/aos/proto5/spec/daemon.md:8)又把三種 target 窄化成 inst。CPU 一句話加「工作 request」，daemon 改稱 target；kernel 一句話主旨清楚。 |
| **R3-3** | [req／在途／出貨箱](/home/guanyu/projs/aos/proto5/spec/kernel.md:34)與正文不完全一致：req 非 null 可是已記未放；出貨箱也可能已放未清。應稱「尚未結清」，別一律稱「還沒放出去」。 |
| **R3-4** | [所有檔從帳本出去](/home/guanyu/projs/aos/proto5/spec/kernel.md:13)、[所有出貨先記再放](/home/guanyu/projs/aos/proto5/spec/kernel.md:195)都有例外：接鏈先放後記、tick ack 不入箱。第 5／6／9 步新增 replies／acks 若統一留待**下一格第 4 步**，流程可行且停機會多等一格，應直接寫出；不要指向當格已走過的步驟。 |
| **R3-5** | [kernel §10](/home/guanyu/projs/aos/proto5/spec/kernel.md:315)仍把已拍板的 aos 計數政策列待確認；[daemon §9](/home/guanyu/projs/aos/proto5/spec/daemon.md:232)把 NameTaken 與作者選的同步 spawn 混列。另 kernel §4「三個計數」應改兩個。 |
| **R3-6** | [斷鏈診斷](/home/guanyu/projs/aos/proto5/spec/kernel.md:193)需要 kernel CPU 的 requests／current，但 [ls 契約](/home/guanyu/projs/aos/proto5/spec/kernel.md:263)只讀 K、D state。補讀取範圍，或明寫另行人工查檔。 |
| **R3-7** | [daemon 名詞表](/home/guanyu/projs/aos/proto5/spec/daemon.md:34)「訊號退出都重拉」漏 restart／主動停止條件；[先停 daemon 的說明](/home/guanyu/projs/aos/proto5/spec/daemon.md:175)及硬砍摘要也不能一概稱 Interrupted。應按 CPU 對帳表分情況。 |
| **R3-8** | [全部檔名帶 chain](/home/guanyu/projs/aos/proto5/spec/kernel.md:152)有未列例外：boot 使用 stop-boot-epoch；給 daemon 的 ack 命名也未列。應限定宣稱範圍，補全命名規則及 ack 序號 n 的配置範圍。 |
| **R3-9** | [daemon 孩子表「唯一記憶」](/home/guanyu/projs/aos/proto5/spec/daemon.md:22)、[沒有只在記憶體的東西](/home/guanyu/projs/aos/proto5/spec/daemon.md:94)說得過滿：restart 到期時間、階梯進度沒有列入 schema。應區分持久身分與可丟棄、重啟時重建的執行狀態。 |