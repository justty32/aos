#include <aos/tooljson.hpp>

#include "tooljson_internal.hpp"

#include <map>
#include <mutex>
#include <utility>

namespace aos::tooljson {
namespace {

std::map<std::string, Parser> &parsers() {
    static std::map<std::string, Parser> value;
    return value;
}

std::mutex &parser_mutex() {
    static std::mutex value;
    return value;
}

}  // namespace

Body::~Body() = default;

SpecState register_type(const std::string &type, Parser parser,
                        std::string &message) {
    message.clear();
    if (type.empty()) {
        message = "_type 要是非空字串，拿到 ''";
        return SpecState::InvalidArgument;
    }
    if (!parser) {
        message = "'" + type + "' 的解析器要是 callable，拿到空解析器";
        return SpecState::InvalidArgument;
    }

    std::lock_guard lock(parser_mutex());
    parsers()[type] = std::move(parser);
    return SpecState::Ok;
}

std::vector<std::string> registered_types() {
    std::lock_guard lock(parser_mutex());
    std::vector<std::string> out;
    out.reserve(parsers().size());
    for (const auto &[type, unused] : parsers()) {
        static_cast<void>(unused);
        out.push_back(type);
    }
    return out;
}

namespace detail {

SpecState find_parser(const std::string &kind, Parser &out) {
    std::lock_guard lock(parser_mutex());
    const auto found = parsers().find(kind);
    if (found == parsers().end()) {
        out = {};
        return SpecState::UnknownType;
    }
    out = found->second;
    return SpecState::Ok;
}

std::string string_list_repr(const std::vector<std::string> &values) {
    std::string out = "[";
    for (std::size_t index = 0; index < values.size(); ++index) {
        if (index != 0) {
            out += ", ";
        }
        out += "'" + values[index] + "'";
    }
    out += "]";
    return out;
}

std::string type_list_repr() {
    return string_list_repr(registered_types());
}

}  // namespace detail
}  // namespace aos::tooljson
