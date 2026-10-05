# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡——過程細節交給 git log（若有「已落地功能目錄」則濃縮一句進去）。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔若過大，就在 repo 頂層新立 **`session_logs/`** 資料夾，按工作流／類別**拆檔 + 一個 index 導航**（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔同時 ① 連到各工作流自己的 session-log（若該工作流已長出自己的），② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態 + 指向細節的連結**（設計決策/修了什麼落到該工作流的文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即整條刪除。

## 最新進度

- 10-05 早（公司 WSL）：用掉 codex 重置額度，15 條 astra 審查／調查報告收在 [proto7-2/notes/reviews/2026-10-05/](../proto7-2/notes/reviews/2026-10-05/README.md)（連 README）；**等使用者挑要修哪些**，程式未動。
- 10-04 傍晚（proto7-2 改進循環＋思考輪次，**進行中**）：核心精簡完成（核心 lib 4501→2791、六個模組包）。step 包（ca7f5159）。loop4（核心 2757／2800）。loop5（subd 回收前代 8c2145c4；**budget 包 v1** 025d2bfe，原名 account，使用者要求改名）；astra-5 找 A6-01／02。**loop6**（Fable 藍圖 [blueprint-loop6](../proto7-2/notes/blueprint-loop6.md)，三線並行、核心零改動）：subd allowed_stop 95426b17、budget A6-02＋五缺口＋step max_resends bd9dcc10、**adapt 包 v1** d3738e04（鄰居 node 最新值轉接）；整合 a1029d47（363 測試約 196 秒）。astra-6 驗收過（f1205964），小修 97191272（A7-01 adapt 四捨五入等）。**使用者 16 點多回來，要求開下一批前先停**。現況頁 proto7-2 現況圖解：https://claude.ai/artifact/UYJCNJfx5XfcP7bda7gzHK（素材＝scratchpad/demo/capture.md 真實示範）。落地順序剩：事件保存 → agent／LLM 作者與 adapt-llm。思考第四～六輪已完成；使用者補「程式語言＝抽象化→一體性→特定空間簡單處理」記在 r4-topic 末。使用者 15:08 起外出運動，交代自己繼續弄、複雜問題開 Fable／astra。教訓：commit 一律 `git commit <paths>`；subagent 有時寫不了 .md 報告，摘要由整合者補。
- 10-04（proto7-2，**等使用者看 W1～W12**）：使用者看完 proto7-1 寫了 `proto7/user-advice.md`（未 commit，使用者還會改）：node 改登記、提前 tock 可選、只留 tasks.json、任務資料夾不每回合新增；追加「歷史做成可選 module，核心只留上一次」。開 [proto7-2](../proto7-2/README.md)：spec（3774a343）＋10-04 照 spec 做完基礎設施（daemon／tick／tock／run／ctl＋歷史 module，測試 103 項全綠，kernel／agent 不做）；待決點 W1～W12 在 [changes-from-7-1](../proto7-2/notes/changes-from-7-1.md)（程式照推薦），實作新冒出的 P2-01、P2-02 在 [problems](../proto7-2/notes/problems.md)。proto7-1 的 K 系列不修（併入 proto7-2 設計）。10-04 astra 第一輪（A2-01～A2-13）與 14 處讀碼疑點已修，加回歸矩陣 116 項（全套 219 項綠），處理表在 [problems](../proto7-2/notes/problems.md) 最後一節。10-04 astra 第二輪 A3-01～09 已處理（A3-02／03 依原則 9 標誤用）、P2-01 (b)／P2-02 retry_lost／until_round 已實作，全套 252 項綠；之後暫停改進循環、做核心精簡。
- 10-03 深夜（proto7-1，**收尾中→停**）：使用者說「今天差不多到這，探針跑完就先停」，接著要 compact、自己來搞清楚狀況。自主期間做完：F／G／H 三輪修補（測試 180 項、21＋探針）、astra 第六～八輪回歸、兩份調查（Linux、其他 OS）、實驗一二三探針（結論：LLM 放進排程迴圈不划算）。**已停：**第三波探針收回（26 探針全綠，新需求 N-79～N-86，建議的 daemon／tick 改動待頂層定）；astra-8 的 K-01～K-10 **未修**，修法已定在 [生命週期三個不變條件](../proto7-1/notes/decisions/2026-10-03-lifecycle-invariants.md)（三態判定、回合／啟動交接／清歷史）。頂層代定的事見現況頁「你不在時」：https://claude.ai/artifact/8KbqoRE1vhojNg4goMtNtv 。使用者授權：頂層自走、「之後再說」的也由頂層取最簡（合作式檔案協定）。
- 10-03（proto7-1，先前曾停：使用者說這批跑完先停，後又說接著做）：kernel／agent 是探針、精力放 daemon／tick；決策範圍：kernel／agent 與 daemon／tick 普通的頂層代定，稍大的才問。現況頁：https://claude.ai/artifact/8KbqoRE1vhojNg4goMtNtv 。收齊：astra 五輪（[play](../proto7-1/notes/play/README.md)）、真模型兩輪、探針兩波 18 個（[probes](../proto7-1/probes/README.md)）、[需求清單](../proto7-1/notes/infra-needs.md) N-01～N-76、批次 tick 評估；測試 108 項全綠。Q5（子 daemon 歸擁有者 node、allow_stop）、Q6（restart 加 reload）使用者已答並做完（6261a304，測試 117 項）。另有 astra 調查 [kernel 能從 Linux 借什麼](../proto7-1/notes/research/2026-10-03-linux-kernel-borrow.md)（artifact：https://claude.ai/artifact/7oDcGFTapV66xABdgHRs4t）。**等使用者說繼續**：修 astra-5 的 F-01～F-11 與 N-55（先收程序再刪空間）→ astra 回歸。待使用者看：S-21 原文「daemon 核心不知道從屬」與新加的所有權句字面有點擰。
- 10-03（proto6，分層討論：四條評估線都收齊）：使用者想法的正本在 [aos 分層筆記](../proto6/notes/2026-10-03-aos-layering.md)（最重要原則：操作與協議用 JSON／文字、LLM 可讀；使用者說核心理論已 OK，daemon 與 tick-tock 剩技術選型）。收齊的四份：thread 與程序評估（[thread-vs-process](../proto6/notes/proposals/2026-10-03-thread-vs-process/README.md)，artifact：https://claude.ai/artifact/FCr539iF7dxE9L3nV6hq74 ，它的五題待使用者答）；時空四層推演（[spacetime](../proto6/notes/proposals/2026-10-03-spacetime/README.md)，Fable 起草途中卡死，01～05 由新線改到最新筆記、06／07／README 由 Claude 改寫；結論是沒有方向題，唯一硬衝突是 tick 跑完所有任務才結束）；[astra-spacetime](../proto6/notes/reviews/2026-10-03-astra-spacetime.md)（照最新筆記與 LLM 可讀原則，也沒有新方向題）；[astra-layering](../proto6/notes/reviews/2026-10-03-astra-layering.md)（評的是較早版本，開頭加了註）。使用者已說 kill／restart、訊息交流、權限、agent 細節、管轄範圍與十條技術問題之後再談。
- 10-03（proto6，待使用者挑）：astra 六條線對三份提案另想完了，收斂點、方向題與建議實驗順序見 [astra-alt 總覽](../proto6/notes/reviews/2026-10-03-astra-alt/README.md)；等使用者選先做哪個實驗。
- 10-02（proto6，擱置待使用者想）：停格檔只記未來方向；node（使用者預感 node 概念會消失，tick 與 daemon 都不做 node 模組）；`peers` 先不做；系統級任務怎麼改用 hooks（[清單](../proto6/notes/2026-10-01-tick-system-tasks.md)）；C++11 等 Python POC 玩過再開。各段狀態見 [plan](../proto6/plan/README.md#各段狀態)。
- 10-02（proto6，超標檔）：排除封存後 proto6 還有 15 份、wf 44 份 Markdown 超過 8 KiB；先刪過時內容再考慮拆，見 [astra 結構審查「建議」](../proto6/notes/reviews/2026-10-02-astra/10-structure.md#建議)。
- 09-25（proto5 整理鏈收尾後還開著）：待董事評分 [brief/2026-09-25.md](../brief/2026-09-25.md)、WAIT_USER 40～73；下一輪：`lessons.md`／`catalog.md` 先改 lib 再拆、`agent_access`／`agent_talk`／`kernel_check`／`kernel_ledger` 沒拆、09-24 notes 三份一組的收攏。[→](session_logs/2026-09/2026-09-25.md#2026-09-25)
- 09-22：09-21 ④⑤ 仍在（① backlog 已於 09-24 清光） [→](session_logs/2026-09/2026-09-22.md#2026-09-22)
- 09-21：④ aos-inst 兩題 ⑤ thinking/ 草案 ④ WSL 沒 lms／jq [→](session_logs/2026-09/2026-09-21.md#2026-09-21)
- 09-13：① 試玩 r1 修 ② LLM cpu 下一段 ③ 提醒 compact [→](session_logs/2026-09/2026-09-13.md#2026-09-13)
- 09-09：① kernel v1 缺項等使用者 [→](session_logs/2026-09/2026-09-09.md#2026-09-09)
- 09-06～08：預算、dev 模型、qa、push、proto4-2 等 [→](session_logs/2026-09/2026-09-06.md#2026-09-06)
- 09-05：① 裁決單 ③ 升格裁決 ⑨⑪ 互動台 [→](session_logs/2026-09/2026-09-05.md#2026-09-05)
- 08-28：批 header、decode 層 [→](session_logs/2026-08.md#2026-08-28-拷問)

其餘（open 已解／無）與全文索引 → [session_logs/](session_logs/README.md)

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。一開始是空表很正常。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
