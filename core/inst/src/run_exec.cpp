#define _POSIX_C_SOURCE 200809L

#include "run_batch.hpp"
#include "run_internal.hpp"

#include <aos/inst.hpp>

#include <cerrno>
#include <charconv>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>

#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

namespace aos::detail {
namespace {

constexpr const char *kAosDir = ".aos";
constexpr const char *kVersionPath = ".aos/version";
constexpr const char *kInstPath = ".aos/inst.json";
constexpr const char *kTurnPath = ".aos/turn";
constexpr const char *kTurnTempPath = ".aos/turn.temp";

int open_retry(const char *path, int flags, mode_t mode = 0) {
    int fd;
    do {
        fd = open(path, flags, mode);
    } while (fd < 0 && errno == EINTR);
    return fd;
}

bool read_input(int fd, std::string &buffer, int &error) {
    char chunk[64 * 1024];
    for (;;) {
        ssize_t count;
        do {
            count = read(fd, chunk, sizeof(chunk));
        } while (count < 0 && errno == EINTR);
        if (count < 0) {
            error = errno;
            return false;
        }
        if (count == 0) return true;
        buffer.append(chunk, static_cast<std::size_t>(count));
    }
}

bool close_checked(int fd, int &error) {
    if (close(fd) == 0) return true;
    error = errno;
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

bool write_fully(int fd, const char *data, std::size_t size, int &error) {
    while (size != 0) {
        ssize_t count;
        do {
            count = write(fd, data, size);
        } while (count < 0 && errno == EINTR);
        if (count <= 0) {
            error = count < 0 ? errno : EIO;
            return false;
        }
        data += count;
        size -= static_cast<std::size_t>(count);
    }
    return true;
}

bool fsync_dir(const char *path, int &error) {
    const int fd = open_retry(path, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (fd < 0) {
        error = errno;
        return false;
    }
    bool ok = true;
    if (!fsync_retry(fd)) {
        error = errno;
        ok = false;
    }
    if (!close_checked(fd, error)) ok = false;
    return ok;
}

// 內容一律是 "<十進位整數>\n"；不是這個形狀一律當成解析失敗，不猜、不當成 0
// （§B-3 只保證「讀不到」視為 0，不保證「讀到壞內容」也視為 0）。
bool parse_turn(const std::string &content, std::uint64_t &value) {
    if (content.empty() || content.back() != '\n') return false;
    const std::size_t digits = content.size() - 1;
    if (digits == 0) return false;
    for (std::size_t index = 0; index < digits; ++index) {
        if (content[index] < '0' || content[index] > '9') return false;
    }
    const auto result =
        std::from_chars(content.data(), content.data() + digits, value);
    return result.ec == std::errc() && result.ptr == content.data() + digits;
}

// `.aos/turn`：讀不到（舊世界）視為 0（§B-3／裁-5，MUST NOT 拒絕、MUST NOT 動
// 版面版本），否則遞增後 temp→fsync→rename→fsync 目錄，與 handoff 的耐久性順序
// 同款寫法。只在 release_instruction 成功後呼叫（見 run_exec_once）。
bool advance_turn(int &error) {
    std::uint64_t value = 0;
    const int fd = open_retry(kTurnPath, O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        if (errno != ENOENT) {
            error = errno;
            return false;
        }
    } else {
        std::string content;
        bool ok = read_input(fd, content, error);
        if (!close_checked(fd, error)) ok = false;
        if (!ok) return false;
        if (!parse_turn(content, value)) {
            error = EINVAL;
            return false;
        }
    }
    ++value;
    const std::string next = std::to_string(value) + "\n";

    const int temp_fd = open_retry(
        kTurnTempPath, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0666);
    if (temp_fd < 0) {
        error = errno;
        return false;
    }
    bool ok = write_fully(temp_fd, next.data(), next.size(), error);
    if (ok && !fsync_retry(temp_fd)) {
        error = errno;
        ok = false;
    }
    if (!close_checked(temp_fd, error)) ok = false;
    if (!ok) return false;

    if (rename(kTurnTempPath, kTurnPath) != 0) {
        error = errno;
        return false;
    }
    return fsync_dir(kAosDir, error);
}

class CwdGuard {
public:
    CwdGuard() : saved_(open_retry(".", O_RDONLY | O_DIRECTORY | O_CLOEXEC)) {}
    ~CwdGuard() {
        if (saved_ >= 0) {
            fchdir(saved_);
            close(saved_);
        }
    }
    bool enter(const char *path, int &error) {
        if (saved_ < 0) {
            error = errno;
            return false;
        }
        if (chdir(path) == 0) return true;
        error = errno;
        return false;
    }

private:
    int saved_;
};

void print_handoff_issues(const HandoffResult &result) {
    for (const HandoffIssue &issue : result.issues) {
        if (issue.kind == HandoffIssueKind::InvalidDelivery) {
            std::fprintf(stderr, "aos exec: warning: %s: %s\n",
                         issue.path.c_str(), to_string(issue.inst_state));
        } else if (issue.error != 0) {
            std::fprintf(stderr, "aos exec: warning: %s: %s: %s\n",
                         issue.path.c_str(), to_string(issue.kind),
                         std::strerror(issue.error));
        } else {
            std::fprintf(stderr, "aos exec: warning: %s: %s\n",
                         issue.path.c_str(), to_string(issue.kind));
        }
    }
}

}  // namespace

int run_exec_once(const char *folder, bool &did_work) {
    did_work = false;
    CwdGuard cwd;
    int error = 0;
    if (!cwd.enter(folder, error)) {
        std::fprintf(stderr, "aos exec: cannot enter %s: %s\n", folder,
                     std::strerror(error));
        return 1;
    }

    struct stat status {};
    if (stat(kAosDir, &status) != 0) {
        error = errno;
        std::fprintf(stderr, "aos exec: invalid %s/%s: %s\n", folder, kAosDir,
                     std::strerror(error));
        return 1;
    }
    if (!S_ISDIR(status.st_mode)) {
        std::fprintf(stderr, "aos exec: invalid %s/%s: %s\n", folder, kAosDir,
                     std::strerror(ENOTDIR));
        return 1;
    }

    std::string version;
    int fd = open_retry(kVersionPath, O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        std::fprintf(stderr, "aos exec: cannot read %s/%s: %s\n", folder,
                     kVersionPath, std::strerror(errno));
        return 1;
    }
    bool read_ok = read_input(fd, version, error);
    const bool close_ok = close_checked(fd, error);
    if (!read_ok || !close_ok || version != "1\n") {
        if (read_ok && close_ok) {
            std::fprintf(stderr, "aos exec: unsupported version in %s/%s\n",
                         folder, kVersionPath);
        } else {
            std::fprintf(stderr, "aos exec: cannot read %s/%s: %s\n", folder,
                         kVersionPath, std::strerror(error));
        }
        return 1;
    }

    HandoffResult handoff_result;
    HandoffState handoff_state =
        aggregate_instructions(kInstPath, handoff_result);
    print_handoff_issues(handoff_result);
    if (handoff_state != HandoffState::Ok) {
        std::fprintf(stderr, "aos exec: cannot aggregate %s: %s: %s\n",
                     handoff_result.path.c_str(), to_string(handoff_state),
                     std::strerror(handoff_result.error));
        return 1;
    }

    std::string buffer;
    handoff_state = claim_instruction(kInstPath, buffer, handoff_result);
    if (handoff_state == HandoffState::Busy) {
        std::fprintf(stderr, "aos exec: refusing %s: %s already exists\n",
                     folder, handoff_result.path.c_str());
        return 3;
    }
    if (handoff_state == HandoffState::NoInstruction) return 0;
    if (handoff_state != HandoffState::Ok) {
        if (handoff_state == HandoffState::RenameFailed) {
            std::fprintf(stderr, "aos exec: cannot rename %s/%s: %s\n", folder,
                         kInstPath, std::strerror(handoff_result.error));
        } else if (handoff_result.path == ".aos/inst.json.runi") {
            std::fprintf(stderr, "aos exec: cannot inspect %s/%s: %s\n", folder,
                         handoff_result.path.c_str(),
                         std::strerror(handoff_result.error));
        } else {
            std::fprintf(stderr, "aos exec: cannot read %s/%s: %s\n", folder,
                         kInstPath, std::strerror(handoff_result.error));
        }
        return 1;
    }
    did_work = true;
    const int result = execute_batch(buffer, ".aos/inst.json.runi");
    handoff_state = release_instruction(kInstPath, handoff_result);
    if (handoff_state != HandoffState::Ok) {
        std::fprintf(stderr, "aos exec: cannot remove %s/%s: %s\n", folder,
                     handoff_result.path.c_str(),
                     std::strerror(handoff_result.error));
        return 1;
    }
    // 回合真的推進了（鎖已釋放）才遞增 PC；失敗就誠實回報，不回滾已完成的回合
    // （§B-3：由 CLI 回合層在 release 成功後遞增）。
    if (!advance_turn(error)) {
        std::fprintf(stderr, "aos exec: cannot advance %s/%s: %s\n", folder,
                     kTurnPath, std::strerror(error));
        return 1;
    }
    return result;
}

}  // namespace aos::detail
