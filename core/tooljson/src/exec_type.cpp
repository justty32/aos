#include "exec_internal.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <limits>
#include <string>
#include <system_error>
#include <utility>
#include <vector>

#include <unistd.h>

namespace aos::tooljson {
namespace {

using json = nlohmann::json;
using detail::bad;

/* exec 配方的解析入口：各段落分別交給 exec_argv / exec_io / exec_limits。 */
SpecState parse_exec(const Spec &spec, BodyPtr &out, std::string &message) {
    const Spec::Impl *impl = detail::SpecAccess::get(spec);
    if (impl == nullptr) {
        return bad("exec 解析器收到無效的 Spec", message);
    }
    auto body = std::make_shared<detail::ExecBody>();
    body->properties = impl->properties;

    SpecState state = detail::parse_exec_argv(impl, body.get(), message);
    if (state != SpecState::Ok) return state;
    state = detail::parse_exec_io(impl, body.get(), message);
    if (state != SpecState::Ok) return state;
    state = detail::parse_exec_limits(impl, body.get(), message);
    if (state != SpecState::Ok) return state;

    out = std::move(body);
    message.clear();
    return SpecState::Ok;
}

[[maybe_unused]] const bool registered_exec = [] {
    std::string message;
    return register_type("exec", parse_exec, message) == SpecState::Ok;
}();

}  // namespace

namespace detail {

SpecState bad(std::string text, std::string &message) {
    message = std::move(text);
    return SpecState::InvalidFormat;
}

std::vector<std::string> unknown_keys(
    const json &object, std::initializer_list<std::string_view> allowed) {
    std::vector<std::string> out;
    for (auto it = object.begin(); it != object.end(); ++it) {
        if (std::find(allowed.begin(), allowed.end(), it.key()) ==
            allowed.end()) {
            out.push_back(it.key());
        }
    }
    return out;
}

bool integer_value(const json &value, std::int64_t &out) {
    if (value.is_number_unsigned()) {
        const std::uint64_t number = value.get<std::uint64_t>();
        if (number > static_cast<std::uint64_t>(
                         std::numeric_limits<std::int64_t>::max())) return false;
        out = static_cast<std::int64_t>(number);
        return true;
    }
    if (value.is_number_integer()) {
        out = value.get<std::int64_t>();
        return true;
    }
    return false;
}

bool finite_number(const json &value, double &out) {
    if (!value.is_number() || value.is_boolean()) return false;
    out = value.get<double>();
    return std::isfinite(out);
}

std::string ExecBody::run(const char *, std::size_t) const {
    return "Error: exec execution is not implemented in S1";
}

std::string ExecBody::target() const {
    if (command.empty()) return {};
    const std::string &program = command.front();
    if (program.find('/') != std::string::npos) {
        std::error_code error;
        return std::filesystem::is_regular_file(program, error) && !error
                   ? program
                   : std::string();
    }

    const char *raw_path = std::getenv("PATH");
    const std::string path = raw_path == nullptr ? "/bin:/usr/bin" : raw_path;
    std::size_t begin = 0;
    for (;;) {
        const std::size_t end = path.find(':', begin);
        const std::string field = path.substr(begin, end - begin);
        std::error_code error;
        std::filesystem::path directory =
            field.empty() ? std::filesystem::current_path(error)
                          : std::filesystem::path(field);
        if (!error && !directory.is_absolute()) {
            directory = std::filesystem::absolute(directory, error);
        }
        const std::filesystem::path candidate = directory / program;
        if (!error && std::filesystem::is_regular_file(candidate, error) &&
            !error && access(candidate.c_str(), X_OK) == 0) {
            return candidate.lexically_normal().string();
        }
        if (end == std::string::npos) break;
        begin = end + 1;
    }
    return {};
}

}  // namespace detail
}  // namespace aos::tooljson
