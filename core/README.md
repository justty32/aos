# core/ — 核心小專案

> 10-22 註：`core/` 是舊一代 C++ 版的「必要模組」資料夾（拿掉它 aos 就不成立），資料夾名不動；跟 proto8 分層（[C-74](../proto8/docs/CONCEPTS/01-設計理念.md#分層10-22-使用者定)）裡的「核心」（aos-exec）、kernel 都無關。

aos 的基本組成部分。這裡的小專案都很通用，`aos <name>` 子命令與 `aos::<name>`
函式庫成對出現，而且一定會被建置。

| 小專案 | target | 子命令 | 做什麼 |
|--------|--------|--------|--------|
| [exec/](exec/) | `aos::exec` | （純函式庫） | 一次 fork 一整批 POSIX 指令、統一等完並回傳結果與起訖時間 |
| [wire/](wire/) | `aos::wire` | （純函式庫） | 在指令／結果／loop state 的協定 JSON 與 C++ struct 之間轉換 |
| [loop/](loop/) | `aos::loop` | `aos run`／`aos deliver` | 匯聚並執行一個資料夾的一回合，落檔後更新 `state.json` |
| [llm/](llm/) | `aos::llm` | `aos llm` | 從 stdin 或 messages JSON 呼叫 OpenAI 相容端點並回傳文字 |
| [agent/](agent/) | `aos::agent` | `aos agent` | 建立並推進會自我投遞、能與 LLM 及工具往返的資料夾 agent |
| [tick/](tick/) | `aos::tick` | `aos tick`／`aos heartbeat`／`aos routine`／`aos schedule` | 掃 heartbeat 兩張清單，把到期的投進 inbox 或交給 agent，更新清單並寫 log |

`aos::core` 這個傘狀 target 一次連上本目錄的全部。

**放這裡還是放 [`../modules/`](../modules/)**：拿掉它 aos 就不再是 aos → `core/`；
拿掉它 aos 仍然成立 → `modules/`。

`common/`、`app/`、`cmake/` 都不是小專案，它們是**基礎設施**（＝建置與共用程式碼的目錄；跟 proto8 CONCEPTS／NORMS 的「基礎設施」主題無關，10-22 註）。

新增小專案照 [`docs/subprojects.md`](../docs/subprojects.md)；`llm/` 是參考範本。
