// stack.cpp：【engine】make_stack——aos-loop、aos-fsm 起來時 $AOS_STACK 有設但資料夾不在就 mkdir -p（11-11，說明見 aos/loop.hpp）。
#include "aos/loop.hpp"
#include "aos/util/proc.hpp"

#include <string>
#include <filesystem>
#include <system_error>

namespace aos::loop {

void make_stack() {
    std::string s = aos::env_or_empty("AOS_STACK");
    if (s.empty()) {
        return;   // 沒設（空字串也算）：照舊（要開窗的由各自報 StackMissing）
    }
    std::error_code ec;
    if (std::filesystem::exists(s, ec)) {
        return;   // 在（不管是不是資料夾）：不碰，照舊
    }
    std::filesystem::create_directories(s, ec);
    if (ec || !std::filesystem::is_directory(s)) {
        throw Error{code::MkdirFailed, std::string("cannot create AOS_STACK: ") + s + (ec ? " (" + ec.message() + ")" : "")};
    }
}

}  // namespace aos::loop
