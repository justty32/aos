// spawn_prep.hpp：fork 之前先備好環境變數合併、argv／envp 實體化，fork 後只做 async-signal-safe 的事（搬自 archive/aos-v1/core/exec，行為不改）。
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
