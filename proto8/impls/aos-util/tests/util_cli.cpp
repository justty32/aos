// util_cli.cpp：測試用的小程式（不是產物）：stdin 讀一份 JSON（read_stdin），原樣 emit；出錯 emit_error。
// tests/test_cli.py 拿它來測三扇門。
#include "aos/io.hpp"

int main() {
    try {
        return aos::emit(aos::read_stdin());
    } catch (const aos::Error& e) {
        return aos::emit_error(e);
    }
}
