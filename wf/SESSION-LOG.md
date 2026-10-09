# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡——過程細節交給 git log（若有「已落地功能目錄」則濃縮一句進去）。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔若過大，就在 repo 頂層新立 **`session_logs/`** 資料夾，按工作流／類別**拆檔 + 一個 index 導航**（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔同時 ① 連到各工作流自己的 session-log（若該工作流已長出自己的），② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態 + 指向細節的連結**（設計決策/修了什麼落到該工作流的文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即整條刪除。

## 最新進度

- 10-09（家機，頂層全權代定；23:xx 收工）：今日約 360 commit 全 push、全套 1216 綠。代定全紀錄 [decisions-2026-10-09](../proto7-2/notes/decisions-2026-10-09.md)（末段最新）。晚間進 main：KE1／KF（kernel 範例＋astra 審修）、ST3、MT（信件白話）、UW（卡住信用語、步／回合）、I2（文件對齊、壞連結 0、inbox 清空）、AP4（學徒 A／B 沒證明，機制收下）、R2（astra-8 報告 A11／B12／C1）。**未完分支**：loop13/AP5（學徒第二次證明，文字交件＋藏慣例郵局題做好，A／B 只跑第 1 題第 1 輪；接手看 aos-wt/AP5/HANDOFF-AP5.md，要 rebase＋全套後才 merge）。**下一步（照序）**：① 修 astra-8 前段（A10-01 金鑰白名單、A10-02 owe、llmcall 退出碼解讀統一、traceback 批）；② 跑完 AP5；③ scaffold 選單（[藍圖](../proto7-2/notes/blueprint-scaffold1.md)，使用者已答 §9：選單由 astra 寫、三錯停下、brain 不動、沿用 AP4 三題；先開 MN1）；④ 狀況頁與兩張圖解頁重寫成 ELI5 比喻版（使用者說看不懂；用「AI 小辦公室：老闆／員工／主管／心跳、檔案櫃＋目錄卡＝記性、整理日記＝compact、抽屜手冊＝技能」比喻）。合併用 `../aos-wt/merge.sh <分支>`；數全套份數用 `ps -eo args | grep -c '^/usr/bin/python3 \(-B \)\?proto7-2/tests/run_all.py'`。對使用者一律 ELI5、少用隊名代號。使用者 19:00 已定：模型分級轉正、心跳可設定、清理先留、LiteLLM 提示不改；`proto7/user-advice.md` 不碰。
- 10-05 早（公司 WSL）：用掉 codex 重置額度，15 條 astra 審查／調查報告收在 [proto7-2/notes/reviews/2026-10-05/](../proto7-2/notes/reviews/2026-10-05/README.md)（連 README）。方向整理在 [proto7-2/notes/next-steps.md](../proto7-2/notes/next-steps.md)。 loop7 第一批（adapt A8-01～04、subd A8-09／MC-01／R8-18）已修並併入 main（全套 376 項：373 過，3 項既有失敗非本輪造成）；藍圖 [blueprint-loop7.md](../proto7-2/notes/blueprint-loop7.md) 待使用者答 D1～D10；思考素材 [r7](../proto7/notes/thinking/2026-10-05-r7-material.md)。晚間現況頁：https://claude.ai/artifact/BvrHKm6L33UDzaoThgnoSG 。3 項 WSL 失敗已查明是測試假設（dash 不 exec 最後命令＋時序），已修測試（[wsl-3-failures](../proto7-2/notes/reviews/2026-10-05/wsl-3-failures.md)），全套 376 全過。proto6 帳號手冊已依現行程式校正（WAIT_USER B 可照跑）；proto7-2 文件對齊 32 條（[docs-align](../proto7-2/notes/reviews/2026-10-05/docs-align.md)）；追進度導讀 [proto7-2/notes/catch-up.md](../proto7-2/notes/catch-up.md)。 修假綠測試（T8 系列）的改動兩次把 WSL 弄掛，已丟棄、不再做（見 lessons 第 11 條）。
- 10-04 傍晚（proto7-2 改進循環＋思考輪次，**暫停**：使用者要求開下一批前先停）：loop4～loop6 已落地（藍圖 [blueprint-loop6](../proto7-2/notes/blueprint-loop6.md)，細節見 git log）。落地順序剩：事件保存 → agent／LLM 作者與 adapt-llm。現況頁 proto7-2 現況圖解：https://claude.ai/artifact/UYJCNJfx5XfcP7bda7gzHK 。使用者補「程式語言＝抽象化→一體性→特定空間簡單處理」記在 r4-topic 末。教訓：commit 一律 `git commit <paths>`；subagent 有時寫不了 .md 報告，摘要由整合者補。
- 10-04（proto7-2，**等使用者看 W1～W12**）：使用者的 `proto7/user-advice.md` 未 commit，使用者還會改。待決點 W1～W12 在 [changes-from-7-1](../proto7-2/notes/changes-from-7-1.md)（程式照推薦，推薦不等於使用者已確認）；A2／A3 修復與 P2-01／P2-02 已做，處理表在 [problems](../proto7-2/notes/problems.md)。proto7-1 的 K 系列不在 7-1 修（併入 proto7-2 設計）。
- 10-03 深夜（proto7-1，**已停**）：K-01～K-10 不在 7-1 修，併入 proto7-2 設計（見上一條；修法方向在 [生命週期三個不變條件](../proto7-1/notes/decisions/2026-10-03-lifecycle-invariants.md)，不代表 K 系列已全修）。第三波探針新需求 N-79～N-86 建議的 daemon／tick 改動待頂層定。頂層代定的事見現況頁「你不在時」：https://claude.ai/artifact/8KbqoRE1vhojNg4goMtNtv 。使用者授權：頂層自走、「之後再說」的也由頂層取最簡（合作式檔案協定）。
- 10-03（proto7-1）：kernel／agent 是探針、精力放 daemon／tick；決策範圍：kernel／agent 與 daemon／tick 普通的頂層代定，稍大的才問。收齊的紀錄：[play](../proto7-1/notes/play/README.md)、[probes](../proto7-1/probes/README.md)、[需求清單](../proto7-1/notes/infra-needs.md)；F-01～F-11 與 N-55 已修（ddda65a9，見 play）。另有 astra 調查 [kernel 能從 Linux 借什麼](../proto7-1/notes/research/2026-10-03-linux-kernel-borrow.md)（artifact：https://claude.ai/artifact/7oDcGFTapV66xABdgHRs4t）。待使用者看：S-21 原文「daemon 核心不知道從屬」與新加的所有權句字面有點擰。
- 10-03（proto6，分層討論：四條評估線都收齊）：使用者想法的正本在 [aos 分層筆記](../proto6/notes/2026-10-03-aos-layering.md)（最重要原則：操作與協議用 JSON／文字、LLM 可讀；使用者說核心理論已 OK，daemon 與 tick-tock 剩技術選型）。收齊的四份：thread 與程序評估（[thread-vs-process](../proto6/notes/proposals/2026-10-03-thread-vs-process/README.md)，artifact：https://claude.ai/artifact/FCr539iF7dxE9L3nV6hq74 ，它的五題待使用者答）；時空四層推演（[spacetime](../proto6/notes/proposals/2026-10-03-spacetime/README.md)，Fable 起草途中卡死，01～05 由新線改到最新筆記、06／07／README 由 Claude 改寫；結論是沒有方向題，唯一硬衝突是 tick 跑完所有任務才結束）；[astra-spacetime](../proto6/notes/reviews/2026-10-03-astra-spacetime.md)（照最新筆記與 LLM 可讀原則，也沒有新方向題）；[astra-layering](../proto6/notes/reviews/2026-10-03-astra-layering.md)（評的是較早版本，開頭加了註）。使用者已說 kill／restart、訊息交流、權限、agent 細節、管轄範圍與十條技術問題之後再談。
- 10-03（proto6，待使用者挑）：astra 六條線對三份提案另想完了，收斂點、方向題與建議實驗順序見 [astra-alt 總覽](../proto6/notes/reviews/2026-10-03-astra-alt/README.md)；等使用者選先做哪個實驗。
- 10-02（proto6，擱置待使用者想）：停格檔只記未來方向；node（使用者預感 node 概念會消失，tick 與 daemon 都不做 node 模組）；`peers` 先不做；系統級任務怎麼改用 hooks（[清單](../proto6/notes/2026-10-01-tick-system-tasks.md)）；C++11 等 Python POC 玩過再開。各段狀態見 [plan](../proto6/plan/README.md#各段狀態)。
- 10-02（proto6，超標檔）：排除封存後 proto6 還有 15 份、wf 44 份 Markdown 超過 8 KiB；先刪過時內容再考慮拆，見 [astra 結構審查「建議」](../proto6/notes/reviews/2026-10-02-astra/10-structure.md#建議)。
- 09-25（proto5 整理鏈收尾後還開著）：待董事評分 [brief/2026-09-25.md](../brief/2026-09-25.md)、WAIT_USER 40～73；下一輪：`lessons.md`／`catalog.md` 先改 lib 再拆、`agent_access`／`agent_talk`／`kernel_check`／`kernel_ledger` 沒拆、09-24 notes 三份一組的收攏。[→](session_logs/2026-09/2026-09-25.md#2026-09-25)
- 09-21／09-22：④ aos-inst 兩題 ⑤ thinking/ 草案 ④ WSL 沒 lms／jq（09-22 記同前一天；① backlog 已於 09-24 清光） [→](session_logs/2026-09/2026-09-21.md#2026-09-21) [→](session_logs/2026-09/2026-09-22.md#2026-09-22)
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
