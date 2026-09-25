#include "../src/parse.hpp"
#include <cassert>
#include <iostream>

int main() {
    auto ok = mini::parse("a=1");
    assert(ok.has_value() && *ok == "1");

    auto empty = mini::parse("a=");
    assert(empty.has_value() && empty->empty());

    assert(!mini::parse("noequal").has_value());

    std::cout << "ok\n";
    return 0;
}
