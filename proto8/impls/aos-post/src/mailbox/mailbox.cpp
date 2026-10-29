// mailbox.cpp：【mailbox】信箱的路徑、建信箱、拿信箱，與 common.hpp 的小工具（說明見 aos/post.hpp、common/common.hpp）。
#include "common/common.hpp"

#include "aos/files.hpp"

#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <filesystem>

namespace fs = std::filesystem;

namespace aos::post {

std::string Mailbox::tmp() const { return aos::join(root, "tmp"); }
std::string Mailbox::fresh() const { return aos::join(root, "new"); }
std::string Mailbox::cur() const { return aos::join(root, "cur"); }
std::string Mailbox::done() const { return aos::join(root, "done"); }

bool is_dir(const std::string& path) {
    std::error_code ec;
    return fs::is_directory(path, ec);
}

std::vector<std::string> names_in(const std::string& dir) {
    std::vector<std::string> out;
    std::error_code ec;
    fs::directory_iterator it(dir, ec);
    if (ec) {
        return out;
    }
    for (fs::directory_iterator end; it != end; it.increment(ec)) {
        if (ec) {
            break;
        }
        std::string name = it->path().filename().string();
        if (!name.empty() && name[0] != '.') {
            out.push_back(name);
        }
    }
    std::sort(out.begin(), out.end());
    return out;
}

void drop(const std::string& path) {
    std::error_code ec;
    fs::remove_all(path, ec);
}

bool move(const std::string& from, const std::string& to) {
    if (std::rename(from.c_str(), to.c_str()) == 0) {
        return true;
    }
    int e = errno;
    if (e == ENOENT || e == ENOTEMPTY || e == EEXIST) {
        return false;
    }
    throw Error{code::WriteFailed, "改名不了 " + from + " → " + to + "：" + std::strerror(e)};
}

static void make_dir(const std::string& dir) {
    std::error_code ec;
    fs::create_directories(dir, ec);
    if (!is_dir(dir)) {
        throw Error{code::MkdirFailed, "建不了 " + dir + (ec ? "：" + ec.message() : "")};
    }
}

void init(const std::string& root) {
    Mailbox mb{aos::abspath(root)};
    make_dir(mb.root);
    make_dir(mb.tmp());
    make_dir(mb.fresh());
    make_dir(mb.cur());
}

Mailbox open(const std::string& root) {
    Mailbox mb{aos::abspath(root)};
    if (!is_dir(mb.root)) {
        throw Error{code::MailboxMissing, "信箱不在：" + root};
    }
    const std::string parts[] = {mb.tmp(), mb.fresh(), mb.cur()};
    for (const std::string& p : parts) {
        if (!is_dir(p)) {
            throw Error{code::MailboxMissing, "信箱沒建好（少了 " + p + "；先 aos-post init）"};
        }
    }
    return mb;
}

void check_id(const std::string& id) {
    if (id.empty() || id[0] == '.' || id.find('/') != std::string::npos) {
        throw Error{code::ArgumentsBad, "信號要是一個單純的名字（不空、不含 /、不以 . 開頭）：" + id};
    }
}

}  // namespace aos::post
