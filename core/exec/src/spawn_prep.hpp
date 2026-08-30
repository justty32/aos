#pragma once

#include <aos/exec.hpp>

#include <string>
#include <vector>

namespace aos::exec::detail {

constexpr int kExitSetupFailed = 126;
constexpr int kExitExecFailed = 127;

struct SpawnPrep {
    std::vector<std::string> environment;
    std::vector<char *> envp;
    std::string executable;
    int failure_status = 0;
};

void prepare_spawn(const Spawn &spawn, SpawnPrep &prep);

}  // namespace aos::exec::detail
