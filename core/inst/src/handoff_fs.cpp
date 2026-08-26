#define _POSIX_C_SOURCE 200809L

// handoff 層：路徑推導與低階檔案存取。

#include "handoff_fs.hpp"

#include <cerrno>
#include <cstddef>
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

bool close_checked(int fd, int &error) {
    if (close(fd) == 0) return true;
    error = errno;
    return false;
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
    if (!close_checked(fd, error)) ok = false;
    return ok;
}

bool write_file(const std::string &path, const std::string &data, int &error) {
    const int fd = open_retry(path.c_str(),
                              O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0666);
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
    if (!close_checked(fd, error)) ok = false;
    return ok;
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
