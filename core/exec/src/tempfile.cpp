#define _POSIX_C_SOURCE 200809L

#include "tempfile.hpp"

#include <cerrno>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include <fcntl.h>
#include <unistd.h>

namespace aos::exec::detail {
namespace {

void append_error(std::string &error, const std::string &message) {
    if (!error.empty()) {
        error += "; ";
    }
    error += message;
}

std::string temp_directory() {
    const char *value = std::getenv("TMPDIR");
    return value != nullptr && *value != '\0' ? value : "/tmp";
}

std::string path_error(const std::string &action, const std::string &path,
                       int error) {
    return action + " '" + path + "': " + std::strerror(error);
}

}  // namespace

int make_temp(const std::string &prefix, std::string &path_out) {
    std::string pattern = temp_directory();
    if (pattern.empty() || pattern.back() != '/') {
        pattern += '/';
    }
    pattern += "aos-exec-" + prefix + "-XXXXXX";

    std::vector<char> writable(pattern.begin(), pattern.end());
    writable.push_back('\0');
    const int fd = mkstemp(writable.data());
    if (fd >= 0) {
        path_out = writable.data();
    }
    return fd;
}

bool write_fully(int fd, const char *data, std::size_t size) {
    while (size != 0) {
        ssize_t written;
        do {
            written = write(fd, data, size);
        } while (written < 0 && errno == EINTR);
        if (written <= 0) {
            return false;
        }
        data += written;
        size -= static_cast<std::size_t>(written);
    }
    return true;
}

bool unlink_file(const std::string &path, std::string &error) {
    if (path.empty()) {
        return true;
    }
    if (unlink(path.c_str()) == 0) {
        return true;
    }
    append_error(error, path_error("無法刪除暫存檔", path, errno));
    return false;
}

bool read_file_and_unlink(const std::string &path, std::string &text,
                          std::string &error) {
    if (path.empty()) {
        return true;
    }

    int fd;
    do {
        fd = open(path.c_str(), O_RDONLY);
    } while (fd < 0 && errno == EINTR);
    if (fd < 0) {
        const int saved_error = errno;
        append_error(error, path_error("無法讀取暫存檔", path, saved_error));
        if (saved_error != ENOENT) {
            unlink_file(path, error);
        }
        return false;
    }

    bool ok = true;
    char buffer[4096];
    for (;;) {
        ssize_t count;
        do {
            count = read(fd, buffer, sizeof(buffer));
        } while (count < 0 && errno == EINTR);
        if (count == 0) {
            break;
        }
        if (count < 0) {
            append_error(error, path_error("無法讀取暫存檔", path, errno));
            ok = false;
            break;
        }
        text.append(buffer, static_cast<std::size_t>(count));
    }
    close(fd);
    return unlink_file(path, error) && ok;
}

}  // namespace aos::exec::detail
