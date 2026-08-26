// format 層：instruction JSON → inst_t。
// 認得的 key、字串位置的 $env／$ref 指示詞、以及 stderr 專屬的 {"$opt":"merge"}
// 都定義在這裡——新增一個 instruction 欄位時，known_key 與 decode 兩處都要加。

#include "format_internal.hpp"

#include <array>
#include <cstdint>
#include <string>
#include <string_view>
#include <utility>

namespace aos::detail {
namespace {

using json = nlohmann::json;

InstState decode_directive(const json &value, DirectiveField field,
                           inst_t &inst, std::size_t argv_index = 0,
                           std::string env_key = {}) {
    if (value.size() != 1) return InstState::DirectiveKeyCountInvalid;
    const auto it = value.begin();
    if (it.key().empty() || it.key().front() != '$') {
        return InstState::FieldTypeMismatch;
    }
    if (it.key() != "$env" && it.key() != "$ref") {
        return InstState::UnknownDirective;
    }
    if (!it.value().is_string()) {
        return InstState::DirectiveValueTypeMismatch;
    }
    PendingDirective directive;
    directive.kind = it.key() == "$env" ? DirectiveKind::Environment
                                         : DirectiveKind::Reference;
    directive.field = field;
    directive.argv_index = argv_index;
    directive.env_key = std::move(env_key);
    directive.argument = it.value().get<std::string>();
    inst.pending_directives.push_back(std::move(directive));
    return InstState::Ok;
}

bool known_key(std::string_view key) {
    constexpr std::array<std::string_view, 9> keys = {
        "argv", "stdin", "stdout", "stderr", "exit", "cwd", "env",
        "timeout_ms", "parallel",
    };
    for (const auto candidate : keys) {
        if (key == candidate) {
            return true;
        }
    }
    return false;
}

}  // namespace

InstState decode(const json &value, inst_t &inst) {
    if (!value.is_object()) {
        return InstState::NotAnObject;
    }
    for (auto it = value.begin(); it != value.end(); ++it) {
        if (!known_key(it.key())) {
            return InstState::UnknownKey;
        }
    }

    const auto argv_it = value.find("argv");
    if (argv_it == value.end()) {
        return InstState::EmptyArgv;
    }
    if (!argv_it->is_array()) {
        return InstState::FieldTypeMismatch;
    }
    std::size_t argv_index = 0;
    for (const auto &arg : *argv_it) {
        if (arg.is_string()) {
            inst.argv.push_back(arg.get<std::string>());
        } else if (arg.is_object()) {
            inst.argv.emplace_back();
            const InstState state = decode_directive(
                arg, DirectiveField::Argv, inst, argv_index);
            if (state != InstState::Ok) return state;
        } else {
            return InstState::FieldTypeMismatch;
        }
        ++argv_index;
    }

    const std::pair<const char *, std::string *> strings[] = {
        {"stdin", &inst.stdin_path}, {"stdout", &inst.stdout_path},
        {"exit", &inst.exit_path},
        {"cwd", &inst.cwd},
    };
    for (const auto &field : strings) {
        const auto it = value.find(field.first);
        if (it != value.end()) {
            if (it->is_string()) {
                *field.second = it->get<std::string>();
            } else if (it->is_object()) {
                DirectiveField directive_field = DirectiveField::Stdin;
                if (std::string_view(field.first) == "stdout") {
                    directive_field = DirectiveField::Stdout;
                } else if (std::string_view(field.first) == "exit") {
                    directive_field = DirectiveField::Exit;
                } else if (std::string_view(field.first) == "cwd") {
                    directive_field = DirectiveField::Cwd;
                }
                const InstState state = decode_directive(
                    *it, directive_field, inst);
                if (state != InstState::Ok) return state;
            } else {
                return InstState::FieldTypeMismatch;
            }
        }
    }

    const auto stderr_it = value.find("stderr");
    if (stderr_it != value.end()) {
        if (stderr_it->is_string()) {
            inst.stderr_path = stderr_it->get<std::string>();
        } else if (stderr_it->is_object()) {
            if (stderr_it->size() != 1) {
                return InstState::DirectiveKeyCountInvalid;
            }
            const auto option_it = stderr_it->find("$opt");
            if (option_it != stderr_it->end()) {
                if (!option_it->is_string()) {
                    return InstState::DirectiveValueTypeMismatch;
                }
                if (option_it->get_ref<const std::string &>() != "merge") {
                    return InstState::UnknownOption;
                }
                inst.stderr_merge = true;
            } else {
                const InstState state = decode_directive(
                    *stderr_it, DirectiveField::Stderr, inst);
                if (state != InstState::Ok) return state;
            }
        } else {
            return InstState::FieldTypeMismatch;
        }
    }

    const auto env_it = value.find("env");
    if (env_it != value.end()) {
        if (!env_it->is_object()) {
            return InstState::FieldTypeMismatch;
        }
        for (auto it = env_it->begin(); it != env_it->end(); ++it) {
            if (it.value().is_string()) {
                inst.env.emplace(it.key(), it.value().get<std::string>());
            } else if (it.value().is_object()) {
                inst.env.emplace(it.key(), std::string{});
                const InstState state = decode_directive(
                    it.value(), DirectiveField::EnvValue, inst, 0, it.key());
                if (state != InstState::Ok) return state;
            } else {
                return InstState::FieldTypeMismatch;
            }
            if (it.key().empty() || it.key().find('=') != std::string::npos) {
                return InstState::EnvKeyInvalid;
            }
        }
    }

    const auto timeout_it = value.find("timeout_ms");
    if (timeout_it != value.end()) {
        if (!timeout_it->is_number_unsigned()) {
            return InstState::FieldTypeMismatch;
        }
        inst.timeout_ms = timeout_it->get<std::uint64_t>();
    }

    const auto parallel_it = value.find("parallel");
    if (parallel_it != value.end()) {
        if (!parallel_it->is_boolean()) {
            return InstState::FieldTypeMismatch;
        }
        inst.parallel = parallel_it->get<bool>();
    }
    return validate(inst);
}

}  // namespace aos::detail
