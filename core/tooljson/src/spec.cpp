#include <aos/tooljson.hpp>

#include "spec_internal.hpp"
#include "tooljson_internal.hpp"

#include <filesystem>
#include <utility>

namespace aos::tooljson {
namespace {

using json = nlohmann::json;

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

const char *format_version() noexcept { return detail::kVersion; }

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

}  // namespace aos::tooljson
