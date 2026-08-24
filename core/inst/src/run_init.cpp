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

}  // namespace aos::detail
