#define _POSIX_C_SOURCE 200809L

#include "run_internal.hpp"

#include <cerrno>
#include <cstdio>
#include <cstring>

#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

namespace aos::detail {
namespace {

constexpr const char *kAosDir = ".aos";

int open_retry(const char *path, int flags) {
    int fd;
    do {
        fd = open(path, flags);
    } while (fd < 0 && errno == EINTR);
    return fd;
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

// fsync 本身可能被訊號中斷（不像 close，重打 fsync 是安全的：fd 沒被回收）。
bool fsync_retry(int fd) {
    int rc;
    do {
        rc = fsync(fd);
    } while (rc != 0 && errno == EINTR);
    return rc == 0;
}

}  // namespace

int run_init_world(const char *folder) {
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
    // 版面版本是崩潰後判斷這個世界能不能用的第一道關卡：內容落盤才算數
    // （S7 fsync 掃尾；turn 已在 S6 補齊，這裡收齊 version）。
    if (ok && !fsync_retry(version_fd)) {
        error = errno;
        ok = false;
    }
    if (version_fd >= 0 && !close_checked(version_fd, error)) ok = false;
    if (ok && mkdirat(aos_fd, "inst.tempd", 0777) != 0) {
        error = errno;
        ok = false;
    }
    // `.aos/turn`：回合計數器（PC），初值 `0`（§B-3）。含 fsync——這是全新落地的
    // 檔案，不像 version 那樣仰賴 S7 掃尾補齊，直接一步到位。
    int turn_fd = -1;
    if (ok) {
        turn_fd = openat(aos_fd, "turn",
                         O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0666);
        ok = turn_fd >= 0;
    }
    if (ok) ok = write_fully(turn_fd, "0\n", 2, error);
    if (ok && !fsync_retry(turn_fd)) {
        error = errno;
        ok = false;
    }
    if (turn_fd >= 0 && !close_checked(turn_fd, error)) ok = false;
    // 目錄項本身也要落盤：`version`／`inst.tempd`／`turn` 三個新項目全在 `.aos`
    // 底下，一次 fsync 這個已經開著的目錄 fd 就夠（S7 fsync 掃尾）。
    if (ok && aos_fd >= 0 && !fsync_retry(aos_fd)) {
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
            unlinkat(cleanup_fd, ".aos/turn", 0);
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

}  // namespace aos::detail
