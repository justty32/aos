#include "parse.hpp"
#include <iostream>

int main(int argc, char **argv) {
    for (int i = 1; i < argc; ++i) {
        const auto value = mini::parse(argv[i]);
        if (value) std::cout << *value;
        std::cout << "\n";
    }
    return 0;
}
