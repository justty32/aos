// help.hpp：【help】aos-json 子命令的 usage、旗標說明與共同旗標解析入口。
#pragma once

#include "aos/cli.hpp"

namespace aos::json {

const std::string& cli_usage(const std::string& command);
const std::string& cli_help(const std::string& command);
Cli parse_args(const std::vector<std::string>& args,
               const std::map<std::string, std::string>& flags,
               const std::map<std::string, std::string>& switches,
               const std::string& command);

}  // namespace aos::json
