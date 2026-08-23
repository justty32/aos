#include <aos/tooljson.hpp>

#include "tooljson_internal.hpp"

#include <cerrno>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <set>
#include <system_error>
#include <utility>

namespace aos::tooljson {
namespace {

using json = nlohmann::json;
constexpr const char *kVersion = "0.1.0";

SpecState fail(SpecState state, std::string text, std::string &message) {
    message = std::move(text);
    return state;
}

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

SpecState load_all_impl(const char *data, std::size_t size,
                        const std::string &source_path,
                        const std::string &base_dir, std::vector<Spec> &out,
                        std::string &message) {
    out.clear();
    message.clear();
    if (data == nullptr) {
        return fail(SpecState::InvalidArgument,
                    "JSON 資料指標不可是 null", message);
    }

    json document;
    try {
        document = json::parse(data, data + size);
    } catch (const json::parse_error &error) {
        return fail(SpecState::JsonSyntax,
                    (source_path.empty() ? std::string("JSON 讀不起來：")
                                         : source_path + " 讀不起來：") +
                        error.what(),
                    message);
    }

    const bool array = document.is_array();
    const std::size_t count = array ? document.size() : 1;
    if (array && count == 0) {
        return fail(SpecState::InvalidFormat,
                    (source_path.empty() ? std::string("這份 JSON") : source_path) +
                        " 是空的 array，一個 tool 都沒有",
                    message);
    }

    std::vector<Spec> parsed;
    parsed.reserve(count);
    for (std::size_t index = 0; index < count; ++index) {
        const json &one = array ? document[index] : document;
        Spec spec;
        std::string detail_message;
        const SpecState state = parse_one(one, source_path, base_dir, spec,
                                          detail_message);
        if (state != SpecState::Ok) {
            const std::string prefix = source_path.empty() ? std::string()
                                                            : source_path + " ";
            return fail(state, prefix + "第 " + std::to_string(index + 1) +
                                   " 個：" + detail_message,
                        message);
        }
        parsed.push_back(std::move(spec));
    }

    std::map<std::string, std::size_t> counts;
    for (const Spec &spec : parsed) {
        ++counts[spec.name()];
    }
    std::vector<std::string> duplicates;
    for (const auto &[name, count_value] : counts) {
        if (count_value > 1) {
            duplicates.push_back(name);
        }
    }
    if (!duplicates.empty()) {
        return fail(SpecState::DuplicateName,
                    (source_path.empty() ? std::string("這份 JSON") : source_path) +
                        " 裡有重複的 function.name " +
                        detail::string_list_repr(duplicates),
                    message);
    }

    out.swap(parsed);
    return SpecState::Ok;
}

SpecState read_file(const char *path, std::string &data,
                    std::string &absolute, std::string &message) {
    if (path == nullptr || path[0] == '\0') {
        return fail(SpecState::InvalidArgument,
                    "spec 路徑要是非空字串", message);
    }
    std::error_code error;
    absolute = std::filesystem::absolute(path, error).lexically_normal().string();
    if (error) {
        return fail(SpecState::IoError,
                    std::string(path) + " 讀不起來：" + error.message(),
                    message);
    }

    errno = 0;
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        const int saved = errno;
        return fail(SpecState::IoError,
                    std::string(path) + " 讀不起來：" +
                        (saved == 0 ? "無法開啟檔案" : std::strerror(saved)),
                    message);
    }
    data.assign(std::istreambuf_iterator<char>(input),
                std::istreambuf_iterator<char>());
    if (input.bad()) {
        return fail(SpecState::IoError,
                    std::string(path) + " 讀不起來：讀取失敗", message);
    }
    return SpecState::Ok;
}

}  // namespace

namespace detail {

std::string json_repr(const nlohmann::json &value) {
    if (value.is_string()) {
        return "'" + value.get<std::string>() + "'";
    }
    if (value.is_null()) {
        return "None";
    }
    if (value.is_boolean()) {
        return value.get<bool>() ? "True" : "False";
    }
    return value.dump(-1, ' ', false, json::error_handler_t::replace);
}

std::string resolve_path(const std::string &value,
                         const std::string &base_dir) {
    const std::filesystem::path path(value);
    if (path.is_absolute()) {
        return path.lexically_normal().string();
    }
    return (std::filesystem::path(base_dir) / path).lexically_normal().string();
}

}  // namespace detail

const char *to_string(SpecState state) noexcept {
    switch (state) {
    case SpecState::Ok: return "Ok";
    case SpecState::InvalidArgument: return "InvalidArgument";
    case SpecState::JsonSyntax: return "JsonSyntax";
    case SpecState::InvalidFormat: return "InvalidFormat";
    case SpecState::UnknownType: return "UnknownType";
    case SpecState::DuplicateName: return "DuplicateName";
    case SpecState::IoError: return "IoError";
    }
    return "Unknown";
}

const char *format_version() noexcept { return kVersion; }

Spec::Spec() noexcept = default;
Spec::Spec(std::shared_ptr<const Impl> impl) noexcept : impl_(std::move(impl)) {}
Spec::Spec(const Spec &) noexcept = default;
Spec::Spec(Spec &&) noexcept = default;
Spec &Spec::operator=(const Spec &) noexcept = default;
Spec &Spec::operator=(Spec &&) noexcept = default;
Spec::~Spec() = default;

Spec::operator bool() const noexcept { return impl_ != nullptr; }

std::string Spec::name() const { return impl_ ? impl_->name : std::string(); }

std::string Spec::description() const {
    if (!impl_) return {};
    const auto found = impl_->function.find("description");
    return found != impl_->function.end() && found->is_string()
               ? found->get<std::string>()
               : std::string();
}

std::string Spec::type() const { return impl_ ? impl_->kind : std::string(); }

std::string Spec::path() const {
    return impl_ ? impl_->source_path : std::string();
}

std::string Spec::schema_json() const {
    if (!impl_) return {};
    json schema = {{"type", "function"}, {"function", impl_->function}};
    return schema.dump(-1, ' ', false, json::error_handler_t::replace);
}

std::string Spec::extra_json() const {
    return impl_ ? impl_->extra.dump(-1, ' ', false,
                                     json::error_handler_t::replace)
                 : std::string();
}

std::string Spec::run(const char *args_json, std::size_t size) const {
    if (!impl_ || !impl_->body) {
        return "Error: invalid tool spec";
    }
    return impl_->body->run(args_json, size);
}

std::string Spec::target() const {
    return impl_ && impl_->body ? impl_->body->target() : std::string();
}

std::optional<bool> Spec::stale() const {
    if (!impl_ || !impl_->body) return std::nullopt;
    const auto source = impl_->extra.find("source");
    if (source == impl_->extra.end() || !source->is_object()) {
        return std::nullopt;
    }
    const auto old = source->find("sha256");
    if (old == source->end() || !old->is_string() ||
        old->get_ref<const std::string &>().empty()) {
        return std::nullopt;
    }
    const std::string path_value = impl_->body->target();
    if (path_value.empty()) return std::nullopt;
    const std::optional<std::string> current = detail::sha256_file(path_value);
    return current ? std::optional<bool>(*current != old->get<std::string>())
                   : std::nullopt;
}

SpecState load_all(const char *data, std::size_t size, const char *base_dir,
                   std::vector<Spec> &out, std::string &message) {
    std::error_code error;
    std::filesystem::path base =
        base_dir == nullptr ? std::filesystem::current_path(error)
                            : std::filesystem::path(base_dir);
    if (error) {
        out.clear();
        return fail(SpecState::IoError,
                    "目前工作目錄讀不起來：" + error.message(), message);
    }
    if (!base.is_absolute()) {
        base = std::filesystem::absolute(base, error);
    }
    if (error) {
        out.clear();
        return fail(SpecState::IoError,
                    "base_dir 讀不起來：" + error.message(), message);
    }
    return load_all_impl(data, size, {}, base.lexically_normal().string(), out,
                         message);
}

SpecState load(const char *data, std::size_t size, const char *base_dir,
               Spec &out, std::string &message) {
    out = Spec{};
    std::vector<Spec> found;
    SpecState state = load_all(data, size, base_dir, found, message);
    if (state != SpecState::Ok) return state;
    if (found.size() != 1) {
        return fail(SpecState::InvalidFormat,
                    "這份 JSON 裡有 " + std::to_string(found.size()) +
                        " 個 tool，用 load_all() 讀",
                    message);
    }
    out = std::move(found.front());
    return SpecState::Ok;
}

SpecState load_all(const char *path, std::vector<Spec> &out,
                   std::string &message) {
    out.clear();
    std::string data;
    std::string absolute;
    SpecState state = read_file(path, data, absolute, message);
    if (state != SpecState::Ok) return state;
    const std::filesystem::path file(absolute);
    return load_all_impl(data.data(), data.size(), path, file.parent_path().string(),
                         out, message);
}

SpecState load(const char *path, Spec &out, std::string &message) {
    out = Spec{};
    std::vector<Spec> found;
    SpecState state = load_all(path, found, message);
    if (state != SpecState::Ok) return state;
    if (found.size() != 1) {
        return fail(SpecState::InvalidFormat,
                    std::string(path) + " 裡有 " +
                        std::to_string(found.size()) +
                        " 個 tool，用 load_all() 讀",
                    message);
    }
    out = std::move(found.front());
    return SpecState::Ok;
}

SpecState load_all(const std::vector<std::string> &paths,
                   std::vector<Spec> &out, std::string &message) {
    out.clear();
    message.clear();
    std::set<std::string> names;
    std::vector<Spec> merged;
    for (const std::string &path : paths) {
        std::vector<Spec> one_file;
        SpecState state = load_all(path.c_str(), one_file, message);
        if (state != SpecState::Ok) return state;
        for (Spec &spec : one_file) {
            if (names.insert(spec.name()).second) {
                merged.push_back(std::move(spec));
            }
        }
    }
    out.swap(merged);
    return SpecState::Ok;
}

SpecState save(const char *data, std::size_t size, const char *path,
               std::string &message) {
    message.clear();
    if (data == nullptr || path == nullptr || path[0] == '\0') {
        return fail(SpecState::InvalidArgument,
                    "JSON 資料與輸出路徑不可是 null 或空字串", message);
    }

    json value;
    try {
        value = json::parse(data, data + size);
    } catch (const json::parse_error &error) {
        return fail(SpecState::JsonSyntax,
                    std::string("JSON 讀不起來：") + error.what(), message);
    }

    std::error_code error;
    const std::filesystem::path output(path);
    const std::filesystem::path parent =
        std::filesystem::absolute(output, error).parent_path();
    if (error) {
        return fail(SpecState::IoError,
                    std::string(path) + " 寫不出去：" + error.message(),
                    message);
    }
    std::filesystem::create_directories(parent, error);
    if (error) {
        return fail(SpecState::IoError,
                    std::string(path) + " 寫不出去：" + error.message(),
                    message);
    }

    errno = 0;
    std::ofstream stream(path, std::ios::binary | std::ios::trunc);
    if (!stream) {
        const int saved = errno;
        return fail(SpecState::IoError,
                    std::string(path) + " 寫不出去：" +
                        (saved == 0 ? "無法開啟檔案" : std::strerror(saved)),
                    message);
    }
    stream << value.dump(2, ' ', false, json::error_handler_t::replace) << '\n';
    if (!stream) {
        return fail(SpecState::IoError,
                    std::string(path) + " 寫不出去：寫入失敗", message);
    }
    return SpecState::Ok;
}

}  // namespace aos::tooljson
