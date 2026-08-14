#pragma once

// 內建的 `_type: "exec"` 解析器。spec.cpp 建註冊表時直接放進去 ——
// 用「靜態物件自己去登記」那招的話，static library 有可能整個 TU 被丟掉，
// 症狀是「exec 型的 spec 讀不起來，但只在 release 建置發生」。
#include "aos/tooljson/spec.hpp"

#include <expected>
#include <memory>
#include <string>

namespace aos::tooljson {

[[nodiscard]] std::expected<std::shared_ptr<Body>, std::string> make_exec_body(
    const Spec& spec);

}  // namespace aos::tooljson
