# code map — core/inst/ C ABI 包裝層

← [core/inst 分冊入口](../inst.md)｜[本資料夾導覽](README.md)｜[code map 總圖](../../code-map.md)

`core/inst/src/` 裡 C ABI 包裝層的逐檔職責，以及例外邊界與 ABI 凍結規則。對外標頭 `include/aos/inst.h` 那一列在 [library.md](library.md)。
**新增／刪除 `core/inst/src/capi*.cpp`／`capi_common.hpp`，就在這一份加／減那一列。**

---

## core/inst/src/ — C ABI 包裝層（只往下看 inst/format/exec，不影響它們）

| 檔案 | 負責 |
|------|------|
| `capi_common.hpp` | **內部標頭**：`aos_instruction` 的實際定義（`struct aos_instruction { aos::inst_t value; }`），只有這幾個 `capi_*.cpp` 看得到 |
| `capi.cpp` | 版本字串、狀態轉字串（`aos_inst_state_string`／`aos_exec_state_string`）。開頭一串 `static_assert` 讓 C 的列舉值與 C++ 的 `InstState`／`ExecState` 對齊——**新增或改一個列舉值，兩邊都要動，這裡的 static_assert 會在改漏時讓建置失敗** |
| `capi_instruction.cpp` | 操作單個 `aos_instruction` 的存取子：建立／釋放／清空、`argv` 讀寫、四個路徑欄位＋`cwd`、stderr merge、`env`、`timeout_ms`、`parallel` |
| `capi_io.cpp` | 讀寫整份 instruction：`read_buffer/fd/file`、`write_buffer/fd/file`（呼叫 `format` 層），以及 `aos_instruction_execute`（呼叫 `exec` 層） |
| `capi_handoff.cpp` | deliver 的 C ABI（SPEC §D-3）：`aos_deliver_buffer`／`aos_deliver_file`（呼叫 `handoff` 層的 `deliver_instructions`）、`aos_handoff_state_string`。開頭 `static_assert` 只鎖 `aos_handoff_state` 鏡射 `aos::HandoffState` 的那 10 個值（0-9），10 以上是 C ABI 專屬延伸值（`ALLOC_FAILED`／`READ_ERROR`／`BUFFER_TOO_SMALL`，不進 static_assert，同 `aos_inst_state` 的做法）。**每次呼叫都是真的投遞一次**，不是「先探大小再重打」的兩段式——`name` buffer 太小時投遞已完成，回 `AOS_HANDOFF_BUFFER_TOO_SMALL` 且 `needed` 給實際長度，呼叫端不得因此重打（會多投一份）；`AOS_DELIVER_NAME_MAX`（inst.h）保證夠大，一般呼叫不會撞到這個狀態 |

**每個 `extern "C"` 進入點都有 `catch (...)`**，把例外接成 `AOS_INST_ALLOC_FAILED` 之類的錯誤碼——例外絕對不能逸出 C 邊界。新增進入點時照抄這個形狀。

**C ABI 的 ABI 規則**：`inst.h` 裡的列舉值一經釋出就凍結，只能在尾端加新值，不能重排或刪除既有值——這條規則寫在標頭裡的註解，改動前先看。
