#pragma once
#include <optional>
#include <string>

namespace mini {

// 解析 "key=value"，失敗時回傳 std::nullopt，成功時回傳值（可能是空字串）。
std::optional<std::string> parse(const std::string &line);

}  // namespace mini
