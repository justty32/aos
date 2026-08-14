# aos

`aos` 是薄型命令列入口；`aos-daemon` 是真正處理命令的常駐程式。
兩者以 Unix Domain Socket 通訊。

```text
Shell → aos（CLI）→ Unix Domain Socket → aos-daemon → 命令樹
```

CLI 不解析業務命令。以下呼叫會把三個參數逐項送給 daemon：

```bash
aos new "bot alpha" --verbose
```

傳送內容是 `new`、`bot alpha`、`--verbose`，不是重新拼接的 shell 字串，
所以空白、引號與空字串的參數邊界都能保留。

## stdin／stdout 是串流的

三條標準串流都是邊產生邊傳，兩邊都不會把整份資料留在記憶體裡：

- CLI 同時跑兩條 coroutine，一條把 stdin 灌進 socket，一條把輸出印出來。
  所以 **stdin 還沒結束就看得到輸出**，`tail -f log | aos echo` 會即時吐字。
- daemon 是用拉的方式讀 stdin（命令呼叫 `read_input()` 才去拿下一塊），
  不是先收完再執行。因此 **stdin 沒有總量上限**，只有單一訊框 8 MiB 的限制。

```bash
printf 'hello\n' | aos echo            # pipe
aos echo < big.bin > copy.bin          # 檔案重導向，20 MiB 也沒問題
tail -f server.log | aos echo          # 邊來邊出
```

## 命令是一棵樹

命令可以有子命令。只打分組名稱會列出它底下有什麼：

```bash
aos help              # 列出所有命令
aos ping              # → pong
aos daemon            # 列出 daemon 這一組的子命令
aos daemon status     # uptime 與服務過的請求數
aos daemon stop       # 做完手上的事之後收工
aos llm ask 你好      # 問語言模型（見下一節）
```

一個命令看得到的世界就是三件套：

| 三件套 | 在程式裡是什麼 |
|---|---|
| stdin／stdout／stderr | `context.session` 的 `read_input()`／`write_output()`／`write_error()` |
| argv | `context.operands()`（已經去掉命令名稱） |
| exit status | 函式的回傳值 |

### 新增一個命令

1. 在 `src/core/commands/` 加一個 `.cpp`，寫一個
   `asio::awaitable<std::int32_t> f(CommandContext&)` 形狀的函式。
2. 在 `src/core/commands/commands.hpp` 加一行宣告。
3. 在 `src/core/commands/registry.cpp` 的表裡加一列。

CMake 是用 glob 掃 `src/core/`，新檔案不必手動加進建置。
子命令就是在 `registry.cpp` 裡多開一張子表，掛到分組節點的 `children`。

## 呼叫語言模型

設定走環境變數，**金鑰不進命令列**（那會留在 shell history 裡）：

```bash
export AOS_LLM_URL=http://localhost:4000   # base url 或完整的 /chat/completions 都可以
export AOS_LLM_MODEL=deepseek-chat
export AOS_LLM_KEY=sk-...                  # 沒設就找 OPENAI_API_KEY

aos llm models                             # 端點上有哪些模型
aos llm ask 這段程式在做什麼                # 問一句話
cat error.log | aos llm ask 這是什麼錯      # argv 與 stdin 會接起來
```

輸出是**邊想邊印**的，而且分兩條路：**答案走 stdout，思考走 stderr**。
所以 `aos llm ask ... > answer.txt` 存到的是答案，思考仍然看得到。

### 程式裡怎麼用

```cpp
#include "aos/llm/bot.hpp"

llm::Bot bot{llm::Llm{{.model = "deepseek-chat"}}, "請簡短回答。"};
llm::Reply reply = co_await bot.ask({.prompt = "你好"});

if (!reply) {                       // 出錯時是 false
    co_await complain(session, *reply.err);
}
std::println("{}", reply.text);
```

`ask()` **永遠回一個 Reply，不丟例外** —— 串流的錯誤發生在「開始收」之後，
早就出了呼叫端的 try 範圍，硬用例外會讓錯誤有兩個住處。

分工是：`Llm` 是引擎（端點、模型、旋鈕），`Bot` 是人格加記憶加能力，
`run_agent()` 則是「說話 → 叫工具 → 餵結果回去 → 再說話」自動跑完。

### 工具可以只是一份 .json

不用重新編譯就能加一個工具：寫一份 spec，指到任何執行檔。

```bash
export AOS_LLM_TOOLS=$PWD/examples/tools/wordcount.json   # 用 : 隔開多個
aos llm tools                                            # 看載得到哪些
aos llm ask 幫我數一下 README 有幾個字
```

**不經過 shell**：argv 是一個陣列，直接 execvp，所以模型給的參數值裡有
`;` 或 `$(...)` 都只是字元。格式見 `include/aos/tooljson/exec.hpp` 開頭。

只是想在同一支程式裡用自己的 C++ 函式的話不需要這一套，
`aos/llm/tool.hpp` 的 `ToolBuilder` 就夠了。

### 一條會擋住的路怎麼不卡住 daemon

daemon 所有連線共用一條 io_context 執行緒，而 libcurl 是同步的。
所以 HTTP 呼叫跑在 worker thread 上，用 asio 的 `concurrent_channel` 把結果送回協程
（`src/core/llm/http.hpp` 開頭有圖）。同樣的手法包成了通用的一個工具：

```cpp
#include "aos/blocking.hpp"

const auto output = co_await run_blocking([argv] { return run_subprocess(argv); });
// co_await 回來就已經在 io_context 執行緒上了，可以放心碰 session
```

## 相依套件

專案使用 vcpkg manifest 管理：

- standalone Asio：Unix Socket 與非同步連線。
- nlohmann/json：request metadata 與 exit code。
- libcurl：對外的 HTTP 呼叫。

版本由 `vcpkg.json` 的 `builtin-baseline` 固定。第三方原始碼與安裝結果位於
`build/`，不會加入 Git。

## 建置與執行

```bash
export VCPKG_ROOT=/home/lorkhan/vcpkg
cmake --preset dev
cmake --build --preset dev
ctest --preset dev
```

先在一個終端啟動 daemon，再從另一個終端呼叫 CLI：

```bash
./bin/aos-daemon
./bin/aos ping
```

## Socket 路徑

兩個程式使用相同規則決定 socket 路徑：

1. 環境變數 `AOS_SOCKET`
2. `$XDG_RUNTIME_DIR/aos.sock`
3. `/tmp/aos-<uid>.sock`

```bash
AOS_SOCKET=/tmp/my-aos.sock ./bin/aos-daemon
AOS_SOCKET=/tmp/my-aos.sock ./bin/aos ping
```

## 程式分工

| 路徑 | 負責 |
|---|---|
| `src/cli/main.cpp` | 收集 argv 與工作目錄，啟動 client |
| `src/daemon/main.cpp` | 選擇 socket 路徑，啟動 daemon |
| `src/core/protocol.cpp` | JSON 控制訊息編解碼 |
| `src/core/channel.cpp` | 訊框讀寫（4 bytes 長度 + 1 byte 種類 + payload） |
| `src/core/session.cpp` | 命令用的三條串流介面 |
| `src/core/commands/` | 命令樹。`registry.cpp` 是那張表，其餘一檔一命令 |
| `src/core/client/` | `run.cpp` 驅動連線，`input.cpp` 轉送 stdin |
| `src/core/daemon/` | `run.cpp` 監聽，`connection.cpp` 處理單一連線，`socket_setup.cpp` 準備 socket 檔 |

`include/aos/runtime.hpp` 的 `Runtime` 存放跨呼叫存活的 daemon 狀態，
每條連線拿到的都是同一份。

## 測試

```bash
ctest --preset dev
```

| 測試 | 涵蓋 |
|---|---|
| `protocol` | JSON 編解碼，純函式，不碰 socket |
| `streaming` | 訊框在真 socket 上往返；命令確實是邊讀邊寫 |
| `end_to_end` | 真的起 daemon 用 CLI 打它，包含 20 MiB 串流與子命令派發 |

測試用 `tests/check.hpp` 而不是 `assert`，因為 `assert` 在 `NDEBUG` 下會整個消失，
Release 建置的測試會變成空跑還回報通過。

## 文件

- `docs/` — 程式碼導覽與各層說明
- `docs/cpp/` — C++23／26 特性筆記

## VS Code

```bash
export VCPKG_ROOT=/home/lorkhan/vcpkg
code /home/lorkhan/repo/simple_tools/aos
```

設定 CMake 後，`build/compile_commands.json` 會保存實際的 C++23 編譯參數與
include 路徑；專案內的 `.vscode/settings.json` 已設定 IntelliSense 使用它。
