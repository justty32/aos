# 聰明度分級與 token 消耗速度（使用者定的總分）

← [team-model](../team-model.md)｜涵蓋：二、聰明度分級（總分）、三、token 消耗速度

本頁由 [`../team-model.md`](../team-model.md) 拆出。

## 二、聰明度分級（總分）

**這是使用者定的總分**（2026-08-30，原話「我這邊定下來的是總分，之後我們慢慢會有更詳細的分類分級」），所以留一欄給用途細分。分級以 **Claude 的收費與聰明度為基準**，往下補級很正常。

| 級 | 誰 | 用途細分 |
|---|---|---|
| S | Fable | 目前唯一一個 S；細分待補 |
| A | Opus | **軟體工程層面**；其餘用途見 B 列 |
| A | gpt-sol（`gpt-5.6-sol`）| 各方面；**軟體工程算 B+** |
| B | Opus | 軟體工程之外 |
| C | gpt-terra（`gpt-5.6-terra`）、Sonnet | 待細分 |
| D | gpt-luna（`gpt-5.6-luna`）| 待細分 |
| E、F… | （預留）| 之後 DeepSeek 之類可以更低 |
| A | `gpt-6.1-sol` | 使用者 10-09 確認；試水溫唯二全中（另一個是 astra）；**gpt 系一般工作一律用它**（本專案走 agent-fsm，`llm.json` 是 `sol` 加 `reasoning_effort` high，不走 codex CLI） |
| A | `gpt-6-astra` | 使用者 10-09 確認；**只派圖像、創意類**（使用者 11-06，見表下）|
| B | `gpt-6-sol` | 使用者 10-09 確認 |
| C | `gpt-reserve`、`gpt-5.5` | 使用者 10-09 確認 |
| D | Haiku、`gpt-6-luna` | 使用者 10-09 確認 |

使用者 11-06：「然後gpt那邊改sol吧，astra主要在於圖像、創意這塊有能力增長，但一般工作上sol也能達到差不多的等級，但價格僅1/3。」——所以級別不動，gpt 系一般工作（寫碼、審查、調查）一律 sol，astra 只在圖像、創意類才派。**11-14 起本專案蒐集和施工不用 terra、不走 codex CLI**（使用者「不要terra，盡量用sol，把sol作爲sonnet來用」「不要走codex」）：簡單工作也給 sol，sol 走不通由 Claude 子 agent 補位（普通 opus、簡單 sonnet），見 [dispatch/aos-teams](../dispatch/aos-teams.md)。（11-06 當時的寫法是「codex 一般工作一律 `gpt-6.1-sol`、簡單工作 `gpt-5.6-terra`」。）

現用版本：Fable 5.2、Opus 5.5、Sonnet 5.5，級別沿用。使用者 10-09 確認的各列依據 [probe](probe-2026-10-09.json)（一題一次）。

新增用途欄（調查、寫作、實機操作…）時**只加欄、不改既有級別**——級別是使用者定的。

## 三、token 消耗速度

兩條規則：

- **Claude 系列**：消耗速度基本**與聰明度成正比**（越聰明越貴）。
- **GPT 系列**：整體**往下移兩級**。

重點是推導出來的那一格：**「聰明度高、消耗速度低」的那一格就是性價比之神，工人層大量用它。**

| 模型 | 聰明度 | 消耗速度 | 結論 |
|---|---|---|---|
| gpt-sol | A | C（A 下移兩級）| **性價比之神；工人層主力** |
| gpt-terra、gpt-luna | C／D | E／F（同規則下移兩級）| 便宜到掉出 Claude 的表 |
| 6.1-sol、astra／6-sol／reserve、5.5／6-luna | A／B／C／D | C／D／E／F | 6.1-sol 接 gpt-sol 的位子；astra 實際價格約 sol 的 3 倍（使用者 11-06「價格僅1/3」），一般工作不派 |
| Haiku | D | D | — |
| Fable／Opus／Sonnet | 見上表 | 與聰明度同級 | — |
