# proto7-2 接下來可以做的方向

← [proto7-2](../README.md)｜[10-05 報告索引](reviews/2026-10-05/README.md)｜[證據濃縮](reviews/2026-10-05/evidence-summary.md)｜[問題與由來](problems.md)｜[回歸紀錄](play/README.md)｜**[第七輪思考素材](../../proto7/notes/thinking/2026-10-05-r7-material.md)**（給使用者深想用：現況一頁、六個大問題、[待決題速查](../../proto7/notes/thinking/2026-10-05-r7-decisions.md)）

10-05 整理自 15 份 astra 報告、[SESSION-LOG](../../wf/SESSION-LOG.md)、[WAIT_USER](../../wf/WAIT_USER.md)。**只整理選項與報告的預設建議，方向由使用者決定**（AGENTS 鐵律 5）；第五節是頂層建議。

類別沿用[組件契約藍圖](component-contracts.md)：**B** 組件 bug、**G** 契約缺口、**M** 誤用、**X** 外部故障。code-quality 的 R8 系列只給嚴重度、沒分類，表裡記「未分類」。

## 一、報告引出的修補（loop7 候選）

逐條清單已抽到 [next-steps-fixes.json](next-steps-fixes.json)（118 列）。欄位：`id` 報告編號（兩份報告同一件時另一個寫在 `also_hit`）；`group` 下面七組之一；`title` 一句話；`cls` 類別；`severity` 嚴重度（報告原文）；`source` 出處報告與錨點；`also_hit` 哪些報告重複撞到；`note` 補充。

各組列數：1 組 4、2 組 2、3 組 7、4 組 3、5 組 27、6 組 38、7 組 37。

**建議做法（照慣例）：** Fable 寫 loop7 藍圖（像 [loop6 藍圖](blueprint-loop6.md)）→ 隊長分線 → astra 回歸驗收。

### 1. adapt 小修自己引入的回歸（最先）

97191272 修了 A7-01 的四捨五入，卻引入 A8-01（Decimal 精度不足，任務反覆退出、留下舊 `ok`）與 A8-02（取整後強轉 float，突破誤差界），見 [play7 §3](reviews/2026-10-05/play7.md#3-97191272-小修驗收)。同包還有 A8-03（浮點端點塌縮）、A8-04（溢位仍發布 `ok/Infinity`，code-quality R8-23 也疑似撞到）。

### 2. subd 合法 stop 後重開誤收保留任務（高）

[play7 A8-09](reviews/2026-10-05/play7.md#a8-09bsubd高合法-no-kill-stop-的回條寫失敗重開後誤收應保留任務)（回條寫失敗）與 [model-check MC-01](reviews/2026-10-05/model-check.md#4-mc-01重新接回前覆寫停止證據可能誤殺應保留任務)（刪 stopped.json 重接、argv 前中斷）。**兩條觸發路徑不同**，同在 subd 的合法 stop 判定；MC-01 是讀碼候選反例、未重現，修時兩條都要有驗收案例。play7 §8 把 A8-09 列第一優先。

### 3. kill／回收時序（高）

三對同族：R8-01＝A8-06（runner 已起、任務未 Popen 時 kill 回成功）；R8-02 與 C8-02（回收沒成功仍起新時間線／node 替換後新舊同活）；R8-03＝A8-05 與 C8-01（登記先改記憶體再寫檔、取消登記後 daemon 被殺回收義務遺失）。根因是回收義務只在 daemon 記憶體（[evidence-summary](reviews/2026-10-05/evidence-summary.md#deep-play)）。另併列 k-crosscheck K-04（inst 子程序在清場快照後出生的漏收窗口）與 R8-29（裸 pgid 缺身分重驗，待核）。

### 4. budget unknown 被 step 當一般失敗

A8-10（G／中）。同一件事 code-quality R8-27、spec-readability F03、packs-use 4.4 都撞到；packs-use 4.3 補一面：rc 3 時可能已結算、只是輸出失敗。step 側的 R8-13（過期 intent 直接 halt、繞過 `on_unknown`）在同一交接面。**這組含一個語意選擇**：讓 rc 3 接上 step 的有限重送，或只在文件明寫兩種 unknown 不同。

### 5. 數值、遷移漏接與其他

巨大整數 interval（A8-11＝k-crosscheck N-21／N-62）、回合已關讀不到時倒數少扣（R8-05＝K-02，相關的 N-06 daemon 重開丟剩餘回合數）、A8-07＝R8-08（動態加掛半提交）、A8-08＝R8-15／R8-16（budget I/O unknown 邊界）、R8 其餘中低級與 §3 待核項、k-crosscheck 的遷移漏接（N-66 子根路徑、N-66 audit＋subd）。頂層清單沒列但報告有的：N-86（已 launch 的 once 改排程後可能再跑）、C8-03（任務包槽外 tmp 檔累積）、R8-20／21（低）。

### 6. 測試

[test-review](reviews/2026-10-05/test-review.md)：T8-01～17 是會假綠的斷言與故障沒命中，T8-18～24 是 flaky 風險，T8-25～35 是規格保證缺固定回歸，T8-36 空選集報成功。報告建議順序見 [§五](reviews/2026-10-05/test-review.md#五建議落地順序)：先修假綠（T8-01～08）→ 共用可信度 → 明確握手 → 契約矩陣。

測試加速：[fast-tests](reviews/2026-10-05/fast-tests.md) 量到 364 項中位數 190→65 秒、19 輪全過，**patch 沒留在 repo，要照報告重做**；原樣複本只有 359／364，見 [evidence-summary](reviews/2026-10-05/evidence-summary.md#fast-tests)。

### 7. 文件

[spec-readability](reviews/2026-10-05/spec-readability.md) 的 F 系列共 **F01～F34**（F01～11 優先、可能讓人操作錯誤；F12～25 一致性落差；F26～34 引用與命名；F03 併入第 4 組）。[packs-use](reviews/2026-10-05/packs-use.md)（新手評 5.4／10）：4.1 三個上層包缺第一份設定範本、4.5 budget「次數」與 `--amount` 不一致（含一個要選的語意：次數或加權成本）、4.7 健康判斷、§5 卡點全表。F04＝4.6、F11＝4.2、F19 與 4.3 相關。

## 二、原定落地順序

SESSION-LOG 10-04 傍晚記的順序是事件保存 → agent／LLM 作者與 adapt-llm；kernel 任務包是 [core-slimming](core-slimming.md) 裡還沒做的一塊。三份報告（[event-store](reviews/2026-10-05/event-store.md)、[llm-author](reviews/2026-10-05/llm-author.md)、[kernel-pack](reviews/2026-10-05/kernel-pack.md)）各自的選項、待決題（5／12／7 題）與預設建議與 prior-art 相關借用，整理在 **[next-steps-landing.md](next-steps-landing.md)**。

## 三、整理類（不急）

**wf 文件結構**（[wf-structure](reviews/2026-10-05/wf-structure.md)）：排除封存後 150 份 Markdown 超過 8 KiB。報告建議先清會誤導的過時條目（[§二 P1](reviews/2026-10-05/wf-structure.md#p1先修會誤導下一輪工作的文件)、[§三 SESSION／WAIT 過時條目](reviews/2026-10-05/wf-structure.md#三sessionwait-已過時或已完成的條目)），再抽資料、按主題拆，**不以全壓到 8 KiB 為目標**；150 份逐檔處置在 [§五](reviews/2026-10-05/wf-structure.md#五150-份未封存超標檔案逐檔處置建議)，執行順序在 [§七](reviews/2026-10-05/wf-structure.md#七建議執行順序)。跟本資料夾有關的：problems.md 現行段與修復歷史混雜、core-slimming 未完成敘述部分失效、layer-interfaces 是舊調查。

**C++ 核心移植**（[cpp-core](reviews/2026-10-05/cpp-core.md)）：路線圖分 0～6 階段（[§6.2](reviews/2026-10-05/cpp-core.md#62-先後順序與驗收門檻)），先重建錯誤判定、程序身分與可恢復的執行交接，再接 agent／LLM；報告另列現有 C++ 的缺口 F01～F13（它自己的編號，跟 spec-readability 的 F 無關）。等原型穩定再開；平台只支援 Linux 還是另做 backend 也還沒定。

## 四、卡在使用者的

**WAIT_USER A 區舊題**：hub 表列 proto2 9、proto5 kernel 7、公司 36 條 open（另 19 條已裁決只留翻案入口）。wf-structure [§3.2](reviews/2026-10-05/wf-structure.md#32-wait-a-區的數字可以下降但不能把尾項弄丟) 核出至少 26 個編號不該再算待裁（含 #74、#75 已決），剩約 45 個，但已裁決檔裡夾著 #33、#35、#39 的未完成尾項不能弄丟。可派人先把這些整理成一張「15 分鐘拍完」的清單給使用者。

**WAIT_USER B 區 proto6 帳號模組真 root 驗收**：要使用者在可丟棄的機器上手動跑。wf-structure 指出[操作手冊](../../proto6/notes/2026-10-01-account-manual.md)的 mq／ctl 介面已落後（socket 參數、`AOS_DAEMON_CTL_SOCKET` 等），**建議先修手冊再請使用者照跑**。

## 五、頂層建議（建議，不是決定）

先開 loop7 修第一節的 1～5 組（adapt 回歸 → subd 誤收 → kill／回收時序 → budget unknown → 其餘），測試（6）與文件（7）視 loop7 分線容量併入或下一輪。loop7 進行期間，使用者看事件保存的 5 題待決；修完回到事件保存，之後照原定順序接 agent／LLM 作者與 adapt-llm。 第 3～6 組（第 6 組只含先修假綠 T8-01～08）的根因、修法選項、待決題與分線見 [loop7 藍圖](blueprint-loop7.md)（逐條在 [blueprint-loop7-items.json](blueprint-loop7-items.json)）。
