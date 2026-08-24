#include "run_batch.hpp"

#include <aos/inst.hpp>

#include <cerrno>
#include <cstdio>
#include <cstring>
#include <new>
#include <stdexcept>
#include <system_error>
#include <thread>
#include <vector>

extern char **environ;

namespace aos::detail {
namespace {

struct ExecutionOutcome {
    ExecState state = ExecState::Ok;
    ExecResult result;
};

ExecutionOutcome execute_one(inst_t &instruction) {
    ExecutionOutcome outcome;
    try {
        outcome.state = execute(instruction, outcome.result);
    } catch (const std::bad_alloc &) {
        outcome.state = ExecState::SpawnFailed;
        outcome.result.error = ENOMEM;
    } catch (const std::length_error &) {
        outcome.state = ExecState::SpawnFailed;
        outcome.result.error = ENOMEM;
    }
    return outcome;
}

void print_resolve_location(const ResolveResult &result) {
    if (result.field == DirectiveField::Argv) {
        std::fprintf(stderr, "argv[%zu]", result.argv_index);
    } else if (result.field == DirectiveField::EnvValue) {
        std::fprintf(stderr, "env[%s]", result.env_key.c_str());
    } else {
        std::fprintf(stderr, "%s", to_string(result.field));
    }
}

void print_reference_error(const ResolveResult &result, ResolveState state) {
    std::fprintf(stderr, "%s: %s#%s", to_string(state),
                 result.reference_path.c_str(), result.pointer.c_str());
    if (result.error != 0) {
        std::fprintf(stderr, ": %s", std::strerror(result.error));
    }
    if (!result.reference_chain.empty()) {
        std::fprintf(stderr, ": chain ");
        for (std::size_t index = 0;
             index < result.reference_chain.size(); ++index) {
            if (index != 0) std::fprintf(stderr, " -> ");
            std::fprintf(stderr, "%s", result.reference_chain[index].c_str());
        }
    }
    std::fputc('\n', stderr);
}

}  // namespace

int execute_batch(const std::string &buffer, const char *source) {
    std::vector<inst_t> instructions;
    std::size_t error_record = 0;
    const char empty = '\0';
    const char *data = buffer.empty() ? &empty : buffer.data();
    InstState parse_state = InstState::Ok;
    try {
        parse_state = read_all(data, buffer.size(), instructions, &error_record);
    } catch (const std::bad_alloc &) {
        std::fprintf(stderr, "aos exec: cannot parse %s: out of memory\n", source);
        return 1;
    } catch (const std::length_error &) {
        std::fprintf(stderr, "aos exec: cannot parse %s: out of memory\n", source);
        return 1;
    }
    if (parse_state != InstState::Ok) {
        if (error_record != 0) {
            std::fprintf(stderr, "aos exec: %s: record %zu: %s\n", source,
                         error_record, to_string(parse_state));
        } else {
            std::fprintf(stderr, "aos exec: %s: %s\n", source,
                         to_string(parse_state));
        }
        return 1;
    }

    ResolveContext resolve_context;
    try {
        if (capture_environment(environ, ".", resolve_context) !=
            ResolveState::Ok) {
            std::fprintf(stderr,
                         "aos exec: cannot capture parent environment\n");
            return 1;
        }
        for (std::size_t index = 0; index < instructions.size(); ++index) {
            ResolveResult result;
            const ResolveState state = resolve(
                instructions[index], resolve_context, result);
            if (state == ResolveState::Ok) continue;
            if (state == ResolveState::EnvironmentVariableMissing) {
                if (result.field == DirectiveField::Argv) {
                    std::fprintf(
                        stderr,
                        "aos exec: %s: record %zu: argv[%zu]: environment "
                        "variable %s does not exist\n",
                        source, index + 1, result.argv_index,
                        result.variable.c_str());
                } else if (result.field == DirectiveField::EnvValue) {
                    std::fprintf(
                        stderr,
                        "aos exec: %s: record %zu: env[%s]: environment "
                        "variable %s does not exist\n",
                        source, index + 1, result.env_key.c_str(),
                        result.variable.c_str());
                } else {
                    std::fprintf(
                        stderr,
                        "aos exec: %s: record %zu: %s: environment variable "
                        "%s does not exist\n",
                        source, index + 1, to_string(result.field),
                        result.variable.c_str());
                }
                if (!result.reference_path.empty()) {
                    std::fprintf(stderr, "aos exec: referenced from %s#%s\n",
                                 result.reference_path.c_str(),
                                 result.pointer.c_str());
                }
            } else if (state == ResolveState::ValidationFailed) {
                std::fprintf(stderr,
                             "aos exec: %s: record %zu: after resolve: %s\n",
                             source, index + 1,
                             to_string(result.validation_state));
            } else if (state == ResolveState::ReferenceReadFailed ||
                       state == ResolveState::ReferenceJsonInvalid ||
                       state == ResolveState::ReferencePointerInvalid ||
                       state == ResolveState::ReferenceValueInvalid ||
                       state == ResolveState::ReferenceCycle) {
                std::fprintf(stderr, "aos exec: %s: record %zu: ", source,
                             index + 1);
                print_resolve_location(result);
                std::fprintf(stderr, ": ");
                print_reference_error(result, state);
            } else {
                std::fprintf(stderr, "aos exec: %s: record %zu: %s\n",
                             source, index + 1, to_string(state));
            }
            return 1;
        }
    } catch (const std::bad_alloc &) {
        std::fprintf(stderr, "aos exec: cannot resolve %s: out of memory\n",
                     source);
        return 1;
    } catch (const std::length_error &) {
        std::fprintf(stderr, "aos exec: cannot resolve %s: out of memory\n",
                     source);
        return 1;
    }

    std::vector<ExecutionOutcome> outcomes;
    std::vector<std::thread> threads;
    try {
        outcomes.resize(instructions.size());
        threads.reserve(instructions.size());
    } catch (const std::bad_alloc &) {
        std::fprintf(stderr, "aos exec: cannot execute %s: out of memory\n", source);
        return 1;
    } catch (const std::length_error &) {
        std::fprintf(stderr, "aos exec: cannot execute %s: out of memory\n", source);
        return 1;
    }
    for (std::size_t index = 0; index < instructions.size(); ++index) {
        if (!instructions[index].parallel) {
            outcomes[index] = execute_one(instructions[index]);
            continue;
        }
        try {
            threads.emplace_back(
                [instruction = instructions[index],
                 &outcome = outcomes[index]]() mutable {
                    outcome = execute_one(instruction);
                });
        } catch (const std::bad_alloc &) {
            outcomes[index].state = ExecState::SpawnFailed;
            outcomes[index].result.error = ENOMEM;
        } catch (const std::system_error &error) {
            outcomes[index].state = ExecState::SpawnFailed;
            outcomes[index].result.error = error.code().value();
        }
    }
    for (std::thread &thread : threads) thread.join();

    bool failed = false;
    for (std::size_t index = 0; index < outcomes.size(); ++index) {
        const ExecutionOutcome &outcome = outcomes[index];
        if (outcome.state == ExecState::Ok) continue;
        failed = true;
        if (outcome.result.error != 0) {
            std::fprintf(stderr, "aos exec: record %zu: %s: %s\n", index + 1,
                         to_string(outcome.state),
                         std::strerror(outcome.result.error));
        } else {
            std::fprintf(stderr, "aos exec: record %zu: %s\n", index + 1,
                         to_string(outcome.state));
        }
    }
    return failed ? 1 : 0;
}

}  // namespace aos::detail
