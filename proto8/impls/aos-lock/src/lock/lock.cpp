// lock.cpp：【lock】mkdir 取鎖、目錄 fd 原子刊登名牌、保管 flock fd、收屍與放鎖。
//
// 只用 Linux 的原子動作（medium-plan § 五、決定 18）：mkdir（拿）、rename（放、收）。
#include "common/common.hpp"

#include "aos/util/files.hpp"
#include "aos/util/proc.hpp"

#include <cerrno>
#include <cstdio>
#include <cstring>
#include <chrono>
#include <thread>
#include <vector>
#include <mutex>
#include <fcntl.h>
#include <sys/file.h>
#include <pthread.h>
#include "aos/util/clock.hpp"

#include <sys/stat.h>
#include <unistd.h>

namespace aos::lock {

std::string lock_dir_of(const std::string& target) {
    std::string t = target;
    bool slash = false;
    while (t.size() > 1 && t.back() == '/') {
        t.pop_back();
        slash = true;
    }
    if (slash || aos::is_dir(t)) {
        return aos::join(aos::abspath(t), ".lock");
    }
    return aos::abspath(t) + ".lock";
}

// fd 持有者：離開 scope 自動關閉；存活 fd 留在 registry，fork 子行程立即關閉繼承副本。
struct Fd {
    int value = -1;
    ~Fd() {
        if (value >= 0) {
            close(value);
        }
    }
    Fd(const Fd&) = delete;
    Fd& operator=(const Fd&) = delete;
    explicit Fd(int fd = -1) : value(fd) {}
};
struct Held {
    std::string path;
    int fd;
};
static std::vector<Held> held;
static std::mutex held_mutex;
static void fork_prepare() {
    held_mutex.lock();
}
static void fork_parent() {
    held_mutex.unlock();
}
static void fork_child() {
    for (Held& h : held) {
        if (h.fd >= 0) {
            close(h.fd);
        }
        h.fd = -1;
    }
    held_mutex.unlock();
}
static void register_fork_cleanup() {
    static const int registered = pthread_atfork(fork_prepare, fork_parent, fork_child);
    if (registered != 0) {
        throw Error{code::WriteFailed, "cannot register lock fork cleanup"};
    }
}
// 呼叫者持有 held_mutex，從開 marker 到註冊期間 fork 都不能進來。
static void keep_fd(const std::string& path, Fd& fd) {
    for (std::vector<Held>::iterator it = held.begin(); it != held.end();) {
        if (it->path == path) {
            if (it->fd >= 0) {
                close(it->fd);
            }
            it = held.erase(it);
        } else {
            ++it;
        }
    }
    held.push_back({path, fd.value});
    fd.value = -1;
}
static void close_held(const std::string& path) {
    std::lock_guard<std::mutex> guard(held_mutex);
    for (std::vector<Held>::iterator it = held.begin(); it != held.end();) {
        if (it->path == path) {
            if (it->fd >= 0) {
                close(it->fd);
            }
            it = held.erase(it);
        } else {
            ++it;
        }
    }
}

// 用目錄 fd 寫，慢到被收屍時也不會把名牌寫進別人新建的鎖。
static void write_holder(int dir_fd, const Json& doc) {
    std::string text = doc.dump(2, ' ', false, Json::error_handler_t::replace);
    Fd fd{openat(dir_fd, ".holder.json.tmp", O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0666)};
    if (fd.value < 0) {
        throw Error{code::WriteFailed, "cannot open holder temporary file: " + std::string(std::strerror(errno))};
    }
    size_t offset = 0;
    while (offset < text.size()) {
        ssize_t n = write(fd.value, text.data() + offset, text.size() - offset);
        if (n < 0 && errno == EINTR) {
            continue;
        }
        if (n <= 0) {
            throw Error{code::WriteFailed, "cannot write holder temporary file"};
        }
        offset += static_cast<size_t>(n);
    }
    int raw_fd = fd.value;
    fd.value = -1;
    if (close(raw_fd) != 0) {
        throw Error{code::WriteFailed, "cannot close holder temporary file: " + std::string(std::strerror(errno))};
    }
    if (renameat(dir_fd, ".holder.json.tmp", dir_fd, "holder.json") != 0) {
        throw Error{code::WriteFailed, "cannot publish holder file: " + std::string(std::strerror(errno))};
    }
}

// 改名成 <鎖>.releasing.<獨一無二的名字>：成功回新名字，鎖不在回空字串。
static std::string move_away(const std::string& lock_dir) {
    std::string gone = lock_dir + ".releasing." + aos::unique_id();
    if (std::rename(lock_dir.c_str(), gone.c_str()) == 0) {
        return gone;
    }
    int e = errno;
    if (e == ENOENT) {
        return "";
    }
    throw Error{code::WriteFailed, "cannot rename " + lock_dir + ": " + std::strerror(e)};
}

// 替死掉的持有者收。好幾個人同時判到同一把死鎖時，直接改名會出事：A 收完、B 剛 mkdir 到新的，C 才改名——
// C 搬走的是 B 的活鎖（10-29 實測：20 個人同時收，B 寫名牌時資料夾不見了）。所以先在鎖裡 mkdir 收屍牌 .reaping：
//   1. mkdir <鎖>/.reaping：只有一個人建得成（這一把歸他收）；建不成＝別人在收（牌子 10 秒沒動＝收的人也死了，拔掉、下次再來）
//   2. 再讀一次名牌：跟判的那份不同（牌子掛進了別人剛拿到的新鎖）＝拔掉牌子、不收；名牌本來就不在的，還要是同一個資料夾（inode）
//   3. 改名成 <鎖>.releasing.<獨一無二的名字> 再刪
static void reap(const std::string& lock_dir, const Seen& judged) {
    std::string token = aos::join(lock_dir, ".reaping");
    if (::mkdir(token.c_str(), 0777) != 0) {
        struct stat st{};
        if (errno == EEXIST && stat(token.c_str(), &st) == 0) {
            long long mtime_ms = (long long)st.st_mtim.tv_sec * 1000LL + st.st_mtim.tv_nsec / 1000000L;
            long long age = now_ms() - mtime_ms;
            if (age >= STALE_MS || age <= -STALE_MS) {   // 11-05 第二輪：時鐘往回跳過的（mtime 在未來）同樣算收的人死了
                ::rmdir(token.c_str());
            }
        }
        return;   // 別人在收、或鎖已經不在
    }
    Seen again = look(lock_dir);
    if (!again.held || again.raw != judged.raw || again.ino != judged.ino) {
        ::rmdir(token.c_str());
        return;
    }
    again.age_ms = judged.age_ms; // .reaping 是我們自己的 mtime 變動，不重設殘缺名牌的年齡。
    if (!reapable(again)) {
        ::rmdir(token.c_str());
        return;
    }
    std::string gone = move_away(lock_dir);
    if (!gone.empty()) {
        close_held(aos::abspath(lock_dir));
        aos::remove_tree(gone);
    }
}

bool try_acquire(const std::string& lock_dir, const Holder& h) {
    if (h.lease_cycles && *h.lease_cycles < 0) {
        throw Error{code::ArgumentsBad, "lease_cycles must be non-negative"};
    }
    register_fork_cleanup();
    for (int i = 0; i < 3; ++i) {
        if (::mkdir(lock_dir.c_str(), 0777) == 0) {
            std::lock_guard<std::mutex> guard(held_mutex);
            Fd dir{open(lock_dir.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC)};
            struct stat st{};
            if (dir.value < 0 || fstat(dir.value, &st) != 0) {
                throw Error{code::WriteFailed, "cannot open lock directory: " + lock_dir};
            }
            Fd marker;
            bool own_artifacts = !h.flock;
            try {
                Holder current = h;
                current.acquired_at = aos::utc_now_ms();
                current.acquired_at_cycles = aos::now_cycle();
                if (h.flock) {
                    marker.value = openat(dir.value, "holder.flock", O_RDWR | O_CREAT | O_CLOEXEC, 0666);
                    if (marker.value < 0) {
                        throw Error{code::WriteFailed, "cannot open holder.flock: " + lock_dir};
                    }
                    if (flock(marker.value, LOCK_EX | LOCK_NB) != 0) {
                        if (errno == EWOULDBLOCK || errno == EAGAIN) {
                            return false;
                        }
                        throw Error{code::WriteFailed, "cannot lock holder.flock: " + lock_dir};
                    }
                    own_artifacts = true;
                }
                write_holder(dir.value, to_json(current));
                struct stat published{};
                if (stat(lock_dir.c_str(), &published) != 0 || published.st_ino != st.st_ino) {
                    continue;
                }
                if (h.flock) {
                    keep_fd(aos::abspath(lock_dir), marker);
                }
            } catch (...) {
                if (!own_artifacts) {
                    throw;
                }
                unlinkat(dir.value, ".holder.json.tmp", 0);
                unlinkat(dir.value, "holder.json", 0);
                unlinkat(dir.value, "holder.flock", 0);
                struct stat current{};
                if (stat(lock_dir.c_str(), &current) == 0 && current.st_ino == st.st_ino) {
                    ::rmdir(lock_dir.c_str());
                }
                throw;
            }
            return true;
        }
        int e = errno;
        if (e != EEXIST) {
            throw Error{code::MkdirFailed, "cannot create " + lock_dir + ": " + std::strerror(e)};
        }
        Seen s = look(lock_dir);
        if (!s.held) {
            continue;   // 剛好被放掉了：再 mkdir 一次
        }
        if (!reapable(s)) {
            return false;
        }
        reap(lock_dir, s);
    }
    return false;
}

bool acquire(const std::string& lock_dir, const Holder& h, long long wait_ms) {
    // 等多久用 steady_clock（牆上時鐘會被校時拉動，WSL 上看過一次跳掉一半）
    std::chrono::steady_clock::time_point end = std::chrono::steady_clock::now() + std::chrono::milliseconds(wait_ms > 0 ? wait_ms : 0);
    while (true) {
        if (try_acquire(lock_dir, h)) {
            return true;
        }
        if (wait_ms >= 0 && std::chrono::steady_clock::now() >= end) {
            return false;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
    }
}

bool release(const std::string& lock_dir) {
    std::string gone = move_away(lock_dir);
    close_held(aos::abspath(lock_dir));
    if (gone.empty()) {
        return false;
    }
    aos::remove_tree(gone);
    return true;
}

}  // namespace aos::lock
