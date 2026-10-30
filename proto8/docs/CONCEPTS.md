# proto8 概念層（AI 從使用者的話抽出來的，2026-10-11）

← [proto8](../README.md)｜來源：[10-11 討論 §2、§3b](../thinking/2026-10-11-restart.md)、使用者九月草稿 [9/19](../../thinking/2026-09-19.md)、[9/23](../../thinking/2026-09-23.md)、[9/24](../../thinking/2026-09-24.md)｜對照：[10-03 核心 spec](../../proto7/spec/core.md)

**只收使用者說過的。** 每條引出處。這份**沒有檔名、沒有格式、沒有程式結構、沒有步驤、沒有第一版**——那是下一層，使用者講了才有。「世界」「需求」「排序器」「順序表」這幾個詞是 AI 之前造的，使用者沒說過，這份不用。

<!-- wf-nav -->
## 分檔（10-15 使用者定：按主題分）

「規則」（使用者說「一定是這樣」的，條號 C-）按主題分檔，條號不重編。C-36 以後來自 10-11 晚的實作口述（restart §3g），使用者講得像定了的，也列進規則；要改隨時改。每份第一行寫出該主題的概念、規範、實作在哪。

| 分檔 | 主題 | 條號 |
|---|---|---|
| [01-設計理念.md](CONCEPTS/01-設計理念.md) | 設計理念 | C-01～C-04、C-07、C-24、C-43、C-45、C-48、C-51～C-56、C-64、C-68～C-74（**C-56 KISS＝最高原則，也是最後原則**；C-52／C-53 兩條總原則；C-54 命名；旁邊的 [abbr.json](CONCEPTS/abbr.json)＝aos 認可縮寫表；C-55 布局成長；C-64 用檔案為了借 Linux 權限；C-68～C-70 資料夾＝程式、aos 只訂環境變數、巢狀由程式自己訂子 stack；C-71 資料夾的比喻用 table；C-72 JSON＝埋在檔案裡的 table、入口尋址方式同樣適用；C-73 entry 的定義＝可執行檔或 aos-exec 完整實作跑得動的檔〔四種〕；C-74 分層＝基礎層〔核心 aos-exec＋loop、daemon〕→ 標準庫〔fsm、tasks〕→ agent／kernel） |
| [02-設計理念-時空.md](CONCEPTS/02-設計理念-時空.md) | 設計理念／時空 | C-05、C-06、C-16、C-17、C-26、C-27、C-30～C-33、C-35、C-37、C-44 |
| [03-基礎設施.md](CONCEPTS/03-基礎設施.md) | 基礎設施：inst、loop 與 daemon、proc 之間的交流（投遞、窗、父子交代，10-29）、組合子（tasks、fsm）、資料夾程式、工作區與 stack（10-19） | C-08、C-18、C-25、C-34、C-36、C-39、C-41、C-42b、C-49、C-65～C-67、C-75 |
| [04-kernel.md](CONCEPTS/04-kernel.md) | kernel | C-09～C-15、C-28、C-29、C-38、C-47 |
| [05-agent.md](CONCEPTS/05-agent.md) | agent：腦、工具、可預測性、函數＋binding、工具（狀態機那幾條隨 fsm 在基礎設施） | C-19～C-23（含 C-22b）、C-40、C-42、C-46、C-50、C-61、C-62 |
| [附錄1-名詞.md](CONCEPTS/附錄1-名詞.md) | 附錄 | 1. 名詞（daemon 兩義各一列；含資料夾程式、入口、`aos-exec`、stack、小格，工作區、指標） |
| [附錄2-例子與待接.md](CONCEPTS/附錄2-例子與待接.md) | 附錄 | 3. 兩個例子、4. 還沒接起來的 16 條、5. AI 對自己的提醒 |

總則（跨主題的規範）沒有專屬的概念條，見 [NORMS 總則](NORMS/01-總則.md)；總則與設計理念維持分開（10-15 使用者「隨你」）。主題總表在 [NORMS.md](NORMS.md)。

## 命名統合的使用者原話（10-23～10-25）

細則都在 [C-54](CONCEPTS/01-設計理念.md#命名10-15-使用者說原文) 與 [C-54 命名方法](CONCEPTS/01-設計理念/C-54-命名方法.md)；這裡只留原話與出處。不留舊名。

- **10-23 命名統合**（[thinking 2026-10-23-naming](../thinking/2026-10-23-naming.md)）：使用者「都先幫我統合。統合好後更新文件和artifact，我等一下重看」；逐條看過頂層的統合，其餘認可，三條改選：純文字也帶 `.txt`、stack 預設位置 `.stack/`（C-65）、題目資料夾 `new/`＋照 Maildir 認領 `cur/`（C-65）。C-54 錯誤代號一律四種結尾＋`Internal`；[縮寫表](CONCEPTS/abbr.json)有 `co`、`dotenv`。
- **10-23 晚「要跑什麼」**：使用者「改，beats改runs，然後val寫要跑啥，通常不會用val，應該用run。」，衝突時選「只有 loop、daemon 用 run」；深夜使用者「fsm.json，現在是用val，幫我改成exec」，再選「exec，loop／daemon 的 run 也一起改 exec」——「要跑什麼」全體系一律叫 `exec`（loop／daemon、fsm 的每一格），C-55 的 `val` 只留給值的展開形；條文與訊息裡說「次」，不說「拍」。
- **10-23 晚入口與 `_` 開頭的 key**（[thinking 2026-10-23-naming](../thinking/2026-10-23-naming.md)）：使用者問「換_entry，有好處嗎」，聽完利弊後「改。然後_開頭=附註這個概念刪掉。」，又補「不認得的key就是忽略」——入口預設名 `_entry`（`AOS_ENTRY` 預設值、入口檔、JSON 的 key；使用者原話裡的 `_exec` 照留）；C-48 是通則「不認得的 key 一律忽略、不報錯」，沒有 `_notes` 慣例。
- **10-23 晚命名方法**（[thinking 2026-10-23-naming-method](../thinking/2026-10-23-naming-method.md)）：使用者「先試試看，不要急着寫進去」，查過 Unix／Linux 老慣例、八題選完後「寫進去吧」——C-54 的「命名方法」一點，R1～R12 細則在 [C-54 命名方法](CONCEPTS/01-設計理念/C-54-命名方法.md)。
- **10-25 state.json、計數、時間點、上限**：使用者「state.json中，runs改counter，at改成recorded_at」、「計數這塊，幫我改成counter_*」；頂層問兩題（時間點規則要不要跟著改、上限要不要照 R6 改 `max_*`），使用者回「都好」（頂層代定、可翻案）——計數一律 `counter_<被數的東西>`（state.json 是 `counter_runs`）、時間點一律 `<發生了什麼>_at`（state.json 是 `recorded_at`）、上限一律 `max` 或 `max_*`（[C-54 命名方法 R3、R6](CONCEPTS/01-設計理念/C-54-命名方法.md)）。
- **10-30 程式名**（[thinking 2026-10-30-eca](../thinking/2026-10-30-eca.md#決定10-30) F-21、[10-30 map-review](../thinking/2026-10-30-map-review.md#決定10-30) 第 9、11 點）：使用者「我其實更prefer前者，因為以後會有一大堆領域，而kernel作為基底，他就是算...lib？」（aos-kernel-llm 改名 aos-llm-kernel），再要 aos-gate 換名字；頂層推成「程式名＝`aos-<領域>-<功能>`」寫進條文草稿，使用者 10-30「都照建議」——[C-54 命名方法](CONCEPTS/01-設計理念/C-54-命名方法.md) R13（頂層推論、可翻案）。

## 條號表

<!-- wf-nav -->
| 分檔 | 涵蓋的段 |
|---|---|
| [附錄3-條號表.md](CONCEPTS/附錄3-條號表.md) | 條號 → 檔（含作廢條號與各批出處） |
