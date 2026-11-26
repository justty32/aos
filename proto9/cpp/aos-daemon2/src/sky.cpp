// sky.cpp：天空表——讀一隻 proc 的 /proc/<PID>/mountinfo，一個掛載一行，對回預定的掛載表標上來源。
#include "common.hpp"

#include <sstream>

namespace d2 {

namespace {

struct MiLine {
    std::string point, fstype;
    bool ro = false;
};

// mountinfo 把空白、tab、換行、反斜線寫成 \040 這種八進位
std::string unescape(const std::string& s) {
    std::string out;
    for (size_t i = 0; i < s.size(); ++i) {
        if (s[i] == '\\' && i + 3 < s.size() &&s[i + 1] >= '0' && s[i + 1] <= '7') {
            out += static_cast<char>((s[i + 1] - '0') * 64 + (s[i + 2] - '0') * 8 + (s[i + 3] - '0'));
            i += 3;
        } else {
            out += s[i];
        }
    }
    return out;
}

std::vector<MiLine> mountinfo(pid_t pid) {
    std::vector<MiLine> out;
    std::istringstream in(read_fd_at(W.procfd, std::to_string(pid) + "/mountinfo"));
    for (std::string line; std::getline(in, line);) {
        std::istringstream ls(line);
        std::string id, parent, dev, root, point, opts, f;
        ls >> id >> parent >> dev >> root >> point >> opts;
        while (ls >> f && f != "-") {}
        MiLine m;
        ls >> m.fstype;
        m.point = unescape(point);
        m.ro = opts.rfind("ro", 0) == 0 && (opts.size() == 2 || opts[2] == ',');
        out.push_back(std::move(m));
    }
    return out;
}

bool under(const std::string& p, const std::string& top) {
    return top == "/" || p == top || (p.size() > top.size() && p.compare(0, top.size(), top) == 0 && p[top.size()] == '/');
}

}  // namespace

std::string esc(const std::string& s) {
    std::string out;
    for (char c : s) {
        if (c == ' ' || c == '\t' || c == '\n' || c == '\\') {
            char b[8];
            snprintf(b, sizeof b, "\\%03o", static_cast<unsigned char>(c));
            out += b;
        } else {
            out += c;
        }
    }
    return out;
}

// 一行：種類 來源 天空裡的位置 ro|rw [locked]
//   locked＝不是設定寫的，是 bind 來源底下外面那層掛的、被迫一起帶進來（卸不掉）的掛載
std::string sky_table(pid_t pid, const std::vector<Mount>& planned, std::string& check) {
    auto mi = mountinfo(pid);
    std::vector<bool> used(planned.size(), false);
    std::string out, problems;
    if (mi.empty()) problems += "mountinfo unreadable; ";
    for (const auto& m : mi) {
        const char* rw = m.ro ? "ro" : "rw";
        int hit = -1;
        for (size_t i = 0; i < planned.size(); ++i)
            if (!used[i] && planned[i].dst == m.point) {
                hit = static_cast<int>(i);
                break;
            }
        if (hit >= 0) {
            used[hit] = true;
            const Mount& p = planned[hit];
            out += p.kind + " " + esc(p.src) + " " + esc(m.point) + " " + rw + "\n";
            if (p.rw == m.ro) problems += m.point + " is " + rw + " but the config says " + (p.rw ? "rw" : "ro") + "; ";
            continue;
        }
        // 最近的那個 bind 祖先帶進來的
        int anc = -1;
        for (size_t i = 0; i < planned.size(); ++i)
            if (planned[i].kind == "bind" && planned[i].dst != "/" && under(m.point, planned[i].dst) &&
                (anc < 0 || planned[i].dst.size() > planned[anc].dst.size()))
                anc = static_cast<int>(i);
        if (anc >= 0) {
            const Mount& p = planned[anc];
            out += "bind " + esc(p.src + m.point.substr(p.dst.size())) + " " + esc(m.point) + " " + rw + " locked\n";
        } else {
            out += "unknown " + esc(m.fstype) + " " + esc(m.point) + " " + rw + "\n";
            problems += "unexpected mount at " + m.point + "; ";
        }
    }
    for (size_t i = 0; i < planned.size(); ++i)
        if (!used[i]) problems += "missing " + planned[i].kind + " at " + planned[i].dst + "; ";
    if (!problems.empty() && problems.size() >= 2) problems.resize(problems.size() - 2);
    check = problems.empty() ? "ok" : problems;
    return out;
}

}  // namespace d2
