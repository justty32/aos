# std::expected

C++23 的 `std::expected<T, E>`：像 `optional`，但失敗時帶著「為什麼失敗」。aos 的 JSON 解析已經在用它。

## 心智模型

`std::expected<T, E>` 裡面**二選一**：要嘛一個 `T`（成功），要嘛一個 `E`（失敗理由）。

跟你熟的東西比：

| 做法 | 帶得動失敗理由 | 呼叫端能忽略 | 成本 |
|---|---|---|---|
| `std::optional<T>` | 不行，只知道「沒有」 | 能 | 零 |
| 例外 | 可以 | 不能（會炸上去） | 丟出時很貴 |
| `std::error_code` 回傳參數 | 可以，但只能是整數碼 | 能 | 零 |
| `std::expected<T, E>` | 可以，`E` 想放什麼都行 | 能（要小心，見最後一節） | 零 |

aos 用 `std::expected<T, std::string>`，`E` 就是給人看的中文訊息。

## 基本操作

```cpp
#include <expected>
#include <print>
#include <string>

std::expected<int, std::string> bad() { return std::unexpected{std::string{"壞了"}}; }

int main() {
    auto r = bad();
    std::println("has_value = {}", r.has_value());
    std::println("error()   = {}", r.error());
    try {
        (void)r.value();               // 失敗時會丟例外
    } catch (const std::bad_expected_access<std::string>& e) {
        std::println("value() 丟出：{} / 內含 error = {}", e.what(), e.error());
    }
    // *r 與 r-> 不檢查，失敗時直接是 UB，別碰。
}
```

輸出：

```
has_value = false
error()   = 壞了
value() 丟出：bad access to std::expected without expected value / 內含 error = 壞了
```

重點：

- `has_value()` / `operator bool` — 問成功沒。
- `*r`、`r->` — 拿值，**不檢查**，先確認成功再用。
- `r.value()` — 拿值，失敗時丟 `std::bad_expected_access<E>`。
- `r.error()` — 拿失敗理由，成功時用它才是 UB。
- `r.value_or(fallback)` — 失敗就給預設值。

## `std::unexpected` 與 aos 的 `invalid()`

回傳失敗要包一層 `std::unexpected{...}`，寫多了很吵。aos 在
[`../../src/core/protocol.cpp`](../../src/core/protocol.cpp) 包了一個小 helper：

```cpp
[[nodiscard]] std::unexpected<std::string> invalid(std::string message) {
    return std::unexpected{std::move(message)};
}
```

於是每個錯誤出口都是一行 `return invalid("request JSON 缺少必要欄位");`。
`std::unexpected<E>` 可以隱式轉成任何 `std::expected<T, E>`，所以同一個 helper
在回傳 `expected<Request, string>` 和 `expected<int32_t, string>` 的函式裡都能用。

## Monadic operations（重點）

這四個成員讓你把「一連串可能失敗的步驟」串成一條線，錯誤自動短路。

| 成員 | 給它的函式 | 作用 |
|---|---|---|
| `and_then(f)` | `T -> expected<U, E>` | 成功才做下一步，下一步也可能失敗 |
| `transform(f)` | `T -> U` | 成功才做，這一步不會失敗 |
| `or_else(f)` | `E -> expected<T, E2>` | 失敗才做，可以救回來 |
| `transform_error(f)` | `E -> E2` | 失敗才做，改寫錯誤訊息 |

```cpp
#include <charconv>
#include <expected>
#include <print>
#include <string>
#include <string_view>

using Fail = std::string;
template <class T> using Result = std::expected<T, Fail>;

[[nodiscard]] std::unexpected<Fail> invalid(std::string message) {
    return std::unexpected{std::move(message)};
}

[[nodiscard]] Result<int> parse_port(std::string_view text) {
    int value = 0;
    const auto [ptr, ec] = std::from_chars(text.data(), text.data() + text.size(), value);
    if (ec != std::errc{} || ptr != text.data() + text.size()) {
        return invalid(std::format("「{}」不是整數", text));
    }
    return value;
}

[[nodiscard]] Result<int> check_range(int port) {
    if (port < 1 || port > 65535) {
        return invalid(std::format("port {} 超出 1..65535", port));
    }
    return port;
}

[[nodiscard]] Result<std::string> describe(std::string_view text) {
    return parse_port(text)
        .and_then(check_range)
        .transform([](int port) { return std::format("listen on :{}", port); })
        .transform_error([text](Fail why) {
            return std::format("設定值 {:?} 有問題：{}", text, why);
        });
}

int main() {
    for (std::string_view input : {"8080", "99999", "abc"}) {
        const auto result = describe(input);
        if (result) {
            std::println("OK   {}", *result);
        } else {
            std::println("FAIL {}", result.error());
        }
    }
    std::println("value_or -> {}", parse_port("x").value_or(-1));

    auto touch = [](bool ok) -> std::expected<void, Fail> {
        if (!ok) return invalid("寫檔失敗");
        return {};
    };
    std::println("void 版：{}", touch(false).error());
}
```

輸出：

```
OK   listen on :8080
FAIL 設定值 "99999" 有問題：port 99999 超出 1..65535
FAIL 設定值 "abc" 有問題：「abc」不是整數
value_or -> -1
void 版：寫檔失敗
```

注意 `parse_port("abc")` 失敗後，`check_range` 和 `transform` 都**沒有被呼叫**，
直接跳到 `transform_error`。這就是短路。

## `std::expected<void, E>`

「只要知道成不成功，成功時沒有值」用 `std::expected<void, E>`。
成功時 `return {};`，其餘用法一樣。適合 `write_file()`、`flush()` 這種。

## 什麼時候還是要用例外

aos 的分法很值得抄：

- **對方送來的內容不對**（欄位缺、版本不合、JSON 壞掉）→ 回傳 `expected`。
  這是**預期會發生**的事，呼叫端有能力回一個錯誤訊息給使用者。
- **傳輸層壞掉**（訊框長度超過 8 MiB、訊框種類不認得）→ 丟 `ProtocolError`。
  見 [`../../src/core/channel.cpp`](../../src/core/channel.cpp)。這種狀況下連線已經
  沒救了，中間每一層都只能往上傳，用 `expected` 只會讓每一層都寫一次 `if`。

判斷法則：**如果中間每一層都只會做「原封不動往上丟」，那就用例外。**
如果某一層真的會處理它、會做決定，才用 `expected`。

## 陷阱：丟掉的 `expected` 會靜靜吃掉錯誤

`std::expected` 本身**沒有** `[[nodiscard]]`。所以這樣寫會編過，錯誤完全消失：

```cpp
save_config(path);   // 回傳 expected，沒人看 -> 錯誤被丟掉，沒有任何警告
```

修法是在**函式**上加 `[[nodiscard]]`，aos 的 header
[`../../include/aos/protocol.hpp`](../../include/aos/protocol.hpp) 每個回傳
`expected` 的宣告都加了：

```cpp
[[nodiscard]] std::expected<Request, std::string>
decode_request_start(std::string_view payload);
```

這樣忘記檢查就會有 `-Wunused-result` 警告。真的要故意忽略時寫 `(void)f();`。

---

下一篇：[14-print-and-format.md](14-print-and-format.md)
