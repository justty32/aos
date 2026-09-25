#include "../src/parse.hpp"
#include <cassert>
#include <iostream>

int main() {
    assert(mini::parse("a=1").has_value());
    assert(*mini::parse("a=1") == "1");
    assert(!mini::parse("noequal").has_value());
    std::cout << "ok\n";
    return 0;
}
