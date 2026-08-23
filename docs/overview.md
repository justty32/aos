# aos 是什麼

← [文件索引](README.md)｜[建置](build.md)｜[使用](usage.md)｜[新增小專案](subprojects.md)

## 一句話

aos 是一組 POSIX 小工具的集合。**每個小專案同時是兩件事**：`aos` 執行檔的一條
子命令，以及一顆可以被別的專案 `#include` 與連結的 C++23 函式庫。

```
$ aos inst jobs.json                      # 當工具用
```
```cpp
#include <aos/inst.hpp>                   // 當函式庫用
```

目前只有一個小專案 `inst/`（讀 JSON 指令檔、`fork`/`exec` 執行）。之後的
`llm/`、`tooljson/` 等會照同一個模子長出來。

## 為什麼是這個形狀

寫小工具常常會遇到同一個岔路：**做成執行檔**，別的程式只能靠開 process 加
剖析 stdout 來用它；**做成函式庫**，就得另外再寫一支 CLI。兩邊各做一份，邏輯
就會開始漂移。

aos 的答案是**兩者同一份實作**：

- 業務邏輯放在小專案的函式庫裡（`aos::inst` → `libaos_inst.so`），公開標頭是
  `<aos/inst.hpp>`。
- CLI 是薄薄一層，**只透過公開 API** 呼叫那顆函式庫。所以只要 CLI 跑得起來，
  就代表公開介面確實夠用——這不是靠紀律維持的，是建置結構逼出來的。
- 所有小專案的 CLI 共用**同一支執行檔** `aos`，用子命令分流。不會出現
  `aos-inst`、`aos-llm`、`aos-tooljson` 這種一長串各自為政的執行檔。

## 佈局

```
CMakeLists.txt      頂層：選項、相依、add_subdirectory、install/export
CMakePresets.json   default / release / merged
vcpkg.json          manifest，釘了 builtin-baseline
cmake/
  AosSubproject.cmake   小專案樣板（aos_add_subproject 等三個函式）
  aos-config.cmake.in   外部 find_package(aos CONFIG) 用的樣板
common/             aos::common（公開共用）＋ aos_common_private（通用私有相依）
app/                唯一的執行檔 aos，只負責把 argv[1] 分派出去
inst/               第一個小專案
docs/               本目錄：整體文件
wf/                 開發工作流（與產品無關）
```

**只能從 repo 根目錄 configure**，子專案的 `CMakeLists.txt` 沒有自己的
`project()`，單獨拿出來是不成立的。

## 三個支撐整件事的機制

### 1. 小專案樣板

`aos_add_subproject()` 產出兩個 target：一個 OBJECT library 負責編譯，一個
SHARED library 對外（`aos::<name>`，安裝並匯出）。合併版 `libaos.so` 撿的是
同一批 `.o`，所以開了合併版也不會編兩次。

新增小專案 = 抄一份 `inst/` 的結構 + 根目錄加一行 `add_subdirectory()`。詳見
[subprojects.md](subprojects.md)。

### 2. 子命令表由建置系統產生

各小專案在自己的 `CMakeLists.txt` 呼叫 `aos_add_subcommand()` 登記；
`app/CMakeLists.txt` 在所有小專案都加完之後，把整張表攤成一份 X-macro 標頭；
`app/src/main.cpp` 用兩種 `AOS_SUBCOMMAND` 定義 include 它兩次——一次產生
`extern "C"` 宣告，一次產生表格內容。

**所以新增子命令不用改 `app/` 的任何檔案。** 登記時會在 configure 期檢查名稱
字集、名稱重複、進入點重複三件事（前兩者若不擋，症狀會是「靜默地叫不到」）。

### 3. 相依分三層

| 相依出現在哪 | 宣告在哪 | 使用者要不要跟著裝 |
|---|---|---|
| 公開標頭上 | `aos_add_subproject()` 的 `PUBLIC_DEPS` + `PUBLIC_PACKAGES` | 要（會產生 `find_dependency`）|
| 多數小專案的 `.cpp` | `common/CMakeLists.txt` 的 `aos_common_private` | 不用 |
| 只有某一個小專案的 `.cpp` | 該小專案的 `PRIVATE_DEPS` | 不用 |

私有相依一律不外流：`aos_add_subproject()` 連完之後會把
`INTERFACE_LINK_LIBRARIES` 重設成只剩公開部分。共享庫真正要連什麼已經記在自己
的 `DT_NEEDED` 裡，不必變成使用者的義務。

**推論**：任何相依只要出現在公開標頭上，你就把使用者綁死在同一個版本上了。所以
走 `PUBLIC_DEPS` 之前，先想清楚能不能用 pimpl 或 C ABI 躲掉。

## 刻意的取捨

**只支援 POSIX。** `WIN32` 直接 `FATAL_ERROR`。`inst` 的整條執行路徑就是
`fork`/`execve`/`waitpid`，沒有打算抽象掉。

**符號預設隱藏。** 全域 `-fvisibility=hidden` 加 `-fvisibility-inlines-hidden`。
公開標頭裡宣告的每個函式都要標 `AOS_API`（來自 `<aos/export.h>`），漏標的話
標頭連得到、實作連不到。inlines-hidden 那半特別重要：少了它，樣板實體化會出現
在 `.so` 的動態符號表上，這顆 `.so` 就變成「只給用同一版相依的人用」。

**C ABI 逐步補。** 每個小專案除了 `<aos/<name>.hpp>` 之外也可以提供
`<aos/<name>.h>`（目前只有 `inst` 有）。要跨語言或跨編譯器邊界時走那條。

**指令檔等同可執行程式碼。** `inst` 對輸入沒有任何大小限制，一份指令檔可以指名
任意程式、引數與環境變數，並以呼叫者的身分執行。它的來源要照「可執行檔」的標準
把關。細節見 [`inst/docs/exec.md`](../inst/docs/exec.md)。
