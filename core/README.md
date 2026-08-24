# core/ — 核心小專案

aos 的基本組成部分。這裡的小專案都很通用，`aos <name>` 子命令與 `aos::<name>`
函式庫成對出現，而且一定會被建置。

| 小專案 | target | 子命令 | 做什麼 |
|--------|--------|--------|--------|
| [inst/](inst/) | `aos::inst` | `aos init`／`aos exec` | 初始化資料夾並消費一回合的 JSON instruction |
| [tooljson/](tooljson/) | `aos::tooljson` | `aos tooljson` | 讀取、驗證 tool spec，並把模型參數展開成 argv |
| [llms/](llms/) | `aos::llms` | `aos llms` | 呼叫 OpenAI 相容端點並查詢模型能力（S3 非串流） |

`aos::core` 這個傘狀 target 一次連上本目錄的全部。

**放這裡還是放 [`../modules/`](../modules/)**：拿掉它 aos 就不再是 aos → `core/`；
拿掉它 aos 仍然成立 → `modules/`。

`common/`、`app/`、`cmake/` 都不是小專案，它們是**基礎設施**。

新增小專案照 [`docs/subprojects.md`](../docs/subprojects.md)；`inst/` 是參考範本。
