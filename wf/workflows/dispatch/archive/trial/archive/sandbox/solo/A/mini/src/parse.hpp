#pragma once
#include <string>
#include <optional>

namespace mini {

// 解析 "key=value"，找不到 '=' 時回傳 std::nullopt。
std::optional<std::string> parse(const std::string &line);

}  // namespace mini
