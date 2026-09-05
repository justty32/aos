#include "parse.hpp"

namespace mini {

std::string parse(const std::string &line) {
    auto pos = line.find('=');
    if (pos == std::string::npos) return std::string();
    return line.substr(pos + 1);
}

}  // namespace mini
