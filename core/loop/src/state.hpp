#pragma once

#include <aos/exec.hpp>
#include <aos/wire.hpp>

#include <vector>

namespace aos::loop::detail {

std::vector<wire::RunningEntry> running_entries(
    const std::vector<wire::Inst> &insts,
    const std::vector<exec::Running> &running);
void mark_done(std::vector<wire::RunningEntry> &entries,
               const std::vector<exec::Result> &results);

}  // namespace aos::loop::detail
