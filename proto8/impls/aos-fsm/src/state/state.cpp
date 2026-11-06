// state.cpp：【state】stage.txt（說明見 state.hpp）。
#include "state/state.hpp"

#include "aos/util/files.hpp"
#include "aos/util/text.hpp"

#include <cerrno>
#include <cstring>

namespace aos::fsm {

std::string read_state(const std::string& stack, const std::string& start) {
    int err = 0;
    std::string path = aos::join(stack, "stage.txt");
    std::optional<std::string> text = aos::read_file(path, err);
    if (!text) {
        if (err == ENOENT) {   // 沒有檔＝從 start 起
            return start;
        }
        throw Error{code::StateBad, "cannot read " + path + ": " + std::strerror(err)};   // 10-22：在但讀不了＝自己的錯
    }
    if (!aos::is_utf8(*text)) {
        throw Error{code::StateBad, "cannot read " + path + ": not UTF-8"};
    }
    std::string s = aos::strip(*text);   // 去頭尾空白（同 Python str.strip()，認 Unicode 空白）
    if (s.empty()) {
        return start;
    }
    return s;
}

void write_state(const std::string& stack, const std::string& name) {
    std::string tmp = aos::join(stack, ".stage.txt");
    std::string dst = aos::join(stack, "stage.txt");
    std::optional<aos::TextWriteError> error = aos::write_text(dst, name + "\n", tmp);
    if (error) {
        if (error->operation == aos::TextWriteOperation::open) {
            throw Error{code::WriteFailed, "cannot write " + tmp + ": " + std::strerror(error->number)};
        }
        if (error->operation == aos::TextWriteOperation::write) {
            throw Error{code::WriteFailed, "cannot write " + tmp};
        }
        throw Error{code::WriteFailed, "cannot rename " + tmp + " -> " + dst + ": " + std::strerror(error->number)};
    }
}

}  // namespace aos::fsm
