#include "../src/parse.hpp"
#include <cassert>
#include <iostream>

int main() {
    assert(mini::parse("a=1") == "1");
    assert(mini::parse("empty=") == "");
    assert(mini::parse("noequal") == std::nullopt);
    std::cout << "ok\n";
    return 0;
}
