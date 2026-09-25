#include "../src/parse.hpp"
#include <cassert>
#include <iostream>

int main() {
    assert(mini::parse("a=1").has_value());
    assert(*mini::parse("a=1") == "1");
    assert(*mini::parse("a=") == "");   // 有 '=' 但值為空 → engaged
    assert(!mini::parse("noequal").has_value());
    assert(!mini::parse("").has_value());  // 空字串沒有 '='

    // 確認呼叫端能區分「值本來就是空的」與「找不到 '='」
    assert(mini::parse("a=") != mini::parse("noequal"));
    std::cout << "ok\n";
    return 0;
}
