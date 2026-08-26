#include "exec_internal.hpp"

#include <algorithm>
#include <string>
#include <utility>
#include <vector>

namespace aos::tooljson {
namespace {

using json = nlohmann::json;

}  // namespace

namespace detail {

SpecState parse_exec_argv(const Spec::Impl *impl, ExecBody *body,
                          std::string &message) {
    const json &extra = impl->extra;

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

    return SpecState::Ok;
}

}  // namespace detail
}  // namespace aos::tooljson
