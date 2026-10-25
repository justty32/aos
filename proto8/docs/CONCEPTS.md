# proto8 概念層（第二版，AI 從使用者的話抽出來的，2026-10-11）

← [proto8](README.md)｜來源：[10-11 討論 §2、§3b](thinking/2026-10-11-restart.md)、使用者九月草稿 [9/19](../thinking/2026-09-19.md)、[9/23](../thinking/2026-09-23.md)、[9/24](../thinking/2026-09-24.md)｜對照：[10-03 核心 spec](../proto7/spec/core.md)｜三份獨立抽的合併：AI 自己第一版（d64dd096）、Fable 獨立抽（已刪：AI 產出，使用者 10-12 夜要求刪除）、診斷為什麼問錯（已刪：AI 產出，使用者 10-12 夜要求刪除）

**只收使用者說過的。** 每條引出處。這份**沒有檔名、沒有格式、沒有程式結構、沒有步驤、沒有第一版**——那是下一層，使用者講了才有。「世界」「需求」「排序器」「順序表」這幾個詞是 AI 之前造的，使用者沒說過，這份不用。

<!-- wf-nav -->
## 分檔（10-15 使用者定：按主題分）

「規則」（使用者說「一定是這樣」的，條號 C-）原本是一份，10-15 起按主題拆；條號不重編，條文原樣搬過來。C-36 以後來自 10-11 晚的實作口述（restart §3g），使用者講得像定了的，所以也列進規則；要改隨時改。每份第一行寫出該主題的概念、規範、實作在哪。

| 分檔 | 主題 | 條號 |
|---|---|---|
| [01-設計理念.md](CONCEPTS/01-設計理念.md) | 設計理念 | C-01～C-04、C-07、C-24、C-43、C-45、C-48、C-51～C-56、C-64、C-68～C-74（**C-56 KISS＝最高原則，也是最後原則**；C-52／C-53 兩條總原則；C-54 命名；旁邊的 [abbr.json](CONCEPTS/abbr.json)＝aos 認可縮寫表；C-55 布局成長；C-64 用檔案為了借 Linux 權限；C-68～C-70 資料夾＝程式、aos 只訂環境變數、巢狀由程式自己訂子 stack；C-71 資料夾的比喻用 table；C-72 JSON＝埋在檔案裡的 table、入口尋址方式同樣適用；C-73 entry 的定義＝可執行檔或 aos-exec 完整實作跑得動的檔〔四種〕；C-74 分層＝基礎層〔核心 aos-exec＋loop、daemon〕→ 標準庫〔fsm、tasks〕→ agent／kernel，10-22） |
| [02-設計理念-時空.md](CONCEPTS/02-設計理念-時空.md) | 設計理念／時空 | C-05、C-06、C-16、C-17、C-26、C-27、C-30～C-33、C-35、C-37、C-44 |
| [03-基礎設施.md](CONCEPTS/03-基礎設施.md) | 基礎設施：inst、loop 與 daemon、組合子（tasks、fsm）、資料夾程式、工作區與 stack（10-19） | C-08、C-18、C-25、C-34、C-36、C-39、C-41、C-42b、C-49、C-65～C-67 |
| [04-kernel.md](CONCEPTS/04-kernel.md) | kernel | C-09～C-15、C-28、C-29、C-38、C-47 |
| [05-agent.md](CONCEPTS/05-agent.md) | agent：腦、工具、可預測性、函數＋binding、工具（狀態機那幾條隨 fsm 在基礎設施） | C-19～C-23（含 C-22b）、C-40、C-42、C-46、C-50、C-61、C-62 |
| [附錄1-名詞.md](CONCEPTS/附錄1-名詞.md) | 附錄 | 1. 名詞（daemon 兩義各一列；10-19 加資料夾程式、入口、`aos-exec`、stack、小格，工作區、指標） |
| [附錄2-例子與待接.md](CONCEPTS/附錄2-例子與待接.md) | 附錄 | 3. 兩個例子、4. 還沒接起來的 16 條、5. AI 對自己的提醒 |

總則（跨主題的規範）沒有專屬的概念條，見 [NORMS 總則](NORMS/01-總則.md)；總則與設計理念維持分開（10-15 使用者「隨你」）。主題總表在 [NORMS.md](NORMS.md)。

**10-23 命名統合**（[thinking 2026-10-23-naming](thinking/2026-10-23-naming.md)，使用者「都先幫我統合。統合好後更新文件和artifact，我等一下重看」）：只換名字、不改原意——C-54 錯誤代號「照舊沿用」翻案、補第四種 `…Failed` 與副檔名／時間／計數規則（原是頂層代定；使用者 10-23 逐條看過，其餘認可，三條改選：純文字也帶 `.txt`、stack 預設位置 `.aos/` 改 `.stack/`（C-65）、題目資料夾 `inbox/` 改 `new/`、照 Maildir 多一步認領 `cur/`（C-65））；C-55 註 loop／daemon 的 `run` 改 `val`；C-48 指示詞例子改 `$path`、註 `_exec`／`.env`；[縮寫表](CONCEPTS/abbr.json)加 `co`、`dotenv`。舊名在歷史敘述裡照留、旁邊加〔10-23 統合…〕註。10-23 晚使用者翻案（「改，beats改runs，然後val寫要跑啥，通常不會用val，應該用run。」，衝突時選「只有 loop、daemon 用 run」）：loop／daemon 改回 `run`（fsm 格仍是 `val`）、state 的 `beats` → `runs`、「拍」→「次」。10-23 深夜：使用者「fsm.json，現在是用val，幫我改成exec」，再選「exec，loop／daemon 的 run 也一起改 exec」——「要跑什麼」全體系一律叫 `exec`（loop／daemon 的 `run`、fsm 格的 `val` 都改），C-55 的 `val` 只留給值的展開形。

**10-23 晚入口改名、刪 `_` 附註**（[thinking 2026-10-23-naming](thinking/2026-10-23-naming.md)，使用者問「換_entry，有好處嗎」，聽完利弊後「改。然後_開頭=附註這個概念刪掉。」，又補「不認得的key就是忽略」）：入口預設名 `_exec` → `_entry`（`AOS_ENTRY` 預設值、入口檔、JSON 的 key 都改；使用者原話裡的 `_exec` 照留）；C-48 刪「`_` 開頭的 key＝附註、宿主程式忽略」與 `_notes` 慣例，改寫成通則「不認得的 key 一律忽略、不報錯」；C-55 跟著刪那半句。

**10-23 晚命名方法**（[thinking 2026-10-23-naming-method](thinking/2026-10-23-naming-method.md)，使用者提方法後「先試試看，不要急着寫進去」，查過 Unix／Linux 老慣例、八題選完後「寫進去吧」）：C-54 加「命名方法」一點，R1～R12 細則放 [CONCEPTS/01-設計理念/C-54-命名方法.md](CONCEPTS/01-設計理念/C-54-命名方法.md)（先寫一行 NAME、每格一句白話、固定格、`<事件>_at`、計數不用 `nr_`、index 用 `idx`、`_` 開頭的檔＝入口…）；C-55 例子跟著改 `stopped`；[縮寫表](CONCEPTS/abbr.json)表頭加 `note`（進表門檻）。

**10-25 state.json 改名**（使用者 10-25「state.json中，runs改counter，at改成recorded_at」）：loop／daemon 的 state.json（N-17、N-32）跑過幾次 `runs` → `counter`、這份 state 的時間 `at` → `recorded_at`；不留舊名。只動 state.json 這兩格：fsm 的 trace、信、kernel-llm 的 queue.json 等其他 JSON 的同名欄位不動。跟 [C-54 命名方法](CONCEPTS/01-設計理念/C-54-命名方法.md)（計數加 s、紀錄時間用固定格 `at`）不同，規則本身沒改，見 C-54 該兩列的註。

**10-25 計數改 `counter_*`**（使用者 10-25「計數這塊，幫我改成counter_*」）：C-54 的計數規則從「被數的東西加 s」改成 `counter_<被數的東西>`（[C-54 命名方法 R6](CONCEPTS/01-設計理念/C-54-命名方法.md)）；一串東西本身（陣列）不算計數。照改：loop／daemon state.json `counter` → `counter_runs`；kernel-llm 的 queue.json `runs` → `counter_runs`、used.json `calls`／`tokens`／`all_calls`／`all_tokens` → `counter_calls`／`counter_tokens`／`counter_all_calls`／`counter_all_tokens`、served.jsonl `tokens`／`waited_runs` → `counter_tokens`／`counter_waited_runs`；信的 `hops` → `counter_hops`；lib 工具輸出的計數（ls、stat、view、json_read、json_edit、copy、memory 索引）與 demo 的紀錄（agent-kai、agent-gus、agent-hal compact、self-improve 的用量）同樣改 `counter_*`；不留舊名。上限（`max`、kernel.json 的 `budget`）與時間點（`at`／`recorded_at`）不動，時間那半還等使用者定。

**10-25 時間點一律 `<發生了什麼>_at`、上限一律 `max_*`**（使用者 10-25 已選 `recorded_at`（「state.json中，runs改counter，at改成recorded_at」），頂層問兩題（時間點規則要不要跟著改、上限要不要照 R6 改 `max_*`），使用者回「都好」；頂層代定（可翻案））：C-54 的「這筆紀錄的時間用固定格 `at`」改成「時間點＝`<發生了什麼>_at`」，不再有單獨的 `at`（[C-54 命名方法 R3、R6](CONCEPTS/01-設計理念/C-54-命名方法.md)；原寫法照留、加註）。照改：fsm 的 trace.jsonl `at` → `started_at`（這格開始跑的時間）、信（send_message）`at` → `sent_at`、kernel-llm 的 served.jsonl `at` → `served_at`（kernel 處理這封信的時間）、claude／codex 互動畫面的 turns.jsonl `at` → `answered_at`、agent-kai 的 context.jsonl `at` → `sent_at`、self-improve 的 version.json／verdict.json／result.json `at` → `created_at`／`judged_at`／`finished_at`、aos-ai 的 runs.jsonl／up.json `at` → `finished_at`／`started_at`。沒用 `max_` 的上限照 R6 補改：kernel-llm 的 kernel.json `budget.calls`／`budget.tokens` → `max_calls`／`max_tokens`（舊名＝`CfgBad`）、self-improve 的 budget.json `rounds`／`elapsed_ms`／`tokens` → `max_rounds`／`max_elapsed_ms`／`max_tokens`（舊名＝`BudgetBad`）、lib 工具參數 `limit` → `max_lines`（read）／`max_items`（ls）／`max_results`（memory）、agent-hal compact 給腦的 `keep_max` 與報告的 `keep_max`／`keep_final_max`／`keep_line_max` → `max_keep`／`max_keep_final`／`max_keep_line_chars`。不留舊名。

## 條號表（2026-10-20 tidy：本檔超過 8 KB，整段逐字下放）

<!-- wf-nav -->
| 分檔 | 涵蓋的段 |
|---|---|
| [附錄3-條號表.md](CONCEPTS/附錄3-條號表.md) | 條號 → 檔（含作廢條號與 10-16～10-19 各批註記） |
