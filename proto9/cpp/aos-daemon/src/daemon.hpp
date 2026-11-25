// daemon.hpp：aos-daemon 內部共用——設定、底下每隻 proc 的表、做事的線交給監工的請求、監工本身與系統小工具的宣告。
#pragma once

#include "aos/procfs.hpp"

#include <chrono>
#include <condition_variable>
#include <deque>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <sys/types.h>
#include <vector>

namespace aosd {

namespace pf = aos::procfs;
using Clock = std::chrono::steady_clock;

struct Config {
    std::string aos_name;     // 自己的名字路；根是 "/"
    std::string mountpoint;   // 自己的掛載點（絕對路徑）
    std::string mount_base;   // 底下的 proc 的掛載點放這裡（絕對路徑）
    std::string aos_root;     // 交給底下的 AOS_ROOT
    bool is_root = false;
    double register_timeout = 10, check_interval = 5, check_timeout = 1, stop_timeout = 10, ctl_timeout = 1;
};

// 表上的一隻。只有監工改它；回答的線、做事的線只在拿著 State::mu 時讀。
struct Proc {
    std::string name;                     // 表上的名字（一層，不含 /）
    unsigned long long id = 0;            // 同名拿掉再加回來時分得出是哪一隻
    bool external = false;                // register 進來的：不送訊號、不卸掛載
    std::vector<std::string> argv, env;   // 怎麼起（env 是額外的 "K=V"）
    std::string phase = "stopped", want = "up";
    pid_t pid = -1;
    int pidfd = -1;                       // 外來的才有：不是自己的子行程，靠它知道死了沒
    std::string code = "-", sig = "-", reason = "-", persist = "-", mailbox = "-", stuck = "no";
    std::string mount;                    // 交給它的 AOS_MOUNT
    bool linked = false, removing = false;
    std::string killed;                   // 被 daemon 強制收時，結束後寫進 reason 的那句
    Clock::time_point deadline;           // starting：登記期限；rm 時：強制收的時間
    Clock::time_point next_try;           // 下次試讀 settings／status
    int inflight = 0;                     // 為它開的、還沒收屍的小行程
    int hung = 0;                         // 其中到期被放棄的（可能殺不掉、卡在它的目錄裡）
    std::string last_error;               // 登記時最後一次試讀的錯
};

// 做事的線（procs_ctl 的 Action）交給監工的一道指令；監工做完 daemon 這邊的動作就 finish。
struct Request {
    std::vector<std::string> words;
    std::string error;
    bool finished = false;
    std::mutex mu;
    std::condition_variable cv;
    void finish(std::string err);
    bool wait(double seconds);
};

struct State {
    std::mutex mu;   // 管下面全部；拿著它時不做會久的事
    std::map<std::string, Proc> procs;
    std::string phase = "running";   // 自己的 aos_phase
    std::deque<std::shared_ptr<Request>> requests;
    bool stop_requested = false;
};

// ---------- sys.cpp ----------

struct MountEntry {
    std::string point, fstype, source;
};
std::vector<MountEntry> read_mountinfo();
std::string mount_of_pid(pid_t pid);   // fsname 是 "...:<pid>" 的 aosproc 掛載點，沒有回 ""
std::string now_iso();
std::string kv_get(const std::string& text, const std::string& name);   // 「名稱: 值」文字裡的一行，沒有回 "-"
std::string signal_name(int sig);
// 拋棄式小行程：只做一次 open＋read（write＝false）或 open＋write，結果寫進回傳的管子。
// 管子內容："O" + ('x' 可執行／'-') + 讀到的資料；或 "E" + errno。fd 是非阻塞、close-on-exec。
struct HelperStart {
    pid_t pid = -1;
    int fd = -1;
};
HelperStart start_helper(const std::string& path, bool write, const std::string& data);
// fork＋execve 一隻底下的 proc；失敗回 -1 並填 err。
pid_t spawn(const std::vector<std::string>& argv, const std::vector<std::string>& env, std::string& err);
std::string find_in_path(const std::string& prog);

// ---------- json.cpp ----------

// {"exec": [argv...], "env": {...}}；錯了回 "代號 原因"，對了回 ""。
std::string parse_spec(const std::string& text, std::vector<std::string>& argv, std::vector<std::string>& env);

// ---------- 監工：唯一會碰底下 proc 的線，自己從不阻塞 ----------

class Supervisor {
public:
    Supervisor(const Config& cfg, State& st, pf::Fs& fs, int sigfd, int evfd);
    void run();   // 回來＝該結束了（stop 收完底下的）

private:
    using Done = std::function<void(bool ok, int err, const std::string& data)>;
    struct Helper {
        std::string proc;
        unsigned long long id = 0;
        int fd = -1;
        bool reaped = false, abandoned = false;
        Clock::time_point deadline;
        std::string out;
        Done done;
    };

    // supervisor.cpp
    void on_signals();
    void reap();
    void read_helper(pid_t pid);
    void finish_helper(pid_t pid, bool timed_out);
    void drop_helper(std::map<pid_t, Helper>::iterator it);
    void tick();
    void helper(Proc& p, const std::string& path, bool write, const std::string& data, double timeout, Done done);
    void registered(const std::string& name, unsigned long long id, const std::string& settings);
    void exited(Proc& p, int status);
    void external_gone(Proc& p);
    void link(Proc& p);
    void unlink(Proc& p);
    Proc* find(const std::string& name, unsigned long long id);

    // commands.cpp
    void handle(const std::shared_ptr<Request>& r);
    void cmd_add(const std::shared_ptr<Request>& r);
    void cmd_register(const std::shared_ptr<Request>& r);
    void cmd_stop(const std::shared_ptr<Request>& r, Proc& p);
    void cmd_rm(const std::shared_ptr<Request>& r, Proc& p);
    std::string start_proc(Proc& p);
    void force_kill(Proc& p, const std::string& why);
    void begin_shutdown();
    bool shutdown_tick();
    std::string child_name(const std::string& name) const;

    const Config& cfg_;
    State& st_;
    pf::Fs& fs_;
    int sigfd_, evfd_;
    std::map<pid_t, Helper> helpers_;
    std::vector<std::string> cleanups_;   // 等放開鎖再清的死掛載
    unsigned long long next_id_ = 1;
    bool shutting_ = false, forced_ = false;
    Clock::time_point shut_deadline_;
};

// 每個節點 "procs/<名>" 的連結目標
inline std::string cwd_of(pid_t pid) { return "/proc/" + std::to_string(pid) + "/cwd"; }

}  // namespace aosd
