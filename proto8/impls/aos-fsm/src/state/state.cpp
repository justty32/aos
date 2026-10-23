// state.cpp：【state】state 與 trace.jsonl（說明見 state.hpp）。
#include "state/state.hpp"

#include "aos/files.hpp"

#include <cerrno>
#include <cstdio>
#include <cstring>
#include <ctime>

namespace aos::fsm {

static std::string strip(const std::string& s) {
    const char* ws = " \t\r\n\f\v";
    size_t b = s.find_first_not_of(ws);
    if (b == std::string::npos) {
        return "";
    }
    size_t e = s.find_last_not_of(ws);
    return s.substr(b, e - b + 1);
}

std::string read_state(const std::string& stack, const std::string& start) {
    int err = 0;
    std::optional<std::string> text = aos::read_file(aos::join(stack, "state"), err);
    if (!text) {
        return start;
    }
    std::string s = strip(*text);
    if (s.empty()) {
        return start;
    }
    return s;
}

// 寫整份字串；mode "w" 或 "a"。失敗丟 WriteFailed。
static void write_text(const std::string& path, const std::string& text, const char* mode) {
    std::FILE* f = std::fopen(path.c_str(), mode);
    if (f == nullptr) {
        throw Error{code::WriteFailed, "寫不了 " + path + "：" + std::strerror(errno)};
    }
    bool ok = std::fwrite(text.data(), 1, text.size(), f) == text.size();
    if (std::fclose(f) != 0) {
        ok = false;
    }
    if (!ok) {
        throw Error{code::WriteFailed, "寫不了 " + path};
    }
}

void write_state(const std::string& stack, const std::string& name) {
    std::string tmp = aos::join(stack, ".state");
    std::string dst = aos::join(stack, "state");
    write_text(tmp, name + "\n", "w");
    if (std::rename(tmp.c_str(), dst.c_str()) != 0) {
        int e = errno;
        std::remove(tmp.c_str());
        throw Error{code::WriteFailed, "改名不了 " + tmp + " → " + dst + "：" + std::strerror(e)};
    }
}

void append_trace(const std::string& stack, const Json& line) {
    write_text(aos::join(stack, "trace.jsonl"), aos::dumps(line) + "\n", "a");
}

std::string utc_now() {
    std::time_t now = std::time(nullptr);
    std::tm tm{};
    gmtime_r(&now, &tm);
    char buf[40];
    std::strftime(buf, sizeof buf, "%Y-%m-%dT%H:%M:%S+00:00", &tm);
    return buf;
}

}  // namespace aos::fsm
