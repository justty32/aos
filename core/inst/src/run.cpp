#define _POSIX_C_SOURCE 200809L

#include "run.hpp"

#include <aos/inst.hpp>

#include <cerrno>
#include <cstdio>
#include <cstring>
#include <new>
#include <stdexcept>
#include <string>
#include <system_error>
#include <thread>
#include <vector>

#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

namespace aos {
namespace {

constexpr const char *kAosDir = ".aos";
constexpr const char *kVersionPath = ".aos/version";
constexpr const char *kInstPath = ".aos/inst.json";
constexpr const char *kRuniPath = ".aos/inst.json.runi";

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

struct ExecutionOutcome {
    ExecState state = ExecState::Ok;
    ExecResult result;
};

ExecutionOutcome execute_one(inst_t &instruction) {
    ExecutionOutcome outcome;
    try {
        outcome.state = execute(instruction, outcome.result);
    } catch (const std::bad_alloc &) {
        outcome.state = ExecState::SpawnFailed;
        outcome.result.error = ENOMEM;
    } catch (const std::length_error &) {
        outcome.state = ExecState::SpawnFailed;
        outcome.result.error = ENOMEM;
    }
    return outcome;
}

int execute_batch(const std::string &buffer, const char *source) {
    std::vector<inst_t> instructions;
    std::size_t error_record = 0;
    const char empty = '\0';
    const char *data = buffer.empty() ? &empty : buffer.data();
    InstState parse_state = InstState::Ok;
    try {
        parse_state = read_all(data, buffer.size(), instructions, &error_record);
    } catch (const std::bad_alloc &) {
        std::fprintf(stderr, "aos exec: cannot parse %s: out of memory\n", source);
        return 1;
    } catch (const std::length_error &) {
        std::fprintf(stderr, "aos exec: cannot parse %s: out of memory\n", source);
        return 1;
    }
    if (parse_state != InstState::Ok) {
        if (error_record != 0) {
            std::fprintf(stderr, "aos exec: %s: record %zu: %s\n", source,
                         error_record, to_string(parse_state));
        } else {
            std::fprintf(stderr, "aos exec: %s: %s\n", source,
                         to_string(parse_state));
        }
        return 1;
    }

    std::vector<ExecutionOutcome> outcomes;
    std::vector<std::thread> threads;
    try {
        outcomes.resize(instructions.size());
        threads.reserve(instructions.size());
    } catch (const std::bad_alloc &) {
        std::fprintf(stderr, "aos exec: cannot execute %s: out of memory\n", source);
        return 1;
    } catch (const std::length_error &) {
        std::fprintf(stderr, "aos exec: cannot execute %s: out of memory\n", source);
        return 1;
    }
    for (std::size_t index = 0; index < instructions.size(); ++index) {
        if (!instructions[index].parallel) {
            outcomes[index] = execute_one(instructions[index]);
            continue;
        }
        try {
            threads.emplace_back(
                [instruction = instructions[index],
                 &outcome = outcomes[index]]() mutable {
                    outcome = execute_one(instruction);
                });
        } catch (const std::bad_alloc &) {
            outcomes[index].state = ExecState::SpawnFailed;
            outcomes[index].result.error = ENOMEM;
        } catch (const std::system_error &error) {
            outcomes[index].state = ExecState::SpawnFailed;
            outcomes[index].result.error = error.code().value();
        }
    }
    for (std::thread &thread : threads) thread.join();

    bool failed = false;
    for (std::size_t index = 0; index < outcomes.size(); ++index) {
        const ExecutionOutcome &outcome = outcomes[index];
        if (outcome.state == ExecState::Ok) continue;
        failed = true;
        if (outcome.result.error != 0) {
            std::fprintf(stderr, "aos exec: record %zu: %s: %s\n", index + 1,
                         to_string(outcome.state),
                         std::strerror(outcome.result.error));
        } else {
            std::fprintf(stderr, "aos exec: record %zu: %s\n", index + 1,
                         to_string(outcome.state));
        }
    }
    return failed ? 1 : 0;
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

    if (lstat(kRuniPath, &status) == 0) {
        std::fprintf(stderr, "aos exec: refusing %s: %s already exists\n",
                     folder, kRuniPath);
        return 3;
    }
    if (errno != ENOENT) {
        std::fprintf(stderr, "aos exec: cannot inspect %s/%s: %s\n", folder,
                     kRuniPath, std::strerror(errno));
        return 1;
    }

    std::string buffer;
    fd = open_retry(kInstPath, O_RDONLY | O_CLOEXEC);
    if (fd < 0 && errno == ENOENT) return 0;
    if (fd < 0) {
        std::fprintf(stderr, "aos exec: cannot read %s/%s: %s\n", folder,
                     kInstPath, std::strerror(errno));
        return 1;
    }
    read_ok = read_input(fd, buffer, error);
    const bool inst_close_ok = close_checked(fd, error);
    if (!read_ok || !inst_close_ok) {
        std::fprintf(stderr, "aos exec: cannot read %s/%s: %s\n", folder,
                     kInstPath, std::strerror(error));
        return 1;
    }
    if (rename(kInstPath, kRuniPath) != 0) {
        std::fprintf(stderr, "aos exec: cannot rename %s/%s: %s\n", folder,
                     kInstPath, std::strerror(errno));
        return 1;
    }
    const int result = execute_batch(buffer, kRuniPath);
    if (unlink(kRuniPath) != 0) {
        std::fprintf(stderr, "aos exec: cannot remove %s/%s: %s\n", folder,
                     kRuniPath, std::strerror(errno));
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
    if (!ok && error == 0) error = errno;
    if (aos_fd >= 0) close(aos_fd);
    close(folder_fd);

    if (!ok) {
        const int cleanup_fd = open_retry(folder, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
        if (cleanup_fd >= 0) {
            unlinkat(cleanup_fd, ".aos/version", 0);
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
