#include "aos/llm/caps.hpp"

#include <algorithm>
#include <array>
#include <format>
#include <ranges>

namespace aos::llm {
namespace {

// 名字與欄位的對照只寫在這一張表裡。names() 和 get() 都從它長出來，
// 才不會出現「加了一個能力，卻忘了更新 names()」這種對不起來的事。
struct Entry {
    std::string_view name;
    std::optional<bool> Caps::* field;
};

constexpr std::array<Entry, 7> entries{{
    {"tools", &Caps::tools},
    {"tool_choice", &Caps::tool_choice},
    {"parallel_tools", &Caps::parallel_tools},
    {"vision", &Caps::vision},
    {"reasoning", &Caps::reasoning},
    {"json_schema", &Caps::json_schema},
    {"caching", &Caps::caching},
}};

}  // namespace

std::expected<std::optional<bool>, std::string> Caps::get(
    std::string_view name) const {
    const auto match = std::ranges::find(entries, name, &Entry::name);
    if (match == entries.end()) {
        std::string known;
        for (const Entry& entry : entries) {
            if (!known.empty()) {
                known += "、";
            }
            known += entry.name;
        }
        return std::unexpected{
            std::format("不認得的能力名稱 {}，可用的是 {}", name, known)};
    }
    return this->*(match->field);
}

Caps Caps::overlay(const Caps& remote, const Caps& override_) {
    Caps result = remote;
    for (const Entry& entry : entries) {
        if ((override_.*(entry.field)).has_value()) {
            result.*(entry.field) = override_.*(entry.field);
        }
    }
    return result;
}

std::span<const std::string_view> Caps::names() {
    static const std::array<std::string_view, entries.size()> table = [] {
        std::array<std::string_view, entries.size()> out{};
        for (std::size_t index = 0; index < entries.size(); ++index) {
            out[index] = entries[index].name;
        }
        return out;
    }();
    return table;
}

}  // namespace aos::llm
