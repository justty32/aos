# 知識工作 flavor 包

← [repo README](../../README.md)（導航中樞）

**非開發的知識工作**用的工作流包：寫作、閱讀消化、規劃、決策、學習、整理。搭配 [`template/`](../../template/) 這個**共用 kernel** 一起用——kernel 提供分層樹骨架（AGENTS / WORKFLOWS 派發器 / INDEX / STRUCTURE / 活狀態 / planning / decisions / common），本包只提供**知識類工作流**：把開發 flavor 的「code map / testing」換成「info-map / 可觀察的 `Done when`」。

## 這個包有什麼

| 路徑 | 角色 |
|------|------|
| [WORKFLOWS.knowledge.md](WORKFLOWS.knowledge.md) | **派發表片段**（六列 + 「分辨」欄），貼進 kernel 的 `WORKFLOWS.md` |
| [COMMON.knowledge.md](COMMON.knowledge.md) | **common 表片段**（兩列），貼進 kernel 的 `workflows/common/README.md` |
| [workflows/write.md](workflows/write.md) | 內容產出：文章 / 筆記 / 文件 / 翻譯 / 貼文 |
| [workflows/digest.md](workflows/digest.md) | 讀懂一份材料，產出摘要與出處索引 |
| [workflows/plan-a-thing.md](workflows/plan-a-thing.md) | 規劃一件非開發的事 |
| [workflows/decide.md](workflows/decide.md) | 結構化決策，結論落到 kernel 的 decisions |
| [workflows/learn.md](workflows/learn.md) | 長期吸收一個主題，長出可回訪的筆記樹 |
| [workflows/organize.md](workflows/organize.md) | 把一堆資訊整理成好導航的結構 |
| [workflows/common/writing.md](workflows/common/writing.md) | 寫作風格（＋ [writing/zh-tw.md](workflows/common/writing/zh-tw.md) 繁中用字），產出給人讀的文字時共用 |
| [workflows/common/info-map.md](workflows/common/info-map.md) | 材料導航 index：`材料 \| 位置 \| 負責什麼 \| 衍生產物` |

## 怎麼合進 kernel

```
tools/wf-init.sh --target <專案> --flavor knowledge
```

通用步驟（複製 kernel → 併 `workflows/` → 貼片段 → 填 `{{}}`／處理〔導入判斷〕〔模板說明〕→ 跑 lint）見 [IMPORT.md](../../IMPORT.md)。本包特有的兩點：`common/writing.md`、`common/writing/`、`common/info-map.md` 併入 `workflows/common/`；片段檔兩個——[WORKFLOWS.knowledge.md](WORKFLOWS.knowledge.md) 貼進 `WORKFLOWS.md` 的 `<!-- wf-insert:WORKFLOWS -->` 之前，[COMMON.knowledge.md](COMMON.knowledge.md) 貼進 `workflows/common/README.md` 的 `<!-- wf-insert:COMMON -->` 之前。

## 可選工作流菜單

上表六個工作流是**菜單、不是套餐**：一個知識工作專案通常只用得到其中兩三個（例：只寫作 → write + writing；只研讀 → digest + learn + info-map）。

- 導入時只複製你要的那幾個工作流檔，派發表也只貼對應的列。
- 已經導入、事後才決定不要某個 → 照下面「移除某工作流要動的地方」表拆乾淨。
- 六個都不夠用時，複製 kernel 的 `workflows/TEMPLATE.workflow.md` 開新的，在派發表加一列。

idea / roadmap / 詳規這條**規劃管線**不在本包——它與領域無關，收在 kernel 的 `workflows/planning.md`。plan-a-thing 是那條管線的「非開發執行段」。

## 混合型專案（同時合 dev 包）

兩包都合、兩張派發表都貼時，會有三處需要人工裁決：

| 撞到的地方 | 怎麼分 |
|-----------|--------|
| dev 的 **spec / plan** vs 本包的 **plan-a-thing** | 以「**產出是不是程式碼**」分流：是 → spec / plan；不是 → plan-a-thing。這條已寫進派發表的「分辨」欄。 |
| dev 的 **conventions** vs 本包的 **writing** | conventions 管**原始碼**（拆檔、命名、breaking change 同步）；writing 管**給人讀的文字**。寫 README、設計說明、commit 訊息這類**文字**時以 writing 為準。 |
| 兩包的 **gotchas** | 沒有衝突：gotchas 是 kernel 內建、只有一份（`workflows/common/gotchas.md`），兩包的派發表都不重複列它。 |

info-map（材料結構）與 code map（程式碼結構）可以並存，各管各的，不必合成一份。

## 移除某工作流要動的地方

移除一個工作流，四個位置都要動；動完跑 `tools/wf-lint.sh`（Claude Code 可用 `/wf-lint`）確認沒有 `BROKEN`。

| 工作流 | 檔案 | 派發表列 | 還被誰引用（要一併改掉那句）|
|--------|------|---------|---------------------------|
| write | `workflows/write.md` | 「寫一篇東西…」 | digest、learn、organize 的「交接」；plan-a-thing 交接 |
| digest | `workflows/digest.md` | 「幫我讀懂這份材料…」 | write「何時不用」；learn 的開頭與「何時不用」、交接 |
| plan-a-thing | `workflows/plan-a-thing.md` | 「規劃一件事…」 | digest 交接；decide 交接；kernel `planning.md` 階段表 |
| decide | `workflows/decide.md` | 「在幾個選項間做決定」 | plan-a-thing「何時不用」與交接；kernel `decisions.md`「何時不用」 |
| learn | `workflows/learn.md` | 「學一個主題…」 | digest「何時不用」與交接 |
| organize | `workflows/organize.md` | 「整理一堆資訊…」 | write 交接；learn 交接；`common/info-map.md` 開頭 |
| （共用）writing | `workflows/common/writing.md`＋`writing/` | — | `common/README.md` 一列；write 的 Done when 與流程 |
| （共用）info-map | `workflows/common/info-map.md` | — | `common/README.md` 一列；organize「導航 index」段與 Done when；digest 交接 |
