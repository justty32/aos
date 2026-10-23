// internal.hpp：resolve.cpp、ref.cpp、env.cpp 之間共用的內部宣告（不公開；放在 aos::directive，公開的只有 aos::resolve）。
//
//   resolve.cpp  走遍整份 JSON、認出指示詞（有 $ref 看 $ref、否則有 $env 看 $env）、換完再接 $path／$prefix
//   ref.cpp      {"$ref": "檔[#/指標]"[, "$at": 指標]}
//   env.cpp      {"$env": "NAME"}
#pragma once

#include "aos/directive.hpp"

#include <optional>
#include <utility>
#include <vector>

namespace aos::directive {

// 正在解的 $ref 鏈：每一層是「實際的檔（realpath）＋指標」。指回鏈上同一個位置＝繞圈。
using Chain = std::vector<std::pair<std::string, std::string>>;

// 走一個值（遇到指示詞就換掉）。base＝這一層相對 $ref 的起點。
Json walk(const Json& v, const std::string& base, Chain& chain);

// {"$ref": …}（整個物件 d）→ 那個位置的值（已接著解完）；寫法不合回 nullopt（物件原封不動留著）。
std::optional<Json> resolve_ref(const Json& d, const std::string& base, Chain& chain);

// {"$env": …}（整個物件 d）→ 環境變數的值；名字不是非空字串回 nullopt；沒設丟 DirectiveBad。
std::optional<Json> resolve_env(const Json& d);

}  // namespace aos::directive
