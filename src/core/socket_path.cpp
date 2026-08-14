#include "aos/socket_path.hpp"

#include <cstdlib>
#include <string>

#include <unistd.h>

namespace aos {

std::filesystem::path socket_path_from_environment() {
    if (const char* value = std::getenv("AOS_SOCKET"); value && *value) {
        return value;
    }
    if (const char* value = std::getenv("XDG_RUNTIME_DIR"); value && *value) {
        return std::filesystem::path{value} / "aos.sock";
    }
    return std::filesystem::path{"/tmp"} /
           ("aos-" + std::to_string(::getuid()) + ".sock");
}

}  // namespace aos
