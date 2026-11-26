// common.hpp：aos-daemon 各檔共用的型別與小工具（設定、天空、proc 表、起動時握住的 fd）。
#pragma once

#include <string>
#include <sys/types.h>
#include <utility>
#include <vector>

namespace d2 {

// 天空設定的一條（json 物件寫法見 README）：bind（src、dst、rw）、tmpfs／proc／dev（dst）、symlink（target、dst）。
struct NsEntry {
    std::string kind;   // bind tmpfs proc dev symlink
    std::string src;    // bind：外面（daemon 起動前那一層）的絕對路徑；symlink：連結的目標
    std::string dst;    // 天空裡的絕對路徑
    bool rw = false;    // 只有 bind 用
};

// 一個預定的掛載（設定展開後的樣子；symlink 不是掛載，不在這裡）。根 tmpfs 是第一個。
struct Mount {
    std::string kind;   // tmpfs bind proc dev（dev＝/dev 那塊 tmpfs；裡面的裝置檔是 bind）
    std::string src;    // bind 的來源（外面的路徑），其他寫 "-"
    std::string dst;
    bool rw = false;
};

// start 收的設定檔（json）讀出來的樣子。
struct ProcConfig {
    std::string name;
    std::vector<std::string> argv;
    std::vector<std::string> env;      // "K=V"
    std::string cwd = "/";
    std::vector<NsEntry> ns;
    int uid = 0;                       // 0＝天空裡的 0 號（外面的使用者本人）；N＞0＝subuid 範圍裡第 N 個
    std::vector<std::pair<std::string, std::string>> cgroup;   // cgroup 檔名 → 值（起動前寫進那隻的 cgroup）
    std::string stdout_path, stderr_path;   // 外面的路徑；空＝/dev/null
    std::string path;                  // 從哪個檔讀來的
    bool landlock = false;             // 設定寫了 locks.landlock: true（其他 proc 不管寫不寫都進；init 寫了才進）
    std::string net = "none";          // "none"（預設：自己一個 network namespace，只有 lo）或 "host"（跟 daemon 同一個）
    // 下面兩個只有 init 的設定收；其他 proc 寫了就拒
    std::string daemon_access;         // "mount"（不寫＝這個）或 "ptrace"
    std::string daemon_path;           // mount 模式時 daemon 的目錄在 init 天空裡的位置；空＝/aos
};

// init（daemon 起的第一隻）怎麼碰 daemon 的目錄（設定檔的 daemon_access）：
//   mount（預設）：daemon 的目錄掛在它天空裡的 daemon_path（預設 /aos），有 cgroup 時 cgroup 夾在
//                  dirname(daemon_path)/cgroup，一個 cap 都不給，AOS_DAEMON=daemon_path
//   ptrace：留 CAP_SYS_PTRACE、走 /proc/1/cwd（舊的做法）
extern const char* const DEFAULT_DAEMON_PATH;   // "/aos"
inline bool init_mounts(const ProcConfig& c) { return c.daemon_access != "ptrace"; }
std::string init_daemon_path(const ProcConfig& c);   // daemon_path 或 /aos
std::string init_cgroup_path(const ProcConfig& c);   // dirname(daemon_path)/cgroup

ProcConfig parse_config(const std::string& text, const std::string& path);   // 錯了丟 std::runtime_error("ConfigBad …")
bool abs_path_ok(const std::string& p);   // 絕對、乾淨（沒有 . .. 空段、尾巴 /）的路徑
std::vector<Mount> plan_mounts(const std::vector<NsEntry>& ns);
// init（mount 模式）的天空不能自己用 daemon_path 與 cgroup 夾的位置：用了回 "ConfigBad …"，沒有回 ""
std::string init_ns_conflict(const ProcConfig& c, bool cgroup_on);
extern const char* const DEV_NODES[5];

// daemon 起動時握住的東西（之後換根進小世界，外面的檔案只能經這些 fd 碰）。
struct World {
    int rootfd = -1;       // 原本那一層的根（O_PATH）；讀設定檔用 openat2 RESOLVE_IN_ROOT
    int procfd = -1;       // 自己 PID namespace 的 procfs
    int hostprocfd = -1;   // 起動那一層的 procfs（查外面的 PID）
    int orignsfd = -1;     // 原本那一層的 mount namespace（組天空、跑的時候掛都先進這裡拿來源）
    int cgfd = -1;         // 交給 daemon 的 cgroup 夾；-1＝沒有
    std::string cg_host;   // 那個 cgroup 夾在外面的路徑
    std::string cg_note;   // 沒有 cgroup 時的原因
    bool setgroups_ok = true;   // 用了 newgidmap（false＝setgroups 被設成 deny）
    long subuid_start = 0, subuid_count = 0;   // 0＝沒有 subuid
    long host_uid = 0, host_gid = 0;
    int landlock_abi = 0;
    long host_pid = 0;     // daemon 自己在起動那一層的 PID
};
extern World W;

// 起動參數（main.cpp 讀，起動那一層與 daemon 都用）：預設值 ← daemon 設定檔（有給的話）← 命令列參數（後蓋前）
struct Options {
    std::string config_path;          // daemon 設定檔（外面的絕對路徑）；空＝只用命令列參數起
    std::string init_path;            // init 的設定檔（外面的路徑）；內嵌時是 "<config_path>#/init"；init_path 與 init_text 都空＝沒有 init
    std::string init_text;            // daemon 設定檔裡內嵌的 init 設定（json 文字）；空＝讀 init_path
    bool restart = true;              // init 死了：true＝restart、false＝exit
    int restart_limit = 5;            // window 秒內死超過這麼多次就不再起
    double restart_window = 60;
    bool restart_limit_stay = false;  // 到重起上限：false＝daemon 結束（exit，預設）、true＝留著、沒有 init（stay）
    bool exit_code_own = false;       // on_init_exit exit 時 daemon 的退出碼：false＝init 的（預設）、true＝自己的 EXIT_INIT_EXITED
    double exit_grace = 0;            // 收到結束訊號：先只對 init 送 SIGTERM，最多等這麼多秒，再全部 SIGKILL
    bool parent_death_exit = true;    // 起動那一層死了 daemon 跟著走（parent-death signal）；false＝stay
    bool cgroup_auto = true;
    std::string cgroup_off_note = "--cgroup off";   // cgroup 關掉時 status 寫的原因（命令列或設定檔）
    bool subuid_auto = true;
};
std::string seconds_text(double s);   // 2 → "2"、0.5 → "0.5"
inline bool has_init(const Options& o) { return !o.init_path.empty() || !o.init_text.empty(); }
const int EXIT_INIT_EXITED = 3;       // exit_code own：init 結束了、on_init_exit exit 時 daemon 的退出碼

// daemon.cpp：PID namespace 的 1 號。sync_fd 等起動那一層寫好 uid/gid 對照表再讀到自己在外面的 PID。
[[noreturn]] void daemon_main(const Options& o, int sync_fd);

// spawn.cpp：在主執行緒上叫（只有主執行緒 fork 與收屍）。
struct Spawned {
    pid_t pid = 0;                 // daemon 那一層的 PID
    long host_pid = 0;             // 起動那一層的 PID
    std::vector<Mount> mounts;
    std::string ns;               // 天空表（從 mountinfo 量的），一行一個掛載的文字
    std::string ns_json;          // 同一張表的 JSON 陣列（一行一個物件），跟 ns 一起量、一起換
    std::string ns_check;         // "ok" 或哪裡對不上
    std::vector<std::string> locks;
    std::string cgroup;            // cgroup 夾名（在 W.cgfd 底下），空＝沒有
};
std::string spawn(const ProcConfig& cfg, bool init, long seq, Spawned& out);   // ""＝成功，否則 "代號 原因"
std::string live_mount(pid_t pid, const std::string& src, const std::string& dst, bool rw);
std::string live_umount(pid_t pid, const std::string& dst);

// ns.cpp
std::string ns_table(pid_t pid, const std::vector<Mount>& planned, std::string& check, std::string& json);
std::string esc(const std::string& s);

// util.cpp
std::string read_host_file(const std::string& path, std::string& err);   // 經 W.rootfd；err 空＝成功
std::string read_fd_at(int dirfd, const std::string& rel);              // 讀不到回空字串
std::string iso_now();
double mono_now();
void log(const std::string& msg);   // "aos-daemon: msg" 寫到 stderr
int signal_number(const std::string& s);   // 認 9、KILL、SIGKILL；不認得回 0
std::string signal_name(int sig);
std::string errstr(int e);

}  // namespace d2
