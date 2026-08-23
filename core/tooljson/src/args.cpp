#include <aos/tooljson.hpp>

#include "tooljson_internal.hpp"

#include <algorithm>
#include <cerrno>
#include <cctype>
#include <charconv>
#include <cmath>
#include <cstdlib>
#include <map>
#include <set>
#include <string_view>

namespace aos::tooljson {
namespace {

using json = nlohmann::json;
constexpr std::size_t kArgMaxBytes = 128 * 1024;

std::string render(const json &value) {
    if (value.is_string()) return value.get<std::string>();
    if (value.is_boolean()) return value.get<bool>() ? "true" : "false";
    return value.dump(-1, ' ', false, json::error_handler_t::replace);
}

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

std::string check_limits(const detail::ExecBody &body,
                         const std::map<std::string, json> &arguments) {
    for (auto it = body.limits.begin(); it != body.limits.end(); ++it) {
        const auto value_it = arguments.find(it.key());
        if (value_it == arguments.end()) continue;
        const json &value = value_it->second;
        const json &rule = it.value();

        const auto cap = rule.find("max_bytes");
        if (cap != rule.end() && value.is_string()) {
            const std::uint64_t limit = cap->get<std::uint64_t>();
            const std::size_t bytes = value.get_ref<const std::string &>().size();
            if (bytes > limit) {
                return "Error: argument '" + it.key() + "' is " +
                       std::to_string(bytes) + " bytes, over the " +
                       std::to_string(limit) + " limit";
            }
        }

        long double number = 0;
        if (!numeric(value, number)) continue;
        const auto low = rule.find("min");
        if (low != rule.end()) {
            long double bound = 0;
            numeric(*low, bound);
            if (number < bound) {
                return "Error: argument '" + it.key() + "' is " +
                       render(value) + ", below the minimum " + render(*low);
            }
        }
        const auto high = rule.find("max");
        if (high != rule.end()) {
            long double bound = 0;
            numeric(*high, bound);
            if (number > bound) {
                return "Error: argument '" + it.key() + "' is " +
                       render(value) + ", above the maximum " + render(*high);
            }
        }
    }
    return {};
}

std::string push_one(const std::string &name, const json &value,
                     const detail::Binding &binding, bool boolean,
                     std::vector<std::string> &argv) {
    if (boolean && !binding.flag.empty()) {
        if (truthy(value)) argv.push_back(binding.flag);
        return {};
    }

    const std::string text = render(value);
    std::string item = text;
    if (!binding.flag.empty() && !binding.separate) {
        item = binding.flag + "=" + text;
    }
    if (item.size() > kArgMaxBytes) {
        return "Error: argument '" + name +
               "' is too long for the command line (" +
               std::to_string(item.size()) + " bytes, limit " +
               std::to_string(kArgMaxBytes) + ")";
    }

    if (binding.flag.empty()) {
        argv.push_back(std::move(item));
    } else if (binding.separate) {
        argv.push_back(binding.flag);
        argv.push_back(std::move(item));
    } else {
        argv.push_back(std::move(item));
    }
    return {};
}

}  // namespace

std::string expand_args(const Spec &spec, const char *args_json,
                        std::size_t size, ExpandedArgs &out) {
    out = ExpandedArgs{};
    if (args_json == nullptr) {
        return "Error: arguments JSON pointer must not be null";
    }

    json parsed;
    try {
        parsed = json::parse(args_json, args_json + size);
    } catch (const json::parse_error &error) {
        return std::string("Error: arguments must be valid JSON: ") + error.what();
    }
    if (!parsed.is_object()) {
        return "Error: arguments must be a JSON object, got " +
               json_type_name(parsed);
    }

    const Spec::Impl *impl = detail::SpecAccess::get(spec);
    if (impl == nullptr || !impl->body) {
        return "Error: invalid tool spec";
    }
    const auto body = std::dynamic_pointer_cast<const detail::ExecBody>(impl->body);
    if (!body) {
        return "Error: tool '" + impl->name + "' is not an exec tool";
    }

    std::map<std::string, json> arguments;
    std::vector<std::string> bad_types;
    for (auto it = parsed.begin(); it != parsed.end(); ++it) {
        json value = it.value();
        if (!coerce(value, schema_type(body->properties, it.key()))) {
            bad_types.push_back(it.key());
        }
        arguments.emplace(it.key(), std::move(value));
    }
    if (!bad_types.empty()) {
        return "Error: argument(s) " +
               [&bad_types] {
                   std::string joined;
                   for (std::size_t index = 0; index < bad_types.size(); ++index) {
                       if (index != 0) joined += ", ";
                       joined += bad_types[index];
                   }
                   return joined;
               }() +
               " have the wrong type";
    }

    for (auto it = arguments.begin(); it != arguments.end();) {
        if (it->second.is_null()) {
            it = arguments.erase(it);
        } else {
            ++it;
        }
    }

    std::vector<std::string> missing;
    for (const std::string &name : impl->required) {
        if (!arguments.contains(name)) missing.push_back(name);
    }
    if (!missing.empty()) {
        std::string joined;
        for (std::size_t index = 0; index < missing.size(); ++index) {
            if (index != 0) joined += ", ";
            joined += missing[index];
        }
        return "Error: missing required argument(s): " + joined;
    }

    std::vector<std::string> unknown;
    for (const auto &[name, unused] : arguments) {
        static_cast<void>(unused);
        if (!body->properties.contains(name)) unknown.push_back(name);
    }
    if (!unknown.empty()) {
        std::string unknown_joined;
        for (std::size_t index = 0; index < unknown.size(); ++index) {
            if (index != 0) unknown_joined += ", ";
            unknown_joined += unknown[index];
        }
        std::vector<std::string> accepted;
        for (auto it = body->properties.begin(); it != body->properties.end(); ++it) {
            accepted.push_back(it.key());
        }
        std::string accepted_joined;
        for (std::size_t index = 0; index < accepted.size(); ++index) {
            if (index != 0) accepted_joined += ", ";
            accepted_joined += accepted[index];
        }
        if (accepted_joined.empty()) accepted_joined = "(none)";
        return "Error: unknown argument(s): " + unknown_joined +
               ". This tool accepts: " + accepted_joined;
    }

    std::string error = check_limits(*body, arguments);
    if (!error.empty()) return error;

    out.argv = body->command;
    for (const detail::Binding &binding : body->bindings) {
        if (body->stdin_param && binding.name == *body->stdin_param) continue;
        const auto found = arguments.find(binding.name);
        if (found == arguments.end()) continue;
        const json &value = found->second;
        if (value.is_array() && !binding.repeat) {
            out = ExpandedArgs{};
            return "Error: argument '" + binding.name +
                   "' does not take a list of values";
        }
        const bool boolean =
            schema_type(body->properties, binding.name) == "boolean";
        if (binding.repeat && value.is_array()) {
            for (const json &item : value) {
                error = push_one(binding.name, item, binding, boolean, out.argv);
                if (!error.empty()) {
                    out = ExpandedArgs{};
                    return error;
                }
            }
        } else {
            error = push_one(binding.name, value, binding, boolean, out.argv);
            if (!error.empty()) {
                out = ExpandedArgs{};
                return error;
            }
        }
    }

    if (body->stdin_param) {
        const auto found = arguments.find(*body->stdin_param);
        if (found != arguments.end()) out.stdin_text = render(found->second);
    }
    return {};
}

}  // namespace aos::tooljson
