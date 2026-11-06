// help.hpp：【help】aos-post 各子命令的英文說明與 usage。
#pragma once

#include <string>

namespace aos::post {

const std::string& cli_usage(const std::string& command);
const std::string& cli_help(const std::string& command);

}  // namespace aos::post
