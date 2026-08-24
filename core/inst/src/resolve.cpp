#include <aos/inst.hpp>

#include <string_view>
#include <utility>

namespace aos {
namespace {

std::string *target(inst_t &inst, const PendingDirective &directive) {
    switch (directive.field) {
    case DirectiveField::Argv:
        if (directive.argv_index >= inst.argv.size()) return nullptr;
        return &inst.argv[directive.argv_index];
    case DirectiveField::Stdin: return &inst.stdin_path;
    case DirectiveField::Stdout: return &inst.stdout_path;
    case DirectiveField::Stderr: return &inst.stderr_path;
    case DirectiveField::Exit: return &inst.exit_path;
    case DirectiveField::Cwd: return &inst.cwd;
    case DirectiveField::EnvValue: {
        const auto it = inst.env.find(directive.env_key);
        return it == inst.env.end() ? nullptr : &it->second;
    }
    }
    return nullptr;
}

void describe(const PendingDirective &directive, ResolveResult &result) {
    result.field = directive.field;
    result.argv_index = directive.argv_index;
    result.env_key = directive.env_key;
    result.variable = directive.argument;
}

}  // namespace

ResolveState capture_environment(const char *const *environment,
                                 const std::string &base_path,
                                 ResolveContext &context) {
    if (environment == nullptr) return ResolveState::InvalidArgument;
    ResolveContext captured;
    captured.base_path = base_path;
    for (std::size_t index = 0; environment[index] != nullptr; ++index) {
        const std::string_view entry(environment[index]);
        const std::size_t separator = entry.find('=');
        if (separator == std::string_view::npos || separator == 0) continue;
        captured.environment.insert_or_assign(
            std::string(entry.substr(0, separator)),
            std::string(entry.substr(separator + 1)));
    }
    context = std::move(captured);
    return ResolveState::Ok;
}

ResolveState resolve(inst_t &inst, const ResolveContext &context,
                     ResolveResult &result) {
    result = {};
    inst_t resolved = inst;
    for (const auto &directive : resolved.pending_directives) {
        describe(directive, result);
        std::string *value = target(resolved, directive);
        if (value == nullptr) return ResolveState::InvalidArgument;
        switch (directive.kind) {
        case DirectiveKind::Environment: {
            const auto it = context.environment.find(directive.argument);
            if (it == context.environment.end()) {
                return ResolveState::EnvironmentVariableMissing;
            }
            *value = it->second;
            break;
        }
        }
    }
    resolved.pending_directives.clear();
    result.validation_state = validate(resolved);
    if (result.validation_state != InstState::Ok) {
        return ResolveState::ValidationFailed;
    }
    inst = std::move(resolved);
    result = {};
    return ResolveState::Ok;
}

const char *to_string(ResolveState state) noexcept {
    switch (state) {
    case ResolveState::Ok: return "Ok";
    case ResolveState::InvalidArgument: return "InvalidArgument";
    case ResolveState::EnvironmentVariableMissing:
        return "EnvironmentVariableMissing";
    case ResolveState::ValidationFailed: return "ValidationFailed";
    }
    return "Unknown";
}

const char *to_string(DirectiveField field) noexcept {
    switch (field) {
    case DirectiveField::Argv: return "argv";
    case DirectiveField::Stdin: return "stdin";
    case DirectiveField::Stdout: return "stdout";
    case DirectiveField::Stderr: return "stderr";
    case DirectiveField::Exit: return "exit";
    case DirectiveField::Cwd: return "cwd";
    case DirectiveField::EnvValue: return "env";
    }
    return "unknown";
}

}  // namespace aos
