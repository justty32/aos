#include <aos/tooljson.hpp>

#include "args_internal.hpp"
#include "tooljson_internal.hpp"

#include <algorithm>
#include <cctype>
#include <cerrno>
#include <charconv>
#include <cmath>
#include <cstdlib>
#include <string>
#include <string_view>

namespace aos::tooljson {
namespace {

using json = nlohmann::json;

std::string_view trim(std::string_view text) {
    while (!text.empty() &&
           (text.front() == ' ' || text.front() == '\t' ||
            text.front() == '\n' || text.front() == '\r' ||
            text.front() == '\f' || text.front() == '\v')) {
        text.remove_prefix(1);
    }
    while (!text.empty() &&
           (text.back() == ' ' || text.back() == '\t' ||
            text.back() == '\n' || text.back() == '\r' ||
            text.back() == '\f' || text.back() == '\v')) {
        text.remove_suffix(1);
    }
    return text;
}
}  // namespace

namespace detail {

std::string render(const json &value) {
    if (value.is_string()) return value.get<std::string>();
    if (value.is_boolean()) return value.get<bool>() ? "true" : "false";
    return value.dump(-1, ' ', false, json::error_handler_t::replace);
}

bool coerce(json &value, const std::string &wanted) {
    if (!value.is_string()) return true;
    const std::string original = value.get<std::string>();
    std::string_view text = trim(original);

    if (wanted == "integer") {
        bool positive_sign = false;
        if (!text.empty() && text.front() == '+') {
            positive_sign = true;
            text.remove_prefix(1);
        }
        if (text.empty()) return false;
        if (!text.empty() && text.front() == '-') {
            std::int64_t parsed = 0;
            const auto result =
                std::from_chars(text.data(), text.data() + text.size(), parsed);
            if (result.ec != std::errc() || result.ptr != text.data() + text.size()) {
                return false;
            }
            value = parsed;
            return true;
        }
        std::uint64_t parsed = 0;
        const auto result =
            std::from_chars(text.data(), text.data() + text.size(), parsed);
        if (result.ec != std::errc() || result.ptr != text.data() + text.size()) {
            return false;
        }
        static_cast<void>(positive_sign);
        value = parsed;
        return true;
    }
    if (wanted == "number") {
        std::string owned(text);
        if (owned.empty()) return false;
        char *end = nullptr;
        errno = 0;
        const double parsed = std::strtod(owned.c_str(), &end);
        if (end == owned.c_str() || end != owned.c_str() + owned.size() ||
            errno == ERANGE ||
            !std::isfinite(parsed)) {
            return false;
        }
        value = parsed;
        return true;
    }
    if (wanted == "boolean") {
        std::string lowered(text);
        std::transform(lowered.begin(), lowered.end(), lowered.begin(),
                       [](unsigned char byte) {
                           return static_cast<char>(std::tolower(byte));
                       });
        if (lowered == "true") {
            value = true;
            return true;
        }
        if (lowered == "false") {
            value = false;
            return true;
        }
        return false;
    }
    return true;
}

std::string schema_type(const json &properties, const std::string &name) {
    const auto property = properties.find(name);
    if (property == properties.end() || !property->is_object()) return {};
    const auto type = property->find("type");
    return type != property->end() && type->is_string()
               ? type->get<std::string>()
               : std::string();
}

bool truthy(const json &value) {
    if (value.is_null()) return false;
    if (value.is_boolean()) return value.get<bool>();
    if (value.is_number_unsigned()) return value.get<std::uint64_t>() != 0;
    if (value.is_number_integer()) return value.get<std::int64_t>() != 0;
    if (value.is_number_float()) return value.get<double>() != 0.0;
    if (value.is_string() || value.is_array() || value.is_object()) {
        return !value.empty();
    }
    return true;
}

std::string json_type_name(const json &value) {
    if (value.is_object()) return "dict";
    if (value.is_array()) return "list";
    if (value.is_string()) return "str";
    if (value.is_boolean()) return "bool";
    if (value.is_number_integer() || value.is_number_unsigned()) return "int";
    if (value.is_number_float()) return "float";
    if (value.is_null()) return "NoneType";
    return value.type_name();
}

bool numeric(const json &value, long double &out) {
    if (value.is_boolean() || !value.is_number()) return false;
    if (value.is_number_unsigned()) {
        out = value.get<std::uint64_t>();
    } else if (value.is_number_integer()) {
        out = value.get<std::int64_t>();
    } else {
        out = value.get<double>();
    }
    return true;
}
}  // namespace detail
}  // namespace aos::tooljson
