# Coroutine 心智模型

看完這篇，你會知道 coroutine 在記憶體裡到底是什麼東西，以及為什麼 `asio::awaitable` 要「呼叫了也不會跑」。

## 一句話版本

只要一個函式的本體裡出現 `co_await`、`co_return` 或 `co_yield`，
編譯器就不再把它當普通函式編譯。它會：

1. 在 heap 上配一塊 **coroutine frame**，
2. 把函式的參數和區域變數搬進那塊 frame，
3. 在每個暫停點記下「下次從哪一行繼續」，
4. 暫停時把控制權還給呼叫端，frame 留著不動。

普通函式的區域變數在 stack 上，函式返回就沒了。
coroutine 的區域變數在 frame 上，**跨過 `co_await` 依然活著**。這是整套機制的重點。

## 誰決定行為：coroutine 型別 vs coroutine 函式

這兩個東西很容易混在一起：

- **coroutine 函式**：你寫的那個含 `co_await` 的函式，例如 `read_frame()`。
- **coroutine 型別**：它的回傳型別，例如 `asio::awaitable<Frame>`、`std::generator<int>`。

回傳型別裡有一個 `promise_type`，編譯器會去問它一連串問題：
一開始要不要先暫停？`co_return` 的值放哪？丟例外了怎麼辦？
**所有行為都由回傳型別決定，不是由函式決定。**

同一段函式本體，配 `asio::awaitable<T>` 就是非同步任務，配 `std::generator<T>` 就是同步序列。

實務上你幾乎不用自己寫 coroutine 型別。專案裡只會用兩種現成的：

| 型別 | 用途 | 章節 |
| --- | --- | --- |
| `asio::awaitable<T>` | 非同步 I/O | [02](02-asio-awaitable.md) |
| `std::generator<T>` | 同步產生一串值 | [05](05-std-generator.md) |

## 看得見的暫停

先用 `std::generator` 看清楚「控制權來回跳」這件事，它最短：

```cpp
#include <generator>
#include <print>

std::generator<int> counter() {
    int local = 0;                 // 這個 local 住在 coroutine frame 裡
    while (local < 3) {
        std::println("  coroutine: 準備交出 {}", local);
        co_yield local;            // 這裡讓出控制權，local 不會消失
        ++local;
    }
    std::println("  coroutine: 結束");
}

int main() {
    for (int value : counter()) {
        std::println("main: 收到 {}", value);
    }
}
```

輸出：

```
  coroutine: 準備交出 0
main: 收到 0
  coroutine: 準備交出 1
main: 收到 1
  coroutine: 準備交出 2
main: 收到 2
  coroutine: 結束
```

兩邊交替執行，但只有一條執行緒。
`local` 從 0 數到 2，中間讓出過三次都沒事，因為它不在 stack 上。

## 一個最小的自製型別（只是為了拆穿魔法）

看一次就好，之後不要自己寫：

```cpp
#include <coroutine>
#include <print>

struct Task {
    struct promise_type {
        Task get_return_object() { return {}; }
        std::suspend_never initial_suspend() { return {}; }  // eager：呼叫就跑
        std::suspend_never final_suspend() noexcept { return {}; }
        void return_void() {}
        void unhandled_exception() {}
    };
};

Task hello() {
    std::println("coroutine 開始跑了");
    co_return;
}

int main() {
    std::println("呼叫之前");
    hello();
    std::println("呼叫之後");
}
```

輸出：

```
呼叫之前
coroutine 開始跑了
呼叫之後
```

這五個成員函式就是 coroutine 型別的全部義務。
真正麻煩的是把「回傳值、例外、取消、誰接手繼續跑」都做對，那才是 `asio::awaitable` 幾百行在處理的事。
所以自己寫沒有好處。

## eager vs lazy：`initial_suspend` 決定的

上面 `initial_suspend()` 回傳 `std::suspend_never`，所以呼叫 `hello()` 就直接跑到底，這叫 **eager**。

`asio::awaitable<T>` 剛好相反，是 **lazy**：呼叫函式只會做出 frame，一行程式碼都不執行。
要等到有人 `co_await` 它，或用 `asio::co_spawn` 把它丟給 executor，它才開始跑。

```cpp
#include <asio/awaitable.hpp>
#include <asio/co_spawn.hpp>
#include <asio/detached.hpp>
#include <asio/io_context.hpp>
#include <print>

asio::awaitable<void> greet() {
    std::println("greet 真的跑了");
    co_return;
}

int main() {
    asio::io_context context;

    auto lazy = greet();          // 什麼都不會發生
    std::println("已經呼叫 greet()，但上面那行沒有輸出");
    (void)lazy;

    asio::co_spawn(context, greet(), asio::detached);  // 這樣才會跑
    context.run();
}
```

輸出：

```
已經呼叫 greet()，但上面那行沒有輸出
greet 真的跑了
```

這件事之所以重要，是因為它直接牽動生命週期：
`greet()` 那一行結束時，傳進去的參數已經被搬進 frame 了，但函式本體還沒開始跑。
如果參數是 `std::string_view`，指到的字串可能在真正執行之前就死了。
這是整份文件裡最容易踩到的雷，[03](03-coroutine-lifetime.md) 專門講它。

## 跟 C++20 比，變了什麼

語言層面幾乎沒變，`co_await` / `co_yield` / `co_return` 還是 C++20 那套。
C++23 補的是**標準函式庫**：終於有了 `std::generator<T>`，不用再自己刻 promise_type。
非同步那邊標準庫還是空的，所以我們用 Asio。

## 下一步

- [`asio::awaitable` 實戰](02-asio-awaitable.md)
- [生命週期：最大的地雷](03-coroutine-lifetime.md)
- [常見錯誤](04-coroutine-pitfalls.md)
- [`std::generator`](05-std-generator.md)
