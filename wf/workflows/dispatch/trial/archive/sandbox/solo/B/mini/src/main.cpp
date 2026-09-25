#include "parse.hpp"
#include <iostream>

int main(int argc, char **argv) {
    for (int i = 1; i < argc; ++i) {
        auto v = mini::parse(argv[i]);
        std::cout << (v.has_value() ? *v : std::string("(no '=')")) << "\n";
    }
    return 0;
}
