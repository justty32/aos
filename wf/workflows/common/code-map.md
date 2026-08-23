# code map — aos 程式碼結構導航圖

← [common/README](README.md)｜[INDEX](../../INDEX.md)｜維護規則見 [conventions](conventions.md)

**要改程式碼，先讀這張圖**：先找到你要動的領域，只讀那一格列出的檔案，不要順手翻無關的目錄。
這張圖與程式碼衝突時**以程式碼為準**，發現不對就當場修這張圖。

---

## 一分鐘看懂這個專案

`aos` 是一個 **monorepo**：只有一個執行檔 `aos`，靠子命令把陸續長出來的各個「小專案」掛上去（例如 `aos inst jobs.json`）。第一個小專案是 `subprojects/inst/`——一支讀 JSON instruction、`fork`/`exec` 跑起來的 POSIX 指令執行器。

```
repo 根
  aos::common（common/，header-only，目前只有 <aos/export.h>）
       ▲ 每個小專案都連它
  aos::inst（subprojects/inst/，第一個小專案 → libaos_inst.so）
       │  C++ 分層，相依單向：inst ← format ← exec
       │    inst    inst_t 資料結構、狀態列舉             （src/inst.cpp）
       │    format  唯一懂 JSON schema 的層                （src/format.cpp）
       │    exec    唯一碰 fork/exec/waitpid 的層          （src/exec.cpp + spawn_prep.cpp + wait.cpp）
       │  外加兩層，各自只往下看：
       │    C ABI 包裝（src/capi*.cpp，對外標頭 <aos/inst.h>）
       │    CLI 執行迴圈（src/run.cpp，進入點 aos_inst_cli_main）
       ▼
app/（唯一執行檔 aos，子命令分派）── `aos inst jobs.json` 掛的就是上面這條
```

三個一直會用到的概念：

1. **單向相依是鐵律**：`inst ← format ← exec`——`format` 可以用 `inst` 的型別，`exec` 可以用 `inst` 的型別，但 `format` 與 `exec` 互相不知道對方存在，`inst` 什麼都不知道。三組宣告目前併在同一個標頭 `include/aos/inst.hpp` 裡，**併在一起不代表可以互相引用**，標頭開頭那段註解就是講這件事。
2. **一個執行檔、多個子命令**：不會有第二個 `main`。新的小專案（未來的 `llm/`、`tooljson/`……）靠自己的 CMakeLists 呼叫 `aos_add_subcommand()` 把子命令掛進 `app/` 的分派表，不用改 `app/` 本身。
3. **每個小專案是一顆獨立的 shared lib**：`aos::inst` → `libaos_inst.so`。要一次連全部才用 `aos::aos`（INTERFACE 傘狀 target）；`AOS_BUILD_MERGED_LIB` 開了才會多產出一顆合併的 `libaos.so`（`aos::merged`）。

> **`subprojects/inst/src` 的核心分層與 C ABI 層視為凍結**——`inst.cpp`／`format.cpp`／`exec.cpp`／`spawn_prep.*`／`wait.*`／`capi*.cpp` 不要改。`run.cpp`（CLI 層）與建置設定不在此限。要改行為就從 CLI 層那側解決。

---

## common/ — 跨小專案共用

兩個 target，職責刻意分開：

| target | 安裝／匯出 | 負責 |
|--------|-----------|------|
| `aos::common` | 是 | Header-only 的公開共用部分，目前只有 `<aos/export.h>`，外加 `cxx_std_23` |
| `aos_common_private` | **否** | 多數小專案的**實作檔**都會用到的相依（目前只有 `nlohmann_json`）。`aos_add_subproject()` 一律以 PRIVATE 連上，所以小專案的 CMakeLists 不用重複宣告，也不會變成使用者 `find_package(aos)` 的義務 |

**相依放哪裡的判準**：會出現在**公開標頭**上 → `aos_add_subproject()` 的 `PUBLIC_DEPS` + `PUBLIC_PACKAGES`（後者會讓 `aos-config.cmake` 產生 `find_dependency()`）。只在 `.cpp` 裡用到、且多數小專案都要 → `aos_common_private`。只有某一個小專案要 → 該小專案的 `PRIVATE_DEPS`。

| 檔案 | 負責 |
|------|------|
| `include/aos/export.h` | `AOS_API` 可見度宏（`__attribute__((visibility("default")))`，定義 `AOS_STATIC` 時展開成空）。每個小專案**公開標頭裡宣告的每一個函式**都要標它，否則 `-fvisibility=hidden` 之下外部連不到 |

## app/ — 唯一的執行檔

產出 `aos` 這一支執行檔本身，靠子命令分派到各小專案。新增子命令**不用改這裡的程式碼**：在對應小專案的 CMakeLists 呼叫 `aos_add_subcommand()` 即可，`app/CMakeLists.txt` 會把大家登記的結果攤成一份 X-macro 標頭（`aos_subcommands.inc`），`main.cpp` 用兩種 `AOS_SUBCOMMAND` 定義 include 它兩次——一次產生 `extern "C"` 宣告，一次產生表格內容。

| 檔案 | 負責 |
|------|------|
| `CMakeLists.txt` | 讀全域屬性、產生 `aos_subcommands.inc`。摘要是自由文字，反斜線／雙引號／換行在這裡跳脫 |
| `src/main.cpp` | 分派：比對 `argv[1]`，把 `argv[0]` 換成 `"aos <command>"` 之後轉發給子命令。`-h`／`--help` 與未知命令都印子命令表 |

登記時會在 configure 期擋三件事，都是「不擋的話症狀很難查」的：`NAME` 必須符合 `^[a-z][a-z0-9-]*$`；`NAME` 不可重複（重名的話 configure／編譯／`--help` 全都正常，但線性分派只叫得到先註冊的那個，**沒有任何訊息**）；`ENTRY` 不可重複（否則錯誤延到連結期，變成看不懂的 multiple definition）。

## subprojects/inst/ — 第一個小專案：POSIX 指令執行器

讀一筆或一批 JSON instruction，準備好環境／重導向後 `fork`＋`execve` 跑起來，等它結束、寫回 exit status。對外是 `aos::inst`（`libaos_inst.so`）＋ `aos inst` 子命令。

### subprojects/inst/include/aos/ — 對外公開標頭

| 檔案 | 負責 | 關鍵型別／函式 |
|------|------|----------------|
| `inst.hpp` | C++ API。三個分層的宣告都在這（見上面「單向相依是鐵律」），標頭上半是 `inst`／`format`，下半是 `exec` | `inst_t`（`argv`／`stdin_path`／`stdout_path`／`stderr_path`／`exit_path`／`cwd`／`env`／`timeout_ms`、`clear()`）、`InstState`、`to_string(InstState)`、`read_one`／`read_all`／`write_one`／`write_all`、`ExecState`、`ExecResult`、`execute()`、`to_string(ExecState)` |
| `inst.h` | C ABI（給非 C++ 呼叫者用），是 `inst.hpp` 的鏡像，型別靠 `static_assert` 對齊（見 `src/capi.cpp`） | `aos_instruction`（opaque）、`aos_exec_result`、`aos_inst_state`／`aos_inst_field`／`aos_exec_state`、`aos_instruction_new/free/clear`、`aos_instruction_argc/arg/push_arg`、`aos_instruction_field/set_field`、`aos_instruction_env_count/env_key/env_value/set_env`、`aos_instruction_timeout_ms/set_timeout_ms`、`aos_instruction_read_buffer/read_fd/read_file`、`aos_instruction_write_buffer/write_fd/write_file`、`aos_instruction_execute`、`aos_*_state_string`、`aos_version_string` |

### subprojects/inst/src/ — 三個核心分層

| 檔案 | 負責 |
|------|------|
| `inst.cpp` | **inst 層**：`inst_t::clear()`、`to_string(InstState)`。不碰位元組／JSON，也不碰行程 |
| `format.cpp` | **format 層**：唯一懂 JSON schema 的檔。已知欄位共 8 個（`argv`／`stdin`／`stdout`／`stderr`／`exit`／`cwd`／`env`／`timeout_ms`），碰到不認得的 key 就回 `UnknownKey`。`read_one`／`read_all` 剖析＋驗證（`argv` 不可空、`env` key 不可空或含 `=`）；`write_one`／`write_all` 編回精簡 JSON（每筆一行）。用 `nlohmann::json`／`nlohmann::ordered_json`。只 catch `json::parse_error`——配置失敗的例外會往上拋 |
| `exec.cpp` | **exec 層**：唯一碰 `fork`／`execve`／`waitpid` 的檔。`execute()`：組 `argv`＋`envp`（透過 `spawn_prep`）→ `fork` → 子行程 `setpgid`＋重導向＋`chdir`＋`execve`（`run_child`，全程 async-signal-safe）→ 父行程視 `timeout_ms` 決定直接 `wait_retry` 或 `wait_until` 輪詢；逾時先對整個行程群組送 `SIGTERM`、給 `kTimeoutGraceMs`（2000ms）緩衝，仍不收就 `SIGKILL` 整個群組——打群組是因為忽略 `SIGTERM` 的孫行程才殺得掉。結束後若 `exit_path` 非空就把 exit code 寫進那個檔 |
| `spawn_prep.hpp`／`.cpp` | **內部標頭**（不對外）。`prepare_spawn()`：在 `fork` 之前把所有會配置記憶體的準備工作做完——合併繼承的環境變數與 `inst.env`（後者覆蓋前者）、組 `envp`、若 `argv[0]` 沒有 `/` 就沿 `PATH`（或 `confstr(_CS_PATH)` 的預設值）逐段找可執行檔。子行程只拿到已經算好的穩定指標 |
| `wait.hpp`／`.cpp` | **內部標頭**。`wait_retry()`：EINTR-safe 的 `waitpid` 包裝。`wait_until()`：用 `CLOCK_MONOTONIC` 算經過時間，指數退避（上限 `kMaxPollMs`＝50ms）輪詢 `waitpid(WNOHANG)` 直到逾時 |

**改 exec 的行為要小心兩件事**：① `fork` 之後、`execve` 之前只能呼叫 async-signal-safe 的操作（細節與理由見 `subprojects/inst/docs/architecture.md`「`fork` 兩側各自要做的工作」）；② 逾時後的 `SIGKILL` 一定要打整個行程群組（`-pid`），不是單一 `pid`。

**這一層有幾處刻意的設計，不要「修」**：PATH 撞到同名目錄時回 exit 126 而不是 127；三處 `kill(-pid, ...)` 的回傳值刻意忽略；`wait_until()` 出錯時直接 return、不 kill 不 reap。外部審查工具會反覆把它們當成 bug 提出來。

### subprojects/inst/src/ — C ABI 包裝層（只往下看 inst/format/exec，不影響它們）

| 檔案 | 負責 |
|------|------|
| `capi_common.hpp` | **內部標頭**：`aos_instruction` 的實際定義（`struct aos_instruction { aos::inst_t value; }`），只有這幾個 `capi_*.cpp` 看得到 |
| `capi.cpp` | 版本字串、狀態轉字串（`aos_inst_state_string`／`aos_exec_state_string`）。開頭一串 `static_assert` 讓 C 的列舉值與 C++ 的 `InstState`／`ExecState` 對齊——**新增或改一個列舉值，兩邊都要動，這裡的 static_assert 會在改漏時讓建置失敗** |
| `capi_instruction.cpp` | 操作單個 `aos_instruction` 的存取子：建立／釋放／清空、`argv` 讀寫、四個路徑欄位＋`cwd`、`env` 的讀寫、`timeout_ms` |
| `capi_io.cpp` | 讀寫整份 instruction：`read_buffer/fd/file`、`write_buffer/fd/file`（呼叫 `format` 層），以及 `aos_instruction_execute`（呼叫 `exec` 層） |

**每個 `extern "C"` 進入點都有 `catch (...)`**，把例外接成 `AOS_INST_ALLOC_FAILED` 之類的錯誤碼——例外絕對不能逸出 C 邊界。新增進入點時照抄這個形狀。

**C ABI 的 ABI 規則**：`inst.h` 裡的列舉值一經釋出就凍結，只能在尾端加新值，不能重排或刪除既有值——這條規則寫在標頭裡的註解，改動前先看。

### subprojects/inst/src/ — CLI 層

| 檔案 | 負責 |
|------|------|
| `run.hpp`／`run.cpp` | `run(argc, argv)`：決定輸入來源（給了檔名就開檔，否則讀 stdin）→ 讀到 EOF 進單一緩衝區 → `read_all()` 一次剖析＋驗證整批 → 依序對每筆呼叫 `execute()`，失敗的印到 stderr、繼續跑下一筆，只要有一筆失敗整體回 1。讀檔、剖析、執行三個階段都接 `bad_alloc`／`length_error`——**這一層是原生 CLI 唯一的例外邊界**（C ABI 那側自己有接）。檔尾的 `extern "C" aos_inst_cli_main()` 是 `aos inst` 子命令的進入點，名字要與 `subprojects/inst/CMakeLists.txt` 的 `aos_add_subcommand(ENTRY ...)` 一致。**為什麼要先把整份輸入讀完**、以及這個設計的代價，見 [`subprojects/inst/docs/architecture.md`](../../../subprojects/inst/docs/architecture.md) |

**新增一個 instruction 欄位**：① `inst.hpp` 的 `inst_t` 加欄位；② `format.cpp` 的 `known_key`／`encode`／`decode` 三處都要加；③ 需要的話 `inst.h` 加對應 C ABI 存取子＋`capi_instruction.cpp` 實作；④ `exec.cpp`／`spawn_prep.cpp` 視欄位語意決定要不要用到。（但注意上面的凍結規則——這種改動要先跟使用者確認。）

## subprojects/inst/tests/ — 測試

跑法見 [testing 工作流](../testing.md)。

| 檔案 | 涵蓋 |
|------|------|
| `test_format_read.cpp`／`test_format_write.cpp`／`test_format_malformed.cpp` | format 層：JSON round trip、各種壞輸入、已知/未知欄位 |
| `test_exec_streams.cpp`／`test_exec_path.cpp`／`test_exec_status.cpp` | exec 層：重導向、PATH 解析、exit status／signal 對應 |
| `test_timeout.cpp` | exec 層：逾時、行程群組 `SIGTERM`→`SIGKILL` |
| `test_run.cpp` | CLI 層：整批剖析＋依序執行的迴圈行為 |
| `exec_test_support.hpp` | 測試共用的小工具 |
| `test_capi.c` | C ABI 往返測試（獨立的 C 執行檔，不連 C++ 測試框架） |

C++ 測試建成一支 `aos_inst_tests`；C ABI 測試建成 `aos_inst_capi_tests`。

## 文件在哪

`docs/`（repo 根）放**整體**文件：[總覽](../../../docs/overview.md)、[建置](../../../docs/build.md)、[使用](../../../docs/usage.md)、[新增小專案](../../../docs/subprojects.md)。改了建置骨架、子命令機制或相依管理，那邊要跟著更新。

`subprojects/inst/docs/` 放 inst 專屬的細節，不是 code map 的一部分，但改東西之前有時值得先看：

| 檔案 | 內容 |
|------|------|
| `architecture.md` | 分層為什麼這樣切、為什麼先把整份輸入讀完再執行、`fork` 兩側各自要做的工作（async-signal-safe 的界線在哪）|
| `format.md` | JSON schema 細節 |
| `exec.md` | 執行語意細節 |
| `capi.md`／`cxxapi.md` | C ABI／C++ API 的使用說明 |

---

## 建置設定

| 路徑 | 負責 |
|------|------|
| 根 `CMakeLists.txt` | 頂層：`option()`、vcpkg toolchain 解析（在 `project()` 之前）、`find_package`、`add_subdirectory`、傘狀 target、合併版、`install`／`export` |
| `cmake/AosSubproject.cmake` | 三個共用函式：`aos_add_subproject()`（產出 OBJECT＋SHARED 兩個 target，並把私有相依從匯出介面剝掉）、`aos_add_subcommand()`（登記子命令＋三道守衛）、`aos_add_test()` |
| `cmake/aos-config.cmake.in` | 讓外部專案 `find_package(aos CONFIG)`。`@AOS_FIND_DEPENDENCIES@` 由根 CMakeLists 從各小專案登記的 `PUBLIC_PACKAGES` 產生 |
| 根 `vcpkg.json` | manifest，有 `builtin-baseline`；測試相依（Catch2）放在 `"tests"` feature |
| `CMakePresets.json` | `default`／`release`／`merged`。vcpkg toolchain 由根 `CMakeLists.txt` 解析（`CMAKE_TOOLCHAIN_FILE` → `VCPKG_ROOT` → `~/dev/vcpkg`），本機不用設環境變數 |
| `common/CMakeLists.txt` | `aos::common` 與 `aos_common_private`（見上面 common/ 那節）|
| `subprojects/inst/CMakeLists.txt` | 小專案的**參考範本**：`aos_add_subproject()`（目前不需要任何 DEPS 參數）＋ CLI 的 OBJECT library ＋ `aos_add_subcommand()` ＋兩個 `aos_add_test()` |

**鐵律**：C++23；**只能從 repo 根目錄 `cmake --preset default` 設定**，子專案不可單獨 configure；外部專案用 `find_package(aos CONFIG REQUIRED)` + `target_link_libraries(x PRIVATE aos::inst)` + `#include <aos/inst.hpp>`。vcpkg 在 `~/dev/vcpkg`。

---

## 常查的東西在哪

| 我想找… | 去哪 |
|---------|------|
| instruction 有哪些欄位、JSON 長什麼樣 | `subprojects/inst/include/aos/inst.hpp` 的 `inst_t`；schema 細節在 `subprojects/inst/src/format.cpp` 的 `known_key`／`encode`／`decode` |
| exit code、逾時、行程群組怎麼處理 | `subprojects/inst/src/exec.cpp` |
| PATH 怎麼解析、環境變數怎麼合併 | `subprojects/inst/src/spawn_prep.cpp` |
| C ABI 怎麼對應到 C++ API | `subprojects/inst/src/capi.cpp` 開頭的 `static_assert` 一串 |
| CLI 怎麼讀輸入、怎麼跑一批 instruction | `subprojects/inst/src/run.cpp` |
| 子命令怎麼被登記、怎麼被分派 | `cmake/AosSubproject.cmake` 的 `aos_add_subcommand()` → `app/CMakeLists.txt` 產表 → `app/src/main.cpp` |
| 某個相依該放在哪一層 | 上面 common/ 那節的判準；完整說明在 [`docs/subprojects.md`](../../../docs/subprojects.md) |
| 為什麼要先把整份輸入讀完才開始執行 | `subprojects/inst/docs/architecture.md`「為什麼要先把整份輸入讀完」|
| `fork` 前後各自能做什麼 | `subprojects/inst/docs/architecture.md`「`fork` 兩側各自要做的工作」；程式碼在 `subprojects/inst/src/exec.cpp` 的 `run_child` |
| 新增一個小專案（像 inst 那樣）要照什麼模子 | [`docs/subprojects.md`](../../../docs/subprojects.md)；函式定義在 `cmake/AosSubproject.cmake` |
