// config.cpp：讀 start 的設定檔（json）與天空的每一行，展開成預定的掛載表。
#include "common.hpp"

#include "nlohmann/json.hpp"

#include <sstream>
#include <stdexcept>

namespace d2 {

const char* const DEV_NODES[5] = {"null", "zero", "full", "random", "urandom"};
const char* const KERNEL_AOS = "/aos";
const char* const KERNEL_CGROUP = "/cgroup";

namespace {

[[noreturn]] void bad(const std::string& why) { throw std::runtime_error("ConfigBad " + why); }

// 絕對路徑、沒有 . 與 ..、沒有空的段；尾巴的 / 拿掉
std::string clean_path(const std::string& p, const std::string& what) {
    if (p.empty() || p[0] != '/') bad(what + " must be an absolute path: " + p);
    std::string out;
    std::istringstream in(p);
    for (std::string part; std::getline(in, part, '/');) {
        if (part.empty()) continue;
        if (part == "." || part == "..") bad(what + " must not contain . or ..: " + p);
        for (char c : part)
            if (c == '\n' || c == '\0') bad(what + " has a control character");
        out += "/" + part;
    }
    return out.empty() ? "/" : out;
}

bool name_ok(const std::string& n) {
    if (n.empty() || n.size() > 64 || n[0] == '.') return false;
    for (char c : n)
        if (!isalnum(static_cast<unsigned char>(c)) && c != '_' && c != '-' && c != '.') return false;
    return true;
}

}  // namespace

NsEntry parse_ns_line(const std::string& line) {
    std::istringstream in(line);
    std::vector<std::string> w;
    for (std::string s; in >> s;) w.push_back(s);
    if (w.empty()) bad("empty ns line");
    NsEntry e;
    e.kind = w[0];
    if (e.kind == "bind") {
        size_t i = 1;
        if (i < w.size() && w[i] == "-w") {
            e.rw = true;
            ++i;
        }
        if (w.size() != i + 2) bad("usage: bind [-w] SRC DST: " + line);
        e.src = clean_path(w[i], "bind source");
        e.dst = clean_path(w[i + 1], "bind target");
    } else if (e.kind == "tmpfs" || e.kind == "proc" || e.kind == "dev") {
        if (w.size() != 2) bad("usage: " + e.kind + " DST: " + line);
        e.dst = clean_path(w[1], e.kind + " target");
    } else if (e.kind == "symlink") {
        if (w.size() != 3) bad("usage: symlink TARGET DST: " + line);
        e.src = w[1];
        e.dst = clean_path(w[2], "symlink path");
    } else {
        bad("unknown ns word " + e.kind + " (bind, tmpfs, proc, dev, symlink)");
    }
    if (e.dst == "/") bad("the root is always a fresh tmpfs; " + e.kind + " / is not allowed");
    return e;
}

std::vector<Mount> plan_mounts(const std::vector<NsEntry>& ns) {
    std::vector<Mount> out{{"tmpfs", "-", "/", false}};
    for (const auto& e : ns) {
        if (e.kind == "bind") out.push_back({"bind", e.src, e.dst, e.rw});
        else if (e.kind == "tmpfs" || e.kind == "proc") out.push_back({e.kind, "-", e.dst, true});
        else if (e.kind == "dev") {
            out.push_back({"dev", "-", e.dst, false});
            for (const char* n : DEV_NODES) out.push_back({"bind", std::string("/dev/") + n, e.dst + "/" + n, true});
        }
    }
    return out;
}

std::string kernel_ns_conflict(const ProcConfig& c, bool cgroup_on) {
    if (!kernel_mounts(c)) return "";
    auto under = [](const std::string& p, const std::string& top) { return p == top || p.rfind(top + "/", 0) == 0; };
    for (const auto& e : c.ns) {
        if (under(e.dst, KERNEL_AOS) || (cgroup_on && under(e.dst, KERNEL_CGROUP)))
            return "ConfigBad ns line for " + e.dst + ": " + KERNEL_AOS + (cgroup_on ? std::string(" and ") + KERNEL_CGROUP : "") +
                   " are where the daemon puts its directory in the main kernel's ns (or set \"daemon_access\": \"ptrace\")";
    }
    return "";
}

ProcConfig parse_config(const std::string& text, const std::string& path) {
    nlohmann::json j;
    try {
        j = nlohmann::json::parse(text);
    } catch (const std::exception& e) {
        bad(std::string("not json: ") + e.what());
    }
    if (!j.is_object()) bad("top level must be an object");
    ProcConfig c;
    c.path = path;
    auto str = [&](const nlohmann::json& v, const std::string& what) {
        if (!v.is_string()) bad(what + " must be a string");
        return v.get<std::string>();
    };
    for (const auto& [k, v] : j.items()) {
        if (k == "name") {
            c.name = str(v, "name");
            if (!name_ok(c.name)) bad("name must be 1-64 of letters, digits, _ - . and not start with .");
        } else if (k == "argv") {
            if (!v.is_array() || v.empty()) bad("argv must be a non-empty array of strings");
            for (const auto& a : v) c.argv.push_back(str(a, "argv item"));
            if (c.argv[0].empty() || c.argv[0][0] != '/') bad("argv[0] must be an absolute path inside the ns");
        } else if (k == "env") {
            if (!v.is_object()) bad("env must be an object of strings");
            for (const auto& [ek, ev] : v.items()) {
                if (ek.empty() || ek.find('=') != std::string::npos) bad("env name " + ek);
                c.env.push_back(ek + "=" + str(ev, "env value"));
            }
        } else if (k == "cwd") {
            c.cwd = clean_path(str(v, "cwd"), "cwd");
        } else if (k == "ns") {
            if (!v.is_array()) bad("ns must be an array of lines");
            for (const auto& l : v) c.ns.push_back(parse_ns_line(str(l, "ns line")));
        } else if (k == "uid") {
            if (!v.is_number_integer() || v.get<long long>() < 0 || v.get<long long>() > 65535)
                bad("uid must be an integer 0..65535");
            c.uid = v.get<int>();
        } else if (k == "locks") {
            if (!v.is_object()) bad("locks must be an object");
            for (const auto& [lk, lv] : v.items()) {
                if (lk == "landlock") {
                    if (lv != true) bad("locks.landlock cannot be turned off (only the main kernel runs without it)");
                } else if (lk == "cgroup") {
                    if (!lv.is_object()) bad("locks.cgroup must be an object of file -> value");
                    for (const auto& [ck, cv] : lv.items()) {
                        bool ok = ck.find('/') == std::string::npos && ck.find('.') != std::string::npos &&
                                  ck.rfind("cgroup.", 0) != 0 && ck[0] != '.';
                        if (!ok) bad("locks.cgroup key " + ck + " (a limit file like memory.max; not cgroup.*)");
                        std::string val = cv.is_string() ? cv.get<std::string>() : cv.dump();
                        if (val.find('\n') != std::string::npos) bad("locks.cgroup value has a newline");
                        c.cgroup.emplace_back(ck, val);
                    }
                } else if (lk == "seccomp") {
                    bad("locks.seccomp is not supported in this version");
                } else {
                    bad("unknown lock " + lk + " (landlock, cgroup)");
                }
            }
        } else if (k == "daemon_access") {
            c.daemon_access = str(v, "daemon_access");
            if (c.daemon_access != "mount" && c.daemon_access != "ptrace") bad("daemon_access must be \"mount\" or \"ptrace\"");
        } else if (k == "stdout" || k == "stderr") {
            (k == "stdout" ? c.stdout_path : c.stderr_path) = clean_path(str(v, k), k);
        } else {
            bad("unknown key " + k + " (name, argv, env, cwd, ns, uid, locks, stdout, stderr, daemon_access)");
        }
    }
    if (c.name.empty()) bad("name is missing");
    if (c.argv.empty()) bad("argv is missing");
    return c;
}

}  // namespace d2
