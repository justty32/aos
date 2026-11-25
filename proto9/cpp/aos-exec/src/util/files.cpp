// util/files.cpp: abspath, dirname, join, is_dir, read_file, split_hash (trimmed copy of proto8 aos-util src/files.cpp and src/dirs.cpp).
#include "util/files.hpp"

#include <cerrno>
#include <filesystem>
#include <sstream>
#include <system_error>
#include <vector>

#include <fcntl.h>
#include <unistd.h>

namespace aos {

std::string abspath(const std::string& path) {
    std::string full = path;
    if (!path.starts_with('/')) {
        full = std::filesystem::current_path().string() + "/" + path;
    }
    std::vector<std::string> parts;
    std::istringstream in(full);
    std::string seg;
    while (std::getline(in, seg, '/')) {
        if (seg.empty() || seg == ".") {
            continue;
        }
        if (seg == "..") {
            if (!parts.empty()) {
                parts.pop_back();
            }
            continue;
        }
        parts.push_back(seg);
    }
    std::string out;
    for (const std::string& p : parts) {
        out += "/" + p;
    }
    if (out.empty()) {
        return "/";
    }
    return out;
}

std::string dirname(const std::string& path) {
    size_t slash = path.rfind('/');
    if (slash == std::string::npos) {
        return "";
    }
    std::string d = path.substr(0, slash + 1);
    while (d.size() > 1 && d.ends_with('/')) {
        d.pop_back();
    }
    return d;
}

std::string join(const std::string& a, const std::string& b) {
    if (b.starts_with('/') || a.empty()) {
        return b;
    }
    if (a.ends_with('/')) {
        return a + b;
    }
    return a + "/" + b;
}

bool is_dir(const std::string& path) {
    std::error_code ec;
    return std::filesystem::is_directory(path, ec);
}

std::optional<std::string> read_file(const std::string& path, int& errno_out) {
    int fd = open(path.c_str(), O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        errno_out = errno;
        return std::nullopt;
    }
    std::string text;
    char buf[65536];
    while (true) {
        ssize_t n = read(fd, buf, sizeof buf);
        if (n < 0 && errno == EINTR) {
            continue;
        }
        if (n < 0) {
            errno_out = errno;   // 例如它是個資料夾（EISDIR）
            close(fd);
            return std::nullopt;
        }
        if (n == 0) {
            break;
        }
        text.append(buf, (size_t)n);
    }
    close(fd);
    errno_out = 0;
    return text;
}

Spec split_hash(const std::string& spec) {
    size_t hash = spec.find('#');
    if (hash == std::string::npos) {
        return Spec{spec, ""};
    }
    std::string pointer = spec.substr(hash + 1);
    if (!pointer.starts_with('/')) {
        throw Error{code::CfgBad, "address must be FILE#/POINTER (# must be followed by /): " + spec};
    }
    return Spec{spec.substr(0, hash), pointer};
}

}  // namespace aos
