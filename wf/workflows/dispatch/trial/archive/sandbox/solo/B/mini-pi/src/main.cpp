#include "parse.hpp"
#include <iostream>

int main(int argc, char **argv) {
    for (int i = 1; i < argc; ++i) {
        const auto value = mini::parse(argv[i]);
        std::cout << value.value_or("") << "\n";
    }
    return 0;
}
