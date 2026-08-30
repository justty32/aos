#include "fs.hpp"

#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <system_error>

#include <limits.h>
#include <stdlib.h>

namespace aos::loop::fs {
namespace {

std::string system_error(const std::string &action,
                         const std::string &path) {
    return action + " " + path + ": " + std::strerror(errno);
}

}  // namespace

bool read_file(const std::string &path, std::string &text,
               std::string &error) {
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        error = "無法讀取 " + path;
        return false;
    }
    std::ostringstream buffer;
    buffer << input.rdbuf();
    if (!input.eof() && input.fail()) {
        error = "讀取失敗 " + path;
        return false;
    }
    text = buffer.str();
    return true;
}

bool write_atomic(const std::string &path, const std::string &text,
                  std::string &error) {
    const std::string temporary = path + ".tmp";
    {
        std::ofstream output(temporary,
                             std::ios::binary | std::ios::out | std::ios::trunc);
        if (!output) {
            error = "無法寫入 " + temporary;
            return false;
        }
        output.write(text.data(), static_cast<std::streamsize>(text.size()));
        output.close();
        if (!output) {
            error = "寫入失敗 " + temporary;
            std::remove(temporary.c_str());
            return false;
        }
    }
    if (std::rename(temporary.c_str(), path.c_str()) != 0) {
        error = system_error("無法發佈", path);
        std::remove(temporary.c_str());
        return false;
    }
    return true;
}

bool mkdir_p(const std::string &path, std::string &error) {
    std::error_code code;
    std::filesystem::create_directories(path, code);
    if (code) {
        error = "無法建立 " + path + ": " + code.message();
        return false;
    }
    return true;
}

std::vector<std::string> list_json_files(const std::string &dir,
                                         std::string &error) {
    std::vector<std::string> paths;
    std::error_code code;
    if (!std::filesystem::exists(dir, code)) return paths;
    if (code) {
        error = "無法檢查 " + dir + ": " + code.message();
        return paths;
    }
    std::filesystem::directory_iterator entries(dir, code);
    if (code) {
        error = "無法列出 " + dir + ": " + code.message();
        return paths;
    }
    for (const auto &entry : entries) {
        const std::string name = entry.path().filename().string();
        if (name.ends_with(".json")) paths.push_back(entry.path().string());
    }
    std::sort(paths.begin(), paths.end());
    return paths;
}

std::string realpath_of(const std::string &path) {
    char resolved[PATH_MAX];
    if (::realpath(path.c_str(), resolved) != nullptr) return resolved;
    std::error_code code;
    const auto absolute = std::filesystem::absolute(path, code);
    return code ? path : absolute.lexically_normal().string();
}

std::string join(const std::string &left, const std::string &right) {
    return (std::filesystem::path(left) / right).lexically_normal().string();
}

std::string basename_sans_json(const std::string &path) {
    std::string name = std::filesystem::path(path).filename().string();
    if (name.ends_with(".json")) name.resize(name.size() - 5);
    return name;
}

}  // namespace aos::loop::fs
