# 05 · 串流（中）：stdin 的三條路

檔案：`src/core/client/input.cpp`（105 行，全部都是為了處理「stdin 到底是什麼」）。

## 入口的三岔路

```cpp
// src/core/client/input.cpp:76-95
asio::awaitable<void> forward_standard_input(LocalSocket& socket) {
    if (::isatty(STDIN_FILENO) == 0) {              // 不是終端才要送
        if (can_be_polled(STDIN_FILENO)) {
            const int copy = ::dup(STDIN_FILENO);   // pipe / socket / tty
            const auto executor = co_await asio::this_coro::executor;
            co_await forward_pollable(
                socket, asio::posix::stream_descriptor{executor, copy});
        } else {
            co_await forward_file(socket, STDIN_FILENO);   // 一般檔案
        }
    }
    co_await write_frame(socket, FrameKind::stdin_end, {});  // 三條路都要收尾
}
```

三種情況：

| stdin 是什麼 | 走哪條 | 為什麼 |
| --- | --- | --- |
| 終端（你直接打 `aos ping`） | 都不走，直接送 `stdin_end` | 不然會停在那裡等你按 Ctrl-D |
| pipe / socket | `forward_pollable`（asio 非同步） | 讀取會阻塞，必須讓出執行權 |
| 一般檔案 / 目錄 | `forward_file`（同步 `::read`） | **epoll 拒收一般檔案** |

## 為什麼一般檔案要另外處理

這是最容易踩到的一點。asio 在 Linux 上用 epoll，而 **epoll 不接受一般檔案的
fd**：`epoll_ctl` 會直接回 `EPERM`。原因是 epoll 的語意是「等到可讀」，
而一般檔案永遠是可讀的，這個問題對它沒有意義。

所以要先問一下這個 fd 是什麼：

```cpp
// src/core/client/input.cpp:23-29
[[nodiscard]] bool can_be_polled(int descriptor) {
    struct ::stat status{};
    if (::fstat(descriptor, &status) < 0) { return false; }
    return !S_ISREG(status.st_mode) && !S_ISDIR(status.st_mode);
}
```

只排除 `S_ISREG`（一般檔案）跟 `S_ISDIR`（目錄）。pipe、socket、字元裝置
（`/dev/zero`、`/dev/urandom`）都是可以 poll 的。

沒有這個判斷的話，`aos echo < input.txt` 會在建 `stream_descriptor` 時就爆掉。
`tests/e2e.sh:63` 就是專門守這一條的：

```bash
printf 'from a regular file' >"${workspace}/input.txt"
check "echo 走檔案重導向" "from a regular file" \
  "$("${cli_binary}" echo <"${workspace}/input.txt")"
```

## 可 poll 的那條

```cpp
// src/core/client/input.cpp:32-50
asio::awaitable<void> forward_pollable(LocalSocket& socket,
                                       asio::posix::stream_descriptor input) {
    std::array<char, stream_chunk_size> buffer{};      // 64 KiB
    while (true) {
        std::error_code error;
        const auto count = co_await input.async_read_some(
            asio::buffer(buffer),
            asio::redirect_error(asio::use_awaitable, error));
        if (error == asio::error::eof) { co_return; }
        if (error) { throw std::system_error{error, "讀取 stdin 失敗"}; }

        co_await write_frame(socket, FrameKind::stdin_chunk,
                             std::string_view{buffer.data(), count});
    }
}
```

兩個細節：

- `asio::redirect_error` 把錯誤變成 out 參數而不是例外。EOF 在這裡是正常結束，
  用例外表達太吵。
- `buffer` 是這條 coroutine 的區域變數，會被放進 coroutine frame，所以
  `write_frame` 拿到的 `string_view` 在 `co_await` 期間是安全的。

## 為什麼要 `dup`

```cpp
const int copy = ::dup(STDIN_FILENO);
asio::posix::stream_descriptor{executor, copy}
```

`stream_descriptor` 的解構子會 `close()` 它拿到的 fd。如果直接把 `0` 給它，
`aos` 真正的 stdin 就被關掉了。複製一份就沒事。

## 一般檔案的那條

```cpp
// src/core/client/input.cpp:54-72
asio::awaitable<void> forward_file(LocalSocket& socket, int descriptor) {
    std::array<char, stream_chunk_size> buffer{};
    while (true) {
        const auto count = ::read(descriptor, buffer.data(), buffer.size());
        if (count < 0) {
            if (errno == EINTR) { continue; }        // 被訊號打斷，重來
            throw std::system_error{errno, std::generic_category(), "讀取 stdin 失敗"};
        }
        if (count == 0) { co_return; }               // EOF
        co_await write_frame(socket, FrameKind::stdin_chunk,
                             std::string_view{buffer.data(),
                                              static_cast<std::size_t>(count)});
    }
}
```

這裡的 `::read` 是**同步**的，會擋住整個執行緒。這在一般檔案上沒問題：
讀磁碟檔案不會像 pipe 那樣無限期等待。

而且迴圈裡的 `co_await write_frame` 還是會讓出執行權，所以即使在讀 20 MiB
的大檔，收輸出的那條 coroutine 也不會餓死。這就是 `tests/e2e.sh:75` 那個
20 MiB 測試能過的原因：

```bash
head -c $((20 * 1024 * 1024)) /dev/urandom >"${workspace}/big.bin"
"${cli_binary}" echo <"${workspace}/big.bin" >"${workspace}/big.out"
```

實測（cksum 完全相同）：

```text
$ cksum < big.bin ; cksum < big.out
2507697104 20971520
2507697104 20971520
```

## 終端那條：什麼都不做

```cpp
if (::isatty(STDIN_FILENO) == 0) { ... }
```

`isatty` 回傳非 0（是終端）時整個 if 被跳過，只送一個 `stdin_end`。
不然你打 `aos ping` 會看到游標停在那裡，得按 Ctrl-D 才有 `pong`。

代價是：目前**不支援互動式命令**。要做互動式（例如讓命令問你問題），
這裡是第一個要改的地方。

---

上一篇：[04 · 串流（上）](04-streaming-overview.md)　·　下一篇：[06 · 串流（下）](06-streaming-trace.md)
