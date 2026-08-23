#pragma once

#include <aos/tooljson.hpp>

#include <nlohmann/json.hpp>

#include <cstdint>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace aos::tooljson {

struct Spec::Impl {
    nlohmann::json data;
    nlohmann::json function;
    nlohmann::json extra;
    nlohmann::json properties;
    std::vector<std::string> required;
    std::string name;
    std::string kind;
    std::string source_path;
    std::string base_dir;
    BodyPtr body;
};

namespace detail {

struct SpecAccess {
    static const Spec::Impl *get(const Spec &spec) noexcept {
        return spec.impl_.get();
    }

    static Spec make(std::shared_ptr<Spec::Impl> impl) noexcept {
        return Spec(std::shared_ptr<const Spec::Impl>(std::move(impl)));
    }
};

struct Binding {
    std::string name;
    std::int64_t position = 0;
    std::string flag;
    bool separate = true;
    bool repeat = false;
};

class ExecBody final : public Body {
public:
    std::vector<std::string> command;
    std::vector<Binding> bindings;
    nlohmann::json properties;
    nlohmann::json limits;
    std::optional<std::string> stdin_param;
    std::string stdout_clip = "head";
    std::string stderr_mode = "merge";
    std::vector<std::int64_t> ok_exit{0};
    std::string cwd;
    double timeout = 60.0;

    std::string run(const char *args_json, std::size_t size) const override;
    std::string target() const override;
};

SpecState find_parser(const std::string &kind, Parser &out);
std::string type_list_repr();
std::string json_repr(const nlohmann::json &value);
std::string string_list_repr(const std::vector<std::string> &values);
std::string resolve_path(const std::string &value,
                         const std::string &base_dir);
std::optional<std::string> sha256_file(const std::string &path);

}  // namespace detail
}  // namespace aos::tooljson
