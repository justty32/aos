# 03 · 傳輸協定

檔案：`include/aos/protocol.hpp`（型別與常數）、`src/core/protocol.cpp`（JSON）、
`src/core/channel.cpp`（讀寫）。

## 訊框長這樣

```text
 0        1        2        3        4        5              5+N
 ├────────┴────────┴────────┴────────┼────────┼───────────────┤
 │  payload 長度 N（4 bytes, 大端序）│ kind   │  payload N bytes
 └───────────────────────────────────┴────────┴───────────────┘
```

固定 5 bytes 表頭，然後是 payload。就這樣，沒有別的欄位。

```cpp
// include/aos/protocol.hpp:15-21
inline constexpr std::size_t frame_header_size    = 5;
inline constexpr std::size_t maximum_payload_size = 8U * 1024U * 1024U;  // 8 MiB
inline constexpr std::size_t stream_chunk_size    = 64U * 1024U;         // 64 KiB
```

- `maximum_payload_size` 是**單一訊框**的上限，不是整條串流的上限。
  20 MiB 的 stdin 會被切成很多個訊框送。
- `stream_chunk_size` 是切塊大小，同時也是 client 讀 stdin 的緩衝區大小。

長度為什麼用大端序？沒有深層理由，就是網路慣例。編碼在
`src/core/channel.cpp:17`，一個 byte 一個 byte 移出來，不靠 `htonl`，
所以不會有平台差異。

## 六種 kind

```cpp
// include/aos/protocol.hpp:38-45
enum class FrameKind : std::uint8_t {
    request_start = 1,   // CLI → daemon：這次要跑什麼（JSON）
    stdin_chunk   = 2,   // CLI → daemon：一塊 stdin 原始 bytes
    stdin_end     = 3,   // CLI → daemon：stdin 到此為止（payload 一定是空的）
    stdout_chunk  = 4,   // daemon → CLI：一塊 stdout 原始 bytes
    stderr_chunk  = 5,   // daemon → CLI：一塊 stderr 原始 bytes
    exit          = 6,   // daemon → CLI：結束了，exit code 多少（JSON）
};
```

方向是固定的。daemon 收到 `stdout_chunk` 會丟 `ProtocolError`，
client 收到 `stdin_chunk` 也一樣（`src/core/client/run.cpp:47`）。

一條連線的訊框順序永遠是：

```text
CLI  →  request_start
CLI  →  stdin_chunk × N   （可能是 0 個）
CLI  →  stdin_end
                            daemon → stdout_chunk / stderr_chunk × M（隨時交錯）
                            daemon → exit          （一定是最後一個）
```

## 兩種 JSON payload

只有 `request_start` 與 `exit` 的 payload 是 JSON，三條串流都是原始 bytes
（所以二進位安全，含 `\0` 也沒問題）。

`request_start`：

```json
{"arguments":["echo"],"version":1,"working_directory":"/home/lorkhan/repo/simple_tools/aos"}
```

`version` 必須是 1，否則 `decode_request_start` 回傳
`std::unexpected{"不支援的 AOS 協定版本"}`（`src/core/protocol.cpp:40`）。
注意 stdin **不在** JSON 裡 —— 它是連線上持續流動的訊框。

`exit`：

```json
{"exit_code":0}
```

編解碼函式都回傳 `std::expected<T, std::string>`，錯誤是給人看的字串：

```cpp
[[nodiscard]] std::expected<std::string, std::string>
encode_request_start(const Request& request);

[[nodiscard]] std::expected<Request, std::string>
decode_request_start(std::string_view payload);
```

## 真的抓下來的 bytes

用 `printf 'hi' | ./bin/aos echo` 實際錄到的線上內容：

```text
CLI  → 00 00 00 5c 01   {"arguments":["echo"],"version":1,"working_directory":"..."}
CLI  → 00 00 00 02 02   'hi'
CLI  → 00 00 00 00 03   （空）
daemon → 00 00 00 02 04   'hi'
daemon → 00 00 00 0f 06   {"exit_code":0}
```

`0x5c` = 92 是 JSON 的長度，`0x0f` = 15 是 `{"exit_code":0}` 的長度。
`stdin_end` 的長度是 0，種類是 3。

## 讀寫的三個函式

```cpp
// include/aos/channel.hpp
asio::awaitable<Frame> read_frame(LocalSocket&);
asio::awaitable<void>  write_frame(LocalSocket&, FrameKind, std::string_view);
asio::awaitable<void>  write_stream(LocalSocket&, FrameKind, std::string_view);
```

`write_frame` 送剛好一個訊框，payload 超過 8 MiB 會丟 `ProtocolError`。

`write_stream` 會自動切塊，所以你不必自己管上限：

```cpp
// src/core/channel.cpp:80-87
asio::awaitable<void> write_stream(LocalSocket& socket, FrameKind kind,
                                   std::string_view bytes) {
    while (!bytes.empty()) {
        const auto count = std::min(bytes.size(), stream_chunk_size);
        co_await write_frame(socket, kind, bytes.substr(0, count));
        bytes.remove_prefix(count);
    }
}
```

空字串會送出 0 個訊框（迴圈一次都不進）。這就是為什麼
`ConnectionSession::write_output("")` 不會在線上留下任何東西。

## 一個一定要記住的陷阱

`write_frame` 的 `payload` 是 `string_view`，`co_await` 期間底下的 bytes
必須還活著。所以**不要**這樣寫：

```cpp
// ✗ 壞掉：暫時的 std::string 在 co_await 之前就死了
co_await session.write_output(std::format("hello {}\n", name));
```

要用 `say()`，它的參數是 by value，字串會被搬進 coroutine frame：

```cpp
// ✓ 安全
co_await say(session, std::format("hello {}\n", name));
```

`say()` / `complain()` 的實作就三行，在 `src/core/session.cpp:7`。

## 兩種錯誤

| 例外 | 意思 | 還能回覆對方嗎 |
| --- | --- | --- |
| `ProtocolError` | 對方講的話不合協定 | 可以，daemon 會回 stderr + exit 2 |
| `std::system_error` | 連線本身壞了（EOF、EPIPE…） | 不行，只能記 log |

`serve()` 就是照這條線分的（`src/core/daemon/connection.cpp:68`）。

---

上一篇：[02 · 大架構](02-architecture.md)　·　下一篇：[04 · 串流（上）](04-streaming-overview.md)
