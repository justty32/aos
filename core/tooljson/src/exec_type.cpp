#include "tooljson_internal.hpp"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <limits>
#include <set>
#include <string_view>

#include <unistd.h>

namespace aos::tooljson {
namespace {

using json = nlohmann::json;
constexpr std::size_t kArgMaxBytes = 128 * 1024;

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

SpecState parse_exec(const Spec &spec, BodyPtr &out, std::string &message) {
    const Spec::Impl *impl = detail::SpecAccess::get(spec);
    if (impl == nullptr) {
        return bad("exec 解析器收到無效的 Spec", message);
    }
    const json &extra = impl->extra;
    auto body = std::make_shared<detail::ExecBody>();
    body->properties = impl->properties;

    const auto command = extra.find("exec");
    if (command == extra.end() || !command->is_array() || command->empty()) {
        return bad("_extra.exec 要是非空的字串 list，第一項是程式本身",
                   message);
    }
    for (const json &item : *command) {
        if (!item.is_string() || item.get_ref<const std::string &>().empty()) {
            return bad("_extra.exec 要是非空的字串 list，第一項是程式本身",
                       message);
        }
        body->command.push_back(item.get<std::string>());
    }
    for (const std::string &item : body->command) {
        if (item.size() > kArgMaxBytes) {
            return bad("_extra.exec 裡有單一 argv 項目超過 131072 bytes",
                       message);
        }
    }
    if (body->command.front().find('/') != std::string::npos) {
        body->command.front() =
            detail::resolve_path(body->command.front(), impl->base_dir);
    }

    const auto argv_it = extra.find("argv");
    if (argv_it != extra.end() && !argv_it->is_object()) {
        return bad("_extra.argv 要是 object，key 是參數名", message);
    }
    const json empty_object = json::object();
    const json &argv = argv_it == extra.end() ? empty_object : *argv_it;
    for (auto it = argv.begin(); it != argv.end(); ++it) {
        const std::string &param = it.key();
        const json &binding = it.value();
        if (!binding.is_object()) {
            return bad("_extra.argv['" + param + "'] 要是 object", message);
        }
        if (!impl->properties.contains(param)) {
            return bad("_extra.argv 綁了 '" + param +
                           "'，但 parameters 裡沒這個",
                       message);
        }
        const std::vector<std::string> unknown = unknown_keys(
            binding, {"position", "flag", "separate", "repeat"});
        if (!unknown.empty()) {
            return bad("_extra.argv['" + param + "'] 有不認得的鍵 " +
                           detail::string_list_repr(unknown) +
                           "，可用的是 ['position', 'flag', 'separate', 'repeat']",
                       message);
        }

        detail::Binding parsed;
        parsed.name = param;
        const auto position = binding.find("position");
        if (position != binding.end() && !integer_value(*position, parsed.position)) {
            return bad("'" + param + "' 的 position 要是整數", message);
        }
        const auto flag = binding.find("flag");
        if (flag != binding.end()) {
            if (!flag->is_string()) {
                return bad("'" + param + "' 的 flag 要是字串", message);
            }
            parsed.flag = flag->get<std::string>();
            if (parsed.flag.size() > kArgMaxBytes) {
                return bad("'" + param +
                               "' 的 flag 超過單一 argv 項目的 131072 bytes 上限",
                           message);
            }
        }
        const auto separate = binding.find("separate");
        if (separate != binding.end()) {
            if (!separate->is_boolean()) {
                return bad("'" + param + "' 的 separate 要是 boolean", message);
            }
            parsed.separate = separate->get<bool>();
        }
        const auto repeat = binding.find("repeat");
        if (repeat != binding.end()) {
            if (!repeat->is_boolean()) {
                return bad("'" + param + "' 的 repeat 要是 boolean", message);
            }
            parsed.repeat = repeat->get<bool>();
        }
        body->bindings.push_back(std::move(parsed));
    }
    std::sort(body->bindings.begin(), body->bindings.end(),
              [](const detail::Binding &left, const detail::Binding &right) {
                  if (left.position != right.position) {
                      return left.position < right.position;
                  }
                  /* 合法 JSON 字串的 UTF-8 位元組序與 Unicode 碼位序一致。 */
                  return left.name < right.name;
              });

    const auto stdin_it = extra.find("stdin");
    if (stdin_it != extra.end() && !stdin_it->is_null()) {
        if (!stdin_it->is_object()) {
            return bad("_extra.stdin 要嘛是 null，要嘛是 {\"param\": \"...\"}",
                       message);
        }
        const auto param = stdin_it->find("param");
        if (param == stdin_it->end() || !param->is_string()) {
            return bad("_extra.stdin 要嘛是 null，要嘛是 {\"param\": \"...\"}",
                       message);
        }
        if (stdin_it->size() != 1) {
            return bad("_extra.stdin 只能有 param", message);
        }
        body->stdin_param = param->get<std::string>();
        if (!impl->properties.contains(*body->stdin_param)) {
            return bad("_extra.stdin 指了 '" + *body->stdin_param +
                           "'，但 parameters 裡沒這個",
                       message);
        }
    }

    const auto stdout_it = extra.find("stdout");
    if (stdout_it != extra.end() && !stdout_it->is_null()) {
        if (!stdout_it->is_object()) {
            return bad("_extra.stdout 要是 object", message);
        }
        const std::vector<std::string> unknown =
            unknown_keys(*stdout_it, {"clip"});
        if (!unknown.empty()) {
            return bad("_extra.stdout 只能有 clip", message);
        }
        const auto clip = stdout_it->find("clip");
        if (clip != stdout_it->end()) {
            if (!clip->is_string()) {
                return bad("_extra.stdout.clip 是 " + detail::json_repr(*clip) +
                               "，只認得 ['head', 'tail']",
                           message);
            }
            body->stdout_clip = clip->get<std::string>();
        }
    }
    if (body->stdout_clip != "head" && body->stdout_clip != "tail") {
        return bad("_extra.stdout.clip 是 '" + body->stdout_clip +
                       "'，只認得 ['head', 'tail']",
                   message);
    }

    const auto stderr_it = extra.find("stderr");
    if (stderr_it != extra.end() && !stderr_it->is_null()) {
        if (!stderr_it->is_object()) {
            return bad("_extra.stderr 要是 object", message);
        }
        const std::vector<std::string> unknown =
            unknown_keys(*stderr_it, {"mode"});
        if (!unknown.empty()) {
            return bad("_extra.stderr 只能有 mode", message);
        }
        const auto mode = stderr_it->find("mode");
        if (mode != stderr_it->end()) {
            if (!mode->is_string()) {
                return bad("_extra.stderr.mode 是 " + detail::json_repr(*mode) +
                               "，只認得 ['merge', 'ignore', 'only']",
                           message);
            }
            body->stderr_mode = mode->get<std::string>();
        }
    }
    if (body->stderr_mode != "merge" && body->stderr_mode != "ignore" &&
        body->stderr_mode != "only") {
        return bad("_extra.stderr.mode 是 '" + body->stderr_mode +
                       "'，只認得 ['merge', 'ignore', 'only']",
                   message);
    }

    const auto ok = extra.find("ok_exit");
    if (ok != extra.end()) {
        if (!ok->is_array()) {
            return bad("_extra.ok_exit 要是整數 list", message);
        }
        std::vector<std::int64_t> exits;
        for (const json &item : *ok) {
            std::int64_t value = 0;
            if (!integer_value(item, value)) {
                return bad("_extra.ok_exit 要是整數 list", message);
            }
            exits.push_back(value);
        }
        if (!exits.empty()) body->ok_exit = std::move(exits);
    }

    const auto timeout = extra.find("timeout");
    if (timeout != extra.end()) {
        if (!finite_number(*timeout, body->timeout) || body->timeout <= 0) {
            return bad("_extra.timeout 要是大於 0 的有限秒數", message);
        }
    }

    const auto cwd = extra.find("cwd");
    if (cwd != extra.end() && !cwd->is_null()) {
        if (!cwd->is_string() || cwd->get_ref<const std::string &>().empty()) {
            return bad("_extra.cwd 要嘛是 null，要嘛是非空路徑字串", message);
        }
        body->cwd = detail::resolve_path(cwd->get<std::string>(), impl->base_dir);
    }

    const auto limits = extra.find("limits");
    if (limits != extra.end() && !limits->is_null()) {
        if (!limits->is_object()) {
            return bad("_extra.limits 要是 object", message);
        }
        body->limits = *limits;
    } else {
        body->limits = json::object();
    }

    std::vector<std::string> unknown_limits;
    for (auto it = body->limits.begin(); it != body->limits.end(); ++it) {
        if (!impl->properties.contains(it.key())) unknown_limits.push_back(it.key());
    }
    if (!unknown_limits.empty()) {
        return bad("_extra.limits 有未知參數 " +
                       detail::string_list_repr(unknown_limits),
                   message);
    }
    for (auto it = body->limits.begin(); it != body->limits.end(); ++it) {
        const std::string &name_value = it.key();
        const json &rule = it.value();
        if (!rule.is_object()) {
            return bad("_extra.limits['" + name_value + "'] 要是 object",
                       message);
        }
        const std::vector<std::string> unknown =
            unknown_keys(rule, {"max_bytes", "min", "max"});
        if (!unknown.empty()) {
            return bad("_extra.limits['" + name_value +
                           "'] 有不認得的鍵 " +
                           detail::string_list_repr(unknown),
                       message);
        }
        const auto cap = rule.find("max_bytes");
        if (cap != rule.end()) {
            const bool valid =
                (cap->is_number_unsigned()) ||
                (cap->is_number_integer() && cap->get<std::int64_t>() >= 0);
            if (!valid) {
                return bad("_extra.limits['" + name_value +
                               "'].max_bytes 要是非負整數",
                           message);
            }
        }
        double low = 0;
        double high = 0;
        const auto low_it = rule.find("min");
        const auto high_it = rule.find("max");
        const bool has_low = low_it != rule.end();
        const bool has_high = high_it != rule.end();
        if (has_low && !finite_number(*low_it, low)) {
            return bad("_extra.limits['" + name_value + "'].min 要是數字",
                       message);
        }
        if (has_high && !finite_number(*high_it, high)) {
            return bad("_extra.limits['" + name_value + "'].max 要是數字",
                       message);
        }
        if (has_low && has_high && low > high) {
            return bad("_extra.limits['" + name_value +
                           "'] 的 min 不可大於 max",
                       message);
        }
    }

    const auto source = extra.find("source");
    if (source != extra.end() && !source->is_null()) {
        if (!source->is_object()) {
            return bad("_extra.source 要是 object", message);
        }
        const auto size = source->find("size");
        if (size != source->end()) {
            const bool valid = size->is_number_unsigned() ||
                               (size->is_number_integer() &&
                                size->get<std::int64_t>() >= 0);
            if (!valid) {
                return bad("_extra.source.size 要是非負整數", message);
            }
        }
        const auto mtime = source->find("mtime");
        std::int64_t ignored_mtime = 0;
        if (mtime != source->end() && !integer_value(*mtime, ignored_mtime)) {
            return bad("_extra.source.mtime 要是整數", message);
        }
        const auto sha256 = source->find("sha256");
        if (sha256 != source->end() && !sha256->is_string()) {
            return bad("_extra.source.sha256 要是字串", message);
        }
    }

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
