#pragma once

/* spec 載入路徑（spec.cpp / spec_parse.cpp / spec_load.cpp）共用的內部宣告。 */

#include "tooljson_internal.hpp"

#include <string>
#include <utility>

namespace aos::tooljson::detail {

constexpr const char *kVersion = "0.1.0";

/* 把訊息塞進 out 參數再回傳狀態碼，載入路徑上到處都在用。 */
inline SpecState fail(SpecState state, std::string text, std::string &message) {
    message = std::move(text);
    return state;
}

/* 解析單一個 {"type": "function", ...} 物件成一份 Spec。 */
SpecState parse_one(const nlohmann::json &data, const std::string &source_path,
                    const std::string &base_dir, Spec &out,
                    std::string &message);

}  // namespace aos::tooljson::detail
