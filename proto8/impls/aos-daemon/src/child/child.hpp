// child.hpp：【child】表上的一個子項＝一支子 loop，或一個 exec 型子項（execs，10-30）。內部標頭。
//
//   child.cpp   spawn：小格 mkdir（只建這一層，$AOS_STACK 不在＝MkdirFailed）、寫 loop.json（子項設定補上 ctl／state、蓋上 _entry、相對的 exec 轉絕對；先 .loop.json 再改名）、
//               fork 一個子行程跑 `aos-exec -- 小格/loop.json#/_entry`（aos-exec 的 run_cli；它 cd 進小格、exec 成 PATH 上的
//               aos-loop，pid 不變；setsid 自成一個行程群組、stdin／stdout 接 /dev/null、stderr 附加到小格的 stderr.txt、AOS_STACK＝小格/）
//               spawn_exec（10-30，thinking 2026-10-30-agent-lifecycle B-12 ②）：exec 型子項——小格、stderr.txt、自成 session、stdin／stdout /dev/null、
//               AOS_STACK＝小格/、cd 到 daemon 的 cwd 都同上，但不包 aos-loop、不寫 loop.json、不補 ctl／state：子行程直接 `aos-exec -- 目標 參數...` 一次
//               alive：自己生的看 waitpid（結束就記 code／signal）；接回來的看 /proc 的 started_at_ticks 還對不對
//               row：寫進 loops_state 的那一列
#pragma once

#include "common/common.hpp"

#include <chrono>
#include <optional>
#include <string>

#include <sys/types.h>

namespace aos::daemon {

struct Child {
    pid_t pid = 0;
    std::optional<long long> started_at_ticks;   // /proc/<pid>/stat 第 22 欄
    bool own = true;                    // 自己 fork 的（false＝adopt 接回來的，不是我們的子行程）
    bool once = false;                  // exec 型子項（execs，10-30）：直接 aos-exec 一次、不包 aos-loop；loops_state 裡在 execs 表
    bool reaped = false;
    std::string phase = "running";      // running／stopping（送了 SIGTERM、還沒退）／done（自己結束）／stopped（daemon 收掉）
    Json code;                          // null 或結束碼（被訊號停掉＝128＋N）
    Json signal;                        // null 或停掉它的訊號
    // 收的途中（phase stopping）：SIGTERM 之後到這一刻還沒退就 SIGKILL 整群（連底下自成一群的單子，10-24 審後）；killed＝已經送過 SIGKILL；
    // removing＝收完要從表上拿掉（ctl 的 loops 少了它；收工時全部收、不拿掉）
    std::chrono::steady_clock::time_point deadline;
    bool killed = false;
    bool removing = false;
};

// 起一支子 loop。cell＝小格（$AOS_STACK/<名字>）、spec＝字串或陣列（aos-exec 的目標，包成 {"exec": 它}）或 loop 設定物件、
// cwd＝daemon 的 cwd（子項 exec 的相對路徑從這裡算：字串、陣列的第一個元素轉成絕對路徑，其他不動、不驗）。
// 小格建不了 MkdirFailed、loop.json 寫不了 WriteFailed、stderr 開不了／fork 失敗 LaunchFailed。
// aos-exec 自己的錯（PATH 上沒有 aos-loop…）寫在小格的 stderr.txt、子 loop 以 1 結束（phase done、code 1）。
Child spawn(const std::string& name, const std::string& cell, const Json& spec, const std::string& cwd);

// 起一個 exec 型子項（execs，10-30）。target＝aos-exec 的目標：字串或 [目標, 參數...]（read_execs 驗過）；相對路徑從 cwd（daemon 的 cwd）算——
// 子行程 cd 到 cwd 才叫 aos-exec，所以不轉。小格建不了 MkdirFailed、stderr 開不了／fork 失敗 LaunchFailed；aos-exec 自己的錯寫在小格的
// stderr.txt、子項以 1 結束（phase done、code 1）。它退了＝done、不重起（同子 loop）。
Child spawn_exec(const std::string& name, const std::string& cell, const Json& target, const std::string& cwd);

// 還活著嗎（自己生的：結束了就收屍、記 code／signal）。
bool alive(Child& c);

// loops_state 裡的一列：{"pid", "started_at_ticks", "phase", "code", "signal"}。
Json row(const Child& c);

}  // namespace aos::daemon
