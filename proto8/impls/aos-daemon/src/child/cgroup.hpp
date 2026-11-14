// cgroup.hpp：管理 daemon 的可選 cgroup v2 委派、份額、事件與整格清理。
#pragma once

#include "common/common.hpp"
#include <string>
#include <sys/types.h>

namespace aos::daemon {

bool cgroup_setup(std::string& base, std::string& reason);
std::string cgroup_prepare(const std::string& base, const std::string& name, const Json& limits);
std::string cgroup_empty_cell(const std::string& cell, bool remove);
std::string cgroup_kill(const std::string& cell);
bool cgroup_populated(const std::string& cell);
long long cgroup_event(const std::string& path, const std::string& key);
bool cgroup_has_pid(const std::string& cell, pid_t pid);

}  // namespace aos::daemon
