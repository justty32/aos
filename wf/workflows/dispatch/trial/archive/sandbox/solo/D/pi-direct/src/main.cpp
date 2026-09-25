#include "parse.hpp"
#include <iostream>

int main(int argc, char **argv) {
    for (int i = 1; i < argc; ++i) {
        std::cout << mini::parse(argv[i]) << "\n";
    }
    return 0;
}
