// spec 的外殼：讀寫、兩個保留鍵、把其餘的轉交給 `_type` 的解析器。
//
// **這個檔不知道有哪些 `_type`** —— 它去問註冊表，所以第三方登記的跟內建的
// `exec` 走同一條路，這裡一行都不用改。
#include "aos/tooljson/spec.hpp"

#include "tooljson/exec_body.hpp"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <fstream>
#include <format>
#include <map>
#include <set>
#include <utility>

namespace aos::tooljson {

// Spec 的側門，只有這個檔用得到（見 spec.hpp 的 friend 宣告）。
struct SpecAccess {
    static std::string& name(Spec& spec) { return spec.name_; }
    static std::string& kind(Spec& spec) { return spec.kind_; }
    static std::string& schema(Spec& spec) { return spec.schema_json_; }
    static std::string& extra(Spec& spec) { return spec.extra_json_; }
    static std::filesystem::path& directory(Spec& spec) {
        return spec.directory_;
    }
    static std::vector<Property>& properties(Spec& spec) {
        return spec.properties_;
    }
    static std::vector<std::string>& required(Spec& spec) {
        return spec.required_;
    }
};

namespace {

using nlohmann::json;

std::map<std::string, BodyParser, std::less<>>& parsers() {
    // 內建的兩件事都在這裡發生：建表、把 "exec" 放進去。
    // 內建的不是特權 —— register_type() 進來的走的是同一張表。
    static auto table = [] {
        std::map<std::string, BodyParser, std::less<>> initial;
        initial.emplace("exec", &make_exec_body);
        return initial;
    }();
    return table;
}

// 檢查不過就回一句話。分成一行一條，看得出總共檢查了什麼。
#define NEED(condition, message)                     \
    do {                                             \
        if (!(condition)) {                          \
            return std::unexpected{std::string(message)}; \
        }                                            \
    } while (false)

[[nodiscard]] std::expected<void, std::string> read_parameters(
    const json& function, std::vector<Property>& properties,
    std::vector<std::string>& required) {
    const auto found = function.find("parameters");
    if (found == function.end()) {
        return {};  // 沒有參數的工具是合法的
    }
    NEED(found->is_object(), "function.parameters 要是 object");

    const auto type = found->find("type");
    NEED(type == found->end() || *type == "object",
         "function.parameters.type 只能是 \"object\"");

    if (const auto props = found->find("properties"); props != found->end()) {
        NEED(props->is_object(), "function.parameters.properties 要是 object");
        for (const auto& [key, rule] : props->items()) {
            NEED(!key.empty() && rule.is_object(),
                 "properties 要把非空參數名映到一個 schema object");
            const auto rule_type = rule.find("type");
            properties.push_back(Property{
                .name = key,
                .type = rule_type != rule.end() && rule_type->is_string()
                            ? rule_type->get<std::string>()
                            : std::string{},
                .schema_json = rule.dump(),
            });
        }
    }

    if (const auto list = found->find("required"); list != found->end()) {
        NEED(list->is_array(), "function.parameters.required 要是 array");
        std::set<std::string> seen;
        for (const json& entry : *list) {
            NEED(entry.is_string() && !entry.get<std::string>().empty(),
                 "required 裡要是非空字串");
            auto name = entry.get<std::string>();
            NEED(seen.insert(name).second,
                 std::format("required 有重複的參數名 {}", name));
            NEED(std::ranges::any_of(properties,
                                     [&name](const Property& property) {
                                         return property.name == name;
                                     }),
                 std::format("required 列了 properties 裡沒有的 {}", name));
            required.push_back(std::move(name));
        }
    }
    return {};
}

[[nodiscard]] std::expected<Spec, std::string> make_spec(
    const json& data, const std::filesystem::path& directory) {
    NEED(data.is_object(), "每一份 spec 都要是一個 JSON object");

    const auto type = data.find("type");
    NEED(type != data.end() && *type == "function",
         "最外層要是 {\"type\": \"function\", ...}");

    const auto function = data.find("function");
    NEED(function != data.end() && function->is_object(),
         "缺了 function");
    const auto name = function->find("name");
    NEED(name != function->end() && name->is_string() &&
             !name->get<std::string>().empty(),
         "function.name 缺了或不是非空字串");
    if (const auto description = function->find("description");
        description != function->end()) {
        NEED(description->is_string(), "function.description 要是字串");
    }

    const auto extra = data.find("_extra");
    NEED(extra != data.end() && extra->is_object(),
         "缺了 _extra；沒有它這份 JSON 只是 schema，跑不起來");

    const auto version = extra->find("_version");
    NEED(version != extra->end() && version->is_string(),
         "_extra._version 缺了");
    NEED(version->get<std::string>() == format_version,
         std::format("_extra._version 是 {}，這支只認得 {}",
                     version->get<std::string>(), format_version));

    const auto kind = extra->find("_type");
    NEED(kind != extra->end() && kind->is_string(), "_extra._type 缺了");
    const auto kind_text = kind->get<std::string>();

    Spec spec;
    SpecAccess::name(spec) = name->get<std::string>();
    SpecAccess::kind(spec) = kind_text;
    SpecAccess::extra(spec) = extra->dump();
    SpecAccess::directory(spec) = directory;
    SpecAccess::schema(spec) =
        json{{"type", "function"}, {"function", *function}}.dump();

    if (auto parsed = read_parameters(*function, SpecAccess::properties(spec),
                                      SpecAccess::required(spec));
        !parsed) {
        return std::unexpected{parsed.error()};
    }

    const auto parser = parsers().find(kind_text);
    if (parser == parsers().end()) {
        std::string known;
        for (const std::string& one : registered_types()) {
            if (!known.empty()) {
                known += "、";
            }
            known += one;
        }
        return std::unexpected{std::format(
            "_extra._type 是 {}，目前登記的只有 {}。自己的執行方式用 "
            "register_type() 加進來",
            kind_text, known.empty() ? "（一個都沒有）" : known)};
    }

    auto body = parser->second(spec);
    if (!body) {
        return std::unexpected{body.error()};
    }
    spec.attach(std::move(*body));
    return spec;
}

#undef NEED

}  // namespace

void register_type(std::string kind, BodyParser parser) {
    parsers().insert_or_assign(std::move(kind), std::move(parser));
}

std::vector<std::string> registered_types() {
    std::vector<std::string> names;
    for (const auto& [kind, ignored] : parsers()) {
        names.push_back(kind);
    }
    return names;  // map 本來就是排好的
}

std::string Spec::run(std::string_view arguments_json) const {
    if (body_ == nullptr) {
        return std::format("Error: 工具 {} 沒有執行端", name_);
    }
    return body_->run(*this, arguments_json);
}

std::expected<std::vector<Spec>, std::string> load_all(
    const std::filesystem::path& path) {
    std::ifstream file{path};
    if (!file) {
        return std::unexpected{std::format("讀不到 {}", path.string())};
    }
    const json data = json::parse(file, nullptr, false);
    if (data.is_discarded()) {
        return std::unexpected{std::format("{} 不是合法的 JSON", path.string())};
    }

    const auto directory = std::filesystem::absolute(path).parent_path();
    const json items = data.is_array() ? data : json::array({data});
    if (items.empty()) {
        return std::unexpected{
            std::format("{} 是空的 array，一個 tool 都沒有", path.string())};
    }

    std::vector<Spec> specs;
    std::set<std::string> seen;
    for (std::size_t index = 0; index < items.size(); ++index) {
        auto spec = make_spec(items[index], directory);
        if (!spec) {
            return std::unexpected{std::format("{} 第 {} 個：{}", path.string(),
                                               index + 1, spec.error())};
        }
        // 同一個檔案裡撞名明顯是打錯字，安靜挑一個只會讓人找不到另一個。
        if (!seen.insert(spec->name()).second) {
            return std::unexpected{std::format("{} 裡有重複的 function.name {}",
                                               path.string(), spec->name())};
        }
        specs.push_back(std::move(*spec));
    }
    return specs;
}

std::expected<Spec, std::string> load(const std::filesystem::path& path) {
    auto specs = load_all(path);
    if (!specs) {
        return std::unexpected{specs.error()};
    }
    if (specs->size() != 1) {
        return std::unexpected{std::format("{} 裡有 {} 個 tool，用 load_all() 讀",
                                           path.string(), specs->size())};
    }
    return std::move(specs->front());
}

std::expected<llm::ToolSet, std::string> load_tools(
    std::span<const std::filesystem::path> sources) {
    llm::ToolSet set;
    for (const std::filesystem::path& source : sources) {
        auto specs = load_all(source);
        if (!specs) {
            return std::unexpected{specs.error()};
        }
        for (Spec& spec : *specs) {
            if (set.dispatch.contains(spec.name())) {
                continue;  // 先給的優先，比照 PATH
            }
            set.schemas.push_back(
                llm::ToolSchema{.name = spec.name(), .json = spec.schema_json()});
            // shared_ptr 讓 dispatch 裡的 lambda 自己抓著那份 spec，
            // 呼叫端不必再管它活多久。
            auto shared = std::make_shared<Spec>(std::move(spec));
            set.dispatch.emplace(
                shared->name(),
                [shared](std::string_view arguments) -> std::string {
                    return shared->run(arguments);
                });
        }
    }
    return set;
}

}  // namespace aos::tooljson
