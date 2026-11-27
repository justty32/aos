// seccomp.cpp：每隻 proc 的 seccomp 過濾器（手寫 BPF）——內建的擋單、使用者的名單檔（x86_64 的系統呼叫名字表，編的時候從標頭產生）、locks 檔的那一行。
#include "common.hpp"

#include "nlohmann/json.hpp"

#include <algorithm>
#include <cerrno>
#include <cstddef>
#include <linux/audit.h>
#include <linux/seccomp.h>

#ifndef __x86_64__
#error "aos-daemon's seccomp filter and syscall name table are for x86_64 only"
#endif

namespace d2 {

namespace {

// x86_64 的系統呼叫名字 → 號碼。表是 make 時從編譯器找得到的 asm/unistd_64.h 產生的（build/gen/syscalls_x86_64.inc，
// 見 Makefile）：以前手抄，Linux 加了新的呼叫（例 6.11 的 uretprobe）就跟不上；x86_64 的號碼不會改，只會加。
struct Sys {
    const char* name;
    int nr;
};
const Sys SYSCALLS[] = {
#include "syscalls_x86_64.inc"
};
static_assert(sizeof SYSCALLS / sizeof SYSCALLS[0] > 300, "the generated syscall table is too short");

// 內建的擋單（使用者 11-26 定：預設就上、跟 Docker 預設的精神相近，但建 namespace、mount 那一族都不擋，好讓 proc 裡再起 daemon）。
// 一個一個為什麼見 README「seccomp」。號碼是 x86_64 的。
//
// 對照的現成清單（daemon職責第 41 條：清單自己維護，記下對照的是哪一份）：
//   1. systemd 255（255.4-1ubuntu8.19）`systemd-analyze syscall-filter` 印出來的群組，11-26 在公司 WSL 上逐個比過：
//      @module、@reboot、@swap、@clock、@raw-io、@keyring 在 x86_64 有的全擋；
//      @debug 擋 ptrace、perf_event_open、pidfd_getfd、lookup_dcookie（rtas、s390_* 不是 x86_64 的）；
//      @obsolete 只擋 create_module、get_kernel_syms、query_module、uselib、_sysctl（afs_syscall、getpmsg、putpmsg、security、
//        tuxcall、vserver 核心沒實作，sysfs、ustat 只讀、無害，沒擋）；
//      @privileged 只擋 acct、bpf、quotactl、quotactl_fd、open_by_handle_at、vhangup、nfsservctl、_sysctl（chown、setuid 這類、
//        capset、chroot、pivot_root、sethostname、setdomainname、fanotify_* 沒擋：天空裡的程式要用，在 user namespace 裡也動不到外面）；
//      @resources 只擋 move_pages、migrate_pages（mbind、set_mempolicy、setpriority 等只動自己，放）；
//      @aio 只擋 io_uring_*；@mount 整組不擋（為了疊 daemon）；@cpu-emulation 的 modify_ldt 沒擋。
//   2. Docker（moby）預設 seccomp 設定檔 profiles/seccomp/default.json 的精神：syslog、userfaultfd、kcmp、name_to_handle_at、
//      process_vm_readv／writev 這幾個在 systemd 的群組裡不算危險（@system-service、@ipc），照 Docker「要 CAP_SYS_PTRACE／CAP_SYSLOG
//      等才放」擋；personality 只放的五個值照它。本機沒有 docker，沒有逐行比對某一版的 default.json。
//   比 6.6 新的 Linux 加的呼叫（11-27 家機 6.18、標頭 7.2 看到的：uretprobe、uprobe、mseal、setxattrat、getxattrat、listxattrat、
//   removexattrat、open_tree_attr、file_getattr、file_setattr、listns、rseq_slice_yield）都沒加進擋單【擬】：多半只動自己的行程或檔，
//   open_tree_attr 是不擋的 mount 那一族；listns 列得出看得到的 namespace，要不要擋見 README「seccomp」。
const int BUILTIN_DENY[] = {
    175, 313, 176, 174, 177, 178,   // init_module finit_module delete_module create_module get_kernel_syms query_module
    246, 320, 169,                  // kexec_load kexec_file_load reboot
    167, 168,                       // swapon swapoff
    164, 227, 305, 159,             // settimeofday clock_settime clock_adjtime adjtimex
    163, 179, 443,                  // acct quotactl quotactl_fd
    321, 298, 323,                  // bpf perf_event_open userfaultfd
    250, 248, 249,                  // keyctl add_key request_key
    101, 310, 311, 312, 438,        // ptrace process_vm_readv process_vm_writev kcmp pidfd_getfd
    304, 303, 212,                  // open_by_handle_at name_to_handle_at lookup_dcookie
    172, 173, 103,                  // iopl ioperm syslog
    134, 153, 180, 156,             // uselib vhangup nfsservctl _sysctl
    279, 256,                       // move_pages migrate_pages
    425, 426, 427,                  // io_uring_setup io_uring_enter io_uring_register
};
const int NR_PERSONALITY = 135;
// personality 只放這幾個值（跟 Docker 一樣）：PER_LINUX、PER_LINUX32、UNAME26、UNAME26|PER_LINUX32、0xffffffff（只查不改）
const uint32_t PERSONALITY_OK[] = {0x0, 0x8, 0x20000, 0x20008, 0xffffffffu};
const uint32_t X32_BIT = 0x40000000u;

sock_filter stmt(uint16_t code, uint32_t k) { return sock_filter{code, 0, 0, k}; }
sock_filter jump(uint16_t code, uint32_t k, uint8_t jt, uint8_t jf) { return sock_filter{code, jt, jf, k}; }

const uint32_t RET_EPERM = SECCOMP_RET_ERRNO | (EPERM & SECCOMP_RET_DATA);

// 開頭：不是 x86_64（例 int 0x80 的 i386 呼叫）或 x32 的號碼 → 整個行程殺掉；之後 A＝系統呼叫號碼
void prologue(std::vector<sock_filter>& f) {
    f.push_back(stmt(BPF_LD | BPF_W | BPF_ABS, offsetof(seccomp_data, arch)));
    f.push_back(jump(BPF_JMP | BPF_JEQ | BPF_K, AUDIT_ARCH_X86_64, 1, 0));
    f.push_back(stmt(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS));
    f.push_back(stmt(BPF_LD | BPF_W | BPF_ABS, offsetof(seccomp_data, nr)));
    f.push_back(jump(BPF_JMP | BPF_JGE | BPF_K, X32_BIT, 0, 1));
    f.push_back(stmt(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS));
}

// 每個號碼兩條：「是它就往下一條（ret），不是就跳過」——不用遠跳，名單多長都行（條件跳只能跳 255 條）
void match(std::vector<sock_filter>& f, int nr, uint32_t action) {
    f.push_back(jump(BPF_JMP | BPF_JEQ | BPF_K, static_cast<uint32_t>(nr), 0, 1));
    f.push_back(stmt(BPF_RET | BPF_K, action));
}

}  // namespace

size_t seccomp_builtin_count() { return sizeof BUILTIN_DENY / sizeof BUILTIN_DENY[0]; }

int syscall_number(const std::string& name) {
    for (const auto& s : SYSCALLS)
        if (name == s.name) return s.nr;
    return -1;
}

std::string load_seccomp_list(ProcConfig& c) {
    if (c.seccomp.empty() || c.seccomp == "off" || c.seccomp == "builtin") return "";
    std::string err, text = read_host_file(c.seccomp, err);
    if (!err.empty()) return "ConfigBad locks.seccomp list: " + err;
    std::string where = "ConfigBad locks.seccomp list " + c.seccomp + ": ";
    if (!json_depth_ok(text)) return where + "nested deeper than " + std::to_string(JSON_MAX_DEPTH) + " levels of [ ] or { }";
    nlohmann::json j;
    try {
        j = nlohmann::json::parse(text);
    } catch (const std::exception& e) {
        return where + "not json: " + e.what();
    }
    if (!j.is_object()) return where + "the top level must be an object like {\"default\": \"allow\", \"deny\": [\"ptrace\"]}";
    auto d = j.find("default");
    if (d == j.end() || !d->is_string() || (*d != "allow" && *d != "deny"))
        return where + "\"default\" must be \"allow\" (with a \"deny\" list) or \"deny\" (with an \"allow\" list)";
    c.sc_default_allow = *d == "allow";
    std::string key = c.sc_default_allow ? "deny" : "allow";
    for (const auto& [k, v] : j.items()) {
        (void)v;
        if (k != "default" && k != key)
            return where + "unknown key \"" + k + "\" (with \"default\": \"" + d->get<std::string>() + "\" the list is \"" + key + "\")";
    }
    auto l = j.find(key);
    if (l == j.end() || !l->is_array()) return where + "\"" + key + "\" must be an array of syscall names";
    c.sc_list.clear();
    for (const auto& n : *l) {
        if (!n.is_string()) return where + "\"" + key + "\" items must be syscall names (strings), not " + n.dump();
        int nr = syscall_number(n.get<std::string>());
        if (nr < 0) return where + "unknown syscall name \"" + n.get<std::string>() + "\" (x86_64 names, like ptrace, bpf, init_module)";
        c.sc_list.push_back(nr);
    }
    // 重複的只留一個（過濾器最多 6＋2×名字表的個數＋1 條；表要過 2000 個才會超過核心的 4096，x86_64 現在 400 個上下）
    std::sort(c.sc_list.begin(), c.sc_list.end());
    c.sc_list.erase(std::unique(c.sc_list.begin(), c.sc_list.end()), c.sc_list.end());
    return "";
}

std::vector<sock_filter> seccomp_filter(const ProcConfig& c) {
    std::vector<sock_filter> f;
    if (c.seccomp == "off") return f;
    prologue(f);
    if (c.seccomp.empty() || c.seccomp == "builtin") {
        for (int nr : BUILTIN_DENY) match(f, nr, RET_EPERM);
        // personality：不是它就跳過這一段（1＋2×值的個數＋1 條）
        size_t n = sizeof PERSONALITY_OK / sizeof PERSONALITY_OK[0];
        f.push_back(jump(BPF_JMP | BPF_JEQ | BPF_K, NR_PERSONALITY, 0, static_cast<uint8_t>(2 + 2 * n)));
        f.push_back(stmt(BPF_LD | BPF_W | BPF_ABS, offsetof(seccomp_data, args)));   // args[0] 的低 32 位（little endian）
        for (uint32_t v : PERSONALITY_OK) {
            f.push_back(jump(BPF_JMP | BPF_JEQ | BPF_K, v, 0, 1));
            f.push_back(stmt(BPF_RET | BPF_K, SECCOMP_RET_ALLOW));
        }
        f.push_back(stmt(BPF_RET | BPF_K, RET_EPERM));
        f.push_back(stmt(BPF_RET | BPF_K, SECCOMP_RET_ALLOW));
        return f;
    }
    for (int nr : c.sc_list) match(f, nr, c.sc_default_allow ? RET_EPERM : SECCOMP_RET_ALLOW);
    f.push_back(stmt(BPF_RET | BPF_K, c.sc_default_allow ? SECCOMP_RET_ALLOW : RET_EPERM));
    return f;
}

std::string seccomp_lock_line(const ProcConfig& c) {
    if (c.seccomp == "off") return "seccomp: off";
    const char* tail = "; other arch and x32 calls kill the process";
    if (c.seccomp.empty() || c.seccomp == "builtin")
        return "seccomp: builtin (" + std::to_string(seccomp_builtin_count()) +
               " syscalls denied with EPERM, personality limited to safe values" + tail + ")";
    return "seccomp: " + c.seccomp + " (default " + (c.sc_default_allow ? "allow, " : "deny, ") + std::to_string(c.sc_list.size()) +
           (c.sc_default_allow ? " denied with EPERM" : " allowed, the rest EPERM") + tail + ")";
}

}  // namespace d2
