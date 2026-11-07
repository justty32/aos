# team-model — 誰來做：角色三層、聰明度分級、選人判準

← [WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

本檔記**誰來做**——分幾層角色、每層派哪一級的模型、按什麼順序選人（分級與速度是使用者定的、跨專案共通，源頭是 `~/repo/moddings/skyrim/agentctl/docs/team-model.md`，兩邊要一起改）。**怎麼做**在別處：切線與交接書見 [dispatch](dispatch/README.md)（含本專案的隊形與 codex 呼叫），資源鎖見 [resources](resources.md)，通訊見 [inbox/PROTOCOL](inbox/PROTOCOL.md)。

**何時用**：要開一個 agent 團隊、要決定某一層派哪級模型、要按用途分角色。
**何時不用**：只有一條線、一兩個檔的小改（見 [dispatch](dispatch/README.md) 的「何時不用」）；只是要送一則情報 → [inbox](inbox/README.md)。

## Done when

- [grades](team-model/grades.md) 的分級表與消耗速度表已按**你自己的模型清單**填完。
- 這一輪要開的每一層都**指名了誰**——頂層、領導、工人各自是哪一格。

## 一、角色三層

### 頂層 agent（使用者直接面對的那一個）

職責四件：接收指令、開 agent 團隊、傳達指令、**協調使用者自己也會用到的資源**（CPU、硬碟、網路）。**資源授權的源頭是使用者**——頂層只是代為分配，**不能自己創造授權**。

模型：**通常 Opus 就夠了**——頂層只是轉達與調度，某些情況下 Sonnet 也可以；skyrim 那邊 2026-08-30 已由 Fable 降回 Opus。aos 頂層 10-09 起多為 Opus（頭腦風暴時換 Fable），都**只派隊、不親做內容**（鐵律 5：方向性的留給使用者）。頂層**比領導笨是正常的**：計畫不在頂層做。

對使用者說話要**適合使用者理解**：初次出現的東西先用白話講一句。**預設不必翻譯**；只有使用者說今天不想動腦才逐項翻，翻譯本身吃太多 context 時，改成直接指出**該先看哪些檔**（[digest](digest/README.md) 工作流就是做這件事）。

頂層通常可以有**自己的私人輔助者**（查資料、盤點），不必事事經過領導。輔助者**不算團隊 headcount**，數量由使用者指定，**沒指定就默認兩個**。

平時**不掛信箱醒鐘**、不逐則讀信——那是領導的事。**例外**：團隊裡有外部 agent 要直接找頂層時，頂層也要盯自己的信箱（見第七節）。

### 團隊領導（＝計畫制定者）

職責：把目標拆成計畫、寫交接書、派工、監看、核驗、收線。本專案的隊長是 **Opus**（11-06 起明定為 Claude Code 自家 subagent，帶兩名隊員，見下方「工人」）：寫任務書、審 diff、跑 build、commit、push。

模型：**依任務難度是 Fable 或 Opus**。負擔重（計畫＋指揮＋匯報），所以 **Opus 是最低標準**；**若「制定計畫」被分出去給某個成員，領導只剩指揮與匯報，Sonnet 也可以。**

**通常不建議 gpt-sol 當領導**：那是另一套 agent 體系，即使有 inbox，和頂層溝通仍然有成本。

兩條實務提醒：交接書的**範圍詞會被線遞移展開**，範圍要用排除法寫死、**件數 gate 與容量 gate 並列**（見 [dispatch](dispatch/README.md)）；領導自己 context 吃緊時**寫 state 檔交棒**，不硬撐。

### 工人

依任務難度／內容，加上**使用者給的 headcount**，開不同聰明程度的 agent。gpt-sol、gpt-terra、gpt-luna 這類便宜 AI **通常在這層大量使用**；工人**不 commit**。

**本專案 11-06 起**：每隊的工人＝**兩名隊員**，一個 codex（`gpt-6.1-sol`）、一個 claude CLI（opus），各自可**無上限**往下派子 agent——codex 那邊普通 sol、簡單 terra，claude 那邊普通 opus、簡單 sonnet；**盡量派 codex**，claude 補位。隊員與其子 agent 一樣先通讀 wf/ 規矩（雜活例外）。細節與使用者原話見 [dispatch/aos-teams](dispatch/aos-teams.md)。

gpt-sol 自己再開 terra／luna 是**它那層的事**——它在那層就是領導，不算「領導不建議 gpt-sol」的例外；我們只在任務書寫明分工與資源（上一段），不替它逐條派。

## 二、聰明度分級（總分）

使用者定的總分表（S Fable；A Opus〔軟工〕、gpt-sol 系、`gpt-6.1-sol`、`gpt-6-astra`；C gpt-terra、Sonnet；D gpt-luna、Haiku…）在 [grades](team-model/grades.md)。**級別是使用者定的**，新增用途欄只加欄、不改級。11-06 起 codex 一般工作一律 `gpt-6.1-sol`，astra 只派圖像、創意類（同級但價格約 sol 的 3 倍，原話見 grades）。

## 三、token 消耗速度

Claude 系列消耗與聰明度成正比、GPT 系列整體往下移兩級，所以 **gpt-sol 系（A 級腦、C 級價）是性價比之神、工人層主力**；表在 [grades](team-model/grades.md)。

## 四、選人判準（按序看這七項）

1. **任務難度／內容**——決定聰明度下限。
2. **使用者給的 headcount**——外生的上限，**不自己加碼**。
3. **token 消耗速度**——所以工人層大量用便宜模型，貴的留給真的需要的那幾件。
4. **溝通方便與否**——跨體系（GPT ↔ Claude）即使有 inbox 仍有成本，所以**領導層不建議 gpt-sol**。另外（使用者 11-07，長期）**gpt 系不參與軟體設計決策與架構規劃**，只照圖紙寫碼、寫文件、做雜活，見 [aos-teams](dispatch/aos-teams.md)「gpt 系不參與設計決策與架構規劃」。
5. **管理上限**——**開太多領導不好管**；寧可少開領導、把量壓在工人層。
6. **時程**——用「產出速度 × 繞圈數 × 模型癖好」反推每段派誰、排多久，算法見 [speed](team-model/speed.md)。
7. **機器負擔**（2026-11-06）——codex、claude 這類 CLI agent 都是 nodejs 做的，跑在使用者自己也在用的機器上，**同時開的 CLI 程序數是外生上限**（本專案每隊兩個）。量往隊員的子 agent 壓、不往程序數壓；頂層稍微監看負載，超門檻才叫各隊收斂（做法見 [aos-teams](dispatch/aos-teams.md)）。

## 五、方案與時間軸

隨帳單與錢包變動，替代表與連帶效果拆到 [plans](team-model/plans.md)。2026-08-30 原計畫 9 月初退 GPT；實際沒退，10-09 實測 codex 9 個 slug 可用，工人層恢復 codex。

## 六、context 管理

每層管自己下級的 context——管得好就是清雜訊，直接提升決策品質。五條規則見 [context](team-model/context.md)。

## 七、信箱——每個角色一格

角色分層之後通訊也跟著分層：每個 agent 一格，開團隊再配團隊一格（本專案同機的隊用子 agent 通道，跨資料夾才走 inbox）。

- **頂層**平時不掛醒鐘；只有 `NEEDS-USER`、`FAILED`、領導的 `DONE`、資源／鎖請求該吵醒它。
- **領導**對自己團隊送來的 STATUS **全醒**；上呈時重寫標題、帶自己的判斷，不是原文轉貼。
- **工人**沒有醒鐘，**每完成一個工作步驟輪詢一次**，延遲上限就是一個工作步驟。

誰醒誰不醒以 [inbox/wake-policy](inbox/wake-policy.md) 為準。

## 內容

| 檔案 | 內容 |
|------|------|
| [team-model/grades.md](team-model/grades.md) | 二、聰明度分級（總分）、三、token 消耗速度（兩張表）|
| [team-model/context.md](team-model/context.md) | 每層怎麼管下級的 context、compact 間隙怎麼預定 |
| [team-model/speed.md](team-model/speed.md) | 執行速度三因素相乘、逐模型指揮心得表 |
| [team-model/plans.md](team-model/plans.md) | 方案與時間軸（隨帳單變動的活頁）|

## 交接

- 切線、交接書、領地表 → [dispatch](dispatch/README.md)。
- 獨佔資源與鎖 → [resources](resources.md)。
- 通訊契約與醒鐘 → [inbox/PROTOCOL](inbox/PROTOCOL.md)。
