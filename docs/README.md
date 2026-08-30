# aos 文件

← [專案 README](../README.md)

這裡是 **aos 整體**的文件。個別小專案自己的細節在它們各自的 `docs/`（目前只有
[`core/agent/docs/`](../core/agent/docs/)）。

## 你想做什麼

| 我想… | 讀這份 |
|-------|--------|
| 搞懂這個專案是什麼、為什麼長這樣 | [overview.md](overview.md) |
| **`.aos` 資料夾長什麼樣、回合怎麼跑**（規格，核心已實作） | [aos-folder.md](aos-folder.md) |
| **知道接下來要做什麼、哪些事在等我拍板** | [roadmap.md](roadmap.md) |
| `$ref`／`$env`／`$opt` **為什麼**長這樣（設計理由，已實作）（`core/inst` 已刪 2026-08-30，本文留作設計理由的歷史紀錄） | [inst-directives.md](inst-directives.md) |
| 把它建起來、跑測試、裝到某個地方 | [build.md](build.md) |
| **用**它——當成命令列工具，或當成函式庫連進我自己的專案 | [usage.md](usage.md) |
| 在 aos 底下**開一個新的小專案** | [subprojects.md](subprojects.md) |

## 這批文件不包含什麼

- **開發流程**（工作流、進度、慣例）在 [`wf/`](../wf/)，入口是
  [AGENTS.md](../AGENTS.md)。那是給在這個 repo 裡幹活的人／agent 看的，不是
  給使用者看的。
