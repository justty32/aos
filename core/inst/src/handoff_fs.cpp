#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif

// handoff 層：路徑推導與低階檔案存取。
// _GNU_SOURCE（取代 _POSIX_C_SOURCE 200809L）只有這個檔需要：renameat2 與
// RENAME_NOREPLACE 是 GNU 擴充，宣告藏在 <cstdio>（glibc 的位置，見 stdio.h 裡
// __USE_GNU 那段），_GNU_SOURCE 本身已涵蓋 _POSIX_C_SOURCE 200809L 這個檔要的東西。

#include "handoff_fs.hpp"

#include <atomic>
#include <cerrno>
#include <cstddef>
#include <cstdio>
#include <string_view>

#include <fcntl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

namespace aos::detail {
namespace {

int open_retry(const char *path, int flags, mode_t mode = 0) {
    int fd;
    do {
        fd = open(path, flags, mode);
    } while (fd < 0 && errno == EINTR);
    return fd;
}

// close 的 errno 只有在前面都還沒出錯時才有資格寫進 error（ok 為 true）。寫失敗
// **且** close 也失敗時，先發生的那個才是真正的原因；讓 close 蓋掉它只會回報一個
// 比較沒用的錯（#24）。無論如何 fd 都關掉，不洩漏。
bool close_checked(int fd, bool ok, int &error) {
    if (close(fd) == 0) return true;
    if (ok) error = errno;
    return false;
}

// fsync 本身可能被訊號中斷（不像 close，重打 fsync 是安全的：fd 沒被回收）。
bool fsync_retry(int fd) {
    int rc;
    do {
        rc = fsync(fd);
    } while (rc != 0 && errno == EINTR);
    return rc == 0;
}

}  // namespace

bool derive_paths(const std::string &base, HandoffPaths &paths) {
    constexpr std::string_view suffix = ".json";
    if (base.size() <= suffix.size() ||
        base.compare(base.size() - suffix.size(), suffix.size(), suffix) != 0) {
        return false;
    }
    paths.base = base;
    paths.temp = base + ".temp";
    paths.runi = base + ".runi";
    paths.inbox = base.substr(0, base.size() - suffix.size()) + ".tempd";
    return true;
}

bool read_file(const std::string &path, std::string &buffer, int &error) {
    const int fd = open_retry(path.c_str(), O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        error = errno;
        return false;
    }
    char chunk[64 * 1024];
    bool ok = true;
    for (;;) {
        ssize_t count;
        do {
            count = read(fd, chunk, sizeof(chunk));
        } while (count < 0 && errno == EINTR);
        if (count < 0) {
            error = errno;
            ok = false;
            break;
        }
        if (count == 0) break;
        buffer.append(chunk, static_cast<std::size_t>(count));
    }
    if (!close_checked(fd, ok, error)) ok = false;
    return ok;
}

namespace {

// write_file 與 write_file_exclusive 只差在建檔旗標（O_TRUNC vs O_EXCL）。
bool write_file_flags(const std::string &path, const std::string &data,
                      int create_flag, int &error) {
    const int fd = open_retry(path.c_str(),
                              O_WRONLY | O_CREAT | create_flag | O_CLOEXEC, 0666);
    if (fd < 0) {
        error = errno;
        return false;
    }
    const char *cursor = data.data();
    std::size_t remaining = data.size();
    bool ok = true;
    while (remaining != 0) {
        ssize_t count;
        do {
            count = write(fd, cursor, remaining);
        } while (count < 0 && errno == EINTR);
        if (count <= 0) {
            error = count < 0 ? errno : EIO;
            ok = false;
            break;
        }
        cursor += count;
        remaining -= static_cast<std::size_t>(count);
    }
    if (ok && !fsync_retry(fd)) {
        error = errno;
        ok = false;
    }
    if (!close_checked(fd, ok, error)) ok = false;
    return ok;
}

}  // namespace

bool write_file(const std::string &path, const std::string &data, int &error) {
    return write_file_flags(path, data, O_TRUNC, error);
}

bool write_file_exclusive(const std::string &path, const std::string &data,
                          int &error) {
    return write_file_flags(path, data, O_EXCL, error);
}

bool fsync_dir(const std::string &path, int &error) {
    const int fd = open_retry(path.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (fd < 0) {
        error = errno;
        return false;
    }
    bool ok = true;
    if (!fsync_retry(fd)) {
        error = errno;
        ok = false;
    }
    if (!close_checked(fd, ok, error)) ok = false;
    return ok;
}

bool publish_exclusive(const std::string &from, const std::string &to, int &error,
                       int *leftover_error) {
    if (renameat2(AT_FDCWD, from.c_str(), AT_FDCWD, to.c_str(),
                  RENAME_NOREPLACE) == 0) {
        return true;
    }
    const int rename_error = errno;
    if (rename_error != EINVAL && rename_error != ENOSYS &&
        rename_error != ENOTSUP) {
        error = rename_error;
        return false;
    }
    // 檔案系統不支援 renameat2（例如 drvfs 上的 9p 掛載）：退階為
    // link()+unlink()，link 一樣是「目的檔已存在就失敗」的排他語意。
    if (link(from.c_str(), to.c_str()) != 0) {
        error = errno;
        return false;
    }
    if (unlink(from.c_str()) != 0) {
        // 目的檔已經連好、內容完整，aggregate 一定會收——這一步失敗只是留下一份
        // from 的殘骸。回報整體失敗會讓呼叫者重做（生產者重投＝真的多出一份，
        // 那才是最貴的方向，#11），所以回 true，errno 走 leftover_error 當警告。
        if (leftover_error != nullptr) *leftover_error = errno;
    }
    return true;
}

std::string next_unique_token() {
    static std::atomic<unsigned long long> counter{0};
    const unsigned long long seq = counter.fetch_add(1, std::memory_order_relaxed);
    return std::to_string(getpid()) + "-" + std::to_string(seq);
}

std::string next_delivery_name() { return next_unique_token(); }

namespace {

// 把行程內唯一的權杖插進最後一個 `.json` 之前，再接上狀況字。名字變成
// `<原名>-<pid>-<seq>`，所以整體仍是 §B-1 的 `<名字>.<副檔名>.<狀況>`。
// 路徑裡沒有 `.json` 時（不該發生，derive_paths／is_delivery_name 都擋掉了）
// 退成把權杖接在最後面，仍然唯一。
std::string unique_status_path(const std::string &path,
                               const std::string &status) {
    constexpr std::string_view suffix = ".json";
    const std::string token = "-" + next_unique_token();
    const std::size_t json = path.rfind(suffix);
    if (json == std::string::npos) return path + token + status;
    return path.substr(0, json) + token + path.substr(json) + status;
}

}  // namespace

std::string unique_temp_path(const std::string &base) {
    return unique_status_path(base, ".temp");
}

std::string unique_bad_path(const std::string &path) {
    return unique_status_path(path, ".bad");
}

std::string parent_directory(const std::string &path) {
    const std::size_t slash = path.find_last_of('/');
    if (slash == std::string::npos) return ".";
    if (slash == 0) return "/";
    return path.substr(0, slash);
}

bool is_delivery_name(const std::string &name) {
    const std::size_t extension = name.find('.');
    return extension != std::string::npos && extension != 0 &&
           name.substr(extension) == ".json";
}

std::string join_path(const std::string &directory, const std::string &name) {
    return directory + "/" + name;
}

}  // namespace aos::detail
