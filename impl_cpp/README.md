impl_cpp：使用者 11-09 起親手重寫 aos 核心的 C++23 實作；這份講開發環境怎麼用（建、跑、測、除錯、目錄、clangd、VS Code）。

# impl_cpp

骨架取自 [`archive/aos-v1/`](../archive/aos-v1/)（一個 CMake 專案、`common/`、「一個零件一夾」的小專案模式），但**自成一體**：不 include proto8 或 archive 的任何檔，這一夾自己看得懂。核心程式由使用者自己寫；現在只有一個驗 build 鏈用的樣板 `core/hello/`。

## 一次建好、跑起來

```sh
cd impl_cpp
cmake --preset debug                    # configure（第一次會用 vcpkg 裝 nlohmann-json 進 build/debug/vcpkg_installed/）
cmake --build --preset debug -j2        # build
./build/debug/bin/aos-hello             # 跑：印 {"hello":"impl_cpp"}
ctest --preset debug                    # 測試
```

機器上同時有別的重活時，build 前面加 `nice -n 15`。

三個 preset（`CMakePresets.json`，都用 Ninja，各自建在 `build/<名字>/`）：

| preset | 用途 |
|---|---|
| `debug` | `-O0 -g`，平常開發、gdb 除錯用；clangd 也看這一份 |
| `release` | `-O3`，量速度或要給人用時 |
| `asan` | Debug＋AddressSanitizer＋UBSan，抓記憶體越界、用了已釋放的記憶體、未定義行為；`ctest --preset asan` 遇到 UBSan 會直接停 |

<details><summary>不用 preset、Debug／Release 預設、warning</summary>

- 不用 preset 也行：`cmake -B build && cmake --build build`。**沒指定 build type 時是 Release**（照 proto8 的做法；preset 都會明寫，所以只影響手打 `cmake -B` 的情況）。
- C++23、不開 GNU 擴充（`-std=c++23`），跟 aos-v1 一樣。
- warning 全開（`-Wall -Wextra -Wpedantic -Wshadow -Wconversion -Wsign-conversion` 等，清單在 `common/CMakeLists.txt`），只管我們自己的檔，vcpkg 的標頭不算。想把 warning 當錯誤：`cmake --preset debug -DAOS_WERROR=ON`。

</details>

## 除錯（gdb）

這台沒有 lldb，用 gdb：

```sh
gdb --args ./build/debug/bin/aos-hello      # 進去後 break main → run → next／step → bt
```

用 `debug` preset 建的才有完整除錯資訊；`asan` 版也能進 gdb，但慢。

## 目錄怎麼放

```
impl_cpp/
  CMakeLists.txt        根：vcpkg 找法、C++23、輸出到 build/<preset>/bin、lib
  CMakePresets.json     debug／release／asan
  vcpkg.json            相依清單（manifest 模式）
  cmake/AosSubproject.cmake   aos_add_subproject()：一個零件一次登記函式庫、執行檔、測試
  common/               所有零件共用：C++23 要求、warning、通用私有相依（nlohmann_json）
  core/CMakeLists.txt   零件清單：一行一個 add_subdirectory()，照依賴序排
  core/<零件>/
    CMakeLists.txt      aos_add_subproject(<零件> SOURCES … HEADERS … PROGRAM … TESTS …)
    include/aos/<零件>.hpp   公開標頭（別的零件寫 #include <aos/<零件>.hpp>）
    src/                實作；src/main.cpp 是執行檔入口（有才產出 build/<preset>/bin/aos-<零件>）
    tests/              每個 .cpp 一支測試執行檔，ctest 跑它，退 0＝過
  build/                產物（不進 git）
```

**加一個新零件**：把 `core/hello/` 整夾抄一份改名（夾名、`CMakeLists.txt` 裡的名字、標頭檔名、namespace），再到 `core/CMakeLists.txt` 加一行 `add_subdirectory(<名字>)`。要用別的零件：在自己的 `aos_add_subproject` 裡寫 `PRIVATE_DEPS aos::<那個零件>`（自己的公開標頭也用到它就寫 `PUBLIC_DEPS`）。`hello` 寫了真的零件後可以整夾刪掉。

測試不加測試框架：一支小執行檔，檢查失敗就印一行、退 1。樣子看 `core/hello/tests/hello_test.cpp`。

## 套件（vcpkg）

- vcpkg 用 `~/dev/vcpkg`：`CMakeLists.txt` 先看環境變數 `VCPKG_ROOT`，沒設就退到 `~/dev/vcpkg`，所以 preset 裡不寫 toolchain 路徑。`vcpkg.json` 的 `builtin-baseline` 就是 `~/dev/vcpkg` 現在的 commit（跟 proto8/impls 同一個），套件版本照它鎖住。
- **nlohmann-json 已接好**：每個零件都自動連上（在 `common/` 的 `aos_common_private`），新程式直接 `#include <nlohmann/json.hpp>` 就能用，不用改 CMake。
- **加新套件**：`~/dev/vcpkg/vcpkg add port <名字>`（或手改 `vcpkg.json` 的 `dependencies`）→ 根 `CMakeLists.txt` 加 `find_package(...)` → 多數零件都用就加進 `common/CMakeLists.txt` 的 `aos_common_private`，只有一個零件用就寫在它的 `PRIVATE_DEPS` → 重跑 `cmake --preset debug`，vcpkg 會自己裝。套件的 CMake 寫法 vcpkg 裝完會印出來。
- **不用更新 vcpkg 本身**：現在這版裝得起來；更新會換 baseline、proto8 也在用，要換再一起換。

## clangd

`.clangd` 叫 clangd 去 `build/debug/compile_commands.json` 找編譯參數（所以要先跑過 `cmake --preset debug`）。之後補完、跳定義、`nlohmann/json.hpp` 的標頭都找得到。新增檔案後重跑一次 configure，clangd 才認得。排版規則在 `.clang-format`（照 aos-v1 手寫的樣子：四格縮排、`char *p`）。

## VS Code 怎麼用

**用 VS Code 開 `impl_cpp/` 這一夾**（不是 repo 根），`.vscode/` 才會生效。這台裝的擴充：Kylin clangd（補完、排版）、Kylin C/C++ Debug（gdb）、CMake Tools；`.vscode/extensions.json` 就推這三個。

- **建／測**：`Ctrl+Shift+B` 跑 `build: debug`（會先 configure）；`Terminal → Run Task` 選 `configure／build／test: debug／release／asan`。
- **除錯**：`F5` 選 `gdb: aos-hello` 或 `gdb: hello_test`，會先跑 `build: debug` 再進 gdb。新程式照抄一個設定、改 `program`（`build/debug/bin/aos-<零件>`）。
- 存檔時自動照 `.clang-format` 排版。

<details><summary>設定細節</summary>

- `settings.json`：CMake Tools 走 `CMakePresets.json`、開資料夾時不自動 configure；clangd 背景建索引、不自動插 `#include`；ms-vscode.cpptools 的 IntelliSense 先關掉（現在沒裝，以後裝了也不會跟 clangd 打架）。
- 這台同時裝了 Kylin CMake Workflow 和 CMake Tools，兩個都讀 `cmake.*` 設定；覺得兩個打架就在這個工作區停用其中一個。
- `tasks.json` 的 build 用 `nice -n 15`、`-j2`，不吃滿機器。

</details>

## 骨架取自 aos-v1，差在哪

| aos-v1 | impl_cpp | 為什麼 |
|---|---|---|
| 每個小專案出共享庫 `.so`＋OBJECT 庫＋合併版 `libaos.so` | 只出靜態庫 `.a` | 只給自己的執行檔用，不必管符號匯出與 `.so` 版本 |
| 單一執行檔 `aos`，各小專案登記子命令（`aos_add_subcommand`、app/ 產生表） | 每個零件自己一支 `aos-<零件>`（`PROGRAM`） | 跟現行 proto8 一樣一支一個名字；要改回單一執行檔再加 |
| `core/` 與 `modules/` 兩類、`AOS_BUILD_*`、install／`find_package(aos)` 匯出 | 只有 `core/`、沒有這些選項 | 還沒有人要從外面連它 |
| `-fvisibility=hidden`、`AOS_API`、RPATH | 拿掉 | 靜態庫用不到 |
| 沒有測試；presets 用 Makefiles | `TESTS` 登記 ctest；presets 用 Ninja、加 asan | 這次要求 |
| 相依 nlohmann-json＋curl | 只有 nlohmann-json | curl 等用到再加 |

C++23、toolchain 找法、`common/` 的 `aos_common_private` 寫法照原樣。
