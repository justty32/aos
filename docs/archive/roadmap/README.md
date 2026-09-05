# aos 接下來要做什麼

← [文件索引](../README.md)｜[aos 是什麼](../overview.md)｜模型來源 [`wf/workflows/ideas/`](../../wf/workflows/ideas/README.md)

> **`.aos` 的規格已經抽成獨立文件：[`.aos` 資料夾標準](../aos-folder.md)。** 版面、命名、
> 交接協定、路徑基準、退出碼、版本、git 邊界一律以那份為準；本檔只留「什麼時候做」與
> 「為什麼這樣排」。

這份只回答**順序**：既然回合制模型已經定了方向，接下來該先做哪一塊、哪些事要先問
使用者、哪些明確不做。**模型本身不在這裡定義**——它在
回合制資料夾 與
全域 LLM CPU，本檔與那兩份衝突時以它們為準。

各階段標了狀態：**已定**（使用者拍過板）、**建議**（本檔的主張，可被推翻）、
**待拍板**（不能由我偷偷補成答案）。

---

## 這個資料夾裝什麼

| 檔案 | 裡面有什麼 | 什麼時候會想看 |
|---|---|---|
| [situation.md](situation.md) | 一句話的方向；`core/inst`／`core/tooljson`／`core/llms` 的現況盤點與一句話的診斷 | 想知道「為什麼主線是先做回合原語，而不是繼續移植 llmkit」 |
| [stages.md](stages.md) | 主線階段 **T0–T6**：每階段做什麼、驗收條件 | 「我接下來要做哪一塊」 |
| [decisions.md](decisions.md) | 決策紀錄 **D1–D10**：每題在問什麼、拍板成什麼、為什麼 | 「當初為什麼決定 X」 |
| [boundaries.md](boundaries.md) | 三條鐵律；明確不做的事 | 想確認某件事是「漏做」還是「刻意不做」 |
| [relations.md](relations.md) | 和 `wf/` 既有紀錄的關係表；從 `agent-machine`／`freepy` 借了什麼、沒借什麼 | 想知道這份和別的紀錄誰說了算 |

原路徑 [`docs/roadmap.md`](../roadmap.md) 保留成指標，並在那裡列出每個 T 與每個 D 的
`#錨點`，舊連結（`roadmap.md#t5`、`roadmap.md#d6` …）仍然可用。
