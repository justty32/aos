# core/inst 分冊各檔導覽

← [core/inst 分冊入口](../inst.md)（小專案總述與「新增一個 instruction 欄位」維護鏈在那裡）｜[code map 總圖](../../code-map.md)

這個資料夾是 `core/inst/` 逐檔表格的四個部分，**按層分檔**。要找「某個檔負責什麼」，先看下表選一份。

| 檔案 | 裡面有什麼 | 什麼時候會想看 |
|------|-----------|---------------|
| [library.md](library.md) | 對外公開標頭（`inst.hpp`／`inst.h`），以及 inst／format／resolve／handoff／exec 五個核心分層的逐檔表格＋改 exec 的注意事項 | 要改 instruction 結構、JSON schema、`$env`／`$ref` 解析、交接或 fork/exec |
| [capi.md](capi.md) | `src/capi*.cpp`／`capi_common.hpp` 的逐檔表格，加上例外邊界與 ABI 凍結規則 | 要改或新增 C ABI 進入點 |
| [cli.md](cli.md) | `src/run*.cpp`／`run*.hpp` 的逐檔表格 | 要改 `aos init`／`aos exec` 的 argv、單回合、loop 或批次 |
| [tests.md](tests.md) | `core/inst/tests/` 的逐檔涵蓋範圍 | 要加測試或找某個行為被誰蓋住 |

**新增或刪除 `core/inst/` 底下一個原始碼／測試檔時，那一列去哪一份加**：
`include/aos/` 的標頭，或 `src/` 底下屬於五個核心分層的檔（`inst.cpp`／`format*.cpp`／`.hpp`／`resolve.cpp`／`handoff*.cpp`／`.hpp`／`exec.cpp`／`spawn_prep.*`／`wait.*`）→ [library.md](library.md)；
`src/capi*.cpp`／`capi_common.hpp` → [capi.md](capi.md)；
`src/run*.cpp`／`run*.hpp` → [cli.md](cli.md)；
`tests/` 底下任何檔 → [tests.md](tests.md)。
這是 AGENTS.md「改了程式碼就要同步 code map」那條鐵律在 `core/inst/` 的落點，**跟程式碼改動同一個 commit**。
