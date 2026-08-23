#include <aos/llms.hpp>

#include "llms_internal.hpp"

#include <algorithm>
#include <new>
#include <set>
#include <stdexcept>
#include <utility>

namespace aos::llms {
namespace {

ToolSetState fail(ToolSetState state, std::string text,
                  std::string &message) {
    message = std::move(text);
    return state;
}

}  // namespace

const char *to_string(ToolSetState state) noexcept {
    switch (state) {
        case ToolSetState::Ok: return "ok";
        case ToolSetState::InvalidArgument: return "invalid argument";
        case ToolSetState::JsonSyntax: return "JSON syntax error";
        case ToolSetState::InvalidFormat: return "invalid format";
        case ToolSetState::NameMismatch: return "name mismatch";
        case ToolSetState::DuplicateName: return "duplicate name";
    }
    return "unknown";
}

ToolSet::ToolSet() : impl_(std::make_shared<Impl>()) {}
ToolSet::ToolSet(std::shared_ptr<const Impl> impl) noexcept
    : impl_(std::move(impl)) {}
ToolSet::ToolSet(const ToolSet &) noexcept = default;
ToolSet::ToolSet(ToolSet &&) noexcept = default;
ToolSet &ToolSet::operator=(const ToolSet &) noexcept = default;
ToolSet &ToolSet::operator=(ToolSet &&) noexcept = default;
ToolSet::~ToolSet() = default;

bool ToolSet::empty() const noexcept { return impl_->schemas.empty(); }

std::string ToolSet::schemas_json() const { return impl_->schemas.dump(); }

std::vector<std::string> ToolSet::names() const {
    std::vector<std::string> result;
    result.reserve(impl_->dispatch.size());
    for (const auto &[name, function] : impl_->dispatch) {
        static_cast<void>(function);
        result.push_back(name);
    }
    return result;
}

std::string ToolSet::dispatch(const std::string &name, const char *args_json,
                              std::size_t size) const {
    const auto found = impl_->dispatch.find(name);
    if (found == impl_->dispatch.end()) {
        return "Error: unknown tool '" + name + "'";
    }
    if (args_json == nullptr) {
        return "Error: tool arguments pointer is null";
    }
    try {
        return found->second(args_json, size);
    } catch (const std::bad_alloc &) {
        throw;
    } catch (const std::exception &error) {
        return "Error: tool '" + name + "' failed: " + error.what();
    } catch (...) {
        return "Error: tool '" + name + "' failed";
    }
}

ToolSetState normalize_tools(const std::vector<ToolBundle> &sources,
                             ToolSet &out, std::string &message) {
    auto combined = std::make_shared<ToolSet::Impl>();
    message.clear();
    for (std::size_t source_index = 0; source_index < sources.size();
         ++source_index) {
        const ToolBundle &source = sources[source_index];
        json schemas;
        try {
            schemas = json::parse(source.schemas_json);
        } catch (const json::parse_error &error) {
            return fail(ToolSetState::JsonSyntax,
                        "第 " + std::to_string(source_index + 1) +
                            " 組 tools JSON 讀不起來：" + error.what(),
                        message);
        }
        if (!schemas.is_array()) {
            return fail(ToolSetState::InvalidFormat,
                        "第 " + std::to_string(source_index + 1) +
                            " 組 schemas 要是 JSON array",
                        message);
        }

        std::vector<std::string> schema_names;
        std::set<std::string> within;
        for (const json &schema : schemas) {
            const auto function = schema.is_object()
                ? schema.find("function") : schema.end();
            if (!schema.is_object() || function == schema.end() ||
                !function->is_object()) {
                return fail(ToolSetState::InvalidFormat,
                            "tool schema 要含 function.name", message);
            }
            const auto name = function->find("name");
            if (name == function->end() || !name->is_string() ||
                name->get_ref<const std::string &>().empty()) {
                return fail(ToolSetState::InvalidFormat,
                            "tool schema 要含非空的 function.name", message);
            }
            const std::string value = name->get<std::string>();
            schema_names.push_back(value);
            if (!within.insert(value).second) {
                return fail(ToolSetState::DuplicateName,
                            "同一組 schemas 有重複工具名稱 '" + value + "'",
                            message);
            }
        }

        std::set<std::string> dispatch_names;
        for (const auto &[name, function] : source.dispatch) {
            if (name.empty() || !function) {
                return fail(ToolSetState::InvalidArgument,
                            "dispatch 名稱不可為空，而且每個值都要能呼叫",
                            message);
            }
            dispatch_names.insert(name);
        }
        if (within != dispatch_names) {
            return fail(ToolSetState::NameMismatch,
                        "tool schemas 與 dispatch 的名稱要完全相同",
                        message);
        }
        for (const std::string &name : schema_names) {
            if (combined->dispatch.contains(name)) {
                return fail(ToolSetState::DuplicateName,
                            "不同 tools 來源撞名 '" + name + "'", message);
            }
        }
        for (const json &schema : schemas) {
            combined->schemas.push_back(schema);
        }
        combined->dispatch.insert(source.dispatch.begin(),
                                  source.dispatch.end());
    }
    out = detail_ToolSetAccess::make(std::move(combined));
    return ToolSetState::Ok;
}

}  // namespace aos::llms
