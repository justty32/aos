#define _POSIX_C_SOURCE 200809L

#include "run.hpp"
#include "run_batch.hpp"

#include <aos/inst.hpp>

#include <cerrno>
#include <cstdio>
#include <cstring>
#include <new>
#include <stdexcept>
#include <string>

#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

namespace aos {
namespace {

constexpr const char *kAosDir = ".aos";
constexpr const char *kVersionPath = ".aos/version";
constexpr const char *kInstPath = ".aos/inst.json";

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

int run_exec_impl(const char *folder) {
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
    const int result = detail::execute_batch(buffer, ".aos/inst.json.runi");
    handoff_state = release_instruction(kInstPath, handoff_result);
    if (handoff_state != HandoffState::Ok) {
        std::fprintf(stderr, "aos exec: cannot remove %s/%s: %s\n", folder,
                     handoff_result.path.c_str(),
                     std::strerror(handoff_result.error));
        return 1;
    }
    return result;
}

int run_init_impl(const char *folder) {
    const int folder_fd = open_retry(folder, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (folder_fd < 0) {
        std::fprintf(stderr, "aos init: cannot open %s: %s\n", folder,
                     std::strerror(errno));
        return 1;
    }
    if (mkdirat(folder_fd, kAosDir, 0777) != 0) {
        const int error = errno;
        close(folder_fd);
        if (error == EEXIST) {
            std::fprintf(stderr, "aos init: refusing %s: .aos already exists\n",
                         folder);
        } else {
            std::fprintf(stderr, "aos init: cannot create %s/.aos: %s\n", folder,
                         std::strerror(error));
        }
        return 1;
    }

    const int aos_fd = openat(folder_fd, kAosDir,
                              O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    int error = 0;
    int version_fd = -1;
    bool ok = aos_fd >= 0;
    if (ok) {
        version_fd = openat(aos_fd, "version",
                            O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0666);
        ok = version_fd >= 0;
    }
    if (ok) ok = write_fully(version_fd, "1\n", 2, error);
    if (version_fd >= 0 && !close_checked(version_fd, error)) ok = false;
    if (ok && mkdirat(aos_fd, "inst.tempd", 0777) != 0) {
        error = errno;
        ok = false;
    }
    if (!ok && error == 0) error = errno;
    if (aos_fd >= 0) close(aos_fd);
    close(folder_fd);

    if (!ok) {
        const int cleanup_fd = open_retry(folder, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
        if (cleanup_fd >= 0) {
            unlinkat(cleanup_fd, ".aos/version", 0);
            unlinkat(cleanup_fd, ".aos/inst.tempd", AT_REMOVEDIR);
            unlinkat(cleanup_fd, kAosDir, AT_REMOVEDIR);
            close(cleanup_fd);
        }
        std::fprintf(stderr, "aos init: cannot write %s/.aos/version: %s\n",
                     folder, std::strerror(error));
        return 1;
    }
    return 0;
}

}  // namespace

int run_exec(int argc, char *argv[]) {
    if (argc != 2 || argv == nullptr || argv[1] == nullptr) {
        const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                                  ? argv[0]
                                  : "aos exec";
        std::fprintf(stderr, "usage: %s <folder>\n", program);
        return 2;
    }
    try {
        return run_exec_impl(argv[1]);
    } catch (const std::bad_alloc &) {
        std::fprintf(stderr, "aos exec: out of memory\n");
        return 1;
    } catch (const std::length_error &) {
        std::fprintf(stderr, "aos exec: out of memory\n");
        return 1;
    }
}

int run_init(int argc, char *argv[]) {
    if (argc != 2 || argv == nullptr || argv[1] == nullptr) {
        const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                                  ? argv[0]
                                  : "aos init";
        std::fprintf(stderr, "usage: %s <folder>\n", program);
        return 2;
    }
    return run_init_impl(argv[1]);
}

}  // namespace aos

extern "C" int aos_exec_cli_main(int argc, char *argv[]) {
    return aos::run_exec(argc, argv);
}

extern "C" int aos_init_cli_main(int argc, char *argv[]) {
    return aos::run_init(argc, argv);
}
