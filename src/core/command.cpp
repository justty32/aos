#include "aos/command.hpp"

#include <sstream>

namespace aos {

Response handle_command(const Request& request) {
    if (request.arguments.empty()) {
        return {
            .exit_code = 2,
            .standard_output = {},
            .standard_error = "用法：aos <command> [arguments...]\n",
        };
    }

    if (request.arguments == std::vector<std::string>{"ping"}) {
        return {
            .exit_code = 0,
            .standard_output = "pong\n",
            .standard_error = {},
        };
    }

    // 第一版先把收到的內容清楚列出，方便確認 CLI 沒有改動參數邊界。
    // 真正的 new、start 等命令之後都只需要從這裡向下分派。
    std::ostringstream output;
    output << "daemon 收到 " << request.arguments.size() << " 個參數\n";
    for (std::size_t index = 0; index < request.arguments.size(); ++index) {
        output << "argv[" << index << "] = <" << request.arguments[index] << ">\n";
    }
    output << "工作目錄 = " << request.working_directory.native() << '\n';
    output << "stdin = " << request.standard_input.size() << " bytes\n";
    return {
        .exit_code = 0,
        .standard_output = std::move(output).str(),
        .standard_error = {},
    };
}

}  // namespace aos
