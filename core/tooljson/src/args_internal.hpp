#pragma once

/* argv 展開共用的單值處理（args_value.cpp 實作，args.cpp 使用）。 */

#include "tooljson_internal.hpp"

#include <string>

namespace aos::tooljson::detail {

/* 把一個 JSON 值轉成要放進 argv 的字串。 */
std::string render(const nlohmann::json &value);
/* 模型常把數字包成字串；照 schema 宣告的型別就地轉回來。 */
bool coerce(nlohmann::json &value, const std::string &wanted);
std::string schema_type(const nlohmann::json &properties,
                        const std::string &name);
bool truthy(const nlohmann::json &value);
/* 回報型別錯誤時用的 Python 風格型別名。 */
std::string json_type_name(const nlohmann::json &value);
bool numeric(const nlohmann::json &value, long double &out);

}  // namespace aos::tooljson::detail
