#pragma once

#include "aos/protocol.hpp"

namespace aos {

// 所有業務命令都從這個入口進入；CLI 不應包含命令語意。
[[nodiscard]] Response handle_command(const Request& request);

}  // namespace aos
