#include <aos/inst.hpp>

#include <nlohmann/json.hpp>

#include <algorithm>
#include <cerrno>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <string_view>
#include <utility>

namespace aos {
namespace {

using json = nlohmann::json;

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
    result.variable.clear();
    result.reference_path.clear();
    result.pointer.clear();
    result.reference_chain.clear();
    result.error = 0;
}

std::filesystem::path normalized_path(const std::string &name,
                                      const ResolveContext &context) {
    std::filesystem::path path(name);
    if (path.is_relative()) {
        path = std::filesystem::path(context.base_path) / path;
    }
    std::error_code error;
    std::filesystem::path normalized =
        std::filesystem::weakly_canonical(path, error);
    if (!error) return normalized;
    error.clear();
    normalized = std::filesystem::absolute(path, error);
    return (error ? path : normalized).lexically_normal();
}

struct Reference {
    std::string path;
    std::string pointer;
};

Reference parse_reference(const std::string &argument,
                          const ResolveContext &context) {
    const std::size_t hash = argument.find('#');
    Reference reference;
    reference.path = normalized_path(argument.substr(0, hash), context).string();
    if (hash != std::string::npos) reference.pointer = argument.substr(hash + 1);
    return reference;
}

std::string identity(const Reference &reference) {
    return reference.path + "#" + reference.pointer;
}

ResolveState resolve_value(inst_t &, const PendingDirective &, const json &,
                           const ResolveContext &, ResolveResult &,
                           std::vector<std::string> &);

ResolveState resolve_reference(inst_t &inst,
                               const PendingDirective &location,
                               const std::string &argument,
                               const ResolveContext &context,
                               ResolveResult &result,
                               std::vector<std::string> &chain) {
    const Reference reference = parse_reference(argument, context);
    const std::string current = identity(reference);
    result.reference_path = reference.path;
    result.pointer = reference.pointer;
    if (std::find(chain.begin(), chain.end(), current) != chain.end()) {
        result.reference_chain = chain;
        result.reference_chain.push_back(current);
        return ResolveState::ReferenceCycle;
    }
    chain.push_back(current);

    errno = 0;
    std::ifstream input(reference.path, std::ios::binary);
    if (!input) {
        result.error = errno;
        result.reference_chain = chain;
        chain.pop_back();
        return ResolveState::ReferenceReadFailed;
    }
    std::string document((std::istreambuf_iterator<char>(input)),
                         std::istreambuf_iterator<char>());
    if (input.bad()) {
        result.error = errno;
        result.reference_chain = chain;
        chain.pop_back();
        return ResolveState::ReferenceReadFailed;
    }

    json root;
    try {
        root = json::parse(document);
    } catch (const json::parse_error &) {
        result.reference_chain = chain;
        chain.pop_back();
        return ResolveState::ReferenceJsonInvalid;
    }

    const json *selected = &root;
    if (!reference.pointer.empty()) {
        try {
            selected = &root.at(json::json_pointer(reference.pointer));
        } catch (const json::parse_error &) {
            result.reference_chain = chain;
            chain.pop_back();
            return ResolveState::ReferencePointerInvalid;
        } catch (const json::out_of_range &) {
            result.reference_chain = chain;
            chain.pop_back();
            return ResolveState::ReferencePointerInvalid;
        } catch (const json::type_error &) {
            result.reference_chain = chain;
            chain.pop_back();
            return ResolveState::ReferencePointerInvalid;
        }
    }

    const ResolveState state = resolve_value(
        inst, location, *selected, context, result, chain);
    if (state != ResolveState::Ok && result.reference_chain.empty()) {
        result.reference_chain = chain;
    }
    chain.pop_back();
    return state;
}

ResolveState resolve_value(inst_t &inst, const PendingDirective &location,
                           const json &value, const ResolveContext &context,
                           ResolveResult &result,
                           std::vector<std::string> &chain) {
    std::string *destination = target(inst, location);
    if (destination == nullptr) return ResolveState::InvalidArgument;
    if (value.is_string()) {
        *destination = value.get<std::string>();
        return ResolveState::Ok;
    }
    if (!value.is_object() || value.size() != 1) {
        return ResolveState::ReferenceValueInvalid;
    }
    const auto item = value.begin();
    if (!item.value().is_string()) return ResolveState::ReferenceValueInvalid;
    const std::string argument = item.value().get<std::string>();
    if (item.key() == "$env") {
        result.variable = argument;
        const auto found = context.environment.find(argument);
        if (found == context.environment.end()) {
            return ResolveState::EnvironmentVariableMissing;
        }
        *destination = found->second;
        return ResolveState::Ok;
    }
    if (item.key() == "$ref") {
        return resolve_reference(inst, location, argument, context, result,
                                 chain);
    }
    if (item.key() == "$opt" && argument == "merge" &&
        location.field == DirectiveField::Stderr) {
        inst.stderr_path.clear();
        inst.stderr_merge = true;
        return ResolveState::Ok;
    }
    return ResolveState::ReferenceValueInvalid;
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
    std::vector<std::string> chain;
    for (const auto &directive : resolved.pending_directives) {
        describe(directive, result);
        ResolveState state = ResolveState::Ok;
        switch (directive.kind) {
        case DirectiveKind::Environment: {
            result.variable = directive.argument;
            const auto it = context.environment.find(directive.argument);
            if (it == context.environment.end()) {
                return ResolveState::EnvironmentVariableMissing;
            }
            std::string *value = target(resolved, directive);
            if (value == nullptr) return ResolveState::InvalidArgument;
            *value = it->second;
            break;
        }
        case DirectiveKind::Reference:
            state = resolve_reference(resolved, directive, directive.argument,
                                      context, result, chain);
            break;
        }
        if (state != ResolveState::Ok) return state;
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
    case ResolveState::ReferenceReadFailed: return "ReferenceReadFailed";
    case ResolveState::ReferenceJsonInvalid: return "ReferenceJsonInvalid";
    case ResolveState::ReferencePointerInvalid:
        return "ReferencePointerInvalid";
    case ResolveState::ReferenceValueInvalid: return "ReferenceValueInvalid";
    case ResolveState::ReferenceCycle: return "ReferenceCycle";
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
