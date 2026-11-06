# aos 的隊形（2026-08-28 改制，2026-11-06 現況）

← [dispatch](README.md)｜選人判準 [team-model](../team-model.md)

本專案實際怎麼開隊。派線的通用規則在 [dispatch](README.md)，這裡只記 aos 專屬的隊形、指令與硬規則；改制時改這裡並標日期。任務書送出前要對一次的坑在 [lessons](lessons.md)。

## 使用者 11-06 原話（現行隊形的出處）

1. 「事情盡量都交給agent做，普通工作交給opus，簡單工作與雜活交給sonnet。agent做事前都要讀過wf/規矩，除了簡單工作與雜活。agent可以再派子agent，模型隨意。」
2. 「具體來說仍然是走team路線，也就是派一個opus去當隊長，隊員用這些。盡量用codex gpt啦」
3. 「然後codex/claude這塊，是這樣的，因為他們都是用nodejs做的，所以建議總數不要太多。因為一方面這是在WSL上，另一方面這台電腦我還要做其他工作，效能上要注意。」
4. 「所以我會建議，一個隊伍內，opus就是我們自家subagent，隊員就兩個，一個codex gpt-sol-6.1，另一個就claude opus-5.5。然後這兩個隊員都可以再派出agent」
5. 「隊員仍然遵循我們的要通讀wf/規矩的規定，包括其子agent。然後codex那邊，允許他跑無上限個子agent，普通工作交給sol，簡單工作交給terra。claude這邊也是無上限，普通工作交給opus，簡單工作交給sonnet。盡量把工作都派給codex。」
6. 「效能這塊，單純跑agent改檔案其實還好...你可以稍微監控一下」
7. 「然後gpt那邊改sol吧，astra主要在於圖像、創意這塊有能力增長，但一般工作上sol也能達到差不多的等級，但價格僅1/3。」

## 誰做什麼

<!-- wf-nav -->
- **頂層（早期是 Fable，10-09 起多為 Opus）只當調度者**：只跟使用者交流與派隊，不親自做內容。使用者 2026-08-30 說「頂層不要做太多事」，**09-24 再講更嚴**「你不要自己做事，盡量交給 agent」，11-06 第 1 句再講一次。頂層在主 repo 親手做的**只剩 `git merge --ff-only`＋`git push`**；重跑驗證、解 rebase 衝突、改 SESSION-LOG／WAIT_USER、清 backlog、報告存檔全派出去。收線＝讀隊長附的證據逐條對，不重跑；真要獨立驗證就派一條便宜的線去跑。想「順手」做小事時先問：能不能一句話交給別人？這條不看頂層跑哪顆模型。
- **一隊的編制（11-06 起，第 2、4 句）**：**opus 隊長**（Claude Code 自家 subagent）＋**兩名隊員**——codex `gpt-6.1-sol`、claude CLI `claude-opus-5-5`。隊長寫任務書、審 diff、跑 build、commit、push；隊員與其子 agent **不 commit**。（11-06 前：codex 工人寫碼 6.1-sol、核心難件與審查用 astra high、跑驗證 6-luna；隊長可自己再派 Opus／Sonnet、人數無上限。）
- **隊員往下派（第 5、7 句）**：兩名隊員都可**無上限**派子 agent。codex 那邊普通工作（寫碼、審查、調查）一律 `gpt-6.1-sol`、簡單工作 `gpt-5.6-terra`；`gpt-6-astra` **只在圖像、創意類才派**（同級但價格約 sol 的 3 倍）。claude 那邊普通 opus、簡單 sonnet。**盡量把工作派給 codex**，claude 隊員補位。任務書寫「不限人數」與這套分工，頂層監看報警時才改寫上限。
- **「簡單工作」的界線**（使用者 11-06 確認：「1.對。2.是。」）：雜活、純文字小改、查找盤點、跑指令收結果才算簡單，給 sonnet／terra。**碰程式碼邏輯、改寫使用者的概念／規範條文不算簡單**，照舊不給 sonnet（09-30「不要 sonnet」「就 opus」；10-19 見 [common/user「子 agent 模型」](../common/user.md)），codex 那邊用同一把尺、不給 terra。
- **讀規矩（第 1、5 句）**：派出去的 agent 做事前先通讀 wf/ 規矩（AGENTS.md、WORKFLOWS.md、common/user.md、common/conventions.md 等），**簡單工作與雜活例外**；隊員與其子 agent 同樣適用。任務書開頭寫明，並要隊員往下派時也寫進子任務書。例外對子 agent 一樣成立（雜活子 agent 可免讀）——使用者 11-06 確認（「1.對。2.是。」）。
- **一般 agent 再派子 agent，模型隨意**（第 1 句）；隊員那層照上面第 5 句的分工。
- **要思考的交 Fable**（使用者 10-13、10-20：高難度思考＆規劃派 fable，盡量少用）：11-06 原話沒提 fable，照舊——頂層代定、可翻案。使用者 11-06：「我們自己的fable subagent規劃者，他也可以派fable子agent」，又說：「不然把整個大架構都堆在一個fable身上，壓力太大」。
  - **公司那台**：fable 預設照舊開自家 subagent（盡量少開），使用者說「走 wsl claude」那次才走 WSL（公司帳號），見 [01-公司WSL](aos-teams/01-公司WSL.md#fable-走-wsl-claude使用者說了才走)。
- **程序數要少（第 3、6 句）**：codex、claude CLI 都是 nodejs，跑在使用者也在用的機器上，所以**每隊同時最多兩個 CLI 程序**（一個 codex、一個 claude），子 agent 跑在隊員自己的程序裡、不另開 CLI。同時開幾隊由頂層看負載定。頂層開一個**背景監看**，定時看負載、可用記憶體、CLI 程序數，**超門檻才通知**；通知了就叫各隊收斂子 agent 或輪流跑。純改檔負擔不大，「稍微監控」即可，不逐次回報。各機門檻與指令見 [公司 WSL](aos-teams/01-公司WSL.md)。
- **codex 要設 goal（11-06）**：codex 愛做到一半就說做完，提示參數要以 `/goal <完成條件>` 開頭，指令與核對見 [02](aos-teams/02-指令沙箱與試玩.md#codex-呼叫與沙箱)。
- **權限邊界（11-06）**：codex 隊員用 `-s workspace-write`（它自己的沙箱），claude 隊員用 `--permission-mode acceptEdits`＋`--allowedTools` 列需要的工具。**agent 不加全繞過沙箱／權限的旗標**——11-06 頂層試著這樣交代時被 Claude Code 的安全檢查擋下：這是使用者的權限邊界，要開由使用者親自開（例：家機 `~/.codex/config.toml` 的 `danger-full-access` 是使用者自己設的，照用）。
- **codex 可用 slug（10-09 家機實測 9 個都可用，codex-cli 0.161.0；公司 11-06 實測見 [公司 WSL](aos-teams/01-公司WSL.md)）**：`gpt-6.1-sol`（一般工作主力）、`gpt-6-astra`、`gpt-6-sol`、`gpt-6-luna`、`gpt-5.6-sol`／`-terra`／`-luna`、`gpt-reserve`、`gpt-5.5`。級別見 [team-model](../team-model.md)，試水溫結果見 [probe](../team-model/probe-2026-10-09.json)。slug 寫錯（如 `gpt-sol-6.1`、裸 `gpt-sol`）會回「not supported」——使用者口頭的「gpt-sol-6.1」就是 `gpt-6.1-sol`；他點名的型號先試，不行再問。
- 開隊前**先把打算怎麼做講給他聽**，等他回應或糾正再派；他可能在手機上、回得慢，問題與選項照發、附預設建議。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../STRUCTURE.md) 按 `##` 標題拆開；本檔留前言、原話與「誰做什麼」，其餘在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-公司WSL](aos-teams/01-公司WSL.md) | 公司那台（WSL）的 codex 捷徑與 slug、claude 隊員帳號、沙箱、監看門檻 |
| [02-指令沙箱與試玩](aos-teams/02-指令沙箱與試玩.md) | 指令與沙箱（開隊長、開隊員、codex 呼叫與沙箱、Claude API 不穩時）、每段做完派人試玩（2026-09-13 起） |

<a id="指令與沙箱"></a>
<a id="codex-呼叫與沙箱"></a>
<a id="每段做完派人試玩2026-09-13-起"></a>

## 交接

- 派線流程、領地表、收線 → [dispatch](README.md)；外部 CLI 線的啟動與監看 → [driving-cli-agents](driving-cli-agents.md)；任務書 checklist → [lessons](lessons.md)。
- 各層派哪級模型 → [team-model](../team-model.md)；隊伍會撞的資源 → [resources](../resources.md)；模型端點 → [dev-env](../dev-env.md)。
