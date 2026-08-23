# aos

一組 POSIX 小工具的集合。每個小專案同時是兩件事：`aos` 執行檔的一條子命令，
以及一個可以被其他專案 `#include` 與連結的 C++23 函式庫。

目前只有一個小專案 [`inst/`](inst/) —— 讀 JSON 指令檔並依序執行。之後的
`llm/`、`tooljson/` 等都會照同一個模子長出來。

## 建置

需要 CMake 3.25+、支援 C++23 的編譯器，以及 [vcpkg](https://vcpkg.io)（裝在
`~/dev/vcpkg` 的話什麼都不用設）。

```bash
cmake --preset default && cmake --build --preset default && ctest --preset default
```

**只能從 repo 根目錄 configure**，子專案不提供獨立建置。產物在 `build/bin/aos`
與 `build/lib/libaos_*.so`。細節見 [docs/build.md](docs/build.md)。

## 當成執行檔用

```bash
aos --help                    # 列出所有子命令
aos inst jobs.json            # 執行一份指令檔
printf '%s\n' '{"argv":["echo","hello"]}' | aos inst
```

## 當成函式庫用

```bash
cmake --install build --prefix ~/.local
```

```cmake
find_package(aos CONFIG REQUIRED)
target_link_libraries(myapp PRIVATE aos::inst)
```

```cpp
#include <aos/inst.hpp>
```

`aos::inst` 是單一小專案；`aos::aos` 是一次連全部的傘狀 target；`aos::merged`
是合併成單一檔案的版本。完整說明見 [docs/usage.md](docs/usage.md)。

## repo 佈局

```
CMakeLists.txt      頂層：選項、相依、add_subdirectory、install/export
cmake/              AosSubproject.cmake（小專案樣板）、aos-config.cmake.in
common/             跨小專案共用：aos::common（<aos/export.h>）與通用私有相依
app/                唯一的執行檔 aos，只負責把 argv[1] 分派到某個子命令
inst/               第一個小專案：aos::inst + `aos inst` 子命令
docs/               整體文件
wf/                 分層工作流文件（開發流程用，與程式無關）
```

## 指令檔必須是可信來源

`aos inst` 沒有任何輸入限制：單筆與整份文件都沒有位元組上限，`argv` 與 `env`
的元素數量沒有上限，JSON 巢狀深度也沒有上限。記憶體用量由呼叫者的 `ulimit`
或 cgroup 決定，不是由這支程式決定；巢狀太深的文件會讓解析器爆堆疊——那是
crash，不是錯誤狀態。**一份指令檔等同一段可執行程式碼，來源要照同樣的標準把關。**

## 文件

| | |
|---|---|
| [docs/](docs/README.md) | 整體：[總覽](docs/overview.md)、[建置](docs/build.md)、[使用](docs/usage.md)、[新增小專案](docs/subprojects.md) |
| [inst/docs/](inst/docs/) | inst 專屬：[記錄格式](inst/docs/format.md)、[執行語意](inst/docs/exec.md)、[C++ API](inst/docs/cxxapi.md)、[C API](inst/docs/capi.md)、[架構](inst/docs/architecture.md) |
| [AGENTS.md](AGENTS.md) → [wf/](wf/) | 開發流程（不是給使用者看的）|
