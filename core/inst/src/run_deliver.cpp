#define _POSIX_C_SOURCE 200809L

// CLI 層：`aos deliver [folder] [-f FILE|-]` —— 把一批 instruction 投進某個世界的
// 收件匣（SPEC §D-3）。分工比照 run.cpp／run_exec.cpp：run_deliver() 只管 argv 與
// 把輸入讀進記憶體，run_deliver_world() 管進世界、驗版面、呼叫庫層、印報告。

#include "run.hpp"
#include "run_internal.hpp"

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
namespace detail {
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

}  // namespace

int run_deliver_world(const char *folder, const std::string &document) {
    CwdGuard cwd;
    int error = 0;
    if (!cwd.enter(folder, error)) {
        std::fprintf(stderr, "aos deliver: cannot enter %s: %s\n", folder,
                     std::strerror(error));
        return 1;
    }

    // 投遞也是對世界動手，所以先確認這是一個認得的世界（§F-2）：沒有 `.aos` 或
    // 版面版本不認得就拒絕，不自己補建（§D-3 明說 deliver MUST NOT 自動建世界）。
    struct stat status {};
    if (stat(kAosDir, &status) != 0) {
        error = errno;
        std::fprintf(stderr, "aos deliver: invalid %s/%s: %s\n", folder, kAosDir,
                     std::strerror(error));
        return 1;
    }
    if (!S_ISDIR(status.st_mode)) {
        std::fprintf(stderr, "aos deliver: invalid %s/%s: %s\n", folder, kAosDir,
                     std::strerror(ENOTDIR));
        return 1;
    }

    std::string version;
    const int fd = open_retry(kVersionPath, O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        std::fprintf(stderr, "aos deliver: cannot read %s/%s: %s\n", folder,
                     kVersionPath, std::strerror(errno));
        return 1;
    }
    const bool read_ok = read_input(fd, version, error);
    const bool close_ok = close_checked(fd, error);
    if (!read_ok || !close_ok || version != "1\n") {
        if (read_ok && close_ok) {
            std::fprintf(stderr, "aos deliver: unsupported version in %s/%s\n",
                         folder, kVersionPath);
        } else {
            std::fprintf(stderr, "aos deliver: cannot read %s/%s: %s\n", folder,
                         kVersionPath, std::strerror(error));
        }
        return 1;
    }

    DeliverResult result;
    const HandoffState state =
        deliver_instructions(kInstPath, document, result);
    if (state == HandoffState::DeliveryInvalid) {
        if (result.error_record != 0) {
            std::fprintf(stderr, "aos deliver: invalid input: record %zu: %s\n",
                         result.error_record, to_string(result.inst_state));
        } else {
            std::fprintf(stderr, "aos deliver: invalid input: %s\n",
                         to_string(result.inst_state));
        }
        return 1;
    }
    if (state != HandoffState::Ok) {
        std::fprintf(stderr, "aos deliver: cannot deliver %s/%s: %s: %s\n",
                     folder, result.path.c_str(), to_string(state),
                     std::strerror(result.error));
        return 1;
    }
    if (result.sync_error != 0) {
        std::fprintf(stderr, "aos deliver: warning: %s: %s\n",
                     result.inbox.c_str(), std::strerror(result.sync_error));
    }

    // 單行 JSON（§D-3）。三個值都是程式自己產生的 ASCII——`<pid>-<seq>.json`、
    // 十進位整數、從 kInstPath 推導出來的固定收件匣路徑——沒有需要跳脫的字元。
    std::printf("{\"delivery\":\"%s\",\"count\":%zu,\"target\":\"%s\"}\n",
                result.name.c_str(), result.count, result.inbox.c_str());
    if (std::fflush(stdout) != 0) {
        // 投遞已經進收件匣了，只是報告送不出去。誠實說明現場：吞掉錯誤會讓
        // 呼叫者以為沒投成功而重投，那就真的多出一份。
        std::fprintf(stderr,
                     "aos deliver: %s/%s delivered, but the report could not be "
                     "written: %s\n",
                     folder, result.name.c_str(), std::strerror(errno));
        return 1;
    }
    return 0;
}

}  // namespace detail

int run_deliver(int argc, char *argv[]) {
    const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                              ? argv[0]
                              : "aos deliver";
    const char *folder = nullptr;
    const char *file = nullptr;
    bool standard_input = false;
    bool usage = argv == nullptr || argc < 1;
    for (int index = 1; !usage && index < argc; ++index) {
        const char *arg = argv[index];
        if (arg == nullptr) {
            usage = true;
        } else if (std::strcmp(arg, "-f") == 0) {
            // 輸入來源只能指定一次，`-f` 後面一定要有東西。
            if (index + 1 >= argc || argv[index + 1] == nullptr ||
                file != nullptr || standard_input) {
                usage = true;
            } else if (std::strcmp(argv[++index], "-") == 0) {
                standard_input = true;
            } else {
                file = argv[index];
            }
        } else if (std::strcmp(arg, "-") == 0) {
            if (file != nullptr || standard_input) usage = true;
            standard_input = true;
        } else if (arg[0] == '-') {
            usage = true;  // 認不得的選項一律拒絕，不當成 folder 吞掉
        } else if (folder != nullptr) {
            usage = true;
        } else {
            folder = arg;
        }
    }
    if (usage) {
        std::fprintf(stderr, "usage: %s [folder] [-f FILE|-]\n", program);
        return 2;
    }

    try {
        // `-f` 的路徑是相對**呼叫者的** cwd 解析的：它是命令的輸入，不是世界的
        // 一部分。所以先讀完輸入，進世界的 chdir 才發生（在 run_deliver_world）。
        std::string document;
        int error = 0;
        if (file != nullptr) {
            const int fd = detail::open_retry(file, O_RDONLY | O_CLOEXEC);
            if (fd < 0) {
                std::fprintf(stderr, "aos deliver: cannot read %s: %s\n", file,
                             std::strerror(errno));
                return 1;
            }
            bool ok = detail::read_input(fd, document, error);
            if (!detail::close_checked(fd, error)) ok = false;
            if (!ok) {
                std::fprintf(stderr, "aos deliver: cannot read %s: %s\n", file,
                             std::strerror(error));
                return 1;
            }
        } else if (!detail::read_input(STDIN_FILENO, document, error)) {
            std::fprintf(stderr, "aos deliver: cannot read standard input: %s\n",
                         std::strerror(error));
            return 1;
        }
        return detail::run_deliver_world(folder != nullptr ? folder : ".",
                                         document);
    } catch (const std::bad_alloc &) {
        std::fprintf(stderr, "aos deliver: out of memory\n");
        return 1;
    } catch (const std::length_error &) {
        std::fprintf(stderr, "aos deliver: out of memory\n");
        return 1;
    }
}

}  // namespace aos

extern "C" int aos_deliver_cli_main(int argc, char *argv[]) {
    return aos::run_deliver(argc, argv);
}
