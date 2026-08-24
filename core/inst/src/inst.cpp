#include <aos/inst.hpp>

namespace aos {

void inst_t::clear() noexcept {
    argv.clear();
    stdin_path.clear();
    stdout_path.clear();
    stderr_path.clear();
    stderr_merge = false;
    exit_path.clear();
    cwd.clear();
    env.clear();
    pending_directives.clear();
    timeout_ms = 0;
    parallel = false;
}

const char *to_string(InstState state) noexcept {
    switch (state) {
    case InstState::Ok: return "Ok";
    case InstState::InvalidArgument: return "InvalidArgument";
    case InstState::JsonSyntax: return "JsonSyntax";
    case InstState::NotAnObject: return "NotAnObject";
    case InstState::UnknownKey: return "UnknownKey";
    case InstState::FieldTypeMismatch: return "FieldTypeMismatch";
    case InstState::EmptyArgv: return "EmptyArgv";
    case InstState::EnvKeyInvalid: return "EnvKeyInvalid";
    case InstState::DirectiveKeyCountInvalid:
        return "DirectiveKeyCountInvalid";
    case InstState::UnknownDirective: return "UnknownDirective";
    case InstState::DirectiveValueTypeMismatch:
        return "DirectiveValueTypeMismatch";
    case InstState::UnknownOption: return "UnknownOption";
    }
    return "Unknown";
}

}  // namespace aos
