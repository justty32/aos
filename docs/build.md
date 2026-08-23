# 建置與安裝

← [文件索引](README.md)｜[總覽](overview.md)｜[使用](usage.md)

## 需求

| | |
|---|---|
| 平台 | POSIX。`WIN32` 會直接 `FATAL_ERROR` |
| 編譯器 | 支援 C++23。C ABI 的測試另外用 C99 建 |
| CMake | 3.25 以上 |
| 相依 | 由 [vcpkg](https://vcpkg.io) manifest 管理，不用手動裝 |

## vcpkg 怎麼被找到

toolchain 在 `project()` 之前解析，優先順序：

1. 你自己給的 `-DCMAKE_TOOLCHAIN_FILE=...`
2. 環境變數 `VCPKG_ROOT`
3. `~/dev/vcpkg`

第 3 條只是讓常見情況不用設環境變數，找不到就靜靜跳過。個人的特殊路徑建議放
`CMakeUserPresets.json`（已在 `.gitignore` 裡）。

`vcpkg.json` 釘了 `builtin-baseline`，所以相依版本是可重現的。Catch2 放在
`tests` feature 裡，只在要建測試時才裝——preset 已經幫你帶上
`VCPKG_MANIFEST_FEATURES=tests`。

## 建置

```bash
cmake --preset default && cmake --build --preset default && ctest --preset default
```

**只能從 repo 根目錄 configure。** 子專案的 `CMakeLists.txt` 沒有自己的
`project()`，`cd inst && cmake ...` 是不成立的。

| preset | 建置目錄 | 用途 |
|--------|---------|------|
| `default` | `build/` | Debug，另外開 `compile_commands.json` |
| `release` | `build/release/` | Release |
| `merged` | `build/merged/` | Debug 加上合併版 `libaos.so` |

產物落在 `build/bin/`（執行檔）與 `build/lib/`（函式庫）。

## 選項

| 選項 | 預設 | 作用 |
|------|------|------|
| `AOS_BUILD_APP` | `ON` | 建置 `aos` 執行檔 |
| `AOS_BUILD_TESTS` | 頂層專案時 `ON` | 建置測試 |
| `AOS_BUILD_MERGED_LIB` | `OFF` | 額外產出把所有小專案併在一起的 `libaos.so` |
| `AOS_INSTALL` | 頂層專案時 `ON` | 產生 install 與 `find_package` 規則 |

後兩個的預設值跟著 `PROJECT_IS_TOP_LEVEL` 走，所以把 aos 用
`add_subdirectory()` 併進別的專案時，它不會擅自裝東西或建測試。

## 測試

```bash
ctest --preset default                    # 全部
ctest --preset default -R '^aos_inst'     # 只跑 inst 的
```

| 測試 | 內容 |
|------|------|
| `aos_inst_tests` | C++ 測試：format 層、exec 層、CLI 層 |
| `aos_inst_capi_tests` | C ABI 往返測試，刻意用 C 編譯器建，這樣 `<aos/inst.h>` 混進 C++ 才有的東西就會編不過 |

之後的小專案照同一個命名慣例掛 `aos_<專案>_tests`。

## 安裝

```bash
cmake --install build --prefix ~/.local
```

裝出來的東西：

```
bin/aos
include/aos/export.h
include/aos/inst.h
include/aos/inst.hpp
lib/libaos_inst.so            → .so.0 → .so.0.1.0
lib/cmake/aos/aos-config.cmake
lib/cmake/aos/aos-config-version.cmake
lib/cmake/aos/aos-targets.cmake
```

執行檔的 RPATH 是 `$ORIGIN/../lib`（macOS 是 `@loader_path/../lib`），所以裝好
之後不用設 `LD_LIBRARY_PATH` 就找得到自己的函式庫。

要怎麼在別的專案裡用它，見 [usage.md](usage.md)。
