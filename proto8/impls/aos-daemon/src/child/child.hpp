// child.hpp：【child】保存 proc 的共同生命週期、可重放入口、公開窗與 stuck 判定資料。內部標頭。
//
// 11-06（no-pid P6）：兩型都可寫通用 auto_restart＝常駐、退了重起，連 3 次起後 3 秒內退才留 stopped；
//   auto_restart、restart_on_stuck 兩欄只在 true 時寫表；P7 依公開窗與 stuck_after_cycles／stuck_after_ms 判卡住、可選重起。
//   （下面的 loop.json、exec.json、stderr.txt 是預設名；11-04 起 daemon.json 的 procs_loop／procs_exec／procs_stderr 可改，見 CellNames）
//   refs.cpp    rel_to／rel_spec／daemon_ref／rel_refs：相對路徑與指示詞改寫
//   child.cpp   spawn：小格（proc 的 stack）建好、寫 loop.json（蓋 _entry、相對的 exec 轉絕對；ws、stack 不寫進去；先 .loop.json 再改名）、
//               fork 一個子行程跑 `aos-exec -- 小格/loop.json#/_entry`（aos-exec 的 run_cli；它 cd 進小格、exec 成 PATH 上的
//               aos-loop，pid 不變；setsid 自成一個行程群組、stdin／stdout 接 /dev/null、stderr 附加到小格的 stderr.txt、AOS_STACK＝小格/）；
//               設定是 null（信箱接回的 stopped 列再 start，11-03）＝不重寫、照小格裡現有的 loop.json 起
//               spawn_exec（exec 型）：小格、stderr.txt、自成 session、stdin／stdout /dev/null、AOS_STACK＝小格/、cd 到 daemon 的 cwd 都同上，
//               但不包 aos-loop、不寫 loop.json：子行程直接 `aos-exec -- 目標 參數...` 一次（目標是單子＝寫成小格的 exec.json 再跑它）
//               小格（11-03）：proc 寫了 stack＝它（procs.cpp 已轉絕對；不在就 mkdir -p）；沒寫＝$AOS_STACK/procs/<名字>/（只建 procs/ 與小格兩層，
//               $AOS_STACK 不在＝MkdirFailed）
//               alive：自己生的看 waitpid（結束就記 code／signal）；接回來的看 /proc 的 started_at_ticks 還對不對
//               row：寫進 procs_state 的那一列
//               ws：設定寫了 ws＝子行程的環境多設 AOS_WS＝它；沒寫＝照舊繼承 daemon 的。AOS_DAEMON 一律設成 daemon 的 stack（dstack：絕對、結尾 /；11-04 晚改名，舊名不認）
//               limits（11-05 feat-proto 件 5）：生效的份額（列的，或 daemon.json 頂層的預設；null＝不限）——子行程在 run_cli 之前照它 setrlimit／換身分
//               （limits.cpp；等同 s6-softlimit／s6-setuidgid），失敗＝小格 stderr.txt 一行 LimitBad、退 1
#pragma once

#include "common/common.hpp"

#include "aos/util/clock.hpp"
#include "aos/util/proc.hpp"
#include <chrono>
#include <optional>
#include <string>

#include <sys/types.h>

namespace aos::daemon {

// 內嵌單子寫進小格之前：只把 $ref 的檔名改成相對小格。
Json rel_refs(const Json& v, const std::string& cell);

// 小格裡 daemon 自己寫的三個檔名（11-04，four-elements 題 6，使用者「是否能在json中設置？但默認用這些名」）：daemon.json 頂層
// procs_loop／procs_exec／procs_stderr，沒寫＝下面的預設；daemon 在 procs_state.json 頂層回報同名欄，讀小格的人從窗拿、不寫死。暫存檔＝「.」＋名字。
struct CellNames {
    std::string loop = "loop.json";      // loop 型：子項設定寫成這份（蓋 _entry）、子 loop 跑 小格/<loop>#/_entry
    std::string exec = "exec.json";      // exec 型的內嵌單子寫成這份 {"exec": 單子}
    std::string err = "stderr.txt";      // 兩型的 stderr 都附加到這份
};

struct Child {
    pid_t pid = 0;
    std::optional<long long> started_at_ticks;   // /proc/<pid>/stat 第 22 欄
    bool own = true;                    // 自己 fork 的（false＝adopt 接回來的，不是我們的子行程）
    Json launch;                        // 可重放的 proc 設定（通常 {exec: [目標, 參數...]}）；只供同 stack 再起，不拿起法判生命週期
    bool auto_restart = false;          // 11-06（no-pid P6）：通用常駐旗標，不看 exec／loop 型
    bool restart_on_stuck = false;      // P7：公開窗刺激逾期時重起
    long long stuck_after_cycles = 10;
    std::optional<long long> stuck_after_ms;   // 有值＝只用牆鐘毫秒，不讀樹的鐘
    bool stuck = false;                 // 表上的投影，不改生命週期 phase
    bool stuck_restart = false;         // 正在收掉卡住的一支
    int stuck_restarts = 0;             // 連續無回應而卡住的次數（起初一輪計入）
    std::optional<aos::Deadline> stuck_deadline;
    std::string observed_at = aos::utc_now_ms(); // 父這次起／接回的 UTC 毫秒基準
    std::string last_response;
    int quick_exits = 0;                // 連續起後 REVIVE_MS 內退出的次數，滿 3 次留 stopped
    bool reaped = false;
    std::string phase = "running";      // running／stopping（收的途中）／done（自己結束）／stopped（行程不在了）／sleeping（daemon 收工時收的，11-03）；
                                        // done 印完 log 下表；已知非 0 留 held stopped＋reason
    bool held = false;                  // stopped／sleeping 的列（11-03）：行程不在、列留在表上（pid 0、stack 留著）；stopped 要 start 才再起，
                                        // sleeping（daemon 收工時還活著的 proc）daemon 再開時自動 wake（不在 stopped 集合＝下一圈用列上的 stack 再起）
    bool soft = false;                  // daemon 下的 stop（往它的公開 ctl 寫了 {"cmd": "stop"}，寫不了也等自行退）：退了就變 held
    bool termed = false;                // 送過 SIGTERM（有 deadline；soft 的寫 ctl 那種沒有時間上限）
    bool nap = false;                   // daemon 收工時收的 proc（11-03 sleep／wake）：退了列留成 sleeping，daemon 再開時用同一個 stack 自動 wake
    std::string stack;                  // 小格＝它的 stack（絕對路徑、結尾不帶 /；子行程的 AOS_STACK＝它＋/）
    Json code;                          // null 或結束碼（被訊號停掉＝128＋N）
    Json signal;                        // null 或停掉它的訊號
    // 收的途中（phase stopping）：SIGTERM 之後到這一刻還沒退就 SIGKILL 整群（連底下自成一群的單子，10-24 審後）；killed＝已經送過 SIGKILL
    std::chrono::steady_clock::time_point deadline;
    bool killed = false;
    Json ws;                            // null 或起它時給的工作區（絕對路徑；子行程的 AOS_WS）——起的那一刻的值，名單後來改了 ws 也不變（已在跑的不重起，N-54）
    Json exec;                          // null 或起它時的目標（11-04 晚，aos-agent 方向題 1「daemon表多一欄記下來」）：Daemon 填（exec_of）；
                                        // adopt 接回的照舊表帶過來；名單後來改了也不變（同 ws）
    Json reason;                        // null 或字串（11-05 portable-flow 衝突 3「留成stopped，並寫原因」）：所有 proc 出錯結束（退非 0）的，列留成 stopped、記原因（11-05 晚：edge-agent 題 1、edge-daemon 題 2）
    bool failed = false;                // 11-05：這一圈剛因出錯結束留成 stopped（reconcile 這圈不再起它）
    bool revived = false;               // 這一支是 wake／start 從 stopped／sleeping 的列再起的（11-05）：REVIVE_MS 內退非 0＝原因寫「起不來」
    std::chrono::steady_clock::time_point revived_at;
    long long err_off = 0;              // 11-05 第二輪：起它那一刻小格 stderr.txt 的長度——reason 只看這次之後寫的（檔是附加的，前幾輩子的話不算）
    Json def;                           // null 或起它時給的定義資料夾（11-04，aos-agent，使用者「那就b。」）：Daemon 填（def_of）；接回、不變同 exec
    Json limits;                        // null 或起它時生效的份額（11-05 feat-proto 件 5；{}＝不限、存成 null）：起的那一刻的值，接回、不變同 exec
    Json as_written;                    // null 或 {"ws"?, "stack"?, "def"?, "exec"?}（11-10 two-machines）：設定／信裡寫成指示詞（$env／$ref）的路徑欄原形
                                        // （$ref 的檔名已轉絕對）；表上照存（列的 as_written），信箱接回只留名的列每次起再解（Daemon::refresh）
};

// 起一支子 loop。cell＝小格（proc 的 stack，絕對、結尾不帶 /；deep＝mkdir -p，不然只建 cell 與上一層）、spec＝loop 設定物件
// （null＝不寫 loop.json、照小格裡現有的起；11-03——這時 ws 用 kept_ws＝列上記的，11-03 晚：不然 wake／start 後表上與子行程的 AOS_WS 都掉了）、
// cwd＝daemon 的 cwd（子項 exec 的相對路徑從這裡算：字串、陣列的第一個元素轉成絕對路徑，其他不動、不驗）。
// spec 有 ws（read_procs 已轉絕對）＝子行程設 AOS_WS＝它；ws、stack、def、limits、auto_restart、restart_on_stuck、stuck_after_cycles、stuck_after_ms 都不寫進 loop.json（daemon 的 key，不是 loop 的）。
// 小格建不了 MkdirFailed、loop.json 寫不了 WriteFailed、stderr 開不了／fork 失敗 LaunchFailed。
// aos-exec 自己的錯（PATH 上沒有 aos-loop…）寫在小格的 stderr.txt、子 loop 以 1 結束（phase done、code 1）。
// dstack＝daemon 的 stack（絕對、結尾 /）：子行程設成 AOS_DAEMON（11-02；11-04 晚改名，舊名不認）。spawn_exec 同。
// names＝小格裡三個檔名（CellNames）。11-04 起不再替設定補 ctl／state（aos-loop 自己沒寫＝ctl.json／state.json，four-elements 07 步 4）。
// limits＝生效的份額（null＝不限；check_limits 驗過的物件），子行程照它做（limits.hpp）。spec 裡的 limits 不寫進 loop.json（daemon 的 key）。
Child spawn(const std::string& name, const std::string& cell, bool deep, const Json& spec, const std::string& cwd,
            const std::string& dstack, const CellNames& names, const Json& limits, const Json& kept_ws = Json());

// 起一個 exec 型 proc。spec＝aos-exec 的目標：字串或 [目標, 參數...]（read_procs 驗過），
// 或 {"exec": 上面兩種或單子, "ws"?, "stack"?, "def"?}（子行程設 AOS_WS＝ws；def 只記進表）；cell、deep 同 spawn；相對路徑從 cwd（daemon 的 cwd）算——
// 子行程 cd 到 cwd 才叫 aos-exec，所以不轉。小格建不了 MkdirFailed、stderr 開不了／fork 失敗 LaunchFailed；aos-exec 自己的錯寫在小格的
// stderr.txt、子項以 1 結束（phase done、code 1）。自然退 0 才下表；已知非 0 一律留 stopped＋reason。
// 11-02 晚：spec 的 exec 是內嵌單子（物件）＝寫成小格的 exec.json {"exec": 單子}（cwd 定成 daemon 的 cwd，pin_cwd），子行程跑 `aos-exec -- 小格/exec.json#/exec`。
Child spawn_exec(const std::string& name, const std::string& cell, bool deep, const Json& spec, const std::string& cwd,
                 const std::string& dstack, const CellNames& names, const Json& limits);

// 公開 ctl：父寫的 loop 設定有非空 ctl 才用它，其他一律 ctl.json。
std::string ctl_name(const std::string& cell, const CellNames& names);

// 還活著嗎（自己生的：結束了就收屍、記 code／signal）。
bool alive(Child& c);

// procs_state 裡的一列：{"pid", "started_at_ticks", "phase", "code", "signal", "stack", "exec", "def"}，起它時給了工作區才多一欄 "ws"、
// 有份額才多一欄 "limits"（11-05 feat-proto 件 5：生效的那份）。
// exec（11-04 晚）一律寫：起它時的目標（絕對）或 null。def（11-04）一律寫：起它時給的定義資料夾或 null。
// held（stopped 的列）的 pid、started_at_ticks 是 null。
// 11-05（portable-flow，使用者「可以用daemon作為相對路徑的一個基準點」）：stack、ws、exec、def 存成相對 dstack（daemon 的 stack）的路徑
// （字串算、不解捷徑；exec 的 `#` 片段照留）；reason 一律寫（null 或字串）。
// 11-10（two-machines）：as_written 有才寫（指示詞原形照存；$ref 的檔名同 launch 存相對 dstack）；ws、stack、exec、def 仍是解好的值（給讀表的人）。
Json row(const Child& c, const std::string& dstack);

// 11-05：path 相對 base 的寫法（兩個都是絕對、已整理過；字串逐段比，不解捷徑；一樣＝"."）。path 不是絕對＝原樣回。
std::string rel_to(const std::string& path, const std::string& base);
// 11-05：`檔#/…` 只把 # 前面相對化（rel_to）；只有 `#/…` 的、相對的原樣回。
std::string rel_spec(const std::string& spec, const std::string& base);
// 11-05：寫進小格的目標＝{"$env": "AOS_DAEMON", "$path": 相對 dstack}（aos-loop／aos-exec 解指示詞時拼回；03 推薦 (b)）。
Json daemon_ref(const std::string& abs, const std::string& dstack);

}  // namespace aos::daemon
