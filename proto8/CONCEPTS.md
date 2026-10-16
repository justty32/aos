# proto8 概念層（第二版，AI 從使用者的話抽出來的，2026-10-11）

← [proto8](README.md)｜來源：[10-11 討論 §2、§3b](thinking/2026-10-11-restart.md)、使用者九月草稿 [9/19](../thinking/2026-09-19.md)、[9/23](../thinking/2026-09-23.md)、[9/24](../thinking/2026-09-24.md)｜對照：[10-03 核心 spec](../proto7/spec/core.md)｜三份獨立抽的合併：AI 自己第一版（f7903867）、Fable 獨立抽（已刪：AI 產出，使用者 10-12 夜要求刪除）、診斷為什麼問錯（已刪：AI 產出，使用者 10-12 夜要求刪除）

**只收使用者說過的。** 每條引出處。這份**沒有檔名、沒有格式、沒有程式結構、沒有步驤、沒有第一版**——那是下一層，使用者講了才有。「世界」「需求」「排序器」「順序表」這幾個詞是 AI 之前造的，使用者沒說過，這份不用。

<!-- wf-nav -->
## 分檔（10-15 使用者定：按主題分）

「規則」（使用者說「一定是這樣」的，條號 C-）原本是一份，10-15 起按主題拆；條號不重編，條文原樣搬過來。C-36 以後來自 10-11 晚的實作口述（restart §3g），使用者講得像定了的，所以也列進規則；要改隨時改。每份第一行寫出該主題的概念、規範、實作在哪。

| 分檔 | 主題 | 條號 |
|---|---|---|
| [01-設計理念.md](CONCEPTS/01-設計理念.md) | 設計理念 | C-01～C-04、C-07、C-24、C-43、C-45、C-48、C-51～C-56（**C-56 KISS＝最高原則，也是最後原則**；C-52／C-53 兩條總原則；C-54 命名；旁邊的 [abbr.json](CONCEPTS/abbr.json)＝aos 認可縮寫表；C-55 布局成長） |
| [02-設計理念-時空.md](CONCEPTS/02-設計理念-時空.md) | 設計理念／時空 | C-05、C-06、C-16、C-17、C-26、C-27、C-30～C-33、C-35、C-37、C-44 |
| [03-基礎設施.md](CONCEPTS/03-基礎設施.md) | 基礎設施：inst、loop 與 daemon、組合子（tasks、fsm） | C-08、C-18、C-25、C-34、C-36、C-39、C-41、C-42b、C-49 |
| [04-kernel.md](CONCEPTS/04-kernel.md) | kernel | C-09～C-15、C-28、C-29、C-38、C-47 |
| [05-agent.md](CONCEPTS/05-agent.md) | agent：腦、工具、可預測性、函數＋binding（狀態機那幾條隨 fsm 在基礎設施） | C-19～C-23（含 C-22b）、C-40、C-42、C-46、C-50 |
| [附錄1-名詞.md](CONCEPTS/附錄1-名詞.md) | 附錄 | 1. 名詞（daemon 兩義各一列） |
| [附錄2-例子與待接.md](CONCEPTS/附錄2-例子與待接.md) | 附錄 | 3. 兩個例子、4. 還沒接起來的 16 條、5. AI 對自己的提醒 |

總則（跨主題的規範）沒有專屬的概念條，見 [NORMS 總則](NORMS/01-總則.md)；總則與設計理念維持分開（10-15 使用者「隨你」）。主題總表在 [NORMS.md](NORMS.md)。

## 條號 → 檔

| 條號 | 檔 |
|---|---|
| C-01～C-04 | [設計理念](CONCEPTS/01-設計理念.md) |
| C-05、C-06 | [設計理念-時空](CONCEPTS/02-設計理念-時空.md) |
| C-07 | [設計理念](CONCEPTS/01-設計理念.md) |
| C-08 | [基礎設施](CONCEPTS/03-基礎設施.md)（inst） |
| C-09～C-15 | [kernel](CONCEPTS/04-kernel.md) |
| C-16、C-17 | [設計理念-時空](CONCEPTS/02-設計理念-時空.md) |
| C-18 | [基礎設施](CONCEPTS/03-基礎設施.md)（fsm） |
| C-19～C-23（含 C-22b） | [agent](CONCEPTS/05-agent.md) |
| C-24 | [設計理念](CONCEPTS/01-設計理念.md) |
| C-25 | [基礎設施](CONCEPTS/03-基礎設施.md)（fsm） |
| C-26、C-27 | [設計理念-時空](CONCEPTS/02-設計理念-時空.md) |
| C-28、C-29 | [kernel](CONCEPTS/04-kernel.md) |
| C-30～C-33 | [設計理念-時空](CONCEPTS/02-設計理念-時空.md) |
| C-34 | [基礎設施](CONCEPTS/03-基礎設施.md)（inst） |
| C-35 | [設計理念-時空](CONCEPTS/02-設計理念-時空.md) |
| C-36 | [基礎設施](CONCEPTS/03-基礎設施.md)（loop 與 daemon） |
| C-37 | [設計理念-時空](CONCEPTS/02-設計理念-時空.md) |
| C-38 | [kernel](CONCEPTS/04-kernel.md) |
| C-39 | [基礎設施](CONCEPTS/03-基礎設施.md)（fsm） |
| C-40 | [agent](CONCEPTS/05-agent.md) |
| C-41 | [基礎設施](CONCEPTS/03-基礎設施.md)（tasks） |
| C-42 | [agent](CONCEPTS/05-agent.md) |
| C-42b | [基礎設施](CONCEPTS/03-基礎設施.md)（inst） |
| C-43 | [設計理念](CONCEPTS/01-設計理念.md) |
| C-44 | [設計理念-時空](CONCEPTS/02-設計理念-時空.md) |
| C-45 | [設計理念](CONCEPTS/01-設計理念.md) |
| C-46 | [agent](CONCEPTS/05-agent.md) |
| C-47 | [kernel](CONCEPTS/04-kernel.md) |
| C-48 | [設計理念](CONCEPTS/01-設計理念.md) |
| C-49 | [基礎設施](CONCEPTS/03-基礎設施.md)（fsm） |
| C-50 | [agent](CONCEPTS/05-agent.md) |
| C-51～C-56 | [設計理念](CONCEPTS/01-設計理念.md)（C-56 KISS＝最高原則，也是最後原則：先滿足需求與其他原則，最後做減法） |
