# code map — core/inst/ CLI 層

← [core/inst 分冊入口](../inst.md)｜[本資料夾導覽](README.md)｜[code map 總圖](../../code-map.md)

`core/inst/src/` 裡 CLI 層（`aos init`／`aos exec`／`aos deliver` 的世界／回合層）的逐檔職責。
**新增／刪除 `core/inst/src/run*.cpp`／`run*.hpp`，就在這一份加／減那一列。**

---

## core/inst/src/ — CLI 層

| 檔案 | 負責 |
|------|------|
| `run.hpp`／`run.cpp` | CLI 對內介面、init／exec argv 解析、folder 預設 `.`、將 `--loop 0` 警告並下限化為 1 ms、配置失敗例外邊界，以及 exec／init 兩個 C 入口（deliver 的解析與 C 入口自帶於 `run_deliver.cpp`，只在 `run.hpp` 掛一行宣告） |
| `run_internal.hpp` | CLI 各實作檔之間的內部宣告：單回合、loop、init world、deliver world |
| `run_init.cpp` | 建立 `.aos/`、版本 1、`inst.tempd/` inbox、回合計數器 `turn`（初值 `0`，§B-3）與 `.gitignore`（§E-4 政策的執行者；舊世界缺它不算錯，exec／deliver 都不檢查），失敗時回滾剛建立的狀態。`version`／`turn`／`.gitignore` 三個檔各自 close 前 `fsync`，寫完後 `fsync` `.aos` 目錄 fd 把四個新目錄項一併落盤，再 `fsync` 父資料夾把 `.aos` 這個目錄項本身落盤。`.aos` 已被普通檔（或 symlink）佔住時印 `invalid <folder>/.aos: Not a directory`，是目錄才印 `already exists` |
| `run_deliver.cpp` | `aos deliver [folder] [-f FILE|-]`：argv 解析（folder 預設 `.`、輸入預設 stdin、`-` 與 `-f -` 都是 stdin、認不得的選項回 2）、把輸入整份讀進記憶體（`-f` 的路徑相對**呼叫者的** cwd，所以讀在 chdir 之前），再進世界驗 `.aos` 與版面版本（`version_is_current`：剝掉尾端空白再與 `1` 全等，與 run_exec 同義各留一份）、呼叫庫層 `deliver_instructions`、把 `{"delivery","count","target"}` 印成單行 JSON（§D-3）。退出碼 0／1／2；`aos_deliver_cli_main` 是它的 C 入口 |
| `run_exec.cpp` | 單回合：進入 world、驗版本（`version_is_current`：剝掉尾端空白再與 `1` 全等，§B-4 只立法「讀不到／不認得＝拒絕」）、**彙整前先 `lstat` `.runi` 決定拒不拒絕啟動**（回 3；claim 的 `Busy` 分支留著兜底 race）、aggregate → claim → execute batch → release，release 成功後呼叫 `run_turn.cpp` 的 `advance_turn()` 遞增 `.aos/turn`，並把結果映成診斷與 0／1／3 |
| `run_turn.cpp` | `.aos/turn`（這台機器的 PC）的遞增（§B-3）：讀不到視為 `0`（裁-5，**MUST NOT** 拒絕、**MUST NOT** 動版面版本）；內容不是「十進位整數＋LF」一律 `EINVAL` 拒絕、不猜；等於 `UINT64_MAX` 回 `ERANGE`，不靜默回繞成 0。寫法是 temp→fsync→rename→fsync 目錄，**rename 之前的任何失敗都 unlink 自己的 `turn.temp`**，殘骸不留給 M3 的 `aos recover`。整個函式期間用 RAII 在**範圍內**忽略 `SIGXFSZ`，讓 `ulimit -f` 觸頂時 write 誠實回 `EFBIG` 而不是行程被砍死——**刻意不在行程層級設 `SIG_IGN`**，因為被忽略的訊號處置會跨 `execve` 繼承給使用者程式（exec 層「凍結的矽」）。從 `run_exec.cpp` 拆出來（該檔過了 300 行門檻，且 turn 與彙整／取件／執行不耦合） |
| `run_loop.cpp` | `--loop` 的空回合輪詢、0／1／3 政策，以及兩段式 SIGINT／SIGTERM 收尾 |
| `run_batch.hpp`／`run_batch.cpp` | CLI 內部批次迴圈：整批解析後以父行程環境 resolve 全部記錄，再同步執行一般記錄、複製 `parallel` 記錄進 thread，最後全數 join；resolve 錯誤會印出記錄、位置與變數 |
