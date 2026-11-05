#include <aos/tick.hpp>

#include <algorithm>
#include <cstdint>

namespace aos::tick {
namespace {

std::string base36(std::uint64_t value) {
    constexpr std::string_view digits = "0123456789abcdefghijklmnopqrstuvwxyz";
    std::string result;
    do {
        result.push_back(digits[value % digits.size()]);
        value /= digits.size();
    } while (value != 0);
    std::reverse(result.begin(), result.end());
    return result;
}

bool contains(const std::vector<std::string> &taken, const std::string &id) {
    return std::find(taken.begin(), taken.end(), id) != taken.end();
}

}  // namespace

bool valid_id(std::string_view id) {
    if (id.empty() || id.size() > 64) return false;
    return std::all_of(id.begin(), id.end(), [](unsigned char ch) {
        return (ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z') ||
               (ch >= '0' && ch <= '9') || ch == '_' || ch == '.' ||
               ch == '-';
    });
}

std::string make_id(std::string_view prefix, Instant now,
                    const std::vector<std::string> &taken) {
    const std::string base = std::string(prefix) + '-' +
                             base36(static_cast<std::uint64_t>(now));
    if (!contains(taken, base)) return base;
    for (std::uint64_t suffix = 2;; ++suffix) {
        std::string candidate = base + '-' + std::to_string(suffix);
        if (!contains(taken, candidate)) return candidate;
    }
}

}  // namespace aos::tick
