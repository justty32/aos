// child.hpp：【child】表上的一個子項＝一支子 loop。照 proto8/bin/aos-daemon 的 Child、Daemon.spawn。內部標頭。
//
//   child.cpp   spawn：小格 mkdir -p、寫 loop.json（子項設定補上 ctl／state、蓋上 _entry、相對的 run 轉絕對；先 .loop.json 再改名）、
//               fork 一個子行程跑 `aos-exec -- 小格/loop.json#/_entry`（aos-exec 的 run_cli；它 cd 進小格、exec 成 PATH 上的
//               aos-loop，pid 不變；setsid 自成一個行程群組、stdin／stdout 接 /dev/null、stderr 附加到小格的 stderr.txt、AOS_STACK＝小格/）
//               alive：自己生的看 waitpid（結束就記 code／signal）；接回來的看 /proc 的 started_at_ticks 還對不對
//               row：寫進 state 的那一列
#pragma once

#include "common/common.hpp"

#include <optional>
#include <string>

#include <sys/types.h>

namespace aos::daemon {

struct Child {
    pid_t pid = 0;
    std::optional<long long> started_at_ticks;   // /proc/<pid>/stat 第 22 欄
    bool own = true;                    // 自己 fork 的（false＝adopt 接回來的，不是我們的子行程）
    bool reaped = false;
    std::string phase = "running";      // running／stopping（只在 stop 裡）／done（自己結束）／stopped（daemon 收掉）
    Json code;                          // null 或結束碼（被訊號停掉＝128＋N）
    Json signal;                        // null 或停掉它的訊號
};

// 起一支子 loop。cell＝小格（$AOS_STACK/<名字>）、spec＝字串或陣列（aos-exec 的目標，包成 {"run": 它}）或 loop 設定物件、
// cwd＝daemon 的 cwd（子項 run 的相對路徑從這裡算：字串、陣列的第一個元素轉成絕對路徑，其他不動、不驗）。
// 小格建不了 MkdirFailed、loop.json 寫不了 WriteFailed、stderr 開不了／fork 失敗 LaunchFailed。
// aos-exec 自己的錯（PATH 上沒有 aos-loop…）寫在小格的 stderr.txt、子 loop 以 1 結束（phase done、code 1）。
Child spawn(const std::string& name, const std::string& cell, const Json& spec, const std::string& cwd);

// 還活著嗎（自己生的：結束了就收屍、記 code／signal）。
bool alive(Child& c);

// state 裡的一列：{"pid", "started_at_ticks", "phase", "code", "signal"}。
Json row(const Child& c);

}  // namespace aos::daemon
