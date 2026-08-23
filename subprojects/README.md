# subprojects/

aos 的小專案都住在這裡。每一個同時是 `aos` 執行檔的一條子命令，以及一顆可以被
外部 `find_package(aos CONFIG)` 連上的共享函式庫。

| 小專案 | target | 子命令 | 做什麼 |
|--------|--------|--------|--------|
| [inst/](inst/) | `aos::inst` | `aos inst` | 讀 JSON 指令檔，依序 `fork`/`exec` 執行 |

`common/`、`app/`、`cmake/` 不在這裡——它們是**基礎設施**，不是小專案。

**要新增一個小專案**，照 [`docs/subprojects.md`](../docs/subprojects.md) 走；
`inst/` 就是參考範本。
