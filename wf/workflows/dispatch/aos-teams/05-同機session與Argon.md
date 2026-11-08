# 同機 session 傳話與 Argon 共同設計（11-08）

← [aos-teams](../aos-teams.md)

## 同機同帳號 session 傳話

**同機同帳號 session 直接 a2a（11-08）**：`ListAgents` 看得到對方的話，就用 `SendMessage` 互傳，不寄 wf/inbox。wf/inbox 只留給跨帳號、跨機器，或看不到對方時用。**例外（11-08 17:45）**：兩邊權限模式不同時，送過去的 a2a 會卡在對方畫面等人批准。使用者說「尷尬，可能還是要用信件」，實測兩個方向都會被攔，所以兩邊**都改回寄 wf/inbox**。等兩邊的權限模式一致了，再切回 a2a。使用者原話：「arcagi主session跟你是同賬號，你跟他直接用a2a協議傳訊息就好。同電腦上，如果list agent能看到對方，那根本不用寄信。」

**現行（11-08 晚）**：兩個方向都寄 wf/inbox 信（`wf/tools/inbox_send.sh`）。同一分鐘、同 STATUS 的第二封會蓋掉第一封，連寄時錯開或換 STATUS；STATUS 只收 PROTOCOL 列的值（`REVIEW` 不收，審稿用 `PROGRESS`）。

## Argon 是參與者，不只審稿（11-08 晚）

使用者：「argon也可以提出意見，不只是審查，他也是參與者」「每次反芻之間都讓argon參一腳」。每輪規劃、每篇 fable 設計後各跑一次 Argon，產出分兩段：(A) 審查、(B) 提案。alt 帳號 fable 額度用完時，整合稿可改由 Argon 寫（11-08 v4 就是）。

- 指令：在 /tmp 跑 `agy -p … --model "Gemini 4 Argon (High)" --mode plan --print-timeout 840s`，檔案內容貼進提示、不給工具；輸出出現 "Authentication required" 時重試（grep 不分大小寫）。
- 提示超過約 128 KB（單一參數上限）時，把提示寫成檔放進 `--add-dir` 的資料夾，叫它用讀檔工具讀完再照做。

## 家機的其他規矩（從 aos-teams 下放）

- **agy（Gemini 4 Argon High）當第二意見（11-08）**：審規劃／設計、查漏補缺，不施工不決策；額度少，頂層統一叫、每輪一兩次。指令與原話見 [03](03-使用者原話.md#agygemini-4-argon當第二意見11-08-午)。
- **家機 LM Studio（11-07 午後）**：本機模型**一次只能 load 一個**（使用者硬規矩）；大小有別，可試。[原話](03-使用者原話.md)。
- **11-07 下午起（家機、假日）的隊形**（[原話](03-使用者原話.md#使用者-11-07-原話家機假日隊形與-gpt-的分工限制)）：**opus 隊長**＋Claude subagent（普通 opus、雜活 sonnet）＋**最多一個 codex** `gpt-6.1-sol`，派法同公司（[02](02-指令沙箱與試玩.md#codex-呼叫與沙箱)）；家機**不限整台 codex／claude 數**（「程序數要少」是公司那台的）。使用者說 gpt 寫文件與雜活「比sonnet好」「sonnet的好處就剩下隨叫隨到了」，照原話記、沒改雜活派 sonnet。99% 額度規矩見 [user/01](../../common/user/01-說話授權與記憶.md#額度緊時2026-11-07-定)。
