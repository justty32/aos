#include "parse.hpp"
#include <iostream>

int main(int argc, char **argv) {
    for (int i = 1; i < argc; ++i) {
        auto value = mini::parse(argv[i]);
        if (value) {
            std::cout << *value << "\n";
        } else {
            std::cout << "<no value>\n";
        }
    }
    return 0;
}
