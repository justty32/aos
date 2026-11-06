// dirs.cpp：【aos-util】查詢、建立、列出、改名與移除目錄及檔案。
#include "aos/util/files.hpp"

#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <filesystem>

namespace aos {

bool is_dir(const std::string& path) {
    std::error_code ec;
    return std::filesystem::is_directory(path, ec);
}

void make_dir(const std::string& dir) {
    std::error_code ec;
    std::filesystem::create_directories(dir, ec);
    if (ec || !is_dir(dir)) {
        throw Error{code::MkdirFailed, "cannot create " + dir + (ec ? ": " + ec.message() : "")};
    }
}

std::vector<std::string> names_in(const std::string& dir, bool directories_only) {
    std::vector<std::string> out;
    std::error_code ec;
    std::filesystem::directory_iterator it(dir, ec);
    if (ec) {
        return out;
    }
    for (std::filesystem::directory_iterator end; it != end; it.increment(ec)) {
        if (ec) {
            break;
        }
        std::string name = it->path().filename().string();
        if (name.empty() || name[0] == '.') {
            continue;
        }
        std::error_code ec2;
        if (!directories_only || it->is_directory(ec2)) {
            out.push_back(name);
        }
    }
    if (directories_only) {
        std::sort(out.begin(), out.end());
    }
    return out;
}

bool move(const std::string& from, const std::string& to) {
    if (std::rename(from.c_str(), to.c_str()) == 0) {
        return true;
    }
    int e = errno;
    if (e == ENOENT || e == ENOTEMPTY || e == EEXIST) {
        return false;
    }
    throw Error{code::WriteFailed, "cannot rename " + from + " -> " + to + ": " + std::strerror(e)};
}

void remove_tree(const std::string& path) {
    std::error_code ec;
    std::filesystem::remove_all(path, ec);
}

}  // namespace aos
