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
