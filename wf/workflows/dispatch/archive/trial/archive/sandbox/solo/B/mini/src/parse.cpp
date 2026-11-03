#include "parse.hpp"

namespace mini {

std::optional<std::string> parse(const std::string &line) {
    auto pos = line.find('=');
    if (pos == std::string::npos) return std::nullopt;
    return line.substr(pos + 1);
}

}  // namespace mini
