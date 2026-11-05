# aos 接下來要做什麼

← [文件索引](README.md)｜[aos 是什麼](overview.md)

這份 roadmap 已經拆進 **[`docs/roadmap/`](roadmap/README.md)**。它只回答**順序**——
`.aos` 的規格以 [`.aos` 資料夾標準](aos-folder.md) 為準，`$` 指示詞的設計以
[inst 的 `$` 指示詞](inst-directives.md) 為準。

**先看導覽：[`roadmap/README.md`](roadmap/README.md)。**

| 檔案 | 裡面有什麼 | 什麼時候會想看 |
|---|---|---|
| [roadmap/situation.md](roadmap/situation.md) | 一句話的方向；`core/inst`／`core/tooljson`／`core/llms` 的現況盤點與一句話的診斷 | 想知道「為什麼主線是先做回合原語」 |
| [roadmap/stages.md](roadmap/stages.md) | 主線階段 **T0–T6**：每階段做什麼、驗收條件 | 「我接下來要做哪一塊」 |
| [roadmap/decisions.md](roadmap/decisions.md) | 決策紀錄 **D1–D10**：每題在問什麼、拍板成什麼、為什麼 | 「當初為什麼決定 X」 |
| [roadmap/boundaries.md](roadmap/boundaries.md) | 三條鐵律；明確不做的事 | 想確認某件事是「漏做」還是「刻意不做」 |
| [roadmap/relations.md](roadmap/relations.md) | 和 `wf/` 既有紀錄的關係表；從 `agent-machine`／`freepy` 借了什麼、沒借什麼 | 想知道這份和別的紀錄誰說了算 |

## 主線階段 T0–T6

全文在 [`roadmap/stages.md`](roadmap/stages.md)。

| # | 標題 | 去哪看 |
|---|---|---|
| T0 | `inst` 的 schema 擴充　**【已完成】** | [stages.md](roadmap/stages.md) |
| T1 | `aos exec <folder>` 與 `aos init`：回合原語　**【已完成】** | [stages.md](roadmap/stages.md) |
| T2<a id="t2"></a> | 取件與投遞協定：`inst.tempd/`、`.temp`、`.runi`　**【已完成，但投遞那一步只有協定沒有 API】** | [stages.md#t2](roadmap/stages.md#t2) |
| T3 | 彙整與發布：接出下一回合　**【已完成】** | [stages.md](roadmap/stages.md) |
| T4<a id="t4-的注意事項"></a> | 迴圈：`aos exec --loop <毫秒>`，不做 `core/daemon`　**【已完成】**（含〈注意〉：crash 後 `--loop` 會永遠拒絕啟動） | [stages.md#t4-的注意事項](roadmap/stages.md#t4-的注意事項) |
| T5<a id="t5"></a> | agent loop：**不需要 `core/llms`**（⚠ 驗收與 [D6](#d6) 矛盾、還沒拍板——**在拍板之前不要照那條驗收去實作**） | [stages.md#t5](roadmap/stages.md#t5) |
| T6<a id="t6"></a> | 把 LLM 內化：`aos llm exec <folder>` | [stages.md#t6](roadmap/stages.md#t6) |

## 決策紀錄 D1–D10

全文在 [`roadmap/decisions.md`](roadmap/decisions.md)。

| # | 標題 | 去哪看 |
|---|---|---|
| D1<a id="d1"></a> | `.aos` 的版面　**已定，且已實作** | [decisions.md#d1](roadmap/decisions.md#d1) |
| D2<a id="d2"></a> | 一回合＝一整批，還是一筆？　**已定：一整批** | [decisions.md#d2](roadmap/decisions.md#d2) |
| D3<a id="d3"></a> | 阻塞還是非阻塞？　**已定：回合內並行，回合邊界不變** | [decisions.md#d3](roadmap/decisions.md#d3) |
| D4<a id="d4"></a> | llms／tooljson 是原地改造還是重長一次？　**已定：先不動** | [decisions.md#d4](roadmap/decisions.md#d4) |
| D5<a id="d5"></a> | `inst` 要不要長出「stderr 併進 stdout」？（跟著 D4 一起延後） | [decisions.md#d5](roadmap/decisions.md#d5) |
| D6<a id="d6"></a> | `.runi` 存在時代表什麼？　**已定：拒絕啟動** | [decisions.md#d6](roadmap/decisions.md#d6) |
| D7<a id="d7"></a> | 投遞怎麼避免撞名？　**已定：投遞匣是目錄 `inst.tempd/`** | [decisions.md#d7](roadmap/decisions.md#d7) |
| D8<a id="d8"></a> | `aos inst` 這條子命令留不留？　**已定：直接刪掉** | [decisions.md#d8](roadmap/decisions.md#d8) |
| D10<a id="d10"></a> | 回合的退出碼怎麼算？　**已定：沿用現有契約，加一個 3** | [decisions.md#d10](roadmap/decisions.md#d10) |
| D9<a id="d9"></a> | `aos exec` 就是那個「唯一入口」　**已定** | [decisions.md#d9](roadmap/decisions.md#d9) |

其餘章節（三條鐵律、明確不做的事、和既有紀錄的關係、參考來源借了什麼）見
[`roadmap/boundaries.md`](roadmap/boundaries.md) 與 [`roadmap/relations.md`](roadmap/relations.md)。
