#define _POSIX_C_SOURCE 200809L

#include "run_batch.hpp"
#include "run_internal.hpp"

#include <aos/inst.hpp>

#include <cerrno>
#include <cstdio>
#include <cstring>
#include <string>
#include <string_view>

#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

namespace aos::detail {
namespace {

constexpr const char *kAosDir = ".aos";
constexpr const char *kVersionPath = ".aos/version";
constexpr const char *kInstPath = ".aos/inst.json";
constexpr const char *kRuniPath = ".aos/inst.json.runi";
constexpr const char *kTurnPath = ".aos/turn";

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



// §B-4 只立法「讀不到＝拒絕」與「不認得（比自己新）＝拒絕」，沒有立法 `.aos/version`
// 的位元組格式。所以比對前先剝掉尾端空白：`1`、`1\n`、`1\n\n` 是同一個版面版本，
// 手寫或編輯器補上的換行不該讓一個好世界進不去。`0`／`2`／空檔／非數字照樣拒絕。
bool version_is_current(const std::string &content) {
    std::size_t end = content.size();
    while (end != 0) {
        const char tail = content[end - 1];
        if (tail != ' ' && tail != '\t' && tail != '\n' && tail != '\r') break;
        --end;
    }
    return std::string_view(content.data(), end) == "1";
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
    if (!read_ok || !close_ok || !version_is_current(version)) {
        if (read_ok && close_ok) {
            std::fprintf(stderr, "aos exec: unsupported version in %s/%s\n",
                         folder, kVersionPath);
        } else {
            std::fprintf(stderr, "aos exec: cannot read %s/%s: %s\n", folder,
                         kVersionPath, std::strerror(error));
        }
        return 1;
    }

    // `.runi` 存在 ⟺ 有一回合沒跑完（§D-7）。這個守衛擺在彙整之前：一個「拒絕
    // 啟動」的回合不該先做完發布新批＋寫 header＋刪投遞這三個不可逆動作，把世界
    // 留成同時掛著兩批待處理的樣子。claim 那邊的 Busy 分支保留當兜底——這兩個
    // 檢查之間仍有 race，只是不再是常態路徑。
    struct stat runi_status {};
    if (lstat(kRuniPath, &runi_status) == 0) {
        std::fprintf(stderr, "aos exec: refusing %s: %s already exists\n", folder,
                     kRuniPath);
        return 3;
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
        } else if (handoff_result.path == kRuniPath) {
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
    const int result = execute_batch(buffer, kRuniPath);
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
