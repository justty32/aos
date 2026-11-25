// internal.hpp：aos-procfs 庫內部共用的型別——節點表、指令檔的鎖與做事的線、掛載的小工具。
#pragma once

#include "aos/procfs.hpp"

#include <atomic>
#include <condition_variable>
#include <map>
#include <mutex>
#include <thread>
#include <unordered_map>

namespace aos::procfs {

// ---------- 指令檔 ----------

struct Ctl::Impl : std::enable_shared_from_this<Ctl::Impl> {
    struct Entry {
        Action act;
        Check check;
    };

    std::string prefix;
    std::map<std::string, Entry> table;   // mount 之後不再改，回答的線讀它不用鎖

    mutable std::mutex mu;
    std::condition_variable cv;
    bool busy = false;                    // 鎖：從收下到做完
    bool has_job = false;
    bool quit = false;
    Command job;
    std::string cmd = "-", state = "-", error = "-";
    long long count = 0;
    std::thread worker;

    // 回答的線上叫：0＝收下（或空寫入），否則 errno（EBUSY／EINVAL）。
    int write(std::string_view data);
    bool open_ok() const;
    void start();
    void stop();   // 不等正在跑的那道指令
    void run();
};

// ---------- 節點表 ----------

enum class Kind { Dir, Text, Json, Ctl, Link, Sock };

struct Node {
    Kind kind = Kind::Dir;
    uint64_t parent = 1;
    std::string name;
    std::vector<uint64_t> kids;           // 照加入的先後，ls 看到的順序就是這個
    uint32_t mode = 0;                    // 不含檔案種類的權限位
    bool sockets = false;
    Producer produce;
    std::shared_ptr<const std::string> data;   // json 內容或 symlink 目標
    Ctl* ctl = nullptr;
};

struct DirEnt {
    std::string name;
    uint64_t nid;
    uint32_t type;
};

struct Fs::Impl {
    Options opt;
    uint32_t uid = 0, gid = 0;
    long long t0 = 0;

    mutable std::mutex mu;                // 管 nodes、fhs、dirs；拿著它時不叫使用者的回呼
    std::unordered_map<uint64_t, Node> nodes;
    uint64_t next_nid = 2;                // 不回收：FORGET 不理也不會認錯人
    std::unordered_map<uint64_t, std::shared_ptr<const std::string>> fhs;
    std::unordered_map<uint64_t, std::shared_ptr<std::vector<DirEnt>>> dirs;
    uint64_t next_fh = 1;
    std::vector<std::unique_ptr<Ctl>> ctls;

    int fd = -1;
    std::string mnt;
    bool created_dir = false;
    bool is_mounted = false;
    std::vector<std::thread> threads;
    std::mutex tmu;
    std::condition_variable tcv;
    int live_threads = 0;

    uint64_t lookup_path(const std::string& path, std::string* leaf, bool want_parent) const;
    uint64_t add_node(const std::string& path, Node n);
    void loop();
    void dispatch(const char* buf, size_t len);
    void reply(uint64_t unique, int err, const void* data = nullptr, size_t len = 0);
};

// ---------- 掛載（mount.cpp） ----------

struct MountEntry {
    unsigned major = 0, minor = 0;
    std::string point, fstype, source;
};

std::vector<MountEntry> read_mountinfo();
// 掛載點的真實路徑：只對上一層 realpath，不碰 path 本身（死掉或卡住的掛載一碰就錯或卡）。
std::string canonical_point(const std::string& path);
// 叫 fusermount3 掛上，回 /dev/fuse 的 fd（close-on-exec）。失敗丟 std::runtime_error。
int fuse_mount(const std::string& mnt, const std::string& opts);
// 跑 fusermount3 args...，回結束碼；quiet＝丟掉它的 stderr。
int run_fusermount(const std::vector<std::string>& args, bool quiet);

void forbid_on_answer_thread(const char* what);
void mark_answer_thread();

}  // namespace aos::procfs
