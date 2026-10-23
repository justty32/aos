// state.cpp：【state】state 與 trace.jsonl（說明見 state.hpp）。
#include "state/state.hpp"

#include "aos/files.hpp"
#include "aos/text.hpp"

#include <cerrno>
#include <cstdio>
#include <cstring>

namespace aos::fsm {

std::string read_state(const std::string& stack, const std::string& start) {
    int err = 0;
    std::string path = aos::join(stack, "state.txt");
    std::optional<std::string> text = aos::read_file(path, err);
    if (!text) {
        if (err == ENOENT) {   // 沒有檔＝從 start 起
            return start;
        }
        throw Error{code::StateBad, "讀不了 " + path + "：" + std::strerror(err)};   // 10-22：在但讀不了＝自己的錯
    }
    if (!aos::is_utf8(*text)) {
        throw Error{code::StateBad, "讀不了 " + path + "：不是 UTF-8"};
    }
    std::string s = aos::strip(*text);   // 去頭尾空白（同 Python str.strip()，認 Unicode 空白）
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
    std::string tmp = aos::join(stack, ".state.txt");
    std::string dst = aos::join(stack, "state.txt");
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

}  // namespace aos::fsm
