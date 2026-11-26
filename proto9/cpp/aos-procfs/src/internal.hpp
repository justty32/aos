// internal.hpp：aos-procfs 庫內部共用的型別——節點表、請求、指令檔的鎖與做事的線、信箱、掛載的小工具。
#pragma once

#include "aos/procfs.hpp"

#include <atomic>
#include <condition_variable>
#include <cstring>
#include <linux/fuse.h>
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
    std::string cmd, state, error;        // 空＝還沒有（寫出來是 "-"）
    long long count = 0;
    std::thread worker;
    // 「做完才回」（reply_when_done）：收下的那次 WRITE 先不回，記在 pending，做事的線做完再回
    std::atomic<bool> wait_done{false}; // mount 之前定；回答的線不拿鎖就讀
    uint64_t pending = 0;                 // 留著沒回的 WRITE 的 unique；0＝沒有
    uint32_t pending_size = 0;            // 成功時回的寫入長度
    // mount 時由 Fs 給：回一次 WRITE（err 0＝成功、寫了 size byte）。拿著 mu 叫，所以 detach 之後不會再有回覆寫出去
    std::function<void(uint64_t unique, int err, uint32_t size)> answer;

    static constexpr int HELD = -1;       // write 的回傳：收下了、回覆留著（做完才回）
    // 回答的線上叫：0＝收下（或空寫入），HELD＝收下、回覆留著，否則 errno（EBUSY／EINVAL）。
    int write(std::string_view data, uint64_t unique = 0, uint32_t size = 0);
    bool interrupt(uint64_t unique);      // 那次 WRITE 還留著就回 EINTR、回 true
    void cancel_pending(int err);         // 留著的那次（有的話）回 err
    void detach();                        // 之後不再回覆（Fs 要關 /dev/fuse 之前）
    bool open_ok() const;
    void start();
    void stop();   // 不等正在跑的那道指令
    void run();
};

// ---------- 節點表 ----------

enum class Kind { Dir, Text, Json, Ctl, Link, Sock, MailDir, MailFile };
// MailDir 是哪一個夾：信箱根、tmp/、new/、cur/，或一封信夾
enum class Role : uint8_t { None, Root, Tmp, New, Cur, Letter };

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
    // 信箱的節點（mb 非空）。都在 Fs::Impl::mu 底下讀寫
    Mailbox::Impl* mb = nullptr;
    Role role = Role::None;
    std::shared_ptr<std::string> body;    // MailFile 的內容
    uint64_t top = 0;                     // 它屬於哪一封（tmp/、new/ 底下頂層那一項；頂層的就是自己）
    size_t lbytes = 0;                    // 頂層那一項：整封幾 byte
    bool sealed = false;                  // 在 new/ 裡（或正在搬進去）：不能再寫、刪、搬
    double mtime = 0, touched = 0;        // 給 stat 看的時間；最後一次有動靜（判過期用，寄的人改不了）
    uint32_t from_uid = 0, from_pid = 0;  // 搬進 new/ 那次請求的發起者
    double arrived = 0;
};

// 一個請求：表頭與本體（本體的長度已經對過）
struct Req {
    fuse_in_header h;
    const char* body;
    size_t blen;
    // 依結構大小把本體抄出來；短了補 0，不越界
    template <class T>
    void in(T& s) const {
        std::memset(&s, 0, sizeof s);
        std::memcpy(&s, body, std::min(sizeof s, blen));
    }
    // 本體 off 起的一個以 NUL 結尾的名字（越界＝空字串）
    std::string name_at(size_t off) const {
        return off < blen ? std::string(body + off, strnlen(body + off, blen - off)) : std::string();
    }
};

struct Mailbox::Impl {
    Fs::Impl* fs = nullptr;
    MailLimits lim;
    Accept accept;
    uint64_t root = 0, tmp = 0, nw = 0, cur = 0;
    int efd = -1;
    size_t entries = 0;                   // tmp/＋new/ 頂層幾項
    size_t bytes = 0;
    unsigned long long delivered = 0, taken = 0, refused = 0, dropped_stale = 0;
    std::string last_refusal;
    double last_sweep = 0;

    // 以下都要拿著 fs->mu 叫
    void sweep(double now);               // 丟掉 tmp/ 裡過期的
    void drop(uint64_t nid);              // 整項（含信夾裡的檔）拿掉、扣掉計數
    Letter letter(uint64_t nid) const;
};

double wall_now();

// 信名與信夾裡的檔名：不空、不是 . ..、沒有 / 與控制字元（aos-post 的 check_name 也擋控制字元）
inline bool mail_name_ok(const std::string& n) {
    if (n.empty() || n.size() > 255 || n == "." || n == "..") return false;
    for (unsigned char c : n)
        if (c == '/' || c < 0x20 || c == 0x7f) return false;
    return true;
}

// 還在 tmp/、還沒封住的（頂層那一項或信夾裡的檔）：寄的人可以寫、刪、改名
inline bool open_in_tmp(const std::unordered_map<uint64_t, Node>& nodes, const Node& n) {
    if (!n.top) return false;
    const Node& t = nodes.at(n.top);
    return t.parent == t.mb->tmp && !t.sealed;
}

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
    std::vector<std::unique_ptr<Ctl>> ctls;   // mount 之後不再改，回答的線讀它不用鎖
    bool any_wait = false;                // 有「做完才回」的 ctl（mount 時定）：要理 INTERRUPT
    std::vector<std::unique_ptr<Mailbox>> mailboxes;

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
    void fill_attr(uint64_t nid, const Node& n, fuse_attr& a) const;
    fuse_entry_out entry_of(uint64_t nid, const Node& n) const;
    uint64_t kid(const Node& dir, const std::string& name) const;   // 沒有回 0

    // 下面的 op_* 進來時拿著 mu、node 是 h.nodeid 那一個；回覆之前自己放開
    using Lock = std::unique_lock<std::mutex>;
    void op_mknod(const Req& r, Lock& lk, uint64_t nid, Node& node);
    void op_unlink(const Req& r, Lock& lk, Node& node);
    void op_open(const Req& r, Lock& lk, Node& node);
    void op_read(const Req& r, Lock& lk);
    void op_write(const Req& r, Lock& lk, Node& node);
    void op_opendir(const Req& r, Lock& lk, uint64_t nid, Node& node);
    void op_readdir(const Req& r, Lock& lk);
    // 信箱的節點：處理了回 true；false＝交給一般的（LOOKUP、GETATTR、OPENDIR…）
    bool mail_op(const Req& r, Lock& lk, uint64_t nid, Node& node);
    void mail_make(const Req& r, Lock& lk, uint64_t pid, const std::string& name, bool dir, uint32_t mode, bool open);
    void mail_setattr(const Req& r, Lock& lk, uint64_t nid, Node& node);
    void mail_write(const Req& r, Lock& lk, Node& node);
    void mail_remove(const Req& r, Lock& lk, Node& node, bool dir);
    void mail_rename(const Req& r, Lock& lk, uint64_t nid, Node& node);
    int mail_resize(Node& f, size_t size);   // 照上限改 MailFile 的長度；回 errno
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
