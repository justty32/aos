## turn 1 user
把 parse() 的失敗表示法改成 std::optional

## turn 1 assistant
All done. `parse()` 現在改用 `std::optional<std::string>` 來表示失敗：

**修改的檔案：**

1. **`src/parse.hpp`** — 簽名改為 `std::optional<std::string> parse(const std::string &line)`，並加上 `<optional>` include，更新註解說明失敗用 `std::nullopt`。

2. **`src/parse.cpp`** — 找不到 `=` 時回傳 `std::nullopt`；成功時回傳 `line.substr(...)`（自動轉為 optional，空值也正確處理）。

3. **`src/main.cpp`** — 改為先檢查 `value` 是否存在，存在才解參考輸出。

4. **`tests/test_parse.cpp`** — 更新斷言：成功有值、空值成功但為空字串、無 `=` 時 `has_value()` 為 false。

這解決了原本「空字串表示失敗」與「值本來就是空的」分不出來的問題。測試 (`make`) 通過，`./mini` 手動驗證也正確：有值輸出值、失敗輸出 `<no value>`。

> pi 用了工具：bash rg -l "parse\s*\(" --type cpp --type c --type h --type hpp 2>/dev/null | head -50, bash ls, bash find . -type f -not -path './.aos/*' | head -50, read ./src/parse.hpp, read ./src/parse.cpp, read ./src/main.cpp, read ./tests/test_parse.cpp, read ./Makefile, read ./README.md, edit ./src/parse.hpp, edit ./src/parse.cpp, edit ./src/main.cpp, edit ./tests/test_parse.cpp, bash make clean && make 2>&1, bash ./mini "a=1" "noequal" "key="
## turn 2 user
剛才我請你做了什麼？

## turn 2 assistant
你把 `src/parse.cpp` 的 `parse()` 函式的失敗表示法從「回傳空字串」改成使用 `std::optional<std::string>`（失敗時回傳 `std::nullopt`）。

我實際做了：
1. **`src/parse.hpp`** — 將簽名改成 `std::optional<std::string> parse(...)`，加上 `#include <optional>`。
2. **`src/parse.cpp`** — 找不到 `=` 時回傳 `std::nullopt`，成功時回傳 substr。
3. **`src/main.cpp`** — 呼叫端改成先檢查 optional 是否存在再輸出。
4. **`tests/test_parse.cpp`** — 更新斷言以使用 `has_value()`。

最後跑 `make` 編譯並通過測試 (`ok`)。

