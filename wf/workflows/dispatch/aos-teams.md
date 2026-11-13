# aos 的隊形

← [dispatch](README.md)｜選人判準 [team-model](../team-model.md)

本專案實際怎麼開隊。派線的通用規則在 [dispatch](README.md)，這裡只記 aos 專屬的隊形、指令與硬規則；改制時直接改成現行寫法。任務書送出前要對一次的坑在 [lessons](lessons.md)。

## 誰做什麼

<!-- wf-nav -->
- **頂層（多為 Opus）只當調度者**：只跟使用者交流與派隊，不親自做內容。使用者原話：「頂層不要做太多事」（08-30）、「你不要自己做事，盡量交給 agent」（09-24），11-06 第 1 句同意思。頂層在主 repo 親手做的**只剩 `git merge --ff-only`＋`git push`**；重跑驗證、解 rebase 衝突、改 SESSION-LOG／WAIT_USER、清 backlog、報告存檔全派出去。收線＝讀隊長附的證據逐條對，不重跑；真要獨立驗證就派一條便宜的線去跑。想「順手」做小事時先問：能不能一句話交給別人？
- **一隊的編制（第 2、4 句）**：**opus 隊長**（Claude Code 自家 subagent）＋**兩名隊員**——codex `gpt-6.1-sol`、claude CLI `claude-opus-5-5`。隊長寫任務書、審 diff、跑 build、commit、push；隊員與其子 agent **不 commit**。
- **隊員往下派（第 5、7 句）**：兩名隊員都可**無上限**派子 agent。codex 那邊普通工作（寫碼、審查、調查）一律 `gpt-6.1-sol`、簡單工作 `gpt-5.6-terra`；`gpt-6-astra` **只在圖像、創意類才派**（同級但價格約 sol 的 3 倍）。claude 那邊普通 opus、簡單 sonnet。**盡量把工作派給 codex**，claude 隊員補位。任務書寫「不限人數」與這套分工，頂層監看報警時才改寫上限。
- **「簡單工作」的界線**（使用者 11-06 確認：「1.對。2.是。」）：雜活、純文字小改、查找盤點、跑指令收結果才算簡單，給 sonnet／terra。**碰程式碼邏輯、改寫使用者的概念／規範條文不算簡單**，不給 sonnet（使用者 09-30「不要 sonnet」「就 opus」；見 [common/user「子 agent 模型」](../common/user.md)），codex 那邊用同一把尺、不給 terra。
- **讀規矩（第 1、5 句）**：派出去的 agent 做事前先通讀 wf/ 規矩（AGENTS.md、WORKFLOWS.md、common/user.md、common/conventions.md 等），**簡單工作與雜活例外**；隊員與其子 agent 同樣適用。任務書開頭寫明，並要隊員往下派時也寫進子任務書。例外對子 agent 一樣成立（雜活子 agent 可免讀）——使用者 11-06 確認（「1.對。2.是。」）。
- **一般 agent 再派子 agent，模型隨意**（第 1 句）；隊員那層照上面第 5 句的分工。
- **fable→opus→gpt**：fable 只做頂層規劃／設計，只讀備料、不廣讀 repo。opus 收集與匯總→fable 一次性規劃→opus 補全加深架構，輪間、輪中皆可，次數不限；gpt 嘗試時 fable 仍不即時參與。opus 負責輪內架構、權衡、審 gpt 與流程；gpt 照設計施工／嘗試。[原話](aos-teams/03-使用者原話.md)。
- **同機 session 傳話**：同帳號原則上用 a2a，但兩邊權限模式不同時會卡在對方畫面等批准，**兩個方向都寄 wf/inbox**；Argon 也是共同設計者（審查＋提案）。細節與原話見 [05](aos-teams/05-同機session與Argon.md)。 agy、LM Studio、家機假日隊形也在 05。
- **程序數要少（第 3、6 句）**：codex、claude CLI 都是 nodejs，跑在使用者也在用的機器上，所以**每隊同時最多兩個 CLI 程序**（一個 codex、一個 claude），子 agent 跑在隊員自己的程序裡、不另開 CLI。同時開幾隊由頂層看負載定。頂層開一個**背景監看**，定時看負載、可用記憶體、CLI 程序數，**超門檻才通知**；通知了就叫各隊收斂子 agent 或輪流跑。純改檔負擔不大，「稍微監控」即可，不逐次回報。各機門檻與指令見 [公司 WSL](aos-teams/01-公司WSL.md)。
- **codex 要設 goal**：codex 愛做到一半就說做完，提示參數要以 `/goal <完成條件>` 開頭，指令與核對見 [02](aos-teams/02-指令沙箱與試玩.md#codex-呼叫與沙箱)。
- **權限邊界**：codex 隊員用 `-s workspace-write`（它自己的沙箱），claude 隊員用 `--permission-mode acceptEdits`＋`--allowedTools` 列需要的工具。**agent 不加全繞過沙箱／權限的旗標**（Claude Code 的安全檢查也會擋）——這是使用者的權限邊界，要開由使用者親自開。家機的 codex 隊員也用沙箱（`-s workspace-write`），不靠不帶 `-s` 去吃家機 `~/.codex/config.toml` 的 `danger-full-access`（使用者 11-08「codex可以改用沙箱，準備好就可以用」，指令見 [02](aos-teams/02-指令沙箱與試玩.md#codex-呼叫與沙箱)）。
- **codex 可用 slug**（`gpt-6.1-sol` 為主力；全表與寫錯 slug 的症狀）見 [02](aos-teams/02-指令沙箱與試玩.md#codex-可用-slug)。
- **進度回報**：各線在開線、做完一批／一個地點、代定、卡住、交棒時叫 `progress_post.sh` 上桌面看板，回報頂層只寫一兩句：[04](aos-teams/04-進度回報.md)。
- 開隊前**先把打算怎麼做講給他聽**，等他回應或糾正再派；他可能在手機上、回得慢，問題與選項照發、附預設建議。
- **gpt 系不參與設計決策與架構規劃（長期）**：原話「gpt系的模型不可參予軟體工程的設計決策與架構規劃，他們只能按照圖紙施工當碼農，以及寫文件(這個很適合gpt系)，以及各類雜活」。codex（任何 gpt slug）**能做**照已定圖紙寫碼、寫文件、雜活、網頁施工（說明頁、互動頁、artifact 等，內容題目由隊長定）；這範圍內**優先派 gpt**（額度多；每隊仍最多一個）；原話見 [03](aos-teams/03-使用者原話.md)；**不能做**軟體設計決策、架構規劃、審查裡判斷設計對錯（可挑實作錯、與圖紙不符）。怎麼改由派工的 Claude 定好寫進任務書；「盡量派 codex」與 02「sol 做調查」照此讀。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../STRUCTURE.md) 按 `##` 標題拆開；本檔留前言與「誰做什麼」，其餘在下列分檔（下面「第 N 句」指 03 裡 11-06 原話的編號）。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-公司WSL](aos-teams/01-公司WSL.md) | 公司那台（WSL）的 codex 捷徑與 slug、claude 隊員帳號、沙箱、監看門檻 |
| [02-指令沙箱與試玩](aos-teams/02-指令沙箱與試玩.md) | 指令與沙箱（開隊長、開隊員、codex 呼叫與沙箱、Claude API 不穩時、codex 可用 slug）、每段做完派人試玩（2026-09-13 起） |
| [03-使用者原話](aos-teams/03-使用者原話.md) | 使用者 11-06 原話（現行隊形的出處）、使用者 11-07 原話（家機假日隊形與 gpt 的分工限制） |
| [04-進度回報](aos-teams/04-進度回報.md) | 進度回報與桌面看板 |
| [05-同機session與Argon](aos-teams/05-同機session與Argon.md) | 同機 session 傳話（a2a 與 inbox）、Argon 共同設計與指令、agy、LM Studio、家機假日隊形 |

<a id="指令與沙箱"></a>
<a id="codex-呼叫與沙箱"></a>
<a id="codex-可用-slug"></a>
<a id="每段做完派人試玩2026-09-13-起"></a>
<a id="使用者-11-06-原話現行隊形的出處"></a>

## 交接

- 派線流程、領地表、收線 → [dispatch](README.md)；外部 CLI 線的啟動與監看 → [driving-cli-agents](driving-cli-agents.md)；任務書 checklist → [lessons](lessons.md)。
- 各層派哪級模型 → [team-model](../team-model.md)；隊伍會撞的資源 → [resources](../resources.md)；模型端點 → [dev-env](../dev-env.md)。
