> 封存 2026-09-05，由 wf/workflows/ideas/README.md（新版構想集）取代

# 怎麼跑起來：最基礎使用方式、agent loop 與單回合流程
← [turn-based-folder](README.md)｜[ideas](../README.md)｜[WORKFLOWS](../../../WORKFLOWS.md)

## 最基礎的 aos 使用方式（方向已定）

1. 給 aos 一個指定資料夾，跑 `aos exec --loop 0 <folder>`。
2. 它持續查詢 `.aos/inst.json` 有沒有待執行內容。
3. instruction 出現後，先完整讀進記憶體，**立刻**把 `inst.json` `rename` 成
   `inst.json.runi`，然後才執行其中的指令。
4. 指令造成的資料夾變化構成下一回合的狀態；執行期間要排入下一回合的生產者，把
   instruction 投遞到 `.aos/inst.tempd/<pid>.json`。
5. 本回合執行完畢後，彙整 `.aos/inst.tempd/` 底下所有投遞，發布成新的 `.aos/inst.json`。
6. 新的 `inst.json` 成為下一回合輸入，再次消費，形成循環。

因此它不是靠時間連續更新資料夾，而是等待離散的 instruction 批次；沒有新的
`inst.json` 就停留在目前回合。

## agent loop 如何建立在回合模型上

> **指令名字已經被更新的一篇取代**：`aos agent start` ＋ `aos agent init ...` 兩段式入口，
> 在 [top-down-cli](../top-down-cli.md)（2026-08-30）被改成單一的 `aos agent init`，`aos exec`
> 也歸進 `aos pu`。這裡保留的是**回合模型怎麼承載 agent loop** 的推導；**指令面以那篇為準**。

```text
aos exec --loop 0 監看 folder
        ↓
使用者在 folder 執行 aos agent start
        ↓
準備 .aos/ 與 agent 所需資料
        ↓
下一回合加入 aos agent init ...
        ↓
載入 folder 資訊、LLM、工具、人格與記憶
        ↓
啟動一次 LLM，完成 agent 的本回合動作
        ↓
需要繼續時，在結束前把下一步投遞到 inst.tempd/
        ↺
```

> **第一版 agent loop 不需要 `core/llms`**：`inst` 跑的是 POSIX 指令，所以「呼叫一次
> 模型」可以先用任何一支現成的 LLM CLI 頂著，整個 loop 就是一份 `.aos/inst.json` 加幾
> 支腳本。自家的 LLM CPU 是之後把它換掉，不是前置條件。見
> [roadmap 的 T5／T6](../../roadmap.md)。

- `aos agent start` 是使用者在指定資料夾內啟動 agent 的入口；它準備所需內容，並讓
  `.aos/inst.json` 的下一回合包含 `aos agent init ...`。
- `aos agent init ...` 會載入該資料夾的各類資訊，包括使用哪個 LLM 思考引擎、可用
  工具、核心人格與記憶，然後觸發 agent 的第一次 LLM 動作。
- agent loop 不必是一個永遠不返回的函式。需要跨多回合長期運作的工作，在本回合快
  結束時把下一次動作投遞到 `.aos/inst.tempd/<pid>.json`；回合結束後彙整並發布下一份
  `inst.json`，下一次消費它就形成下一回合。
- 使用者介入也成為回合模型的一部分：可以在後續 instruction 被消費前改變世界狀態，
  或提供會影響下一回合的輸入。

## 與目前 aos 元件的關係

- `core/inst` 提供「執行一次狀態轉移」的底層能力，`aos exec` 是它的子命令。
- `core/llms` 與 `core/tooljson` 可提供 agent 回合中的思考與工具能力——但兩者目前的
  形狀不符合本模型，要改造（見 [SESSION-LOG](../../../SESSION-LOG.md) 與
  [roadmap](../../roadmap.md)）。
- **不再需要獨立的 `core/daemon`**：持續執行是 `aos exec --loop 0` 這個旗標，
  不是另一個小專案。
- agent 初始化與 LLM 回合邏輯仍是建立在 `exec`／`inst` 之上的後續能力，不混進回合
  原語的基礎職責。

## 單回合流程（已定）

```text
等待 .aos/inst.json
        ↓
完整讀入記憶體
        ↓
立刻 rename 成 .aos/inst.json.runi   ← 對 inst.json 那個位置來說就是刪除了
        ↓
執行本回合 instruction（資料夾狀態轉移）
        ↓
掃描 .aos/inst.tempd/ 下所有投遞（略過 .temp）
        ↓
彙整成 .aos/inst.json.temp，再 rename 蓋掉 .aos/inst.json
        ↓
進入下一回合
```

先讓當前 `inst.json` 從那個位置消失再執行，是基礎協定的一部分，不等執行成功才做。
`.aos/inst.tempd/` 則是本回合各個生產者提交後續動作的投遞匣；只在本回合執行結束後收集
它們。
