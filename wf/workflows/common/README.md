# common — 跨工作流共享（入口）

← [INDEX](../../INDEX.md)｜[AGENTS.md](../../../AGENTS.md)

不專屬任一工作流、各工作流共用的東西。這是本區的**入口**。

<!-- wf-nav -->
| 路徑 | 內容 | 來源 |
|------|------|------|
| [gotchas.md](gotchas.md) | 跨工作流共通踩坑（工作流專屬的坑在各自的 `gotchas.md`，那裡有導流表）| kernel |
| [user.md](user.md) | 使用者偏好、確認邊界、分支慣例、時區、工作模式 | kernel |
| [data-files.md](data-files.md) | 資料檔契約 `wf-table/1`：給 AI 消化的條列 >1 KB 抽 `.json`／`.csv`、`tabledb.py` 讀寫；給人導航的連結表留 md | kernel |
| [data-files-fmt.md](data-files-fmt.md) | json 值裡跨層路徑用 `$fmt` 代號展開，省 `../../../` | kernel |
| [conventions.md](conventions.md) | **程式碼慣例 + code map 維護鏈**；碰原始碼的工作流共用 | dev 包 |
| [code-map.md](code-map.md) | **程式碼結構導航圖**（本專案的導航中樞）＋ 真相層優先序；逐檔分冊在 [`code-map/`](code-map/README.md) | dev 包 |

> 過時的共通文檔封存進 `common/archive/`。本入口檔若膨脹，照 [STRUCTURE](../../STRUCTURE.md) 拆。
