# code map — aos 程式碼結構導航圖

← [common/README](README.md)｜[INDEX](../../INDEX.md)｜維護規則見 [conventions](conventions.md)

**要改程式碼，先讀這張圖**：先找到你要動的領域，只讀那一格列出的檔案，不要順手翻無關的目錄。
這張圖與程式碼衝突時**以程式碼為準**，發現不對就當場修這張圖。

---

## 一分鐘看懂這個專案

```
shell → aos（CLI，src/cli/main.cpp）
          │   收 argv + 目前工作目錄，其他什麼都不解析
          ▼
        Unix Domain Socket（路徑由 AOS_SOCKET / XDG_RUNTIME_DIR / /tmp 決定）
          │   訊框 = 4 bytes 大端長度 + 1 byte 種類 + payload
          ▼
        aos-daemon（src/daemon/main.cpp）
          │   每條連線 co_spawn 一個 serve()
          ▼
        命令樹（src/core/commands/registry.cpp 那兩張表）
```

三個一直會用到的概念：

1. **三件套**：一個命令看得到的世界只有三樣東西——**三條標準串流**（`context.session`）、**argv**（`context.operands()`）、**exit status**（函式回傳值）。要多給命令什麼，加欄位到 `CommandContext` 就好，不必改每個命令的簽名。
2. **stdin／stdout 是串流的**：CLI 同時跑兩條 coroutine（一條灌 stdin、一條印輸出），所以 **stdin 還沒 EOF 就看得到輸出**；daemon 端是**用拉的**（命令呼叫 `read_input()` 才去拿下一塊），不先收完再執行，所以 **stdin 沒有總量上限**，只有單一訊框 8 MiB 的限制。
3. **命令是一棵樹**：命令可以有子命令（例如 `aos daemon status`）。分組節點只有 `children`、沒有 `run`。

---

## include/aos/ — 公開標頭

`aos_core` 的 PUBLIC include 目錄。CLI、daemon、測試都只從這裡拿東西。

| 檔案 | 負責 | 關鍵型別／函式 |
|------|------|----------------|
| `protocol.hpp` | **線上格式**：訊框常數、種類、控制訊息的編解碼宣告 | `frame_header_size`(5)、`maximum_payload_size`(8 MiB)、`stream_chunk_size`(64 KiB)、`ProtocolError`、`Request`、`FrameKind`、`Frame`、`encode/decode_request_start`、`encode/decode_exit`、`is_known_frame_kind` |
| `channel.hpp` | **訊框層 IO**：在 socket 上讀一個／寫一個／寫一串訊框 | `LocalSocket`（＝`asio::local::stream_protocol::socket`）、`read_frame`、`write_frame`、`write_stream` |
| `session.hpp` | **命令對外的唯一管道**（三條串流的抽象介面，虛擬函式，測試可以塞假的） | `Session`（`read_input`／`write_output`／`write_error`）、`say()`／`complain()` |
| `command.hpp` | **命令樹的型別與入口** | `CommandContext`（三件套都在這）、`CommandHandler`、`Command`、`commands()`、`Resolution`、`resolve_command`、`handle_command`、`render_command_list` |
| `runtime.hpp` | **跨呼叫存活的 daemon 狀態**（header-only class） | `Runtime`：`executor()`、`uptime()`、`served_requests()`／`count_request()`、`set_stop_handler()`／`request_stop()` |
| `client.hpp` | CLI 側的唯一進入點 | `run_client(request, socket_path) -> int` |
| `daemon.hpp` | daemon 側的唯一進入點 | `run_daemon(socket_path) -> int` |
| `socket_path.hpp` | socket 路徑怎麼決定 | `socket_path_from_environment()` |
| `blocking.hpp` | **協程 ↔ 執行緒的通用接縫**（header-only template）：把會擋住的同步程式碼搬到 worker thread 跑，`co_await` 等它 | `run_blocking(fn)` |

### include/aos/llm/ — 語言模型呼叫

| 檔案 | 負責 | 關鍵型別／函式 |
|------|------|----------------|
| `message.hpp` | 純資料：對話裡的一則訊息、一次工具呼叫、一次工具結果 | `Message`、`ToolCall`（`arguments` 保持成**原始 JSON 文字**，不先剖析）、`ToolResult` |
| `params.hpp` | 生成參數。**只送有設定的欄位** | `Params`（含 `extra`：直接併進 body 最上層的一段 JSON） |
| `caps.hpp` | 端點加模型做得到什麼。**三態**：true／false／nullopt（不知道） | `Caps`、`Caps::get()`（名字打錯回錯誤，不裝作不知道）、`Caps::overlay()`、`Caps::names()` |
| `reply.hpp` | 一步的結果，串流與否都是它 | `Reply`（`text`／`calls`／`reasoning`／`finish_reason`／`usage`／`err`、`spoke()`）、`Usage`、`PartKind`、`PartHandler` |
| `tool.hpp` | 工具的兩半：給模型看的 schema，和真的做事的那一端 | `ToolSchema`、`ToolFunction`、`ToolSet`、`merge_tools()`、`ToolBuilder`（手寫 schema 的建構器） |
| `wire.hpp` | **線路格式，全是純函式**：組 request、拆 response。不碰網路，所以測得起來 | `build_payload()`、`parse_completion()`、`StreamAccumulator`、`normalize_base_url()`／`root_url()`、`image_data_url()`、`parse_model_info()` |
| `engine.hpp` | `Llm`：端點、模型、旋鈕、能力。金鑰**只從環境變數讀**且不會被印出去 | `LlmConfig`、`Llm::ask()`／`caps()`／`models()`／`check()` |
| `bot.hpp` | `Bot`：人格＋記憶＋能力＋一顆 `Llm`（整顆拿著，不是共用） | `Bot::ask(Turn)`、`history()`、`pending_calls()`、`reset()` |
| `agentloop.hpp` | 「說話 → 叫工具 → 餵回去 → 再說話」自動跑完 | `run_agent(bot, instruction, options)`、`AgentOptions`（`max_steps`／`on_part`／`approve`／`on_tool`）、`AgentOutcome` |

**LLM 這一層的三條鐵律**：① `ask()` 永遠回一個 `Reply`，**不丟例外**——串流的錯誤發生在「開始收」之後，早就出了呼叫端的 try 範圍。② 工具的回傳值**錯誤也是字串**，因為它會直接變成送回模型的 tool message。③ `Caps` 的「不知道」一律**放行**，只有明確的 false 才擋。

### include/aos/tooljson/ — 工具即設定檔

| 檔案 | 負責 | 關鍵型別／函式 |
|------|------|----------------|
| `spec.hpp` | spec 的外殼、`_type` 註冊表、載入 | `Spec`、`Body`（`run(spec, args)`）、`Property`、`register_type()`、`load()`／`load_all()`、`load_tools()`（→ 可直接給 `Bot` 的 `ToolSet`） |
| `exec.hpp` | 內建的 `_type: "exec"`：跑一個執行檔 | `plan_exec()`（純函式：模型給的 JSON → argv + stdin）、`decode_output()`、`clip_output()`、`set_approver()` |

`Body::run()` **每次都把 `Spec` 當參數收**，body 裡不存一個指回去的指標——`Spec` 讀好之後會被搬進 `shared_ptr`（見 `load_tools`），存起來的指標會指到搬走後的殼上，而且只在搬家之後才發作。

**兩種錯誤要分清楚**：`ProtocolError` ＝ 對方講的話不合協定，**還能回覆對方**；`std::system_error` ＝ 連線本身壞了，回不了了，往上拋讓收尾函式處理。

## src/core/ — 共用實作（靜態函式庫 `aos_core`）

CMake 用 `GLOB_RECURSE` 掃 `src/core/*.cpp`，**新增 `.cpp` 不用手動登記到建置**。
`src/core/` 是 PRIVATE include 目錄，所以底下那些 `*.hpp`（`commands.hpp`、`connection.hpp`、`socket_setup.hpp`、`input.hpp`）是**內部標頭**，外面看不到。

### 頂層三個檔

| 檔案 | 負責 |
|------|------|
| `protocol.cpp` | 用 nlohmann/json 編解碼兩種控制訊息（`request_start`／`exit`）。協定版本寫死 `protocol_version = 1`，版本不合就拒絕。`is_known_frame_kind` 的 switch 也在這 |
| `channel.cpp` | 訊框的實際讀寫。`encode_header`／`decode_header` 處理 4 bytes 大端長度 + 1 byte 種類；`write_stream` 把超過 `stream_chunk_size` 的資料自動切塊 |
| `session.cpp` | 只有 `say()` 與 `complain()` 兩個小函式——參數 by value 搬進 coroutine frame，避免 `string_view` 指向已死的暫時字串 |

### src/core/commands/ — 命令樹

| 檔案 | 負責 |
|------|------|
| `commands.hpp` | **內部標頭**：每個內建命令的函式宣告（`aos::builtin` namespace），開頭的註解就是「新增命令的三步驟」 |
| `registry.cpp` | **這裡是命令表**。`commands()` 是根表、`daemon_children()` 是 `daemon` 的子表；另外還有 `resolve_command`（沿樹往下比對）、`CommandContext::path()`／`operands()`、`render_command_list`（help 與分組提示共用的渲染）、`handle_command`（所有命令的唯一入口） |
| `ping.cpp` | `aos ping` → 回 `pong` |
| `echo.cpp` | `aos echo` → stdin 原樣送回 stdout。**這是驗證串流真的有效的最小命令**（邊讀邊寫，任何時刻只有一塊在記憶體裡）|
| `help.cpp` | `aos help` → 列出所有命令（走 stdout，因為是「使用者明確要求」的正常輸出）|
| `daemon.cpp` | `aos daemon status`（uptime／服務次數）與 `aos daemon stop`（請 daemon 收工）|
| `describe.cpp` | **後備**：命令名認不得時，把收到的 argv、工作目錄、stdin 位元組數原樣印出來除錯 |
| `llm.cpp` | `aos llm ask`／`models`／`tools`。設定全走環境變數（`AOS_LLM_URL`／`AOS_LLM_MODEL`／`AOS_LLM_TOOLS`；金鑰由 `Llm` 自己讀），因為金鑰不該進 shell history。`ask` 把 argv 與 stdin 接起來當提示，**思考走 stderr、答案走 stdout**，所以 `aos llm ask ... > out.txt` 拿到的是答案 |

**新增一個命令**：① `src/core/commands/` 加一個 `.cpp`，寫 `asio::awaitable<std::int32_t> f(CommandContext&)`；② `commands.hpp` 加一行宣告；③ `registry.cpp` 的表加一列。子命令就是多開一張子表、掛到分組節點的 `children`。

**exit code 的約定**：正常 `0`；沒給命令、或只打到分組節點沒再往下 → `2`（並把命令清單寫到 **stderr**）；協定錯誤 → `2`。

### src/core/daemon/ — 常駐端

| 檔案 | 負責 |
|------|------|
| `run.cpp` | `run_daemon()`：準備 socket → `bind` → `chmod 0600`（只有自己連得進來）→ `listen` → 建 `Runtime` → 掛 SIGINT／SIGTERM → `accept_connections` 迴圈，每條連線 `co_spawn` 一個 `serve()`。**收工＝停止接受新連線**（`acceptor.close()`），跑到一半的連線會做完，`io_context` 沒事做 `run()` 自然返回 |
| `connection.hpp`／`connection.cpp` | 一條連線的生命週期。`ConnectionSession` 把 socket 包成命令看得懂的 `Session`（stdin 訊框 → `read_input()` 的回傳值；命令寫的東西 → 立刻變 stdout／stderr 訊框）。`serve()` = 讀 `request_start` → `handle_command` → `drain_input()` → 回 `exit` 訊框。`report_session_error()` 收尾，client 中途離線（EOF／EPIPE／aborted）視為正常、不吵 |
| `socket_setup.hpp`／`socket_setup.cpp` | socket **檔**的準備與清理。`prepare_socket_path()`：路徑沒東西就直接用；有殘留的死 socket 就 `unlink`；**連得上代表另一個 daemon 還活著 → 丟例外**。`SocketPathGuard` 在解構時 `unlink`，避免留下殘檔 |

`drain_input()` 那步別拿掉：命令沒讀完的 stdin 要吃掉，否則 client 還在灌資料就收到 `exit`，會拿到 EPIPE 而不是乾淨結束。

### src/core/client/ — CLI 端

| 檔案 | 負責 |
|------|------|
| `run.cpp` | `run_client()`：連 socket → `run_session()` 送出 `request_start` → **`co_spawn` 一條 coroutine 灌 stdin**，同時自己跑 `receive_output()` 收輸出。少了這個併行，stdin 沒 EOF 之前一個字都印不出來。`write_raw()` 每次寫完立刻 `fflush`，否則輸出會卡在 libc 緩衝區 |
| `input.hpp`／`input.cpp` | `forward_standard_input()`：stdin 是終端就不等 EOF，直接送 `stdin_end`；否則**分兩條路**——`can_be_polled()` 為真（pipe／terminal／socket）走 asio 的 `stream_descriptor`（要先 `dup` 一份，因為它會關掉自己拿到的 fd），一般檔案與目錄 epoll 收不了，走同步 `::read`（中間的 `co_await write_frame` 仍會讓出執行權，所以大檔案不會餓死收輸出的那條）|

### src/core/llm/ — 語言模型呼叫的實作

| 檔案 | 負責 |
|------|------|
| `http.hpp`／`http.cpp` | **內部標頭**。libcurl 包成 awaitable，是整個專案唯一一處協程 ↔ 執行緒接縫。`curl_easy_perform()` 在 `std::jthread` 上跑，用 asio 的 **`concurrent_channel`**（跨執行緒安全的那一種）把結果送回協程：worker 端 `try_send`（不阻塞、可在非 asio 執行緒呼叫），協程端 `async_receive`。串流的 channel 容量 64，滿了 worker 就等——那就是背壓。**不用 curl multi interface**：要自己接管 socket 註冊與時鐘，程式碼多好幾倍且難查，而 HTTP 呼叫本來就低頻 |
| `wire_build.cpp` | 組 request body。`model`／`messages`／`stream` 這三個**最後才寫**，確保蓋得過 `params.extra`。另有 base64 圖片編碼與 URL 整理 |
| `wire_parse.cpp` | 拆 response。`parse_completion()` 是非串流；`StreamAccumulator` 是串流——它存在的唯一理由是**一段 TCP 資料常常切在半行中間**，要記得上次剩下什麼。工具呼叫的碎片依 `index` 拼回去 |
| `caps.cpp` | 能力名稱與欄位的對照只寫在一張 `entries` 表裡，`names()` 與 `get()` 都從它長出來 |
| `engine.cpp` | `Llm` 的實作。金鑰在建構時解析完就把 `config_.key` 清掉 |
| `bot.cpp` | `Bot::ask()`。開頭記 `checkpoint`，**整輪落空就把這輪送出去的訊息收回來**——不然下次會帶著一個沒被回答的問題再問一次 |
| `agentloop.cpp` | 自動跑工具的迴圈。模型要的**每一個**工具都得回一則 tool message（放行被拒、工具不存在也要回，只是內容不同），少一個下次送出會被打回票。工具是同步的，所以透過 `run_blocking()` 丟到別的執行緒 |

### src/core/tooljson/ — 工具即設定檔的實作

| 檔案 | 負責 |
|------|------|
| `spec.cpp` | 外殼：讀檔、檢查兩個保留鍵、其餘交給 `_type` 的解析器。`SpecAccess` 是只給這個檔用的側門（讀好的 `Spec` 對外唯讀）。註冊表在 `parsers()` 裡建，`"exec"` 直接放進去——**不用「靜態物件自己去登記」那招**，static library 有可能整個 TU 被丟掉，症狀是只在 release 建置才發作 |
| `exec_body.hpp` | **內部標頭**：`make_exec_body()`，讓 `spec.cpp` 對 `exec.cpp` 產生明確的連結相依 |
| `exec.cpp` | 三件事分得很開：**解析**（`make_exec_body`，載入時一次）、**展開**（`plan_exec`，純函式）、**執行**（`capture_process`，fork + execvp）。不經過 shell，所以模型給的 `$(...)` 只是字元。`stderr.mode: merge` 是**真的 dup2 到同一條管子**，時序才對。同時 poll 讀 stdout 與寫 stdin，只做一邊會在管線塞滿時互相等死 |

## src/cli/ 與 src/daemon/ — 兩個入口

| 檔案 | 產出 | 做什麼 |
|------|------|--------|
| `src/cli/main.cpp` | `bin/aos` | 把 `argv` 包成 span 再切掉程式名稱（`argc` 可能是 0，不要直接算 `argc - 1`）→ 取工作目錄 → 組 `Request` → `run_client()` |
| `src/daemon/main.cpp` | `bin/aos-daemon` | 取 socket 路徑 → `run_daemon()`。就這樣 |

兩個 `main` 都只做「組裝 + 把例外轉成一行錯誤訊息 + 回傳 1」，沒有任何命令語意。

## tests/ — 測試

跑法與分類見 [testing 工作流](../testing.md)。

| 檔案 | ctest 名稱 | 涵蓋 |
|------|-----------|------|
| `protocol_test.cpp` | `protocol` | 純函式：JSON round trip（含空字串、引號、非 ASCII 參數）、各種壞輸入、`exit` 編解碼、`is_known_frame_kind` |
| `streaming_test.cpp` | `streaming` | `RecordingSession`（假的 `Session`，把讀寫事件依序記下來）驗證 `echo` 真的是**讀一塊寫一塊**；`ping` 完全不碰 stdin；沒給參數時走 stderr 並回 2；訊框在真 socket 上往返（含 NUL、空 payload）；`write_stream` 自動切塊 |
| `e2e.sh` | `end_to_end` | 真的起 daemon、用真的 CLI 打它：ping、exit code、pipe／檔案重導向兩條 stdin 路徑、含 NUL 的二進位、**20 MiB 串流**（遠超單一訊框上限）、daemon 狀態跨呼叫累積、`ping` 忽略大量 stdin 不卡死、分組節點列子命令 |
| `check.hpp` | — | 測試用的 `AOS_CHECK`。**故意不用 `assert`**：`assert` 在 `NDEBUG` 下會整個消失，Release 建置的測試會變成空跑還回報通過 |
| `llm_test.cpp` | `llm` | **完全離線**：只送有設定的旋鈕、`extra` 蓋不掉那三個受管欄位、tool call 往返成 payload、usage 缺欄位是 nullopt 不是 0、端點錯誤變成 `reply.err`、**SSE 切在半行中間**、思考與答案分開、工具碎片重組、`Caps` 打錯字是錯誤、`ToolBuilder` 的逃脫、`merge_tools` 拒收沒人接的 schema |
| `tooljson_test.cpp` | `tooljson` | 載入期驗證（缺 `_extra`、版本不認得、綁到不存在的參數、同檔撞名）、argv 展開（三種綁定、position 排序、字串數字轉型、缺／多參數、壞 JSON 原文回傳、limits、stdin 參數不上命令列）、輸出裁切；最後幾項**真的 fork 一次** `/bin/cat`、`echo`、`false`（證明 stdin 管線不會互相等死、`$(...)` 不被 shell 解析、`ok_exit` 的行為），不連網路 |

## 建置設定

| 檔案 | 重點 |
|------|------|
| `CMakeLists.txt` | CMake 3.25+、C++23（`CXX_EXTENSIONS OFF`）。三個 target：`aos_warnings`（INTERFACE，統一警告選項）、`aos_core`（STATIC，來源是 `src/core/*.cpp` 的 glob）、`aos_cli` → `bin/aos`、`aos_daemon` → `bin/aos-daemon`。`find_package`：`Threads`、`asio`、`nlohmann_json`、`CURL` |
| `CMakePresets.json` | 只有一個 `dev` preset：Ninja、Debug、`binaryDir=build/`、toolchain 取 `$env{VCPKG_ROOT}` |
| `vcpkg.json` | manifest：`asio`、`nlohmann-json`、`curl[ssl]`，版本由 `builtin-baseline` 固定 |

---

## 施工中的區域（**不要碰**）

| 區域 | 狀態 |
|------|------|
| `docs/` | **只寫到一半就停了**（程式碼導覽 `01`–`05` 與 `docs/cpp/`）。內容沒錯，但不完整，而且**還沒涵蓋 LLM／tooljson 那兩層**。要續寫可以，但別把它當成完整的說明 |

## 常查的東西在哪

| 我想找… | 去哪 |
|---------|------|
| 訊框長什麼樣、有哪幾種 | `include/aos/protocol.hpp` |
| 8 MiB／64 KiB 這些數字 | `include/aos/protocol.hpp` 的三個 `inline constexpr` |
| 命令有哪些、怎麼加一個 | `src/core/commands/registry.cpp` + `commands.hpp` 開頭註解 |
| 命令怎麼拿 stdin／寫 stdout | `include/aos/session.hpp` + `include/aos/command.hpp` |
| 跨呼叫要存的狀態放哪 | `include/aos/runtime.hpp` 的 `Runtime` |
| socket 路徑怎麼決定 | `src/core/socket_path.cpp`（`AOS_SOCKET` → `$XDG_RUNTIME_DIR/aos.sock` → `/tmp/aos-<uid>.sock`）|
| daemon 怎麼收工 | `src/core/daemon/run.cpp` 的 `stop_accepting` + `include/aos/runtime.hpp` 的 `request_stop()` |
| 為什麼 stdin 走兩條不同路徑 | `src/core/client/input.cpp` 的 `can_be_polled()` |
| 怎麼在協程裡跑會擋住的事 | `include/aos/blocking.hpp` 的 `run_blocking()` |
| libcurl 為什麼不卡住 daemon | `src/core/llm/http.hpp` 開頭那段圖 |
| 送出去的 JSON 長什麼樣 | `src/core/llm/wire_build.cpp` 的 `build_payload()` |
| 串流怎麼拼回完整的一句話 | `src/core/llm/wire_parse.cpp` 的 `StreamAccumulator` |
| 工具的 .json 怎麼寫 | `include/aos/tooljson/exec.hpp` 開頭那段範例 |
| 模型給的參數怎麼變成 argv | `src/core/tooljson/exec.cpp` 的 `plan_exec()` |
