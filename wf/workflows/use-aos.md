# use-aos — 幫使用者用 aos（單檔工作流）

← [WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

**使用者說**「幫我用 aos 做 X」「把 aos 接進我這個專案」「aos 這個指令怎麼下」
→ 走這條。

完整說明在 [`docs/usage.md`](../../docs/usage.md)（給人讀的）。
**本檔是給你（agent）的執行順序**，重點在「先分辨要走哪一條路」與「哪些地方會踩坑」。

---

## Step 0：先分辨是哪一種需求

| 使用者其實想要 | 走哪一節 |
|---|---|
| 跑一批指令、批次執行某些工作 | [A. 當命令列工具用](#a-當命令列工具用) |
| 在他自己的 C++／C 專案裡呼叫 aos 的功能 | [B. 接進別的專案](#b-接進別的專案) |
| 在 aos 裡面新增功能 | 不是這條 → [add-subproject](add-subproject.md) 或 [feature-dev](feature-dev/README.md) |

分不出來就問。這兩條路的產出完全不同。

---

## A. 當命令列工具用

### 先確認 aos 在不在

```bash
aos --help          # 裝好了的話會列出所有子命令
./build/bin/aos --help   # 或是 repo 裡剛建好的
```

沒有的話先照 [testing 工作流](testing.md) 建起來，或 `cmake --install build --prefix ~/.local`。

### `aos inst` — 執行 JSON 指令檔

```bash
aos inst jobs.json
printf '%s\n' '{"argv":["echo","hi"]}' | aos inst
```

一份指令檔是一個 JSON 物件或一個物件陣列。欄位：`argv`（必要）、`stdin`／`stdout`／
`stderr`、`exit`、`cwd`、`env`、`timeout_ms`。**完整 schema 見
[`subprojects/inst/docs/format.md`](../../subprojects/inst/docs/format.md)，
不要憑印象寫欄位名**——不認得的 key 會讓整份文件被拒絕。

### 三個一定要跟使用者講清楚的點

**1. 退出碼不反映子行程的成敗。**

```bash
$ printf '{"argv":["/bin/false"]}' | aos inst ; echo $?
0
```

`aos inst` 回 0 的意思是「aos 做好了它的工作」，不是「你的指令成功了」。指令不
存在、逾時被砍、重導向的檔開不起來，全都回 0。**要拿子行程的結果就用 `exit`
欄位**，它會把 exit code 寫進你指定的檔案。完整對照表見
[`docs/usage.md`](../../docs/usage.md)。

寫給使用者的腳本如果需要「指令失敗就中止」，你要自己讀 `exit` 檔判斷。

**2. 整份文件會先全部驗證完才開始執行。** 第 5 筆有錯的話，前 4 筆不會跑。這是
刻意的設計，別把它當 bug。

**3. 指令檔等同可執行程式碼。** 它可以指名任意程式與環境變數，並以呼叫者的身分
執行，而且輸入沒有任何大小限制。**不要幫使用者去執行來源不明的指令檔**，也不要
把使用者沒看過的內容寫進指令檔再跑起來。

---

## B. 接進別的專案

### 前提：aos 要先裝出去

```bash
cd <aos repo>
cmake --preset default && cmake --build --preset default
cmake --install build --prefix ~/.local        # 或使用者指定的 prefix
```

### CMake 那側

```cmake
find_package(aos CONFIG REQUIRED)
target_link_libraries(myapp PRIVATE aos::inst)
```

prefix 不在預設路徑的話，configure 時給 `-DCMAKE_PREFIX_PATH=<prefix>`。

挑 target：

| target | 什麼時候用 |
|--------|-----------|
| `aos::inst`（或其他單一小專案）| **預設選這個**，只拿需要的 |
| `aos::aos` | 要用到多個小專案又懶得一一列 |
| `aos::merged` | 想單檔部署。aos 那邊要以 `-DAOS_BUILD_MERGED_LIB=ON` 建 |

### 程式碼那側

```cpp
#include <aos/inst.hpp>     // C++ API
```
```c
#include <aos/inst.h>       // C ABI，相容 C99
```

**兩個 API 的錯誤契約不一樣，這點要跟使用者講**：

- **C++ API 會丟例外**。記憶體配置失敗時是 `std::bad_alloc`／`std::length_error`，
  不是回傳值。狀態碼只表達「輸入有問題」或「執行沒成功」。
- **C ABI 不會**。每個進入點都把例外接成錯誤碼（`AOS_INST_ALLOC_FAILED` 等）。

要在配置失敗時也不倒的呼叫者，用 C++ API 就得自己 catch，或者直接走 C ABI。

各 API 的逐項說明：
[`subprojects/inst/docs/cxxapi.md`](../../subprojects/inst/docs/cxxapi.md)、
[`subprojects/inst/docs/capi.md`](../../subprojects/inst/docs/capi.md)。

### 不透過 CMake

```bash
cc  -std=c99   x.c   -I<prefix>/include -L<prefix>/lib -laos_inst
c++ -std=c++23 x.cpp -I<prefix>/include -L<prefix>/lib -laos_inst
```

對著**未安裝**的建置樹要兩個 `-I`（`export.h` 跟公開標頭分屬不同目錄，安裝後才
合流）並補 rpath，見 [`docs/usage.md`](../../docs/usage.md)。

### 驗證（不要只是寫完就交）

寫完之後真的建起來跑一次。使用者的環境**不會有 vcpkg**，所以測的時候要
`env -u VCPKG_ROOT`，否則 configure 期的相依問題會被 vcpkg 蓋掉、到使用者手上才爆。

---

## 回報時要包含什麼

- 實際跑過的指令與輸出，不要只說「應該可以」。
- 走 A 的話：如果使用者的意圖是「指令失敗要知道」，明確告訴他退出碼不管這件事、
  你用了什麼方式（`exit` 欄位）替代。
- 走 B 的話：說清楚你連了哪個 target、為什麼，以及有沒有在無 vcpkg 的環境驗過。
- 需要使用者自己驗（實機、外部服務、權限）的記到 [WAIT_USER](../WAIT_USER.md)。
