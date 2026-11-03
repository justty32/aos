// child.hpp：【child】表上的一個 proc（11-03 起 loops／execs 統稱 procs）＝一支子 loop（loop 型），或 aos-exec 跑一次（exec 型）。內部標頭。
//
//   child.cpp   spawn：小格（proc 的 stack）建好、寫 loop.json（設定補上 ctl／state、蓋 _entry、相對的 exec 轉絕對；ws、stack 不寫進去；先 .loop.json 再改名）、
//               fork 一個子行程跑 `aos-exec -- 小格/loop.json#/_entry`（aos-exec 的 run_cli；它 cd 進小格、exec 成 PATH 上的
//               aos-loop，pid 不變；setsid 自成一個行程群組、stdin／stdout 接 /dev/null、stderr 附加到小格的 stderr.txt、AOS_STACK＝小格/）；
//               設定是 null（信箱接回的 stopped 列再 start，11-03）＝不重寫、照小格裡現有的 loop.json 起
//               spawn_exec（exec 型）：小格、stderr.txt、自成 session、stdin／stdout /dev/null、AOS_STACK＝小格/、cd 到 daemon 的 cwd 都同上，
//               但不包 aos-loop、不寫 loop.json：子行程直接 `aos-exec -- 目標 參數...` 一次（目標是單子＝寫成小格的 exec.json 再跑它）
//               小格（11-03）：proc 寫了 stack＝它（daemon.cpp 已轉絕對；不在就 mkdir -p）；沒寫＝$AOS_STACK/procs/<名字>/（只建 procs/ 與小格兩層，
//               $AOS_STACK 不在＝MkdirFailed）
//               alive：自己生的看 waitpid（結束就記 code／signal）；接回來的看 /proc 的 started_at_ticks 還對不對
//               row：寫進 procs_state 的那一列
//               ws：設定寫了 ws＝子行程的環境多設 AOS_WS＝它；沒寫＝照舊繼承 daemon 的。AOS_DAEMON_STACK 一律設成 daemon 的 stack（dstack：絕對、結尾 /）
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
    bool once = false;                  // exec 型（直接 aos-exec 一次、不包 aos-loop）；接回來的看小格有沒有 daemon 寫的 loop.json（沒有＝exec 型）
    bool reaped = false;
    std::string phase = "running";      // running／stopping（收的途中）／done（自己結束）／stopped（行程不在了）；
                                        // done 與沒 held 的 stopped 只是印 log 那一刻的值，印完就從表上拿掉（11-02 子項結束後不留名單）
    bool held = false;                  // stopped 的列（11-03）：daemon 下的 stop 讓它退了、列留在表上（pid 0、行程不在、stack 留著），start 才再起
    bool soft = false;                  // daemon 下的 stop（往它的 ctl.json 寫了 {"cmd": "stop"}，或沒 ctl 時 SIGTERM）：退了就變 held
    bool termed = false;                // 送過 SIGTERM（有 deadline；soft 的寫 ctl 那種沒有時間上限）
    std::string stack;                  // 小格＝它的 stack（絕對路徑、結尾不帶 /；子行程的 AOS_STACK＝它＋/）
    Json code;                          // null 或結束碼（被訊號停掉＝128＋N）
    Json signal;                        // null 或停掉它的訊號
    // 收的途中（phase stopping）：SIGTERM 之後到這一刻還沒退就 SIGKILL 整群（連底下自成一群的單子，10-24 審後）；killed＝已經送過 SIGKILL
    std::chrono::steady_clock::time_point deadline;
    bool killed = false;
    Json ws;                            // null 或起它時給的工作區（絕對路徑；子行程的 AOS_WS）——起的那一刻的值，名單後來改了 ws 也不變（已在跑的不重起，N-54）
};

// 起一支子 loop。cell＝小格（proc 的 stack，絕對、結尾不帶 /；deep＝mkdir -p，不然只建 cell 與上一層）、spec＝loop 設定物件
// （null＝不寫 loop.json、照小格裡現有的起；11-03）、
// cwd＝daemon 的 cwd（子項 exec 的相對路徑從這裡算：字串、陣列的第一個元素轉成絕對路徑，其他不動、不驗）。
// spec 有 ws（read_procs 已轉絕對）＝子行程設 AOS_WS＝它；ws、stack 都不寫進 loop.json（daemon 的 key，不是 loop 的）。
// 小格建不了 MkdirFailed、loop.json 寫不了 WriteFailed、stderr 開不了／fork 失敗 LaunchFailed。
// aos-exec 自己的錯（PATH 上沒有 aos-loop…）寫在小格的 stderr.txt、子 loop 以 1 結束（phase done、code 1）。
// dstack＝daemon 的 stack（絕對、結尾 /）：子行程設成 AOS_DAEMON_STACK（11-02）。spawn_exec 同。
Child spawn(const std::string& name, const std::string& cell, bool deep, const Json& spec, const std::string& cwd,
            const std::string& dstack);

// 起一個 exec 型 proc。spec＝aos-exec 的目標：字串或 [目標, 參數...]（read_procs 驗過），
// 或 {"exec": 上面兩種或單子, "ws"?, "stack"?}（子行程設 AOS_WS＝ws）；cell、deep 同 spawn；相對路徑從 cwd（daemon 的 cwd）算——
// 子行程 cd 到 cwd 才叫 aos-exec，所以不轉。小格建不了 MkdirFailed、stderr 開不了／fork 失敗 LaunchFailed；aos-exec 自己的錯寫在小格的
// stderr.txt、子項以 1 結束（phase done、code 1）。它退了＝done、從表上拿掉、本次執行不再起（同子 loop，11-02）。
// 11-02 晚：spec 的 exec 是內嵌單子（物件）＝寫成小格的 exec.json {"exec": 單子}（cwd 定成 daemon 的 cwd，pin_cwd），子行程跑 `aos-exec -- 小格/exec.json#/exec`。
Child spawn_exec(const std::string& name, const std::string& cell, bool deep, const Json& spec, const std::string& cwd,
                 const std::string& dstack);

// 還活著嗎（自己生的：結束了就收屍、記 code／signal）。
bool alive(Child& c);

// procs_state 裡的一列：{"pid", "started_at_ticks", "phase", "code", "signal", "stack"}，起它時給了工作區才多一欄 "ws"。
// held（stopped 的列）的 pid、started_at_ticks 是 null。
Json row(const Child& c);

}  // namespace aos::daemon
