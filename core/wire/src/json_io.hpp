#pragma once

#include <cstdint>
#include <limits>
#include <map>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include <nlohmann/json.hpp>

namespace aos::wire::detail {

using Json = nlohmann::ordered_json;

inline bool fail_field(const std::string &key, const std::string &reason,
                       std::string &error) {
    error = "欄位 '" + key + "' " + reason;
    return false;
}

inline bool parse_object(const std::string &text, Json &object,
                         std::string &error) {
    try {
        object = Json::parse(text);
    } catch (const nlohmann::json::exception &exception) {
        error = std::string("JSON 解析失敗: ") + exception.what();
        return false;
    }
    if (!object.is_object()) {
        error = "JSON 頂層必須是物件";
        return false;
    }
    return true;
}

inline bool take_string(const Json &object, const std::string &key,
                        std::string &out, std::string &error,
                        bool required = true) {
    const auto item = object.find(key);
    if (item == object.end()) {
        return required ? fail_field(key, "不可缺席", error) : true;
    }
    if (!item->is_string()) {
        return fail_field(key, "必須是字串", error);
    }
    out = item->get<std::string>();
    return true;
}

inline bool take_uint(const Json &object, const std::string &key,
                      std::uint64_t &out, std::string &error,
                      bool required = true) {
    const auto item = object.find(key);
    if (item == object.end()) {
        return required ? fail_field(key, "不可缺席", error) : true;
    }
    if (!item->is_number_unsigned()) {
        return fail_field(key, "必須是非負整數", error);
    }
    out = item->get<std::uint64_t>();
    return true;
}

inline bool take_string_array(const Json &object, const std::string &key,
                              std::vector<std::string> &out,
                              std::string &error, bool required = true) {
    const auto item = object.find(key);
    if (item == object.end()) {
        return required ? fail_field(key, "不可缺席", error) : true;
    }
    if (!item->is_array()) {
        return fail_field(key, "必須是字串陣列", error);
    }
    std::vector<std::string> values;
    values.reserve(item->size());
    for (const Json &value : *item) {
        if (!value.is_string()) {
            return fail_field(key, "必須是字串陣列", error);
        }
        values.push_back(value.get<std::string>());
    }
    out = std::move(values);
    return true;
}

inline bool take_string_map(const Json &object, const std::string &key,
                            std::map<std::string, std::string> &out,
                            std::string &error, bool required = true) {
    const auto item = object.find(key);
    if (item == object.end()) {
        return required ? fail_field(key, "不可缺席", error) : true;
    }
    if (!item->is_object()) {
        return fail_field(key, "必須是字串值物件", error);
    }
    std::map<std::string, std::string> values;
    for (const auto &[name, value] : item->items()) {
        if (!value.is_string()) {
            return fail_field(key, "的所有值都必須是字串", error);
        }
        values.emplace(name, value.get<std::string>());
    }
    out = std::move(values);
    return true;
}

inline bool take_opt_int(const Json &object, const std::string &key,
                         std::optional<int> &out, std::string &error) {
    const auto item = object.find(key);
    if (item == object.end() || item->is_null()) {
        out.reset();
        return true;
    }
    if (item->is_number_unsigned()) {
        const std::uint64_t value = item->get<std::uint64_t>();
        if (value > static_cast<std::uint64_t>(std::numeric_limits<int>::max())) {
            return fail_field(key, "超出 int 範圍", error);
        }
        out = static_cast<int>(value);
        return true;
    }
    if (!item->is_number_integer()) {
        return fail_field(key, "必須是整數或 null", error);
    }
    const std::int64_t value = item->get<std::int64_t>();
    if (value < std::numeric_limits<int>::min() ||
        value > std::numeric_limits<int>::max()) {
        return fail_field(key, "超出 int 範圍", error);
    }
    out = static_cast<int>(value);
    return true;
}

inline bool take_nullable_int64(const Json &object, const std::string &key,
                                std::int64_t &out, std::string &error) {
    const auto item = object.find(key);
    if (item == object.end() || item->is_null()) {
        out = -1;
        return true;
    }
    if (item->is_number_unsigned()) {
        const std::uint64_t value = item->get<std::uint64_t>();
        if (value > static_cast<std::uint64_t>(
                        std::numeric_limits<std::int64_t>::max())) {
            return fail_field(key, "超出 int64 範圍", error);
        }
        out = static_cast<std::int64_t>(value);
        return true;
    }
    if (!item->is_number_integer()) {
        return fail_field(key, "必須是整數或 null", error);
    }
    out = item->get<std::int64_t>();
    return true;
}

inline std::string dump_text(const Json &value) {
    return value.dump(2, ' ', false, Json::error_handler_t::replace) + '\n';
}

}  // namespace aos::wire::detail
