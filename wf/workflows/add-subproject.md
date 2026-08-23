# add-subproject — 在 aos 底下新增一個小專案（單檔工作流）

← [WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)｜程式碼慣例見 [common/conventions](common/conventions.md)

**使用者說**「幫我加一個叫 `xxx` 的小專案」「我要做一個新工具」→ 走這條。

完整的說明文件在 [`docs/subprojects.md`](../../docs/subprojects.md)（給人讀的）。
**本檔是給你（agent）照著做的執行順序**，含每一步要問什麼、驗什麼。

---

## 開始之前

先讀 [code map](common/code-map.md) 的「一分鐘看懂這個專案」，確認你理解這三件事：

1. 小專案住在 `core/`（核心）或 `modules/`（擴充）。`common/`／`app/`／`cmake/` 是基礎設施，不是小專案。
2. 每個小專案同時是一顆共享函式庫（`aos::<name>`）與 `aos` 執行檔的一條子命令。
3. **`core/inst/` 是參考範本**，照抄就對了。

## Step 0：先跟使用者確認五件事

不要猜。這幾項一旦定下來，改名成本很高：

| 要問 | 限制 | 例 |
|------|------|-----|
| 小專案名稱 | `^[a-z][a-z0-9-]*$`（會直接當子命令名與目錄名）；不可用 `aos`／`core`／`modules`／`merged`／`common` | `llm` |
| **核心還是擴充** | 拿掉它 aos 就不再是 aos → `core/`；仍然成立 → `modules/`。拿不定主意放 `modules/` | 擴充 |
| 這個小專案做什麼 | 一行說明，會印在 `aos --help` | 「呼叫 LLM 並回傳結果」|
| 要不要子命令 | 純函式庫的小專案可以不要 | 要 |
| 有沒有新的外部相依 | 有的話問清楚是**公開標頭**要用還是只有 `.cpp` 要用 | 需要 libcurl，只有 .cpp 用 |

**沒有子命令的小專案**就跳過下面所有跟 `aos_add_subcommand()`／`src/run.cpp` 有關的步驟。

## Step 1：建目錄

```
core/<name>/  或  modules/<name>/       ← Step 0 決定的那個
  include/aos/<name>.hpp     公開標頭
  src/<name>.cpp             實作
  src/run.cpp                CLI 層（要子命令才需要）
  tests/test_<name>.cpp
  docs/                      這個小專案的細節文件（可以先空著）
  CMakeLists.txt
```

**公開標頭一定要放在 `include/aos/` 底下**，這樣內部與外部寫的 include 路徑一致。

## Step 2：公開標頭

```cpp
#pragma once

#include <aos/export.h>

namespace aos::<name> {

AOS_API 回傳型別 函式名(參數);

}
```

**每一個宣告在公開標頭裡的函式都要標 `AOS_API`。** 漏標的話編譯會過、外部
include 也會過，但連結時找不到符號——因為全域是 `-fvisibility=hidden`。這是這個
專案最容易犯、而且最晚才會被發現的錯。

## Step 3：CLI 進入點（要子命令才做）

`src/run.cpp` 檔尾：

```cpp
extern "C" int aos_<name>_cli_main(int argc, char *argv[]) {
    // argv[0] 是 "aos <name>"，印用法訊息直接用它
    return 0;
}
```

用 C 連結是因為 CMake 產生的子命令表要直接寫出這個宣告，不能依賴 C++ 的名稱修飾。

**CLI 只能透過公開 API 呼叫自己的函式庫**，不要 include `src/` 底下的內部標頭。
這條規則是刻意的：CLI 跑得起來就等於證明公開介面夠用。

## Step 4：小專案自己的 `CMakeLists.txt`

照抄 `core/inst/CMakeLists.txt` 改名字：

```cmake
aos_add_subproject(<name>
    SOURCES src/<name>.cpp
    HEADERS include/aos/<name>.hpp
)

add_library(aos_<name>_cli OBJECT src/run.cpp)
target_link_libraries(aos_<name>_cli PUBLIC aos::<name>)

aos_add_subcommand(
    NAME <name>
    ENTRY aos_<name>_cli_main
    LIBRARY aos_<name>_cli
    SUMMARY "一行說明"
)

aos_add_test(aos_<name>_tests
    SOURCES tests/test_<name>.cpp
    LINK aos_<name>_cli
)
```

**相依要放對層**（判準與理由見 [`docs/subprojects.md`](../../docs/subprojects.md)）：

| 相依出現在 | 寫在哪 |
|---|---|
| 公開標頭 | `aos_add_subproject()` 的 `PUBLIC_DEPS` ＋ `PUBLIC_PACKAGES` |
| 多數小專案的 `.cpp` | `common/CMakeLists.txt` 的 `aos_common_private`（自動連上，這裡不用寫）|
| 只有這個小專案的 `.cpp` | `PRIVATE_DEPS` |

nlohmann_json 屬第二類，**不要寫進 `PRIVATE_DEPS`**。

## Step 5：掛上去

在 **Step 0 決定的那個目錄**的 `CMakeLists.txt` 加一行——`core/CMakeLists.txt`
或 `modules/CMakeLists.txt`：

```cmake
add_subdirectory(<name>)
```

分類就是靠這個決定的（那兩份各自 `set` 了 `AOS_SUBPROJECT_CATEGORY`，會沿著
`add_subdirectory` 繼承下來）。

**根 `CMakeLists.txt` 與 `app/` 都不要動。** 如果你覺得需要動它們，代表前面某一步
做錯了，回去檢查。

## Step 6：驗證（每一項都要真的跑）

```bash
cmake --preset default
cmake --build --preset default
ctest --preset default                      # 要全綠
./build/bin/aos --help                      # 新子命令要出現、說明要正確
./build/bin/aos <name> ...                  # 真的叫得動

# 加的是擴充小專案的話，再確認關掉之後整包還是建得起來
cmake -S . -B /tmp/aos-nomod -DAOS_BUILD_MODULES=OFF && cmake --build /tmp/aos-nomod
```

然後**一定要做外部消費測試**——這一步會抓到只有從 repo 外面看才看得出來的問題
（最典型的是私有相依洩漏到匯出介面，症狀是使用者在沒有 vcpkg 的環境 configure 直接失敗）：

```bash
cmake --install build --prefix /tmp/aos-check
mkdir -p /tmp/aos-consumer && cd /tmp/aos-consumer
cat > CMakeLists.txt <<'EOF'
cmake_minimum_required(VERSION 3.25)
project(c LANGUAGES CXX)
find_package(aos CONFIG REQUIRED)
add_executable(c main.cpp)
target_link_libraries(c PRIVATE aos::<name>)
EOF
# main.cpp 寫幾行真的呼叫到公開 API 的程式
env -u VCPKG_ROOT cmake -S . -B build -DCMAKE_PREFIX_PATH=/tmp/aos-check
cmake --build build && ./build/c
```

`env -u VCPKG_ROOT` 是重點，不要省略——有 vcpkg 在的話這個測試就失去意義了。

## Step 7：收尾（commit 之前）

照 [AGENTS.md](../../AGENTS.md) 的鐵律，這幾份都要同步，缺一不可：

- [ ] [code map](common/code-map.md)：新增這個小專案的段落（哪個檔負責什麼）
- [ ] [`core/README.md`](../../core/README.md) 或 [`modules/README.md`](../../modules/README.md)：表格加一列
- [ ] `<core|modules>/<name>/docs/`：這個小專案自己的細節文件
- [ ] [`docs/overview.md`](../../docs/overview.md)：如果小專案清單有寫在裡面
- [ ] 有新相依的話，[`docs/subprojects.md`](../../docs/subprojects.md) 的相依那節要不要跟著調整

## 常見錯誤

| 症狀 | 原因 |
|------|------|
| 外部連得到標頭、連不到實作 | 公開標頭的函式漏標 `AOS_API` |
| 使用者 `find_package(aos)` 說找不到某個套件 | 私有相依被寫成 `PUBLIC_DEPS` |
| configure 報「子命令已經由 … 登記過了」| 名稱撞到別的小專案，換一個 |
| 連結期 multiple definition | 兩個小專案用了同一個 `ENTRY` 符號名 |
| 新子命令沒出現在 `--help` | `core/` 或 `modules/` 的 `CMakeLists.txt` 忘了加 `add_subdirectory()`；或它是擴充但你用了 `-DAOS_BUILD_MODULES=OFF` |
| configure 報「小專案必須放在 core/ 或 modules/ 底下」| `add_subdirectory()` 加錯地方了 |
| configure 報「'xxx' 是保留名稱」| 名字撞到傘狀 target，換一個 |
