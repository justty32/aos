#include "../src/parse.hpp"
#include <cassert>
#include <iostream>

int main() {
    assert(mini::parse("a=1") == "1");
    assert(!mini::parse("noequal").has_value());

    const auto empty_value = mini::parse("empty=");
    assert(empty_value.has_value());
    assert(empty_value->empty());
    std::cout << "ok\n";
    return 0;
}
