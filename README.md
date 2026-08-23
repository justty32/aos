# aos

一組 POSIX 小工具的集合。每個小專案同時是兩件事：`aos` 執行檔的一條子命令，
以及一個可以被其他專案 `#include` 與連結的 C++23 函式庫。

目前只有一個小專案 [`inst/`](inst/) —— 讀 JSON 指令檔並依序執行。之後的
`llm/`、`tooljson/` 等都會照同一個模子長出來。

## 建置

需要 CMake 3.25+、支援 C++23 的編譯器，以及 [vcpkg](https://vcpkg.io)。
toolchain 的解析順序是「呼叫者給的 `CMAKE_TOOLCHAIN_FILE` → 環境變數
`VCPKG_ROOT` → `~/dev/vcpkg`」，所以 vcpkg 裝在 `~/dev/vcpkg` 的話什麼都不用設。

```bash
cmake --preset default && cmake --build --preset default && ctest --preset default
```

**只能從 repo 根目錄 configure**，子專案不提供獨立建置。產物在 `build/bin/aos`
與 `build/lib/libaos_*.so`。

其他 preset：`release`、`merged`（額外產出合併版 `libaos.so`）。

## 當成執行檔用

```bash
aos --help                    # 列出所有子命令
aos inst jobs.json            # 執行一份指令檔
printf '%s\n' '{"argv":["echo","hello"]}' | aos inst
```

## 當成函式庫用

先安裝：

```bash
cmake --install build --prefix ~/.local
```

然後在別的專案裡：

```cmake
find_package(aos CONFIG REQUIRED)
target_link_libraries(myapp PRIVATE aos::inst)
```

```cpp
#include <aos/inst.hpp>
```

可以連的 target：

| target | 內容 |
|--------|------|
| `aos::inst` | 只要 inst 這個小專案（`libaos_inst.so`）|
| `aos::aos` | 傘狀 INTERFACE target，一次連上所有小專案 |
| `aos::merged` | 合併版 `libaos.so`，需要 `-DAOS_BUILD_MERGED_LIB=ON` |

每個小專案也各自提供一份 C ABI 標頭（`<aos/inst.h>`），語言邊界要用時走那邊。
這一塊還在陸續補齊。

## 建置選項

| 選項 | 預設 | 作用 |
|------|------|------|
| `AOS_BUILD_APP` | `ON` | 建置 `aos` 執行檔 |
| `AOS_BUILD_TESTS` | 頂層專案時 `ON` | 建置測試 |
| `AOS_BUILD_MERGED_LIB` | `OFF` | 額外產出合併版 `libaos.so` |
| `AOS_INSTALL` | 頂層專案時 `ON` | 產生 install 與 `find_package` 規則 |

## repo 佈局

```
CMakeLists.txt      頂層：選項、相依、add_subdirectory、install/export
cmake/              AosSubproject.cmake（小專案樣板）、aos-config.cmake.in
common/             跨小專案共用：aos::common（<aos/export.h>）與通用私有相依
app/                唯一的執行檔 aos，只負責把 argv[1] 分派到某個子命令
inst/               第一個小專案：aos::inst + `aos inst` 子命令
wf/                 分層工作流文件（開發流程用，與程式無關）
```

### 新增一個小專案

1. 複製 `inst/` 的結構：`include/aos/<name>.hpp`、`src/`、`tests/`、`CMakeLists.txt`。
2. 在它的 `CMakeLists.txt` 裡呼叫 `aos_add_subproject()`，需要子命令就再呼叫
   `aos_add_subcommand()`（`NAME` 限 `^[a-z][a-z0-9-]*$`，重名與進入點撞名都會
   在 configure 期擋下來）。nlohmann_json 之類**多數小專案都會用到的相依不用寫**
   —— 它們集中宣告在 `common/CMakeLists.txt` 的 `aos_common_private`，樣板會
   自動連上。
3. 在根目錄 `CMakeLists.txt` 的小專案區塊加一行 `add_subdirectory(<name>)`。

`app/` 不用動 —— 子命令表是從各小專案的登記結果產生的。細節見
[`cmake/AosSubproject.cmake`](cmake/AosSubproject.cmake) 的註解。

## 指令檔必須是可信來源

`aos inst` 沒有任何輸入限制：單筆與整份文件都沒有位元組上限，`argv` 與 `env`
的元素數量沒有上限，JSON 巢狀深度也沒有上限。記憶體用量由呼叫者的 `ulimit`
或 cgroup 決定，不是由這支程式決定；巢狀太深的文件會讓解析器爆堆疊——那是
crash，不是錯誤狀態。**一份指令檔等同一段可執行程式碼，來源要照同樣的標準把關。**

## 文件

- inst：[記錄格式](inst/docs/format.md)、[執行語意](inst/docs/exec.md)、
  [C++ API](inst/docs/cxxapi.md)、[C API](inst/docs/capi.md)、
  [架構](inst/docs/architecture.md)
- 開發流程：[AGENTS.md](AGENTS.md) → [wf/](wf/)
