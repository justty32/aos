#include <aos/tooljson.hpp>

#include "spec_internal.hpp"
#include "tooljson_internal.hpp"

#include <set>
#include <utility>

namespace aos::tooljson {

using detail::fail;

namespace {

using json = nlohmann::json;

bool nonempty_string(const json &value) {
    return value.is_string() && !value.get_ref<const std::string &>().empty();
}

SpecState validate_parameters(const json &function, json &properties,
                              std::vector<std::string> &required,
                              std::string &message) {
    const auto description = function.find("description");
    if (description != function.end() && !description->is_string()) {
        return fail(SpecState::InvalidFormat,
                    "function.description 要是字串", message);
    }

    const auto parameters_it = function.find("parameters");
    if (parameters_it == function.end()) {
        properties = json::object();
        required.clear();
        return SpecState::Ok;
    }
    const json &parameters = *parameters_it;
    if (!parameters.is_object()) {
        return fail(SpecState::InvalidFormat,
                    "function.parameters 要是 object", message);
    }

    const auto type = parameters.find("type");
    if (type != parameters.end() &&
        (!type->is_string() || type->get_ref<const std::string &>() != "object")) {
        return fail(SpecState::InvalidFormat,
                    "function.parameters.type 只能是 'object'", message);
    }

    const auto props = parameters.find("properties");
    if (props == parameters.end()) {
        properties = json::object();
    } else if (!props->is_object()) {
        return fail(SpecState::InvalidFormat,
                    "function.parameters.properties 要是 object", message);
    } else {
        for (auto it = props->begin(); it != props->end(); ++it) {
            if (it.key().empty() || !it.value().is_object()) {
                return fail(
                    SpecState::InvalidFormat,
                    "function.parameters.properties 要把非空參數名映到 schema object",
                    message);
            }
        }
        properties = *props;
    }

    const auto required_it = parameters.find("required");
    if (required_it == parameters.end()) {
        required.clear();
        return SpecState::Ok;
    }
    if (!required_it->is_array()) {
        return fail(SpecState::InvalidFormat,
                    "function.parameters.required 要是非空字串 list", message);
    }

    std::set<std::string> seen;
    required.clear();
    for (const json &name : *required_it) {
        if (!nonempty_string(name)) {
            return fail(SpecState::InvalidFormat,
                        "function.parameters.required 要是非空字串 list",
                        message);
        }
        const std::string value = name.get<std::string>();
        if (!seen.insert(value).second) {
            return fail(SpecState::InvalidFormat,
                        "function.parameters.required 不可有重複名稱",
                        message);
        }
        required.push_back(value);
    }

    std::vector<std::string> unknown;
    for (const std::string &name : required) {
        if (!properties.contains(name)) {
            unknown.push_back(name);
        }
    }
    if (!unknown.empty()) {
        return fail(SpecState::InvalidFormat,
                    "function.parameters.required 有未知參數 " +
                        detail::string_list_repr(unknown),
                    message);
    }
    return SpecState::Ok;
}
}  // namespace

namespace detail {

SpecState parse_one(const json &data, const std::string &source_path,
                    const std::string &base_dir, Spec &out,
                    std::string &message) {
    if (!data.is_object()) {
        return fail(SpecState::InvalidFormat,
                    "最外層要是 {\"type\": \"function\", ...}", message);
    }
    const auto type = data.find("type");
    if (type == data.end() || !type->is_string() ||
        type->get_ref<const std::string &>() != "function") {
        return fail(SpecState::InvalidFormat,
                    "最外層要是 {\"type\": \"function\", ...}", message);
    }

    const auto function = data.find("function");
    if (function == data.end() || !function->is_object()) {
        return fail(SpecState::InvalidFormat,
                    "function.name 缺了或不是非空字串", message);
    }
    const auto name = function->find("name");
    if (name == function->end() || !nonempty_string(*name)) {
        return fail(SpecState::InvalidFormat,
                    "function.name 缺了或不是非空字串", message);
    }

    const auto extra = data.find("_extra");
    if (extra == data.end() || !extra->is_object()) {
        return fail(SpecState::InvalidFormat,
                    "_extra 缺了；沒有它這份 JSON 只是 schema，跑不起來",
                    message);
    }
    const json null;
    const auto version = extra->find("_version");
    if (version == extra->end() || !version->is_string() ||
        version->get_ref<const std::string &>() != kVersion) {
        const json &got = version == extra->end() ? null : *version;
        return fail(SpecState::InvalidFormat,
                    "_extra._version 是 " + detail::json_repr(got) +
                        "，這支只認得 '0.1.0'",
                    message);
    }

    const auto kind = extra->find("_type");
    const std::string kind_value =
        kind != extra->end() && kind->is_string()
            ? kind->get<std::string>()
            : std::string();
    Parser parser;
    if (kind == extra->end() || !kind->is_string() || kind_value.empty() ||
        detail::find_parser(kind_value, parser) != SpecState::Ok) {
        const json &got = kind == extra->end() ? null : *kind;
        return fail(
            SpecState::UnknownType,
            "_extra._type 是 " + detail::json_repr(got) +
                "，目前登記的只有 " + detail::type_list_repr() +
                "。自己的執行方式用 tooljson::register_type() 加進來",
            message);
    }

    auto impl = std::make_shared<Spec::Impl>();
    impl->data = data;
    impl->function = *function;
    impl->extra = *extra;
    impl->name = name->get<std::string>();
    impl->kind = kind_value;
    impl->source_path = source_path;
    impl->base_dir = base_dir;
    SpecState state = validate_parameters(*function, impl->properties,
                                          impl->required, message);
    if (state != SpecState::Ok) {
        return state;
    }

    Spec shell = detail::SpecAccess::make(impl);
    BodyPtr body;
    state = parser(shell, body, message);
    if (state != SpecState::Ok) {
        return state;
    }
    if (!body) {
        return fail(SpecState::InvalidFormat,
                    "'" + kind_value + "' 的解析器沒有回傳 body", message);
    }
    impl->body = std::move(body);
    out = std::move(shell);
    return SpecState::Ok;
}

}  // namespace detail
}  // namespace aos::tooljson
