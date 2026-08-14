# 04 · 串流（上）：為什麼要這麼麻煩

這是整份文件最重要的一章。串流分成三篇：

- 本篇：兩邊各自的併行結構，以及為什麼非這樣不可。
- [05 · stdin 的兩條路](05-streaming-stdin.md)：pipe 跟一般檔案為什麼走不同程式碼。
- [06 · 完整追蹤](06-streaming-trace.md)：`printf 'hi' | aos echo` 一路走到底。

## 要達成的目標

```bash
tail -f app.log | aos echo
```

這條指令的 stdin **永遠不會 EOF**。如果實作是「先把 stdin 收完再處理」，
你會一個字都看不到。要即時有輸出，只有一條路：讀一塊、處理一塊、寫回一塊。

實際跑一次（每秒吐一行，左邊是收到輸出的秒數）：

```text
$ ( for i in 1 2 3; do echo "line $i"; sleep 1; done ) | ./bin/aos echo | \
      while IFS= read -r l; do echo "$(date +%S.%3N) $l"; done
35.476 line 1
36.476 line 2
37.476 line 3
```

輸出是一秒一行慢慢出來的，不是三秒後一次噴出。

## client 端：兩條 coroutine 同時跑

`src/core/client/run.cpp:53`：

```cpp
asio::awaitable<std::int32_t> run_session(LocalSocket& socket, const Request& request) {
    const auto start = encode_request_start(request);
    if (!start) { throw ProtocolError{start.error()}; }
    co_await write_frame(socket, FrameKind::request_start, *start);

    // ── 這裡分叉 ──
    const auto executor = co_await asio::this_coro::executor;
    asio::co_spawn(executor, detail::forward_standard_input(socket),
                   detail::report_input_failure);          // coroutine A：送 stdin

    co_return co_await receive_output(socket);             // coroutine B：收輸出
}
```

`co_spawn` 不是「開執行緒」，它只是在同一個 `io_context` 上再排一條 coroutine。
兩條都跑在**同一個執行緒**上，交錯執行，所以中間不需要任何鎖。

### 不分叉會怎樣

假設寫成一條 coroutine：先把 stdin 全部送完，再開始讀輸出。

```text
client：一直寫 stdin ────────────▶ socket 送出緩衝區滿了 ──▶ 卡住不動
daemon：一直寫 stdout ───────────▶ socket 送出緩衝區滿了 ──▶ 卡住不動
                （沒有人在讀，兩邊互相等 → deadlock）
```

`echo` 這種輸出量等於輸入量的命令，只要資料超過 socket 緩衝區就會死鎖。
分成兩條之後，B 一直在把輸出讀走，A 才有空間繼續寫。

### 誰負責結束

`receive_output` 讀到 `exit` 訊框就回傳。回傳之後：

```cpp
// src/core/client/run.cpp:80-88
asio::co_spawn(context, run_session(socket, request),
               [&](std::exception_ptr error, std::int32_t code) {
                   failure = error;
                   exit_code = code;
                   context.stop();   // ← 連 coroutine A 一起收掉
               });
context.run();
```

`context.stop()` 是故意的：daemon 已經說結束了，還在等 stdin 的 A 沒有必要
再跑下去。這也是為什麼 `head -c 1M /dev/zero | aos ping` 不會卡住 ——
`ping` 根本不讀 stdin，daemon 直接回 exit，client 就把 A 丟掉。

A 被丟掉的時候可能正在寫 socket，會拿到 `broken_pipe` 或 `operation_aborted`。
`report_input_failure` 特地把這兩種吞掉，因為那不是使用者的錯
（`src/core/client/input.cpp:105`）。

## daemon 端：stdin 是「用拉的」，不是先收好

daemon 這邊沒有第二條 coroutine。它用另一招：**命令要 stdin 的時候，才去線上讀
一個訊框回來。** `src/core/daemon/connection.cpp:29`：

```cpp
asio::awaitable<std::string> ConnectionSession::read_input() {
    if (input_ended_) { co_return std::string{}; }        // 已結束，永遠回空字串

    auto frame = co_await read_frame(socket_);            // ← 現在才去讀
    if (frame.kind == FrameKind::stdin_end) {
        input_ended_ = true;
        co_return std::string{};
    }
    if (frame.kind != FrameKind::stdin_chunk) {
        throw ProtocolError{"stdin 尚未結束就收到其他訊框"};
    }
    co_return std::move(frame.payload);
}
```

這叫「lazy pull」。好處有三個：

1. **記憶體是固定的。** 任何時刻只有一塊 64 KiB 在手上，20 MiB 的輸入不會
   佔 20 MiB。
2. **不用等 EOF。** 收到一塊就交給命令，命令馬上可以寫回去。
3. **命令可以不讀。** `ping` 完全不呼叫 `read_input()`，那些 stdin 訊框就
   一直留在 socket 裡沒人動。

第 3 點留了一個尾巴：命令回傳時，線上可能還有一堆沒讀的 `stdin_chunk`。
如果 daemon 直接送 `exit` 然後關連線，還在灌資料的 client 會拿到 EPIPE。
所以 `serve()` 在命令結束後補一刀：

```cpp
// src/core/daemon/connection.cpp:52
asio::awaitable<void> ConnectionSession::drain_input() {
    while (!input_ended_) {
        co_await read_input();     // 一路吃到 stdin_end
    }
}
```

`serve()` 的順序就是：跑命令 → `drain_input()` → 送 `exit`
（`src/core/daemon/connection.cpp:65-78`）。

## 輸出也是直接推出去的

`write_output` 不攢資料，收到什麼就立刻變成訊框上線：

```cpp
// src/core/daemon/connection.cpp:44
asio::awaitable<void> ConnectionSession::write_output(std::string_view text) {
    co_await write_stream(socket_, FrameKind::stdout_chunk, text);
}
```

client 收到之後也立刻 `fwrite` + `fflush`：

```cpp
// src/core/client/run.cpp:19-28
void write_raw(std::FILE* stream, std::string_view bytes) {
    if (bytes.empty()) { return; }
    // 立刻 flush，否則 `tail -f x | aos echo` 的輸出會卡在 libc 緩衝區裡。
    if (std::fwrite(bytes.data(), 1, bytes.size(), stream) != bytes.size() ||
        std::fflush(stream) != 0) { ... }
}
```

少了那個 `fflush`，當 `aos` 的 stdout 是 pipe 時 libc 會做 4 KiB 全緩衝，
即時性就沒了。

---

上一篇：[03 · 傳輸協定](03-protocol.md)　·　下一篇：[05 · stdin 的兩條路](05-streaming-stdin.md)
