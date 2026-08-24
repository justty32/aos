# code map — aos 程式碼結構導航圖

← [common/README](README.md)｜[INDEX](../../INDEX.md)｜維護規則見 [conventions](conventions.md)

**要改程式碼，先讀這張圖**：先找到你要動的領域，只讀那一格列出的檔案，不要順手翻無關的目錄。
這張圖與程式碼衝突時**以程式碼為準**，發現不對就當場修這張圖。

---

## 一分鐘看懂這個專案

`aos` 是一個 **monorepo**：只有一個執行檔 `aos`，靠子命令把陸續長出來的各個「小專案」掛上去（例如 `aos inst jobs.json`）。第一個小專案是 `core/inst/`——一支讀 JSON instruction、`fork`/`exec` 跑起來的 POSIX 指令執行器。

```
repo 根
  aos::common（common/，header-only，目前只有 <aos/export.h>）
       ▲ 每個小專案都連它
  aos::inst（core/inst/，核心小專案 → libaos_inst.so）
       │  C++ 分層，相依單向：inst ← format ← exec
       │    inst    inst_t 資料結構、狀態列舉             （src/inst.cpp）
       │    format  唯一懂 JSON schema 的層                （src/format.cpp）
       │    exec    唯一碰 fork/exec/waitpid 的層          （src/exec.cpp + spawn_prep.cpp + wait.cpp）
       │  外加兩層，各自只往下看：
       │    C ABI 包裝（src/capi*.cpp，對外標頭 <aos/inst.h>）
       │    CLI 執行迴圈（src/run.cpp，進入點 aos_inst_cli_main）
       ▼
app/（唯一執行檔 aos，子命令分派）── `aos inst jobs.json` 掛的就是上面這條

  aos::tooljson（core/tooljson/，核心小專案 → libaos_tooljson.so）
       │  spec／registry：驗證 tool spec 與開放的 _type 登記
       │  exec_type／args：只解析 exec 配方並展開 argv，不啟動行程
       ▼
app/ ── `aos tooljson list|check spec.json` 掛的就是這條

  aos::llms（core/llms/，核心小專案 → libaos_llms.so）
       │  LLM：端點、模型、Params、能力三態與可抽換 HTTP transport
       │  Bot／Reply：system、history、tools 與非串流 ask 的交易式收尾
       ▼
app/ ── `aos llms ask|models` 掛的就是這條（成功路徑會連網）
```

三個一直會用到的概念：

1. **單向相依是鐵律**：`inst ← format ← exec`——`format` 可以用 `inst` 的型別，`exec` 可以用 `inst` 的型別，但 `format` 與 `exec` 互相不知道對方存在，`inst` 什麼都不知道。三組宣告目前併在同一個標頭 `include/aos/inst.hpp` 裡，**併在一起不代表可以互相引用**，標頭開頭那段註解就是講這件事。
2. **一個執行檔、多個子命令**：不會有第二個 `main`。新的小專案（未來的 `llm/`、`tooljson/`……）靠自己的 CMakeLists 呼叫 `aos_add_subcommand()` 把子命令掛進 `app/` 的分派表，不用改 `app/` 本身。
3. **每個小專案是一顆獨立的 shared lib**：`aos::inst` → `libaos_inst.so`。傘狀 target 有 `aos::core`（核心）、`aos::modules`（擴充，有擴充存在時才建）、`aos::aos`（全部）；`AOS_BUILD_MERGED_LIB` 開了才會多產出一顆合併的 `libaos.so`（`aos::merged`）。
4. **小專案分兩類，靠所在目錄決定**：`core/` 是 aos 的基本組成（一定會建），`modules/` 是可選的擴充（`-DAOS_BUILD_MODULES=OFF` 整批不建）。建置方式完全一樣，`core/CMakeLists.txt` 與 `modules/CMakeLists.txt` 各自 `set` 了 `AOS_SUBPROJECT_CATEGORY`，`aos_add_subproject()` 讀它來分類。判準：拿掉它 aos 就不再是 aos → core。

> **2026-08-24：`core/inst` 的凍結已由使用者解除。** `inst.cpp`／`format.cpp`／`exec.cpp`／`spawn_prep.*`／`wait.*`／`capi*.cpp` 現在可以改。解凍是為了兩件已拍板的事：每筆 instruction 的 non-blocking 欄位，以及 JSON 的 `$ref`／`$env`／`$opt` 指示詞（設計見 [`docs/inst-directives.md`](../../../docs/inst-directives.md)、順序見 [`docs/roadmap.md`](../../../docs/roadmap.md) 的 T0）。解凍**不等於可以隨手改**——單向相依 `inst ← format ← exec` 仍然是鐵律，`format` 與 `exec` 依舊互不相識。

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

## core/inst/ — 第一個小專案：POSIX 指令執行器

讀一筆或一批 JSON instruction，準備好環境／重導向後 `fork`＋`execve` 跑起來，等它結束、寫回 exit status。對外是 `aos::inst`（`libaos_inst.so`）＋ `aos inst` 子命令。

### core/inst/include/aos/ — 對外公開標頭

| 檔案 | 負責 | 關鍵型別／函式 |
|------|------|----------------|
| `inst.hpp` | C++ API。三個分層的宣告都在這（見上面「單向相依是鐵律」），標頭上半是 `inst`／`format`，下半是 `exec` | `inst_t`（`argv`／`stdin_path`／`stdout_path`／`stderr_path`／`stderr_merge`／`exit_path`／`cwd`／`env`／`timeout_ms`、`clear()`）、`InstState`、`to_string(InstState)`、`read_one`／`read_all`／`write_one`／`write_all`、`ExecState`、`ExecResult`、`execute()`、`to_string(ExecState)` |
| `inst.h` | C ABI（給非 C++ 呼叫者用），是 `inst.hpp` 的鏡像，型別靠 `static_assert` 對齊（見 `src/capi.cpp`） | `aos_instruction`（opaque）、`aos_exec_result`、`aos_inst_state`／`aos_inst_field`／`aos_exec_state`、`aos_instruction_new/free/clear`、`aos_instruction_argc/arg/push_arg`、`aos_instruction_field/set_field`、`aos_instruction_stderr_merge/set_stderr_merge`、`aos_instruction_env_count/env_key/env_value/set_env`、`aos_instruction_timeout_ms/set_timeout_ms`、`aos_instruction_read_buffer/read_fd/read_file`、`aos_instruction_write_buffer/write_fd/write_file`、`aos_instruction_execute`、`aos_*_state_string`、`aos_version_string` |

### core/inst/src/ — 三個核心分層

| 檔案 | 負責 |
|------|------|
| `inst.cpp` | **inst 層**：`inst_t::clear()`、`to_string(InstState)`。不碰位元組／JSON，也不碰行程 |
| `format.cpp` | **format 層**：唯一懂 JSON schema 的檔。已知欄位共 8 個（`argv`／`stdin`／`stdout`／`stderr`／`exit`／`cwd`／`env`／`timeout_ms`），其中 `stderr` 接受路徑字串或 `{"$opt":"merge"}`；碰到不認得的 key 就回 `UnknownKey`。`read_one`／`read_all` 剖析＋驗證（`argv` 不可空、`env` key 不可空或含 `=`）；`write_one`／`write_all` 編回精簡 JSON（每筆一行）。用 `nlohmann::json`／`nlohmann::ordered_json`。只 catch `json::parse_error`——配置失敗的例外會往上拋 |
| `exec.cpp` | **exec 層**：唯一碰 `fork`／`execve`／`waitpid` 的檔。`execute()`：組 `argv`＋`envp`（透過 `spawn_prep`）→ `fork` → 子行程 `setpgid`＋重導向（stderr merge 時在 stdout 設好後 `dup2(1, 2)`）＋`chdir`＋`execve`（`run_child`，全程 async-signal-safe）→ 父行程視 `timeout_ms` 決定直接 `wait_retry` 或 `wait_until` 輪詢；逾時先對整個行程群組送 `SIGTERM`、給 `kTimeoutGraceMs`（2000ms）緩衝，仍不收就 `SIGKILL` 整個群組——打群組是因為忽略 `SIGTERM` 的孫行程才殺得掉。結束後若 `exit_path` 非空就把 exit code 寫進那個檔 |
| `spawn_prep.hpp`／`.cpp` | **內部標頭**（不對外）。`prepare_spawn()`：在 `fork` 之前把所有會配置記憶體的準備工作做完——合併繼承的環境變數與 `inst.env`（後者覆蓋前者）、組 `envp`、若 `argv[0]` 沒有 `/` 就沿 `PATH`（或 `confstr(_CS_PATH)` 的預設值）逐段找可執行檔。子行程只拿到已經算好的穩定指標 |
| `wait.hpp`／`.cpp` | **內部標頭**。`wait_retry()`：EINTR-safe 的 `waitpid` 包裝。`wait_until()`：用 `CLOCK_MONOTONIC` 算經過時間，指數退避（上限 `kMaxPollMs`＝50ms）輪詢 `waitpid(WNOHANG)` 直到逾時 |

**改 exec 的行為要小心兩件事**：① `fork` 之後、`execve` 之前只能呼叫 async-signal-safe 的操作（細節與理由見 `core/inst/docs/architecture.md`「`fork` 兩側各自要做的工作」）；② 逾時後的 `SIGKILL` 一定要打整個行程群組（`-pid`），不是單一 `pid`。

**這一層有幾處刻意的設計，不要「修」**：PATH 撞到同名目錄時回 exit 126 而不是 127；三處 `kill(-pid, ...)` 的回傳值刻意忽略；`wait_until()` 出錯時直接 return、不 kill 不 reap。外部審查工具會反覆把它們當成 bug 提出來。

### core/inst/src/ — C ABI 包裝層（只往下看 inst/format/exec，不影響它們）

| 檔案 | 負責 |
|------|------|
| `capi_common.hpp` | **內部標頭**：`aos_instruction` 的實際定義（`struct aos_instruction { aos::inst_t value; }`），只有這幾個 `capi_*.cpp` 看得到 |
| `capi.cpp` | 版本字串、狀態轉字串（`aos_inst_state_string`／`aos_exec_state_string`）。開頭一串 `static_assert` 讓 C 的列舉值與 C++ 的 `InstState`／`ExecState` 對齊——**新增或改一個列舉值，兩邊都要動，這裡的 static_assert 會在改漏時讓建置失敗** |
| `capi_instruction.cpp` | 操作單個 `aos_instruction` 的存取子：建立／釋放／清空、`argv` 讀寫、四個路徑欄位＋`cwd`、`env` 的讀寫、`timeout_ms` |
| `capi_io.cpp` | 讀寫整份 instruction：`read_buffer/fd/file`、`write_buffer/fd/file`（呼叫 `format` 層），以及 `aos_instruction_execute`（呼叫 `exec` 層） |

**每個 `extern "C"` 進入點都有 `catch (...)`**，把例外接成 `AOS_INST_ALLOC_FAILED` 之類的錯誤碼——例外絕對不能逸出 C 邊界。新增進入點時照抄這個形狀。

**C ABI 的 ABI 規則**：`inst.h` 裡的列舉值一經釋出就凍結，只能在尾端加新值，不能重排或刪除既有值——這條規則寫在標頭裡的註解，改動前先看。

### core/inst/src/ — CLI 層

| 檔案 | 負責 |
|------|------|
| `run.hpp`／`run.cpp` | `run(argc, argv)`：決定輸入來源（給了檔名就開檔，否則讀 stdin）→ 讀到 EOF 進單一緩衝區 → `read_all()` 一次剖析＋驗證整批 → 依序對每筆呼叫 `execute()`，失敗的印到 stderr、繼續跑下一筆，只要有一筆失敗整體回 1。讀檔、剖析、執行三個階段都接 `bad_alloc`／`length_error`——**這一層是原生 CLI 唯一的例外邊界**（C ABI 那側自己有接）。檔尾的 `extern "C" aos_inst_cli_main()` 是 `aos inst` 子命令的進入點，名字要與 `core/inst/CMakeLists.txt` 的 `aos_add_subcommand(ENTRY ...)` 一致。**為什麼要先把整份輸入讀完**、以及這個設計的代價，見 [`core/inst/docs/architecture.md`](../../../core/inst/docs/architecture.md) |

**新增一個 instruction 欄位**：① `inst.hpp` 的 `inst_t` 加欄位；② `format.cpp` 的 `known_key`／`encode`／`decode` 三處都要加；③ 需要的話 `inst.h` 加對應 C ABI 存取子＋`capi_instruction.cpp` 實作；④ `exec.cpp`／`spawn_prep.cpp` 視欄位語意決定要不要用到。（凍結已於 2026-08-24 解除，但這種改動仍要先確認它屬於已拍板的範圍。）

## core/inst/tests/ — 測試

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

## core/tooljson/ — tool spec 外殼與參數展開

讀取格式版本 `0.1.0` 的 OpenAI tool JSON 加 `_extra`，在載入時驗證外殼與 exec
配方，並把模型給的參數純函式地展開成 argv／stdin。S1 完全不 fork、不 exec；
對外是 `aos::tooljson`（`libaos_tooljson.so`）與只提供 `list`／`check` 的
`aos tooljson` 子命令。

| 檔案 | 負責 |
|------|------|
| `include/aos/tooljson.hpp` | 不含 nlohmann 的公開 C++ API：`Spec` pimpl、`SpecState`、字串 JSON 的 load/save、開放 registry、`ExpandedArgs` 與文字收尾函式；所有公開函式與 out-of-line 成員都標 `AOS_API` |
| `src/tooljson_internal.hpp` | 只供本小專案使用的 nlohmann 邊界、`Spec::Impl`、exec binding/body 與內部存取器 |
| `src/spec.cpp` | 讀寫 JSON、驗證兩個保留鍵與 function schema、單檔撞名、跨檔先到先贏、剝除 `_extra`，並以 JSON 檔所在資料夾建立相對路徑中心 |
| `src/registry.cpp` | 執行環境的 `_type` → parser 開放登記表；同名覆蓋、排序列出目前型別 |
| `src/exec_type.cpp` | 內建 `exec` parser；經同一 registry 登記，載入期驗證 exec／argv／stdio／runtime／limits 並解析路徑；S1 的 `run()` 只回尚未實作字串 |
| `src/args.cpp` | 模型 args JSON → argv + stdin 的純函式；排序、coerce、flag/repeat、未知／缺少參數、limits 與單項 128KB 上限 |
| `src/text.cpp` | 輸出 UTF-8 解碼、NUL 二進位偵測，以及按 Unicode 字元計數的 head／tail 裁切 |
| `src/fingerprint.cpp` | 不依賴外部雜湊函式庫的串流 SHA-256；供 `Spec::stale()` 比對 `_extra.source.sha256`，讀不到時回「不知道」 |
| `src/run.hpp`／`src/run.cpp` | CLI 層與 `aos_tooljson_cli_main`；只透過公開 API 實作 `aos tooljson list`／`check`，是 CLI 的配置失敗例外邊界 |
| `CMakeLists.txt` | 建 `aos::tooljson`、CLI OBJECT library、登記 `tooljson` 子命令與 `aos_tooljson_tests` |

### core/tooljson/tests/ — 測試

| 檔案 | 涵蓋 |
|------|------|
| `test_support.hpp` | 建立 exec spec、暫存檔與目錄的共用測試工具 |
| `test_spec.cpp` | object／array、版本、同檔與跨檔撞名、schema 剝除、以 spec 位置解析路徑、save/load、source 指紋 stale 三態 |
| `test_validation.cpp` | function schema 與 exec 的 argv／stdio／runtime／limits 載入期壞檔案例 |
| `test_registry.cpp` | 未知與 python 型別訊息、第三方字串 JSON parser/body、內建 exec 同門登記 |
| `test_args.cpp` | position＋Unicode 排序、JSON 字面、flag/repeat/separate、coerce、null／缺席、stdin、未知參數與 byte limits |
| `test_text.cpp` | NUL 二進位、無效 UTF-8、head／tail 與 Unicode 字元裁切 |
| `test_run.cpp` | `list`／`check` 成功與失敗，以及 S1 不接受 `run` |

細節契約與 C++ registry 的 JSON 邊界見 `core/tooljson/docs/format.md`。

## core/llms/ — OpenAI 相容端點 client（非串流 + SSE 串流）

公開介面不含 nlohmann 或 curl 型別；JSON 以字串進出。`Bot::ask()` 除
`std::bad_alloc` 外永遠回 `Reply`，錯誤放在分類化的 `reply.err`。HTTP 由
完整回應的 `Transport` 與 callback 式 `StreamTransport` 都可抽換，ctest 全部使用假端點。

| 檔案 | 負責 |
|------|------|
| `include/aos/llms.hpp` | 全部公開 C++ API：`HttpRequest`／`Transport`／`StreamTransport`、`Params`、`Caps`／`LLM`、`ToolSet`、串流 sink 與 `Reply`／`Bot`、presets 與 content 純函式；每個公開函式與 out-of-line 成員都標 `AOS_API` |
| `src/llms_internal.hpp` | 唯一共用的內部 nlohmann 邊界與各 pimpl／測試不到的 access bridge；公開標頭不 include 它 |
| `src/content.cpp` | base／completion／root URL 正規化、API key fallback、本機圖片 MIME＋base64 data URL、圖片／文字 content parts |
| `src/params.cpp` | `Params` → request JSON；只送已設定欄位，再直接展開 `extra_json`；model／messages／stream 由 Bot 最後固定、不讓 extra 覆蓋 |
| `src/toolcalls.cpp` | raw call → 呼叫端 entry／API history；非法 arguments 保留 raw；串流碎片按 index 增量累積 |
| `src/toolset.cpp` | C++ 的 `(schemas_json, dispatch)` bundle 驗證與合併；名稱須完全配對且不可撞名，不做 Python callable 反射 |
| `src/transport.cpp` | 預設 libcurl 完整／串流 transport；curl 型別與 header 只停在本檔，串流以 `CURLOPT_WRITEFUNCTION` 即時推 2xx body，非 2xx body 留給錯誤訊息 |
| `src/sse.hpp`／`src/sse.cpp` | 內部增量 SSE parser；跨任意 transport callback 切割組 line／event，處理多個 `data:` 行與 `[DONE]` |
| `src/caps.cpp` | GET `<root>/model/info`，轉成七項 `optional<bool>`；失敗吞掉，以 `(root URL, key)` 快取且空表也快取 |
| `src/llm.cpp` | `LLM` 值與能力檢查；只有明確 `false` 擋請求，tool choice 沒 tools 直接回明確錯誤 |
| `src/reply.cpp` | 非串流整包吸收、同一 `Reply` 的結果投影與唯一 `finish()`；解構與 move assignment 都確定收尾，空且未完成的輪退回 checkpoint |
| `src/stream_reply.cpp` | 延遲啟動 push transport、逐 SSE event 防禦性拆 chunk、答案／思考 sink 分流、usage-only 尾片、tool-call accumulator 餵入與串流期錯誤收斂 |
| `src/bot.cpp` | 組 system＋history＋tool results＋user message、最後覆寫 model／messages／stream；非串流立即送出，串流建立延遲 Reply 並固定 include_usage，兩路都由 `Reply::finish()` 寫回或退回 history |
| `src/presets.cpp`／`src/presets_data.hpp.in`／`presets.json` | 嚴格驗證並載入內嵌 preset；每筆只准 endpoint／model／parameters／可省略 description，能力不放 preset |
| `src/run.hpp`／`src/run.cpp` | `aos llms ask`／`models` CLI 與 `aos_llms_cli_main`；成功路徑會連端點，配置失敗由 CLI 例外邊界收住 |
| `CMakeLists.txt` | 建 `aos::llms`、以 `PRIVATE_DEPS CURL::libcurl` 連 curl、內嵌 presets、登記 `llms` 子命令與離線測試 |
| `README.md` | 非串流／串流 API、push 資料流、Reply 收尾、與 Python 的解構差異、能力／toolset／presets 與 CLI 使用說明 |
| `proxy/` | 從 reference 原樣搬入的 LiteLLM yaml、Linux／PowerShell 啟動腳本與 README；不建置、不安裝 |

### core/llms/tests/ — 測試

| 檔案 | 涵蓋 |
|------|------|
| `test_support.hpp` | 假端點、HTTP 回應與暫存檔共用工具 |
| `test_content_params.cpp` | URL／root／key、本機與遠端圖片、image-only content、Params 只送設定值 |
| `test_toolcalls.cpp` | 交錯 index 碎片累積、非法 JSON arguments、tool-call history 與 null content |
| `test_toolset_presets.cpp` | schemas／dispatch 完整配對與撞名、內建 preset、缺鍵／多鍵拒絕 |
| `test_caps.cpp` | 能力 true／false／不知道、override、只擋明確 false、root＋key 快取、空表命中與清快取 |
| `test_reply_bot.cpp` | ask 全錯誤契約、checkpoint rollback、extra 保護欄位、image-only、text＋calls、pending calls、system／reset、usage 缺值與 finish 落空退回 |
| `test_stream.cpp` | 同份 SSE 的整包／不規則／逐 byte 切割等價、答案／思考分流、交錯 index tool-call 碎片、usage-only／防禦欄位、零位元組斷線、串流錯誤與解構／提前收尾；全用假 transport |
| `test_run.cpp` | S4 CLI 接受 `--stream`，以未知 preset 驗到執行期而不連網 |

## 文件在哪

`docs/`（repo 根）放**整體**文件：[總覽](../../../docs/overview.md)、[建置](../../../docs/build.md)、[使用](../../../docs/usage.md)、[新增小專案](../../../docs/subprojects.md)。改了建置骨架、子命令機制或相依管理，那邊要跟著更新。

`core/inst/docs/` 放 inst 專屬的細節，不是 code map 的一部分，但改東西之前有時值得先看：

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
| 根 `CMakeLists.txt` | 頂層：`option()`、vcpkg toolchain 解析（在 `project()` 之前）、`find_package(nlohmann_json/CURL/Catch2)`、`add_subdirectory(common/core/modules/app)`、三個傘狀 target、合併版、`install`／`export` |
| `core/CMakeLists.txt`／`modules/CMakeLists.txt` | 兩份小專案清單。新增小專案就是往其中一份加一行 `add_subdirectory()`；它們各自 `set(AOS_SUBPROJECT_CATEGORY ...)` 來決定分類 |
| `cmake/AosSubproject.cmake` | 三個共用函式：`aos_add_subproject()`（產出 OBJECT＋SHARED 兩個 target、把私有相依從匯出介面剝掉、檢查保留名稱與分類）、`aos_add_subcommand()`（登記子命令＋三道守衛）、`aos_add_test()` |
| `cmake/aos-config.cmake.in` | 讓外部專案 `find_package(aos CONFIG)`。`@AOS_FIND_DEPENDENCIES@` 由根 CMakeLists 從各小專案登記的 `PUBLIC_PACKAGES` 產生 |
| 根 `vcpkg.json` | manifest，有 `builtin-baseline`；測試相依（Catch2）放在 `"tests"` feature |
| `CMakePresets.json` | `default`／`release`／`merged`。vcpkg toolchain 由根 `CMakeLists.txt` 解析（`CMAKE_TOOLCHAIN_FILE` → `VCPKG_ROOT` → `~/dev/vcpkg`），本機不用設環境變數 |
| `common/CMakeLists.txt` | `aos::common` 與 `aos_common_private`（見上面 common/ 那節）|
| `core/inst/CMakeLists.txt` | 小專案的**參考範本**（核心類）：`aos_add_subproject()`（目前不需要任何 DEPS 參數）＋ CLI 的 OBJECT library ＋ `aos_add_subcommand()` ＋兩個 `aos_add_test()` |

**鐵律**：C++23；**只能從 repo 根目錄 `cmake --preset default` 設定**，子專案不可單獨 configure；外部專案用 `find_package(aos CONFIG REQUIRED)` + `target_link_libraries(x PRIVATE aos::inst)` + `#include <aos/inst.hpp>`。vcpkg 在 `~/dev/vcpkg`。

---

## 常查的東西在哪

| 我想找… | 去哪 |
|---------|------|
| instruction 有哪些欄位、JSON 長什麼樣 | `core/inst/include/aos/inst.hpp` 的 `inst_t`；schema 細節在 `core/inst/src/format.cpp` 的 `known_key`／`encode`／`decode` |
| exit code、逾時、行程群組怎麼處理 | `core/inst/src/exec.cpp` |
| PATH 怎麼解析、環境變數怎麼合併 | `core/inst/src/spawn_prep.cpp` |
| C ABI 怎麼對應到 C++ API | `core/inst/src/capi.cpp` 開頭的 `static_assert` 一串 |
| CLI 怎麼讀輸入、怎麼跑一批 instruction | `core/inst/src/run.cpp` |
| 子命令怎麼被登記、怎麼被分派 | `cmake/AosSubproject.cmake` 的 `aos_add_subcommand()` → `app/CMakeLists.txt` 產表 → `app/src/main.cpp` |
| 某個相依該放在哪一層 | 上面 common/ 那節的判準；完整說明在 [`docs/subprojects.md`](../../../docs/subprojects.md) |
| 為什麼要先把整份輸入讀完才開始執行 | `core/inst/docs/architecture.md`「為什麼要先把整份輸入讀完」|
| `fork` 前後各自能做什麼 | `core/inst/docs/architecture.md`「`fork` 兩側各自要做的工作」；程式碼在 `core/inst/src/exec.cpp` 的 `run_child` |
| 新增一個小專案（像 inst 那樣）要照什麼模子 | [`docs/subprojects.md`](../../../docs/subprojects.md)；函式定義在 `cmake/AosSubproject.cmake` |
