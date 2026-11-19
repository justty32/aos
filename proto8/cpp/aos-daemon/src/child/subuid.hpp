// subuid.hpp：【child】免 root 把 proc 換成 subuid（limits.user 寫 "sub:N"；kernel-limits-plan 段 3 的最小一刀，線 subuid-1119）。內部標頭。
//
// 做法照 kernel-limits-plan 03 第一節第 4 點（K4 已裁）：每支 proc 自己一個 user namespace，不是整棵樹進 ns。
//   父行程 fork 之前：prep_sub 查 /etc/subuid、/etc/subgid 與 PATH 上的 newuidmap／newgidmap；finish_sub 備好子行程的環境（白名單）；
//                     grant_cell 把小格（proc 的 stack）改成 0700＋ACL u:<subuid>:rwx，預設 ACL u:<subuid>:rwx、u:<daemon 的 uid>:rwx（K16、08 G6）
//   子行程：enter_sub＝unshare(CLONE_NEWUSER) → 經 socketpair 通知父行程 → 等父行程對好號碼 → setgroups({})＋setresgid(G)＋setresuid(N)
//           → 換成備好的環境、關掉 3 以上的 fd（L5）→ 檢查小格、daemon 的 cwd、工作區走不走得到；失敗＝stderr 一行 LimitBad、_exit(1)
//   父行程 fork 之後：map_sub＝等子行程開好 ns，跑 `newuidmap PID 0 <我的 uid> 1 N <起點+N-1> 1` 與 `newgidmap PID 0 <我的 gid> 1 G <起點+G-1> 1`，
//                     回報子行程；失敗＝小格 stderr.txt 一行 LimitBad（子行程默默退 1）
// 群組：一台 daemon 一個（K6、K18）：daemon.json `group`（ns 裡 60001～65536，沒寫＝60001），同台換了身分的 proc 主群組都是它、附屬群組清空。
// 號碼：sub:N 的 N 是 1～60000（同 aos-asuser）；真的 uid＝/etc/subuid 這個帳號第一段的起點＋N－1。
#pragma once

#include <string>
#include <vector>

#include <sys/types.h>

namespace aos::daemon {

// /etc/passwd、/etc/group、/etc/subuid 這類冒號分隔的檔，一行一列（讀不到＝空）。不經 NSS（daemon 是靜態連結的，見 limits.cpp）。
std::vector<std::vector<std::string>> etc_rows(const char* path);

// "sub:N" 的 N（1～60000、不收前導 0）；不是這個寫法＝0。
int sub_number(const std::string& user);
inline bool is_sub(const std::string& user) { return user.rfind("sub:", 0) == 0; }

// daemon.json 的 group（ns 裡的號碼），daemon 起來時設一次；沒設＝60001。
inline constexpr int SUB_GROUP_MIN = 60001;
inline constexpr int SUB_GROUP_MAX = 65536;
void set_sub_group(int group);
int sub_group();

struct Sub {
    int n = 0;                        // 0＝不換
    int group = 0;                    // ns 裡的主群組
    uid_t uid = 0;                    // 真的 uid／gid（給 ACL 與訊息）
    gid_t gid = 0;
    std::string uidmap, gidmap;       // newuidmap／newgidmap 的絕對路徑
    std::vector<std::string> uid_args, gid_args;   // PID 後面的參數
    std::vector<std::string> env;     // 子行程換身分後的整份環境（NAME=VALUE）
    std::vector<std::pair<std::string, int>> reach;   // 換身分後要走得到的路與 access 模式
};

// fork 之前：user＝"sub:N"（check_limits 驗過）。查號碼段與兩支 helper；做不到丟 LimitBad。
void prep_sub(Sub& s, const std::string& user);
// fork 之前：環境白名單（PATH、LANG、LC_ALL、LC_CTYPE、TZ、TERM、PYTHONDONTWRITEBYTECODE、PYTHONIOENCODING 與 AOS_*；
// HOME＝/nonexistent；有工作區＝git safe.directory 指到它），與要檢查的路（小格 rwx、cwd 與工作區 x）。
void finish_sub(Sub& s, const std::string& cell, const std::string& cwd, const std::string& ws);
// fork 之前：小格 0700＋ACL；檔案系統不吃 ACL 之類＝LimitBad。
void grant_cell(const Sub& s, const std::string& cell);
// 父行程 fork 之後：sock＝socketpair 父這端（用完關掉）、err_fd＝小格 stderr.txt。
void map_sub(const Sub& s, pid_t pid, int sock, int err_fd);
// 子行程裡：sock＝socketpair 子這端；envp＝s.env 的指標陣列（fork 之前備好、結尾 nullptr）。失敗不回來。
void enter_sub(const Sub& s, int sock, char** envp);

}  // namespace aos::daemon
