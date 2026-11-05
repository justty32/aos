// env.cpp：【env】工作區與 AOS_STACK（說明見 env.hpp）。
#include "env/env.hpp"

#include "aos/files.hpp"

#include <cstdlib>
#include <filesystem>
#include <system_error>

#include <sys/stat.h>
#include <unistd.h>

namespace aos::exec {

namespace fs = std::filesystem;

// 這次 aos-exec 自己新建的 stack（絕對、不帶結尾 /）與新建的最外一層；沒建＝空（drop_stack_if_empty 用）。
static std::string made_stack;
static std::string made_top;

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

std::string setup_stack(const std::string& ws, const std::string& stack_flag) {
    std::string stack = stack_flag;
    if (stack.empty() || stack == "-") {
        stack = join(ws, ".stack");
        const char* s = std::getenv("AOS_STACK");
        if (s != nullptr && s[0] != '\0') {
            stack = s;
        }
    }
    std::string abs = abspath(stack);
    std::string top;   // 還不在的最外一層（stack 已在＝空）
    for (std::string d = abs; d != "/" && !fs::exists(d); d = dirname(d)) {
        top = d;
    }
    std::error_code ec;
    fs::create_directories(stack, ec);
    if (ec) {
        throw Error{code::MkdirFailed, "建不了 AOS_STACK：" + stack + "（" + ec.message() + "）"};
    }
    if (!top.empty() && made_stack.empty()) {
        made_stack = abs;
        made_top = top;
    }
    if (abs != "/") {
        abs += "/";
    }
    setenv("AOS_WS", ws.c_str(), 1);
    setenv("AOS_STACK", abs.c_str(), 1);
    return abs;
}

void drop_stack_if_empty() {
    if (made_stack.empty()) {
        return;
    }
    for (std::string d = made_stack; ::rmdir(d.c_str()) == 0 && d != made_top; d = dirname(d)) {
    }
    made_stack.clear();
}

}  // namespace aos::exec
