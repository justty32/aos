#include "parse.hpp"
#include <iostream>

int main(int argc, char **argv) {
    for (int i = 1; i < argc; ++i) {
        auto value = mini::parse(argv[i]);
        std::cout << (value ? *value : std::string()) << "\n";
    }
    return 0;
}
