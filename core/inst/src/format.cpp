#include <aos/inst.hpp>

#include <nlohmann/json.hpp>

#include <array>
#include <string_view>
#include <utility>

namespace aos {
namespace {

using json = nlohmann::json;

json parse_json(const char *data, std::size_t size) {
    return json::parse(data, data + size);
}

const PendingDirective *find_directive(const inst_t &inst,
                                       DirectiveField field,
                                       std::size_t argv_index = 0,
                                       std::string_view env_key = {}) {
    for (const auto &directive : inst.pending_directives) {
        if (directive.field != field) continue;
        if (field == DirectiveField::Argv &&
            directive.argv_index != argv_index) continue;
        if (field == DirectiveField::EnvValue &&
            directive.env_key != env_key) continue;
        return &directive;
    }
    return nullptr;
}

nlohmann::ordered_json encode_directive(const PendingDirective &directive) {
    switch (directive.kind) {
    case DirectiveKind::Environment:
        return {{"$env", directive.argument}};
    case DirectiveKind::Reference:
        return {{"$ref", directive.argument}};
    }
    return nullptr;
}

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

nlohmann::ordered_json encode(const inst_t &inst) {
    nlohmann::ordered_json value;
    value["argv"] = nlohmann::ordered_json::array();
    for (std::size_t index = 0; index < inst.argv.size(); ++index) {
        const auto *directive = find_directive(
            inst, DirectiveField::Argv, index);
        value["argv"].push_back(directive ? encode_directive(*directive)
                                           : nlohmann::ordered_json(inst.argv[index]));
    }
    const auto encode_string = [&](const char *name, DirectiveField field,
                                   const std::string &literal) {
        if (const auto *directive = find_directive(inst, field)) {
            value[name] = encode_directive(*directive);
        } else if (!literal.empty()) {
            value[name] = literal;
        }
    };
    encode_string("stdin", DirectiveField::Stdin, inst.stdin_path);
    encode_string("stdout", DirectiveField::Stdout, inst.stdout_path);
    if (const auto *directive = find_directive(inst, DirectiveField::Stderr)) {
        value["stderr"] = encode_directive(*directive);
    } else if (inst.stderr_merge) {
        value["stderr"] = {{"$opt", "merge"}};
    } else if (!inst.stderr_path.empty()) {
        value["stderr"] = inst.stderr_path;
    }
    encode_string("exit", DirectiveField::Exit, inst.exit_path);
    encode_string("cwd", DirectiveField::Cwd, inst.cwd);
    if (!inst.env.empty()) {
        value["env"] = nlohmann::ordered_json::object();
        for (const auto &[key, literal] : inst.env) {
            const auto *directive = find_directive(
                inst, DirectiveField::EnvValue, 0, key);
            value["env"][key] = directive ? encode_directive(*directive)
                                           : nlohmann::ordered_json(literal);
        }
    }
    if (inst.timeout_ms != 0) value["timeout_ms"] = inst.timeout_ms;
    if (inst.parallel) value["parallel"] = true;
    return value;
}

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

}  // namespace

InstState validate(const inst_t &inst) {
    if (inst.argv.empty()) return InstState::EmptyArgv;
    if (inst.argv.front().empty() &&
        find_directive(inst, DirectiveField::Argv, 0) == nullptr) {
        return InstState::EmptyArgv;
    }
    for (const auto &entry : inst.env) {
        if (entry.first.empty() || entry.first.find('=') != std::string::npos) {
            return InstState::EnvKeyInvalid;
        }
    }
    return InstState::Ok;
}

InstState read_one(const char *data, std::size_t size, inst_t &out) {
    out.clear();
    if (data == nullptr) {
        return InstState::InvalidArgument;
    }

    try {
        const json value = parse_json(data, size);
        inst_t parsed;
        const InstState state = decode(value, parsed);
        if (state == InstState::Ok) {
            out = std::move(parsed);
        }
        return state;
    } catch (const json::parse_error &) {
        return InstState::JsonSyntax;
    }
}

InstState read_all(const char *data, std::size_t size,
                   std::vector<inst_t> &out, std::size_t *error_record) {
    out.clear();
    if (error_record != nullptr) {
        *error_record = 0;
    }
    if (data == nullptr) {
        return InstState::InvalidArgument;
    }

    try {
        const json document = parse_json(data, size);
        const bool single = document.is_object();
        if (!single && !document.is_array()) {
            return InstState::NotAnObject;
        }

        const std::size_t count = single ? 1 : document.size();
        std::vector<inst_t> parsed;
        parsed.reserve(count);
        for (std::size_t index = 0; index < count; ++index) {
            const json &value = single ? document : document[index];
            if (error_record != nullptr) {
                *error_record = index + 1;
            }
            inst_t inst;
            const InstState state = decode(value, inst);
            if (state != InstState::Ok) {
                return state;
            }
            parsed.push_back(std::move(inst));
        }
        out.swap(parsed);
        if (error_record != nullptr) {
            *error_record = 0;
        }
        return InstState::Ok;
    } catch (const json::parse_error &) {
        return InstState::JsonSyntax;
    }
}

InstState write_one(const inst_t &inst, std::string &out) {
    const InstState state = validate(inst);
    if (state != InstState::Ok) {
        return state;
    }

    std::string record = encode(inst).dump();
    record.push_back('\n');
    out.append(record);
    return InstState::Ok;
}

InstState write_all(const std::vector<inst_t> &insts, std::string &out,
                    std::size_t *error_record) {
    if (error_record != nullptr) {
        *error_record = 0;
    }
    for (std::size_t index = 0; index < insts.size(); ++index) {
        const InstState state = validate(insts[index]);
        if (state != InstState::Ok) {
            if (error_record != nullptr) {
                *error_record = index + 1;
            }
            return state;
        }
    }

    nlohmann::ordered_json document = nlohmann::ordered_json::array();
    for (const auto &inst : insts) {
        document.push_back(encode(inst));
    }
    std::string batch = document.dump();
    batch.push_back('\n');
    out.append(batch);
    return InstState::Ok;
}

}  // namespace aos
