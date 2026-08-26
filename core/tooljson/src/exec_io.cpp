#include "exec_internal.hpp"

#include <string>
#include <vector>

namespace aos::tooljson {
namespace {

using json = nlohmann::json;

}  // namespace

namespace detail {

SpecState parse_exec_io(const Spec::Impl *impl, ExecBody *body,
                        std::string &message) {
    const json &extra = impl->extra;

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

    return SpecState::Ok;
}

}  // namespace detail
}  // namespace aos::tooljson
