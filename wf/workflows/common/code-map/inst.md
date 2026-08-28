# code map — core/inst/

← [code map 總圖](../code-map.md)｜[code-map 各分冊導覽](README.md)｜[本冊各檔導覽](inst/README.md)

`core/inst/` 這個小專案的逐檔職責：對外公開標頭、五個核心分層、C ABI 包裝層、CLI 層、測試，以及「新增一個 instruction 欄位」要動哪幾個地方。
逐檔表格按層拆在 [`inst/`](inst/README.md) 底下四份，**新增／刪除 `core/inst/` 底下的原始碼或測試檔，就照下面那張表選一份加／減那一列。**

---

## core/inst/ — 第一個小專案：POSIX 指令執行器

讀一筆或一批 JSON instruction，準備好環境／重導向後 `fork`＋`execve` 跑起來，等它結束、寫回 exit status。對外是 `aos::inst`（`libaos_inst.so`）＋ `aos init`／`aos exec`／`aos deliver` 子命令。

---

## 逐檔表格在哪：core/inst 分冊的四份

| 檔案 | 涵蓋 | 什麼時候會想看 |
|------|------|---------------|
| [inst/library.md](inst/library.md) | 對外公開標頭（`inst.hpp`／`inst.h`），以及 inst／format／resolve／handoff／exec 五個核心分層的逐檔表格＋改 exec 的注意事項 | 要改 instruction 結構、JSON schema、`$env`／`$ref` 解析、交接或 fork/exec |
| [inst/capi.md](inst/capi.md) | `src/capi*.cpp`／`capi_common.hpp` 的逐檔表格，加上例外邊界與 ABI 凍結規則 | 要改或新增 C ABI 進入點 |
| [inst/cli.md](inst/cli.md) | `src/run*.cpp`／`run*.hpp` 的逐檔表格 | 要改 `aos init`／`aos exec` 的 argv、單回合、loop 或批次 |
| [inst/tests.md](inst/tests.md) | `core/inst/tests/` 的逐檔涵蓋範圍 | 要加測試或找某個行為被誰蓋住 |

**新增或刪除一個 `core/inst/` 底下的檔（或某個檔的職責變了）時，那一列去哪一份加**：
`include/aos/` 的標頭，或 `src/` 底下屬於五個核心分層的檔（`inst.cpp`／`format*.cpp`／`.hpp`／`resolve.cpp`／`handoff*.cpp`／`.hpp`／`exec.cpp`／`spawn_prep.*`／`wait.*`）→ [inst/library.md](inst/library.md)；
`src/capi*.cpp`／`capi_common.hpp` → [inst/capi.md](inst/capi.md)；
`src/run*.cpp`／`run*.hpp` → [inst/cli.md](inst/cli.md)；
`tests/` 底下任何檔 → [inst/tests.md](inst/tests.md)。
**這一步跟程式碼改動同一個 commit**（AGENTS.md 的「改了程式碼就要同步 code map」）。

---

## 跨層的維護鏈

**新增一個 instruction 欄位**：① `inst.hpp` 的 `inst_t` 加欄位；② `format_decode.cpp` 的 `known_key`／`decode` 與 `format_encode.cpp` 的 `encode` 三處都要加；③ 需要的話 `inst.h` 加對應 C ABI 存取子＋`capi_instruction.cpp` 實作；④ `exec.cpp`／`spawn_prep.cpp` 視欄位語意決定要不要用到。（凍結已於 2026-08-24 解除，但這種改動仍要先確認它屬於已拍板的範圍。）
