# 新增一個小專案

← [文件索引](README.md)｜[總覽](overview.md)｜[建置](build.md)

小專案都住在 `subprojects/` 底下。`subprojects/inst/` 就是這件事的參考範本，
整份抄過去改名字，大致就成立了。

## 三個步驟

**1. 建立目錄結構**

```
subprojects/<name>/
  include/aos/<name>.hpp     公開標頭（會被安裝）
  include/aos/<name>.h       C ABI（可選，之後再補也行）
  src/                       實作 + CLI 層
  tests/
  docs/                      這個小專案自己的細節文件
  CMakeLists.txt
```

公開標頭一律放在 `include/aos/` 底下，所以內部與外部都寫成
`#include <aos/<name>.hpp>`，兩邊看到的路徑一致。

**2. 寫它的 `CMakeLists.txt`**

```cmake
aos_add_subproject(<name>
    SOURCES src/foo.cpp src/bar.cpp
    HEADERS include/aos/<name>.hpp
)

# CLI 層另外放：它屬於 aos 執行檔，不是函式庫的公開介面，所以不安裝。
# 做成 OBJECT library 是為了讓執行檔與測試共用同一份編譯結果。
add_library(aos_<name>_cli OBJECT src/run.cpp)
target_link_libraries(aos_<name>_cli PUBLIC aos::<name>)

aos_add_subcommand(
    NAME <name>
    ENTRY aos_<name>_cli_main
    LIBRARY aos_<name>_cli
    SUMMARY "一行說明，會印在 aos --help 裡"
)

aos_add_test(aos_<name>_tests
    SOURCES tests/test_foo.cpp
    LINK aos_<name>_cli
)
```

CLI 的進入點在 `src/run.cpp` 裡長這樣，名字要跟 `ENTRY` 一致：

```cpp
extern "C" int aos_<name>_cli_main(int argc, char *argv[]) { ... }
```

用 C 連結是為了讓 CMake 產生的那張表可以直接寫出宣告，不必知道 C++ 的名稱修飾
規則。`aos` 會把 `argv[0]` 設成 `"aos <name>"` 再呼叫進來，所以子命令印用法訊息
時直接用 `argv[0]` 就對了。

**3. 在 `subprojects/CMakeLists.txt` 加一行**

```cmake
add_subdirectory(<name>)
```

**根 `CMakeLists.txt` 與 `app/` 都不用動。** 根目錄只寫了
`add_subdirectory(subprojects)`；子命令表是從各小專案的登記結果產生的。

順手在 [`subprojects/README.md`](../subprojects/README.md) 的表格加一列。

---

## 相依怎麼放

這是最容易做錯、而且錯了要很久以後才發現的地方。三層判準：

### 公開標頭上用到 → `PUBLIC_DEPS` + `PUBLIC_PACKAGES`

```cmake
aos_add_subproject(llm
    SOURCES ...
    HEADERS include/aos/llm.hpp
    PUBLIC_DEPS     aos::inst           # 標頭裡出現 aos::inst 的型別
    PUBLIC_PACKAGES SomePackage         # 外部套件才需要列，會產生 find_dependency
)
```

`PUBLIC_PACKAGES` 列的是「使用者的 `find_package(aos)` 也得先找出來」的套件名，
會被寫進 `aos-config.cmake`。相依到別的**小專案**不用列（它們在同一個匯出集合
裡）。

> 走這條路之前先想清楚：任何相依只要出現在公開標頭上，你就把使用者綁死在同一個
> 版本上了。能用 pimpl 或 C ABI 躲掉就躲。

### 多數小專案的實作都要 → `common/CMakeLists.txt` 的 `aos_common_private`

```cmake
add_library(aos_common_private INTERFACE)
target_link_libraries(aos_common_private INTERFACE
    nlohmann_json::nlohmann_json
)
```

`aos_add_subproject()` 一律自動 PRIVATE 連上，所以小專案不用重複宣告。新增一項
= 根 `CMakeLists.txt` 加 `find_package()`，這裡加一行。

**准入規則**：只收「header-only 或等價零成本」**且**「多數小專案都會用到」的
東西。放一個真正的 `.so` 進來的話，每個小專案的 `libaos_*.so` 都會多一條它用不到
的 `DT_NEEDED`，部署也被迫拖著它。curl、openssl、sqlite 這類不該進來。

### 只有這個小專案要 → `PRIVATE_DEPS`

```cmake
aos_add_subproject(llm
    SOURCES ...
    PRIVATE_DEPS CURL::libcurl
)
```

私有相依（包含 `aos_common_private`）都不會外流到匯出介面：`aos_add_subproject()`
連完之後會把 `INTERFACE_LINK_LIBRARIES` 重設成只剩公開部分。共享庫真正要連什麼
已經記在自己的 `DT_NEEDED` 裡。

### 成長軌跡

相依變多之後（大概四五個以上），把它們拆成一個 `cmake/AosDependencies.cmake`，
一個相依一個具名 target，讓小專案按名字取用。現在只有一個，不值得先做。

---

## CMake 函式參考

三個函式都在 [`cmake/AosSubproject.cmake`](../cmake/AosSubproject.cmake)，
原始碼裡有更詳細的註解。

### `aos_add_subproject(<name> ...)`

| 參數 | 說明 |
|------|------|
| `SOURCES` | 實作檔（必要）|
| `HEADERS` | 公開標頭，會被安裝到 `include/aos/` |
| `PUBLIC_DEPS` | 公開標頭裡用到的相依 |
| `PRIVATE_DEPS` | 這個小專案專屬、只有實作檔用到的相依 |
| `PUBLIC_PACKAGES` | `PUBLIC_DEPS` 來自哪些 `find_package`，用來產生 `find_dependency` |

產出 `aos_<name>_objects`（OBJECT，給合併版撿）與 `aos_<name>`（SHARED，別名
`aos::<name>`，安裝並匯出）。SHARED 的來源是 `$<TARGET_OBJECTS:>` 而不是 link，
所以兩者之間沒有相依邊，`install(EXPORT)` 才不會要求把 OBJECT library 也塞進
匯出集合。

### `aos_add_subcommand(...)`

| 參數 | 說明 |
|------|------|
| `NAME` | 使用者打的字。必須符合 `^[a-z][a-z0-9-]*$` |
| `ENTRY` | `extern "C" int <entry>(int, char **)` 的符號名 |
| `LIBRARY` | 提供該符號、要被 `aos` 連進去的 target |
| `SUMMARY` | 一行說明，印在 `aos --help`。自由文字，分號與引號都會被正確處理 |

configure 期會擋三件事，都是「不擋的話症狀很難查」的：

- `NAME` 字集不合 —— 順便擋掉 `--help` 這種會跟旗標混淆的名字
- `NAME` 重複 —— 不擋的話 configure、編譯、`aos --help` 全都正常，但分派是線性
  掃描取第一個相符，後註冊的那個實作**永遠叫不到，而且沒有任何訊息**
- `ENTRY` 重複 —— 不擋的話錯誤會延到連結期，變成跟「子命令」八竿子打不著的
  multiple definition

### `aos_add_test(<name> ...)`

| 參數 | 說明 |
|------|------|
| `SOURCES` | 測試檔 |
| `LINK` | 要連的 target |
| `LANGUAGE` | `CXX`（預設，會自動連上 `Catch2::Catch2WithMain`）或 `C`（自帶 `main`，以 C99 建）|

`AOS_BUILD_TESTS` 關掉時整個函式直接 return。

---

## 檢查清單

新的小專案落地之後，跑一遍：

```bash
cmake --preset default && cmake --build --preset default && ctest --preset default
./build/bin/aos --help                    # 新子命令有出現嗎
cmake --install build --prefix /tmp/p     # 標頭與 .so 都裝出去了嗎
```

然後**在 repo 外面開一個小專案**，`find_package(aos CONFIG REQUIRED)` 加
`target_link_libraries(x PRIVATE aos::<name>)`，確認在**沒有 vcpkg** 的環境下也
configure 得過。這一步會抓到「私有相依不小心洩漏到匯出介面」這類只有從外面看才
看得出來的問題。

最後別忘了照 [AGENTS.md](../AGENTS.md) 的鐵律更新
[code map](../wf/workflows/common/code-map.md)。
