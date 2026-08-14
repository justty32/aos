#pragma once

#include <print>
#include <string_view>

// assert 在 NDEBUG 下會整個消失，Release 建置的測試就變成空跑還報 pass。
// 這個檢查不會被編譯選項拿掉。
namespace aos::testing {

inline int failure_count = 0;

inline void check(bool passed, std::string_view expression,
                  std::string_view file, int line) {
    if (passed) {
        return;
    }
    std::println(stderr, "{}:{}：檢查失敗：{}", file, line, expression);
    ++failure_count;
}

[[nodiscard]] inline int report() {
    if (failure_count > 0) {
        std::println(stderr, "共 {} 項檢查失敗", failure_count);
        return 1;
    }
    return 0;
}

}  // namespace aos::testing

#define AOS_CHECK(expression) \
    ::aos::testing::check((expression), #expression, __FILE__, __LINE__)
