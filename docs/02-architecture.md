# 02 · 大架構

## 兩個 process，一條 socket

```text
  你的 shell
      │  argv, stdin
      ▼
┌───────────────────────┐                       ┌───────────────────────────┐
│  aos（CLI process）   │                       │  aos-daemon（常駐）       │
│                       │                       │                           │
│  src/cli/main.cpp     │                       │  src/daemon/main.cpp      │
│    收 argv + cwd      │                       │    決定 socket 路徑       │
│         │             │                       │         │                 │
│         ▼             │                       │         ▼                 │
│  run_client()         │   Unix Domain Socket  │  run_daemon()             │
│  client/run.cpp       │◀─────────────────────▶│  daemon/run.cpp           │
│    ├ coroutine A      │   $AOS_SOCKET         │    acceptor 迴圈          │
│    │   送 stdin       │   （SOCK_STREAM）     │         │ 每條連線一個    │
│    │   client/input   │                       │         ▼   coroutine     │
│    └ coroutine B      │   一連串 Frame        │  serve()                  │
│        收 stdout/     │   4B 長度+1B 種類     │  daemon/connection.cpp    │
│        stderr/exit    │   +payload            │         │                 │
└───────────────────────┘                       │         ▼                 │
      │  stdout, stderr, exit code              │  handle_command()         │
      ▼                                         │  commands/registry.cpp    │
  你的 shell                                    │         │                 │
                                                │         ▼                 │
                                                │  ping / echo / daemon …   │
                                                │  commands/*.cpp           │
                                                │         ▲                 │
                                                │         │ Runtime&        │
                                                │  （活過每一條連線）       │
                                                └───────────────────────────┘
```

重點只有三個：

1. CLI 完全不懂命令。它不知道有 `ping` 這回事，只負責把 argv 打包送出去。
   所有命令語意都在 daemon 那邊（`include/aos/command.hpp:74` 的註解講得很白）。
2. 三條標準串流全部走同一條 socket，用「訊框種類」區分。
3. `Runtime` 是唯一活過連線的東西，所以它是放跨呼叫狀態的地方。

## 檔案分工

| 路徑 | 做什麼 |
| --- | --- |
| `src/cli/main.cpp` | 收 argv 與 cwd，呼叫 `run_client` |
| `src/daemon/main.cpp` | 呼叫 `run_daemon` |
| `src/core/protocol.cpp` | 控制訊息的 JSON 編解碼（純函式，不碰 socket） |
| `src/core/channel.cpp` | 訊框的讀與寫 |
| `src/core/session.cpp` | `say()` / `complain()` 兩個小工具 |
| `src/core/socket_path.cpp` | 決定 socket 路徑 |
| `src/core/client/run.cpp` | client 主流程：連線、送 request、收輸出 |
| `src/core/client/input.cpp` | client 把本機 stdin 轉成訊框 |
| `src/core/daemon/run.cpp` | 建 acceptor、接連線、關機 |
| `src/core/daemon/socket_setup.cpp` | socket 檔的建立前檢查與離開時清理 |
| `src/core/daemon/connection.cpp` | 一條連線的生命週期 + `ConnectionSession` |
| `src/core/commands/registry.cpp` | 命令表、命令解析、help 渲染、派發 |
| `src/core/commands/*.cpp` | 一個檔案一個（或一組）命令 |

`include/aos/*.hpp` 是給別人看的介面；`src/core/**/*.hpp`（`commands.hpp`、
`connection.hpp`、`input.hpp`、`socket_setup.hpp`）只有 `aos_core` 自己看得到，
因為 CMake 把 `src/core` 設成 `PRIVATE` include 路徑。

## CMake 只有三個 target

```cmake
add_library(aos_core STATIC ${AOS_CORE_SOURCES})  # glob 掃 src/core/**/*.cpp
add_executable(aos_cli    src/cli/main.cpp)       # 輸出成 bin/aos
add_executable(aos_daemon src/daemon/main.cpp)    # 輸出成 bin/aos-daemon
```

`AOS_CORE_SOURCES` 是 `file(GLOB_RECURSE ... CONFIGURE_DEPENDS)`，所以
**在 `src/core/` 下新增 `.cpp` 不用改 CMakeLists**，重跑 build 就會編進去。

## 三條串流各自的角色

| 串流 | 方向 | 誰產生 | 誰消費 |
| --- | --- | --- | --- |
| stdin | CLI → daemon | 你的 shell | 命令的 `session.read_input()` |
| stdout | daemon → CLI | 命令的 `session.write_output()` | CLI 的 `stdout` |
| stderr | daemon → CLI | 命令的 `session.write_error()` | CLI 的 `stderr` |
| exit code | daemon → CLI | 命令的 `co_return` 值 | CLI 的 `main` 回傳值 |

命令端看到的抽象就是 `Session`（`include/aos/session.hpp`）：

```cpp
class Session {
public:
    virtual asio::awaitable<std::string> read_input() = 0;      // 拉 stdin
    virtual asio::awaitable<void> write_output(std::string_view) = 0;
    virtual asio::awaitable<void> write_error(std::string_view) = 0;
};
```

真實的實作是 `ConnectionSession`（socket）；測試裡塞的是 `RecordingSession`
（記憶體），命令本身完全不知道差別。

---

上一篇：[01 · 快速上手](01-quickstart.md)　·　下一篇：[03 · 傳輸協定](03-protocol.md)
