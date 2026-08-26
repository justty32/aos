// format 層：inst_t → instruction JSON。

#include "format_internal.hpp"

namespace aos::detail {
namespace {

nlohmann::ordered_json encode_directive(const PendingDirective &directive) {
    switch (directive.kind) {
    case DirectiveKind::Environment:
        return {{"$env", directive.argument}};
    case DirectiveKind::Reference:
        return {{"$ref", directive.argument}};
    }
    return nullptr;
}

}  // namespace

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

}  // namespace aos::detail
