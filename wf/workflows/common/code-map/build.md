# code map — common/、app/ 與建置設定

← [code map 總圖](../code-map.md)｜[本資料夾導覽](README.md)

不屬於任何一個小專案的骨架：跨小專案共用的 `common/`、唯一執行檔 `app/`，以及根 CMake／`cmake/`／vcpkg／presets 這些建置設定檔。
**新增／刪除 `common/`、`app/` 或建置設定檔（含新增一個小專案要加的那行 `add_subdirectory()`），就在這一份加／減那一列。**

---

## common/ — 跨小專案共用

兩個 target，職責刻意分開：

| target | 安裝／匯出 | 負責 |
|--------|-----------|------|
| `aos::common` | 是 | Header-only 的公開共用部分，目前只有 `<aos/export.h>`，外加 `cxx_std_23` |
| `aos_common_private` | **否** | 多數小專案的**實作檔**都會用到的相依（目前只有 `nlohmann_json`）。`aos_add_subproject()` 一律以 PRIVATE 連上，所以小專案的 CMakeLists 不用重複宣告，也不會變成使用者 `find_package(aos)` 的義務 |

**相依放哪裡的判準**：會出現在**公開標頭**上 → `aos_add_subproject()` 的 `PUBLIC_DEPS` + `PUBLIC_PACKAGES`（後者會讓 `aos-config.cmake` 產生 `find_dependency()`）。只在 `.cpp` 裡用到、且多數小專案都要 → `aos_common_private`。只有某一個小專案要 → 該小專案的 `PRIVATE_DEPS`。

| 檔案 | 負責 |
|------|------|
| `include/aos/export.h` | `AOS_API` 可見度宏（`__attribute__((visibility("default")))`，定義 `AOS_STATIC` 時展開成空）。每個小專案**公開標頭裡宣告的每一個函式**都要標它，否則 `-fvisibility=hidden` 之下外部連不到 |

## app/ — 唯一的執行檔

產出 `aos` 這一支執行檔本身，靠子命令分派到各小專案。新增子命令**不用改這裡的程式碼**：在對應小專案的 CMakeLists 呼叫 `aos_add_subcommand()` 即可，`app/CMakeLists.txt` 會把大家登記的結果攤成一份 X-macro 標頭（`aos_subcommands.inc`），`main.cpp` 用兩種 `AOS_SUBCOMMAND` 定義 include 它兩次——一次產生 `extern "C"` 宣告，一次產生表格內容。

| 檔案 | 負責 |
|------|------|
| `CMakeLists.txt` | 讀全域屬性、產生 `aos_subcommands.inc`。摘要是自由文字，反斜線／雙引號／換行在這裡跳脫 |
| `src/main.cpp` | 分派：比對 `argv[1]`，把 `argv[0]` 換成 `"aos <command>"` 之後轉發給子命令。`-h`／`--help` 與未知命令都印子命令表 |

登記時會在 configure 期擋三件事，都是「不擋的話症狀很難查」的：`NAME` 必須符合 `^[a-z][a-z0-9-]*$`；`NAME` 不可重複（重名的話 configure／編譯／`--help` 全都正常，但線性分派只叫得到先註冊的那個，**沒有任何訊息**）；`ENTRY` 不可重複（否則錯誤延到連結期，變成看不懂的 multiple definition）。
---

## 建置設定

| 路徑 | 負責 |
|------|------|
| 根 `CMakeLists.txt` | 頂層：`option()`、vcpkg toolchain 解析（在 `project()` 之前）、`find_package(nlohmann_json/CURL/Catch2)`、`add_subdirectory(common/core/modules/app)`、三個傘狀 target、合併版、`install`／`export` |
| `core/CMakeLists.txt`／`modules/CMakeLists.txt` | 兩份小專案清單。新增小專案就是往其中一份加一行 `add_subdirectory()`；它們各自 `set(AOS_SUBPROJECT_CATEGORY ...)` 來決定分類 |
| `cmake/AosSubproject.cmake` | 三個共用函式：`aos_add_subproject()`（產出 OBJECT＋SHARED 兩個 target、把私有相依從匯出介面剝掉、檢查保留名稱與分類）、`aos_add_subcommand()`（登記子命令＋三道守衛）、`aos_add_test()` |
| `cmake/aos-config.cmake.in` | 讓外部專案 `find_package(aos CONFIG)`。`@AOS_FIND_DEPENDENCIES@` 由根 CMakeLists 從各小專案登記的 `PUBLIC_PACKAGES` 產生 |
| 根 `vcpkg.json` | manifest，有 `builtin-baseline`；測試相依（Catch2）放在 `"tests"` feature |
| `CMakePresets.json` | `default`／`release`／`merged`。vcpkg toolchain 由根 `CMakeLists.txt` 解析（`CMAKE_TOOLCHAIN_FILE` → `VCPKG_ROOT` → `~/dev/vcpkg`），本機不用設環境變數 |
| `common/CMakeLists.txt` | `aos::common` 與 `aos_common_private`（見上面 common/ 那節）|
| `core/inst/CMakeLists.txt` | 小專案的**參考範本**（核心類）：`aos_add_subproject()`（目前不需要任何 DEPS 參數）＋ CLI 的 OBJECT library ＋ `aos_add_subcommand()` ＋公開 API／C ABI 測試 |

**鐵律**：C++23；**只能從 repo 根目錄 `cmake --preset default` 設定**，子專案不可單獨 configure；外部專案用 `find_package(aos CONFIG REQUIRED)` + `target_link_libraries(x PRIVATE aos::inst)` + `#include <aos/inst.hpp>`。vcpkg 在 `~/dev/vcpkg`。
