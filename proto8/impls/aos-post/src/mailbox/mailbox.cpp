// mailbox.cpp：【mailbox】信箱的路徑、建信箱、拿信箱、信件名稱的規則（check_name、is_ordered、sort_letters）、
// reply_to 的相對化與拼回（reply_to_rel、reply_to_abs），
// 與 common.hpp 的小工具（說明見 aos/post.hpp、common/common.hpp）。
#include "common/common.hpp"

#include "aos/util/files.hpp"

#include <algorithm>

#include <sys/stat.h>

namespace aos::post {

std::string Mailbox::tmp() const { return aos::join(root, "tmp"); }
std::string Mailbox::fresh() const { return aos::join(root, "new"); }
std::string Mailbox::cur() const { return aos::join(root, "cur"); }
std::string Mailbox::archive() const { return aos::join(root, "archive"); }

std::vector<std::string> names_in(const std::string& dir) {
    std::vector<std::string> out = aos::names_in(dir);
    sort_letters(out);
    return out;
}

void drop(const std::string& path) {
    aos::remove_tree(path);
}

void need_dir(const std::string& path) {
    if (!is_dir(path)) {
        throw Error{code::MailboxMissing, "mailbox not set up (missing " + path + "); run aos-post init first"};
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
        struct stat st{};
        if (::stat(mb.root.c_str(), &st) == 0) {   // 11-05 第二輪：在、但不是資料夾（例 --reply-to 指到一般檔）：原本說「找不到」，像是路徑打錯
            throw Error{code::MailboxMissing, "mailbox is not a directory: " + root};
        }
        throw Error{code::MailboxMissing, "mailbox not found: " + root};
    }
    return mb;
}

// 絕對路徑拆成一層一層（空的、. 不算；呼叫的人先 abspath 過，不會有 ..）。
static std::vector<std::string> parts_of(const std::string& path) {
    std::vector<std::string> out;
    size_t i = 0;
    while (i <= path.size()) {
        size_t j = path.find('/', i);
        if (j == std::string::npos) {
            j = path.size();
        }
        std::string s = path.substr(i, j - i);
        if (!s.empty() && s != ".") {
            out.push_back(s);
        }
        i = j + 1;
    }
    return out;
}

// 字串算、不 realpath（捷徑當普通路徑，搬家時跟著走；portable-flow 03 原則 6）。
std::string reply_to_rel(const Mailbox& mb, const std::string& box) {
    std::string to = aos::abspath(box);
    std::vector<std::string> b = parts_of(aos::abspath(mb.root));
    std::vector<std::string> t = parts_of(to);
    size_t n = 0;
    while (n < b.size() && n < t.size() && b[n] == t[n]) {
        ++n;
    }
    if (n == 0) {
        return to;   // 沒有共同的第一層（/tmp/… 對 /home/…）：相對了也沒意思，存絕對
    }
    std::string out;
    for (size_t i = n; i < b.size(); ++i) {
        out += out.empty() ? ".." : "/..";
    }
    for (size_t i = n; i < t.size(); ++i) {
        out += (out.empty() ? "" : "/") + t[i];
    }
    return out.empty() ? "." : out;
}

std::string reply_to_abs(const Mailbox& mb, const std::string& reply_to) {
    if (!reply_to.empty() && reply_to[0] == '/') {
        return reply_to;   // 絕對（11-05 前的舊信、或沒有共同第一層的）照用
    }
    return aos::abspath(aos::join(mb.root, reply_to));
}

void check_name(const std::string& name) {
    if (name.empty() || name[0] == '.' || name.find('/') != std::string::npos) {
        throw Error{code::ArgumentsBad, "letter name must be a plain name (non-empty, no /, not starting with .): " + name};
    }
    // take-all 一行一個名字：名字裡有換行等控制字元會被拆成兩個不存在的名字（11-04 夜 C 線）
    for (unsigned char ch : name) {
        if (ch < 0x20 || ch == 0x7f) {
            throw Error{code::ArgumentsBad, "letter name must not contain control characters (newline, tab, ...)"};
        }
    }
}

// ^[0-9]{12}\.——明寫的規則，不靠字典序碰巧（thinking 11-03 aos-post § 2）。
bool is_ordered(const std::string& name) {
    if (name.size() < 13 || name[12] != '.') {
        return false;
    }
    for (int i = 0; i < 12; ++i) {
        if (name[i] < '0' || name[i] > '9') {
            return false;
        }
    }
    return true;
}

void sort_letters(std::vector<std::string>& names) {
    std::sort(names.begin(), names.end(), [](const std::string& a, const std::string& b) {
        bool oa = is_ordered(a);
        bool ob = is_ordered(b);
        if (oa != ob) {
            return oa;   // 有序在前
        }
        return a < b;
    });
}

}  // namespace aos::post
