#define _POSIX_C_SOURCE 200809L

#include "run_batch.hpp"
#include "run_internal.hpp"

#include <aos/inst.hpp>

#include <cerrno>
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

int open_retry(const char *path, int flags) {
    int fd;
    do {
        fd = open(path, flags);
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
    return result;
}

}  // namespace aos::detail
