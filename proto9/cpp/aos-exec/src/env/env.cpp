// env.cpp：【env】工作區（說明見 env.hpp）。proto9: setup_stack and drop_stack_if_empty are gone (no AOS_STACK).
#include "env/env.hpp"

#include "util/files.hpp"

#include <cstdlib>

#include <sys/stat.h>

namespace aos::exec {

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
        throw Error{code::WsMissing, "workspace does not exist: " + ws};
    }
    return abspath(ws);
}

}  // namespace aos::exec
