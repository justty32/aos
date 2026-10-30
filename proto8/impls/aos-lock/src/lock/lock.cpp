// lock.cpp：【lock】鎖本身——目標換成鎖資料夾、拿（mkdir＋寫名牌）、收屍、等、放（說明見 aos/lock.hpp）。
//
// 只用 Linux 的原子動作（medium-plan § 五、決定 18）：mkdir（拿）、rename（放、收）。
#include "common/common.hpp"

#include "aos/files.hpp"
#include "aos/proc.hpp"

#include <cerrno>
#include <cstdio>
#include <cstring>
#include <chrono>
#include <filesystem>
#include <thread>

#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

namespace fs = std::filesystem;

namespace aos::lock {

std::string lock_dir_of(const std::string& target) {
    std::string t = target;
    bool slash = false;
    while (t.size() > 1 && t.back() == '/') {
        t.pop_back();
        slash = true;
    }
    std::error_code ec;
    if (slash || fs::is_directory(t, ec)) {
        return aos::join(aos::abspath(t), ".lock");
    }
    return aos::abspath(t) + ".lock";
}

// 名牌：先寫 .holder.json.tmp 再改名（不替人建資料夾：鎖資料夾不見了＝寫不了，不要把它建回來）。
static bool write_holder(const std::string& lock_dir, const Json& doc, std::string& why) {
    std::string tmp = aos::join(lock_dir, ".holder.json.tmp");
    std::string path = aos::join(lock_dir, "holder.json");
    std::string text = doc.dump(2, ' ', false, Json::error_handler_t::replace);
    int fd = ::open(tmp.c_str(), O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0666);
    if (fd < 0) {
        why = "開不了 " + tmp + "：" + std::strerror(errno);
        return false;
    }
    size_t done = 0;
    while (done < text.size()) {
        ssize_t n = ::write(fd, text.data() + done, text.size() - done);
        if (n < 0 && errno == EINTR) {
            continue;
        }
        if (n <= 0) {
            why = "寫不了 " + tmp + "：" + std::strerror(errno);
            ::close(fd);
            ::unlink(tmp.c_str());
            return false;
        }
        done += (size_t)n;
    }
    ::close(fd);
    if (std::rename(tmp.c_str(), path.c_str()) != 0) {
        why = "改名不了 " + tmp + "：" + std::strerror(errno);
        ::unlink(tmp.c_str());
        return false;
    }
    return true;
}

// 改名成 <鎖>.releasing.<信號>：成功回新名字，鎖不在回空字串。
static std::string move_away(const std::string& lock_dir) {
    std::string gone = lock_dir + ".releasing." + aos::unique_id();
    if (std::rename(lock_dir.c_str(), gone.c_str()) == 0) {
        return gone;
    }
    int e = errno;
    if (e == ENOENT) {
        return "";
    }
    throw Error{code::WriteFailed, "改名不了 " + lock_dir + "：" + std::strerror(e)};
}

// 替死掉的持有者收。好幾個人同時判到同一把死鎖時，直接改名會出事：A 收完、B 剛 mkdir 到新的，C 才改名——
// C 搬走的是 B 的活鎖（10-29 實測：20 個人同時收，B 寫名牌時資料夾不見了）。所以先在鎖裡 mkdir 收屍牌 .reaping：
//   1. mkdir <鎖>/.reaping：只有一個人建得成（這一把歸他收）；建不成＝別人在收（牌子 10 秒沒動＝收的人也死了，拔掉、下次再來）
//   2. 再讀一次名牌：跟判的那份不同（牌子掛進了別人剛拿到的新鎖）＝拔掉牌子、不收；名牌本來就不在的，還要是同一個資料夾（inode）
//   3. 改名成 <鎖>.releasing.<信號> 再刪
static void reap(const std::string& lock_dir, const Seen& judged) {
    std::string token = aos::join(lock_dir, ".reaping");
    if (::mkdir(token.c_str(), 0777) != 0) {
        struct stat st{};
        if (errno == EEXIST && stat(token.c_str(), &st) == 0) {
            long long mtime_ms = (long long)st.st_mtim.tv_sec * 1000LL + st.st_mtim.tv_nsec / 1000000L;
            if (now_ms() - mtime_ms >= STALE_MS) {
                ::rmdir(token.c_str());
            }
        }
        return;   // 別人在收、或鎖已經不在
    }
    Seen again = look(lock_dir);
    if (!again.held || again.raw != judged.raw || (!judged.raw && again.ino != judged.ino)) {
        ::rmdir(token.c_str());
        return;
    }
    std::string gone = move_away(lock_dir);
    std::error_code ec;
    if (!gone.empty()) {
        fs::remove_all(gone, ec);
    }
}

bool try_acquire(const std::string& lock_dir, const Holder& h) {
    for (int i = 0; i < 3; ++i) {
        if (::mkdir(lock_dir.c_str(), 0777) == 0) {
            std::string why;
            if (!write_holder(lock_dir, to_json(h), why)) {
                ::rmdir(lock_dir.c_str());   // 只拆空的（自己剛建的）；萬一已經不是自己那把，裡面有名牌、拆不掉
                throw Error{code::WriteFailed, why};
            }
            return true;
        }
        int e = errno;
        if (e != EEXIST) {
            throw Error{code::MkdirFailed, "建不了 " + lock_dir + "：" + std::strerror(e)};
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
    if (gone.empty()) {
        return false;
    }
    std::error_code ec;
    fs::remove_all(gone, ec);
    return true;
}

}  // namespace aos::lock
