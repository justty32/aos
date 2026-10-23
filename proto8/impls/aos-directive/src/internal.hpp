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

// {"$ref": …}（整個物件 d）→ 每一份的原文（還沒往下解）＋位置（檔＋指標，推上鏈用）：$ref 是字串＝一份；
// 是陣列（10-23 使用者）＝照順序每個元素一份（$at 接在每一份的指標後面）。寫法不合（含空陣列、有一個元素不合）回 nullopt。
// 讀不到、指不到、繞圈（here 已在 chain 上）丟 DirectiveBad。
struct Fetched {
    Json value;
    std::pair<std::string, std::string> here;
};
std::optional<std::vector<Fetched>> fetch_ref(const Json& d, const std::string& base, const Chain& chain);

// {"$ref": …}（整個物件 d）→ 那個位置的值（每一份接著解完、再合成一份）；寫法不合回 nullopt（物件原封不動留著）。
std::optional<Json> resolve_ref(const Json& d, const std::string& base, Chain& chain);

// $ref 陣列的幾份合成一份（10-23 使用者）：只有一份＝它本身；都是物件＝合 key（同名後面的蓋前面的，淺層、位置留在第一次出現的地方）；
// 都是陣列＝照順序接起來；其他（種類混在一起、兩份以上卻不是物件也不是陣列）＝DirectiveBad。
// 回的 Resolved 記著每個 key／元素來自哪份檔的資料夾（resolve_shallow 的呼叫者往下解時用）。
Resolved merge(std::vector<Resolved>& parts, const std::string& where);

// $path／$prefix：換出來的 got 是字串時照 d 的 $path 接上去、再加 $prefix；不是字串原樣回（D11）。
Json decorate(const Json& d, const Json& got);

// {"$env": …}（整個物件 d）→ 環境變數的值；名字不是非空字串回 nullopt；沒設丟 DirectiveBad。
std::optional<Json> resolve_env(const Json& d);

}  // namespace aos::directive
