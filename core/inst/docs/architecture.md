# 架構

這份實作刻意切成四個範圍狹窄的分層：

- `inst` 擁有 `inst_t`、它的公開狀態，以及清除與狀態字串的輔助函式。
  它既不懂位元組／JSON，也不懂行程。
- `format` 是唯一懂得 JSON 文件 schema 的分層。它把位元組緩衝區轉換成經過
  驗證的指令，也把指令轉回精簡的記錄；它完全不懂 `fork`、不懂路徑作為作業系統
  資源這件事，也不懂 CLI I/O。
- `exec` 接收一個已經建好的 `inst_t`。它負責環境變數與 PATH 的準備、
  `fork`/`execve`、重導向、行程群組、等待、逾時、狀態檔輸出，以及執行狀態；
  它從不剖析 JSON，也不讀取指令來源。
- `run` 負責 `aos init` 建立世界，以及 `aos exec` 的版本檢查、完整讀取、取件
  rename、CLI 診斷、整批剖析與依 `parallel` 決定同步執行或開 thread、最後 join
  全部 thread 的批次迴圈。它也是原生 CLI
  這一側**唯一的例外邊界**：讀檔、剖析、執行三個階段都接住 `std::bad_alloc` 與
  `std::length_error`，轉成一行訊息與非零退出碼（C ABI 那側則是每個 `extern "C"`
  進入點各自接）。它透過 `aos_exec_cli_main` 與 `aos_init_cli_main` 兩個 C 連結
  進入點，掛成 `aos` 執行檔的 `exec` 與 `init` 子命令。

`format` 和 `exec` 是兄弟關係，彼此不相依；兩者都相依於 `inst`。公開函式庫
`libaos_inst.so`（CMake target `aos::inst`）包含 `inst`、`format`、`exec`、
spawn 準備，以及 C ABI；`run` 則另外編成一個不安裝、不進 `aos::inst` 的
OBJECT library（`aos_inst_cli`）。`run` 只透過 `aos::inst` 的公開 API 呼叫
前三層，這也順便驗證了公開介面本身就夠用，不必開後門。

唯一的執行檔 `aos`（`app/`）沒有任何業務邏輯：`main` 只依 `argv[1]` 查一張由
各小專案登記出來的子命令表，把剩下的引數原樣轉發給對應的進入點。`inst` 小專案
登記 `exec` 與 `init` 兩條命令，但沒有自己的 `main`。

## 為什麼要先把整份輸入讀完

runner 會把 `.aos/inst.json` 一路讀到 EOF，全部進到一個記憶體緩衝區裡，立刻
rename 成 `.aos/inst.json.runi`，接著在啟動第一個命令之前剖析並驗證每一筆記錄。
解析與執行正常返回後（不論結果為 0 或 1），會在所有 parallel thread join 完畢後
unlink `.runi`；若 unlink 失敗，該回合回 1 並明確診斷。
由此得到的保證是格式錯誤的批次原子性：只要第五筆記錄
格式不正確，就代表第一到第四筆記錄都不會執行。串流式的讀取器無法提供這種保證，
因為等到發現第五筆記錄有問題時，先前那些命令的副作用早已無法回復。

這個選擇有實際的代價。FIFO 與管線輸入無法逐步執行：第一筆記錄要一直等到生產端
關閉其輸出為止，所以長時間存活的生產端沒辦法持續地餵資料給這個 runner。記憶體
用量的上界是整份輸入，而不是最長的那一筆記錄，而且**這個上界沒有內建的限制**：
runner 不對輸入設任何上限，一個無界的生產端就能讓它一直配置記憶體下去。這是
刻意的取捨——指令檔的大小由部署方決定，該由部署方的 `ulimit` 或 cgroup 去設
邊界，而不是由一個猜出來的常數。位元組數、`argv` 元素數、`env` 條目數與 JSON
巢狀深度都比照辦理，一條上限都沒有留。深度那條的代價是實在的：深層巢狀的輸入
會讓遞迴下降的解析器爆掉堆疊，那是崩潰而不是驗證失敗。這個 runner 假設它的
指令來源是可信的。

一份完整 JSON 陣列會被一次驗證，再依輸入順序啟動；標成 `parallel` 的記錄可與後續記錄重疊執行，
但整批返回前仍會全部 join。

## `fork` 兩側各自要做的工作

在多執行緒的行程裡，就在 `fork` 複製行程的那一瞬間，可能有另一個執行緒正握著
配置器或函式庫的鎖。子行程裡只有呼叫端那個執行緒會存活下來，所以 fork 之後若
有呼叫試圖去取得那種鎖，就可能永遠死結。因此 POSIX 規定，在 `exec` 換掉行程
映像之前，子行程只能呼叫 async-signal-safe 的操作。

所有的記憶體配置與複雜的準備工作，都在 `fork` 之前於父行程裡完成：實作會驗證
環境變數的 key、把繼承來的環境合併進來、把字串與 `envp` 實體化、建好 `argv`、
取得有效的工作目錄，並解析 PATH 候選項。子行程只收到穩定的指標，然後呼叫
`setpgid`、`open`、`dup2`、`close`、`chdir`、`execve` 與 `_exit`。這些都是
async-signal-safe 的 POSIX 操作；那裡不會發生任何 C++ 記憶體配置、`setenv`、
字串操作或 `execvp`。父行程也會呼叫 `setpgid`，好在逾時訊號鎖定整個群組之前，
先關掉父／子行程之間的排程競速。

## 外部專案怎麼用

`aos` 是一個 monorepo，`inst` 只是掛在它底下的其中一個小專案——具體來說是一個
**核心**小專案（住在 `core/`，一定會被建置；相對的 `modules/` 底下是可選的擴充，
可以用 `-DAOS_BUILD_MODULES=OFF` 整批不建）。外部的 CMake 專案想用 `inst` 的
C++ API，走 `find_package`：

```cmake
find_package(aos CONFIG REQUIRED)
target_link_libraries(myapp PRIVATE aos::inst)
```

再 `#include <aos/inst.hpp>`（或 C 用戶端 `#include <aos/inst.h>`）即可；
`aos::inst` 這個 target 已經帶著它自己的 include 目錄與 `aos::common`
（提供 `<aos/export.h>`）這個相依，不需要另外連。這一份 `libaos_inst.so`
的建置與連結細節見[C API](capi.md)與[C++ API](cxxapi.md)。

如果同時裝了多個小專案，也可以連傘狀 target：`aos::core`（所有核心小專案）、
`aos::modules`（所有擴充，沒有擴充時不會被匯出）、`aos::aos`（全部）。它們都是
INTERFACE target，只是轉連到已建置的那些小專案。另外有個關掉的選項 `AOS_BUILD_MERGED_LIB`，開了會多產出
一份把所有小專案合在一起的單檔 `libaos.so`（target `aos::merged`）——這是給
想單檔部署的場景用的，預設不建。
