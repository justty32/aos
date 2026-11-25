// env.cpp：讀 daemon 交給「它起的那一支」的環境變數 AOS_NAME、AOS_MOUNT；AOS_NAME_PID 對不上自己的 PID 就不算（照 systemd 的 LISTEN_PID）。
#include "aos/procfs.hpp"

#include <cstdlib>
#include <string>
#include <unistd.h>

namespace aos::procfs {

std::optional<EnvAssignment> env_assignment() {
    const char* name = std::getenv("AOS_NAME");
    const char* mount = std::getenv("AOS_MOUNT");
    const char* pid = std::getenv("AOS_NAME_PID");
    if (!name || !*name || !mount || !*mount || !pid || !*pid) return std::nullopt;
    // 整串都要是數字、而且等於自己：孫子行程原樣繼承到的是孩子的 PID，對不上就當沒給
    std::string p = pid;
    if (p.size() > 18 || p.find_first_not_of("0123456789") != std::string::npos) return std::nullopt;
    if (std::stoll(p) != static_cast<long long>(getpid())) return std::nullopt;
    return EnvAssignment{name, mount};
}

}  // namespace aos::procfs
