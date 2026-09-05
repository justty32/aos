> 封存 2026-09-05，由 wf/workflows/ideas/README.md（新版構想集）取代

# 鏈＝行程：CPS、三層與 `series.json`（§九–§十三）

← [assembly-and-chains](README.md)｜[ideas](../README.md)｜[WORKFLOWS](../../../WORKFLOWS.md)

## 第二部分 · 我的觀察（主 session，不是裁決，使用者可否決）

### 九、自供給＝CPS，而它在三個地方付錢

「執行完自己投下一步」就是 **continuation-passing style**：控制流不在任何資料結構裡，
只在**還沒被呼叫的那個後繼**裡。結構性弱點是**未來不可見**，三處付錢：

| 付錢的地方 | 怎麼付 |
|---|---|
| **容錯** | inst 在投出後繼**之前**掛掉，這條鏈**無聲死亡**，沒有 PC 可以恢復 |
| **排程**（`G16`） | 看不見未來，就排不了優先序、算不出配額 |
| **GOAP**（`G04`） | GOAP 要的正是**可見的 plan**，CPS 剛好把它藏起來 |

**建議：自供給當機制，stored program 當資料。** plan 存成世界裡的一個檔（JSON 陣列，
天生有序）＋一個**游標檔**（游標就是這條鏈的 PC）；每一步**讀 plan、推游標、投遞下一步**。

這正好就是 `G14` 要的**載入器**，而且**全部可以用 inst 做在使用者層、不進 loop**——與第十輪
「**loop 只收無法成為 inst 的東西**」的判準相容（**「不進 loop」已被第三部分取代**：使用者
把它上移進 loop）。附帶：plan 用 JSON 陣列即有序，
[program-form](../program-form.md) 的 program-form 裂縫 1（**資料夾無序**）在這條線上**不必解**。

### 十、兩難其實是三層疊在一個詞上

使用者的兩難之所以難，是因為「指令」一個詞扛了三層：

| 層 | 是什麼 | 對應 |
|---|---|---|
| `inst` | **指令** | 一條 |
| 自供給的鏈 | **行程** | `G06` |
| 批 | **tick** | 遊戲引擎一格掃所有 entity |

**該模仿的不是單發射 CPU，是遊戲引擎。** 一個 tick 掃所有 entity，本來就該一次拿一批——
所以「留著批」與 [game-process-model](../game-process-model.md) 是同一個決定的兩面。

代價很具體：**鏈需要 id**（後繼要歸屬到哪條鏈、中斷要指名哪條鏈——那就是 signal），
而**「id 寫哪」＝批 header**。於是——

> **`B1`（批沒有名字／header）現在被三條線同時需要**：CPU 線要它做去重、REPL 線要它做
> 輸入歷程（[theses-review §二](../theses-review.md)）、彙編線要它做**鏈歸屬**。
> **它是全局最超載的未決點。**

## 第三部分 · `series.json`（使用者口述 2026-09-01）

### 十一、自供給最基本，但投遞失敗整條鏈就斷

所以 **loop 必須另讀一個 `series.json`**：記**在執行哪些一串彙編**與**執行到哪裡**，
跑 inst 時自然去抓 serie 的下一筆。**排程**沿用它：serie 可報未來幾回合的**資源消耗**
（cpu／llm…）與**建議優先級**；**可見性**＝serie 可報自身未來好幾回合要幹嘛。
**格式等實作再說。**

### 十二、（以下皆觀察）一份檔四種身分

行程表（`G06`）＋游標（PC）＋排程輸入（`G16`）＋可見窗口。**loop 讀它決定抓哪筆＝
`B2`「loop 沒有可分支狀態」的答案方向**；抓取天生只有 loop 做得到，故合第十輪判準。

### 十三、四個邊緣狀況

1. **游標誰推、何謂成功才推**：A 區「exit status 分不開傳輸與應用失敗」**從欠帳升為擋路**。
2. **多寫者熱點**：loop／串自身／外部中斷寫同一格，`B14` 重演；刪了它串全死＝**架構狀態**→ **atomic 寫＋`fsync`**（第三次被點名）、進 git。
3. **串的生滅**：新串怎麼誕生、跑完誰清沒定，別重犯 `batch/` 只長不清。
4. **資源是自我申報**：排程器只能當參考，單人環境夠用。

## 相關

- [interrupts](interrupts.md)——本篇的上一段：中斷／跳轉、批的裁決
- [c-language](c-language.md)——C 語言線：函數／堆疊框怎麼對應到串
- [self-delivery-in-loop](../self-delivery-in-loop.md)——自我投遞埋不埋進 loop（自供給的現成案例）
- [theses-review](../theses-review.md)——批 header 是 CPU／REPL 兩讀法的共同地基
- [machine-shape/instruction](../machine-shape/instruction.md)——批沒有名字與 header（`B1`）
- [cpu-to-os-gaps](../cpu-to-os-gaps.json)——`G04`／`G06`／`G14`／`G16`
