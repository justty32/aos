// env.cpp：【env】工作區與 AOS_STACK（說明見 env.hpp）。對應 proto8/bin/aos-exec 的 hop 開頭。
#include "env/env.hpp"

#include "aos/files.hpp"

#include <cstdlib>
#include <filesystem>
#include <system_error>

#include <sys/stat.h>

namespace aos::exec {

namespace fs = std::filesystem;

std::string check_ws(const std::string& ws_flag) {
    std::string ws = ws_flag;
    if (ws.empty() || ws == "-") {
        const char* v = std::getenv("AOS_WS");
        ws = ".";
        if (v != nullptr && v[0] != '\0') {
            ws = v;
        }
    }
    struct stat st;
    if (stat(ws.c_str(), &st) != 0 || !S_ISDIR(st.st_mode)) {
        throw Error{code::WsMissing, "工作區不存在：" + ws};
    }
    return abspath(ws);
}

void setup_stack(const std::string& ws) {
    std::string stack = join(ws, ".stack");
    const char* s = std::getenv("AOS_STACK");
    if (s != nullptr && s[0] != '\0') {
        stack = s;
    }
    std::error_code ec;
    fs::create_directories(stack, ec);
    if (ec) {
        throw Error{code::MkdirFailed, "建不了 AOS_STACK：" + stack + "（" + ec.message() + "）"};
    }
    std::string abs = abspath(stack);
    if (abs != "/") {
        abs += "/";
    }
    setenv("AOS_WS", ws.c_str(), 1);
    setenv("AOS_STACK", abs.c_str(), 1);
}

}  // namespace aos::exec
