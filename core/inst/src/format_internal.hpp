#pragma once

// format 層內部標頭：不對外，只給 format_*.cpp 彼此看。
// 這裡只放 format 層自己的東西——它是唯一懂 instruction JSON schema 的層，
// 不可以引用 handoff／resolve／exec。

#include <aos/inst.hpp>

#include <nlohmann/json.hpp>

#include <cstddef>
#include <string_view>

namespace aos::detail {

// 在 inst.pending_directives 裡找出指定位置尚未解析的指示詞，沒有就回 nullptr。
const PendingDirective *find_directive(const inst_t &inst,
                                       DirectiveField field,
                                       std::size_t argv_index = 0,
                                       std::string_view env_key = {});

// inst_t → JSON。未解析的指示詞照原樣寫回，所以能無損 round trip。
nlohmann::ordered_json encode(const inst_t &inst);

// JSON → inst_t。成功時以 validate() 的結果作為回傳值。
InstState decode(const nlohmann::json &value, inst_t &inst);

}  // namespace aos::detail
