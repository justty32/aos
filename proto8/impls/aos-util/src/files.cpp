// files.cpp：【aos-util】路徑、讀檔、壞檔留證與文字及 JSON 原子寫入（說明見 include/aos/util/files.hpp）。
//
// 為什麼要「原子寫入」：ctl 窗、state 窗是兩個行程透過檔案講話。如果直接打開舊檔、清空、再寫，
// 讀的人剛好在中間讀到，就會讀到半份（壞 JSON）或空的。改成「寫到旁邊的暫存檔 → rename 蓋過去」：
// rename 在同一個檔案系統裡是原子的，讀的人只會看到「整份舊的」或「整份新的」，不會看到一半。
// 暫存檔放在同一個資料夾，才保證在同一個檔案系統上（跨檔案系統的 rename 會失敗）。
// 暫存名：write_json 用 .名字.<pid>.tmp（帶 pid，多人同寫一個檔不互踩；改名前 fsync）；write_text 由呼叫的人給。
#include "aos/util/files.hpp"
#include "aos/util/proc.hpp"

#include <algorithm>
#include <cstdio>
#include <cerrno>
#include <cstring>
#include <filesystem>
#include <sstream>
#include <set>
#include <utility>

#include <fcntl.h>
#include <unistd.h>
#include <linux/fs.h>
#include <sys/syscall.h>

namespace aos {

std::string abspath(const std::string& path) {
    std::string full = path;
    if (!path.starts_with('/')) {
        full = std::filesystem::current_path().string() + "/" + path;
    }
    std::vector<std::string> parts;
    std::istringstream in(full);
    std::string seg;
    while (std::getline(in, seg, '/')) {
        if (seg.empty() || seg == ".") {
            continue;
        }
        if (seg == "..") {
            if (!parts.empty()) {
                parts.pop_back();
            }
            continue;
        }
        parts.push_back(seg);
    }
    std::string out;
    for (const std::string& p : parts) {
        out += "/" + p;
    }
    if (out.empty()) {
        return "/";
    }
    return out;
}

std::string dirname(const std::string& path) {
    size_t slash = path.rfind('/');
    if (slash == std::string::npos) {
        return "";
    }
    std::string d = path.substr(0, slash + 1);
    while (d.size() > 1 && d.ends_with('/')) {
        d.pop_back();
    }
    return d;
}

std::string join(const std::string& a, const std::string& b) {
    if (b.starts_with('/') || a.empty()) {
        return b;
    }
    if (a.ends_with('/')) {
        return a + b;
    }
    return a + "/" + b;
}

std::optional<TextWriteError> write_text(const std::string& path, const std::string& text,
                                        const std::string& tmp) {
    int fd = open(tmp.c_str(), O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0666);
    if (fd < 0) {
        int saved = errno;
        unlink(tmp.c_str());
        return TextWriteError{TextWriteOperation::open, saved};
    }
    size_t done = 0;
    while (done < text.size()) {
        ssize_t n = write(fd, text.data() + done, text.size() - done);
        if (n < 0 && errno == EINTR) {
            continue;
        }
        if (n <= 0) {
            int saved = EIO;
            if (n < 0) {
                saved = errno;
            }
            close(fd);
            unlink(tmp.c_str());
            return TextWriteError{TextWriteOperation::write, saved};
        }
        done += static_cast<size_t>(n);
    }
    if (close(fd) != 0) {
        int saved = errno;
        unlink(tmp.c_str());
        return TextWriteError{TextWriteOperation::write, saved};
    }
    if (std::rename(tmp.c_str(), path.c_str()) != 0) {
        int saved = errno;
        unlink(tmp.c_str());
        return TextWriteError{TextWriteOperation::rename, saved};
    }
    return std::nullopt;
}

std::optional<std::string> read_file(const std::string& path, int& errno_out) {
    int fd = open(path.c_str(), O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        errno_out = errno;
        return std::nullopt;
    }
    std::string text;
    char buf[65536];
    while (true) {
        ssize_t n = read(fd, buf, sizeof buf);
        if (n < 0 && errno == EINTR) {
            continue;
        }
        if (n < 0) {
            errno_out = errno;   // 例如它是個資料夾（EISDIR）
            close(fd);
            return std::nullopt;
        }
        if (n == 0) {
            break;
        }
        text.append(buf, (size_t)n);
    }
    close(fd);
    errno_out = 0;
    return text;
}

std::optional<Json> read_json(const std::string& path) {
    int err = 0;
    std::optional<std::string> text = read_file(path, err);
    if (!text) {
        return std::nullopt;
    }
    Json doc = Json::parse(*text, nullptr, false);   // false＝不丟例外，壞的回 discarded
    if (doc.is_discarded()) {
        return std::nullopt;
    }
    return doc;
}

// 留證只動主檔；改名與複製都禁止覆蓋已有的 bad 檔，撞名就加尾碼。
std::string keep_bad(const std::string& path, bool copy) {
    std::string stamp = aos::utc_now_ms();
    std::replace(stamp.begin(), stamp.end(), ':', '-');
    std::string base = path + ".bad-" + stamp;
    for (size_t suffix = 0; ; ++suffix) {
        std::string kept = base;
        if (suffix > 0) {
            kept += "-" + std::to_string(suffix);
        }
        std::error_code ec;
        if (copy) {
            std::filesystem::copy_file(path, kept, std::filesystem::copy_options::none, ec);
        } else if (::syscall(SYS_renameat2, AT_FDCWD, path.c_str(), AT_FDCWD, kept.c_str(),
                             RENAME_NOREPLACE) != 0) {
            ec = std::error_code(errno, std::generic_category());
        }
        if (!ec) {
            return std::filesystem::path(kept).filename().string();
        }
        if (ec == std::errc::file_exists) {
            continue;
        }
        throw Error{code::WriteFailed, "cannot keep " + path + " as " + kept + ": " + ec.message()};
    }
}

// 旁觀窗讀不了時只提醒一次；fork 後各自提醒，不動窗檔。
std::optional<Json> read_window(const std::string& prog, const std::string& path) {
    int err = 0;
    std::optional<std::string> text = read_file(path, err);
    std::string reason;
    Json doc;
    if (!text) {
        std::error_code ec;
        std::filesystem::file_status st = std::filesystem::symlink_status(path, ec);
        if (err == ENOENT && st.type() == std::filesystem::file_type::not_found) {
            return std::nullopt;
        }
        reason = "cannot read file: " + std::string(std::strerror(err));
    } else {
        doc = Json::parse(*text, nullptr, false);
        if (doc.is_discarded()) {
            reason = "invalid JSON";
        } else if (!doc.is_object()) {
            reason = "root is not an object";
        } else {
            return doc;
        }
    }
    static std::set<std::pair<pid_t, std::string>> warned;
    if (warned.emplace(::getpid(), path).second) {
        warn(prog, path + " is unreadable (" + reason + "); treating it as missing");
    }
    return std::nullopt;
}

Spec split_hash(const std::string& spec) {
    size_t hash = spec.find('#');
    if (hash == std::string::npos) {
        return Spec{spec, ""};
    }
    std::string pointer = spec.substr(hash + 1);
    if (!pointer.starts_with('/')) {
        throw Error{code::CfgBad, "address must be FILE#/POINTER (# must be followed by /): " + spec};
    }
    return Spec{spec.substr(0, hash), pointer};
}

// 把 text 整份寫進 fd；失敗回 false（errno 留著）。
static bool write_all(int fd, const std::string& text) {
    size_t done = 0;
    while (done < text.size()) {
        ssize_t n = write(fd, text.data() + done, text.size() - done);
        if (n < 0 && errno == EINTR) {
            continue;
        }
        if (n < 0) {
            return false;
        }
        done += (size_t)n;
    }
    return true;
}

std::optional<std::string> write_json(const std::string& path, const Json& doc) {
    std::string dir = dirname(path);
    std::string name = path.substr(path.rfind('/') + 1);
    std::string tmp = join(dir, "." + name + "." + std::to_string(getpid()) + ".tmp");

    // 1. 所在的資料夾沒有就建
    if (!dir.empty()) {
        std::error_code ec;
        std::filesystem::create_directories(dir, ec);
        if (ec) {
            return "cannot create directory " + dir + ": " + ec.message();
        }
    }
    // 2. 寫暫存檔（.名.<pid>.tmp，多人同寫不互踩），改名前 fsync（照 aos-json save_file；不 fsync 資料夾）
    std::string text = doc.dump(2, ' ', false, Json::error_handler_t::replace);
    int fd = open(tmp.c_str(), O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0666);
    if (fd < 0) {
        return "cannot open " + tmp + ": " + std::strerror(errno);
    }
    bool ok = write_all(fd, text);
    int saved = errno;
    if (ok && fsync(fd) != 0) {
        ok = false;
        saved = errno;
    }
    if (close(fd) != 0 && ok) {
        ok = false;
        saved = errno;
    }
    // 3. 改名蓋過去（原子）；任何一步失敗都清掉暫存檔
    if (ok && rename(tmp.c_str(), path.c_str()) == 0) {
        return std::nullopt;
    }
    if (ok) {
        saved = errno;
    }
    unlink(tmp.c_str());
    return "cannot write " + path + ": " + std::strerror(saved);
}

}  // namespace aos
