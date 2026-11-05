// limits.hpp：【child】proc 的份額 limits（11-05 feat-proto 件 5，使用者「會想要限制特定aos proc所占用的資源。以及daemon/kernel自己本身被限制占用資源，
// 並且會分配份額給proc」、「讓daemon偷偷給底下的proc包s6」）。內部標頭。
//
//   check_limits  驗一份 limits（daemon.json 頂層、procs 每列、procs_ctl、信共用）：物件；key 只有 mem_mb、cpu_s、procs、file_mb、files（正整數）
//                 與 user（非空字串）；壞丟 CfgBad（呼叫者照 stack 那三條錯誤路徑處理：daemon.json 退 1、procs_ctl 不採用、壞信）
//   prep_limits   fork 之前把 limits 備成系統呼叫要的值（rlimit 的數字、user 的 uid／gid／groups 先查好）
//   apply_limits  子行程裡（setsid、接好 stderr 之後、run_cli 之前）照備好的做：setrlimit（soft＝hard＝寫的值）、setgroups＋setgid＋setuid；
//                 失敗＝stderr（小格的 stderr.txt）一行 `aos-daemon: error: LimitBad …`、_exit(1)
// 等同 s6-softlimit／s6-setuidgid：做的就是那兩支程式內部那幾個系統呼叫（代定 1：daemon 自己做、不 exec s6、不依賴 PATH；題 6 留使用者翻案）。
// mem_mb→RLIMIT_AS＋RLIMIT_DATA（不碰 RLIMIT_STACK，同 aos-sandbox）、cpu_s→RLIMIT_CPU、procs→RLIMIT_NPROC、file_mb→RLIMIT_FSIZE、files→RLIMIT_NOFILE。
// rlimit 是每個行程各自的上限，不從 daemon 的總額扣；daemon 自己的 hard limit 子項天生超不過（比它寬＝setrlimit EPERM＝LimitBad，不自動夾）。
#pragma once

#include "common/common.hpp"

#include <string>
#include <vector>

#include <sys/types.h>

namespace aos::daemon {

// 驗 v（null＝當沒寫，不驗）；where＝錯誤訊息裡的位置（例 procs[bob].limits）。
// user 只認本機 /etc/passwd、/etc/group 裡的帳號（不經 NSS：靜態連結的 daemon 用 getpwnam 會出事，見 limits.cpp）。
void check_limits(const Json& v, const std::string& where);

struct Limits {
    struct Rl {
        int resource;
        unsigned long long value;   // 給 setrlimit 的值（MB 已換成位元組）
        const char* key;            // 訊息用：寫的 key
        long long shown;            // 訊息用：寫的值
    };
    std::vector<Rl> rl;
    bool has_user = false;
    bool user_found = false;
    std::string user;
    uid_t uid = 0;
    gid_t gid = 0;
    std::vector<gid_t> groups;
    bool empty() const { return rl.empty() && !has_user; }
};

// limits（null 或驗過的物件）→ 備好的值。user 查不到＝user_found false（子行程報 LimitBad）。
Limits prep_limits(const Json& limits);

// 子行程裡呼叫：照做；失敗＝stderr 一行、_exit(1)（不回來）。lim.empty()＝什麼都不做。
void apply_limits(const Limits& lim);

}  // namespace aos::daemon
