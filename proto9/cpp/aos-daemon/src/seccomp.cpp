// seccomp.cpp：每隻 proc 的 seccomp 過濾器（手寫 BPF）——內建的擋單、使用者的名單檔（x86_64 的系統呼叫名字表）、locks 檔的那一行。
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

// x86_64 的系統呼叫名字 → 號碼（照 Linux 的 asm/unistd_64.h 抄來；x86_64 的號碼不會改）
struct Sys {
    const char* name;
    int nr;
};
const Sys SYSCALLS[] = {
    {"read", 0}, {"write", 1}, {"open", 2}, {"close", 3}, {"stat", 4}, {"fstat", 5}, {"lstat", 6}, {"poll", 7},
    {"lseek", 8}, {"mmap", 9}, {"mprotect", 10}, {"munmap", 11}, {"brk", 12}, {"rt_sigaction", 13},
    {"rt_sigprocmask", 14}, {"rt_sigreturn", 15}, {"ioctl", 16}, {"pread64", 17}, {"pwrite64", 18}, {"readv", 19},
    {"writev", 20}, {"access", 21}, {"pipe", 22}, {"select", 23}, {"sched_yield", 24}, {"mremap", 25}, {"msync", 26},
    {"mincore", 27}, {"madvise", 28}, {"shmget", 29}, {"shmat", 30}, {"shmctl", 31}, {"dup", 32}, {"dup2", 33},
    {"pause", 34}, {"nanosleep", 35}, {"getitimer", 36}, {"alarm", 37}, {"setitimer", 38}, {"getpid", 39},
    {"sendfile", 40}, {"socket", 41}, {"connect", 42}, {"accept", 43}, {"sendto", 44}, {"recvfrom", 45},
    {"sendmsg", 46}, {"recvmsg", 47}, {"shutdown", 48}, {"bind", 49}, {"listen", 50}, {"getsockname", 51},
    {"getpeername", 52}, {"socketpair", 53}, {"setsockopt", 54}, {"getsockopt", 55}, {"clone", 56}, {"fork", 57},
    {"vfork", 58}, {"execve", 59}, {"exit", 60}, {"wait4", 61}, {"kill", 62}, {"uname", 63}, {"semget", 64},
    {"semop", 65}, {"semctl", 66}, {"shmdt", 67}, {"msgget", 68}, {"msgsnd", 69}, {"msgrcv", 70}, {"msgctl", 71},
    {"fcntl", 72}, {"flock", 73}, {"fsync", 74}, {"fdatasync", 75}, {"truncate", 76}, {"ftruncate", 77},
    {"getdents", 78}, {"getcwd", 79}, {"chdir", 80}, {"fchdir", 81}, {"rename", 82}, {"mkdir", 83}, {"rmdir", 84},
    {"creat", 85}, {"link", 86}, {"unlink", 87}, {"symlink", 88}, {"readlink", 89}, {"chmod", 90}, {"fchmod", 91},
    {"chown", 92}, {"fchown", 93}, {"lchown", 94}, {"umask", 95}, {"gettimeofday", 96}, {"getrlimit", 97},
    {"getrusage", 98}, {"sysinfo", 99}, {"times", 100}, {"ptrace", 101}, {"getuid", 102}, {"syslog", 103},
    {"getgid", 104}, {"setuid", 105}, {"setgid", 106}, {"geteuid", 107}, {"getegid", 108}, {"setpgid", 109},
    {"getppid", 110}, {"getpgrp", 111}, {"setsid", 112}, {"setreuid", 113}, {"setregid", 114}, {"getgroups", 115},
    {"setgroups", 116}, {"setresuid", 117}, {"getresuid", 118}, {"setresgid", 119}, {"getresgid", 120},
    {"getpgid", 121}, {"setfsuid", 122}, {"setfsgid", 123}, {"getsid", 124}, {"capget", 125}, {"capset", 126},
    {"rt_sigpending", 127}, {"rt_sigtimedwait", 128}, {"rt_sigqueueinfo", 129}, {"rt_sigsuspend", 130},
    {"sigaltstack", 131}, {"utime", 132}, {"mknod", 133}, {"uselib", 134}, {"personality", 135}, {"ustat", 136},
    {"statfs", 137}, {"fstatfs", 138}, {"sysfs", 139}, {"getpriority", 140}, {"setpriority", 141},
    {"sched_setparam", 142}, {"sched_getparam", 143}, {"sched_setscheduler", 144}, {"sched_getscheduler", 145},
    {"sched_get_priority_max", 146}, {"sched_get_priority_min", 147}, {"sched_rr_get_interval", 148}, {"mlock", 149},
    {"munlock", 150}, {"mlockall", 151}, {"munlockall", 152}, {"vhangup", 153}, {"modify_ldt", 154},
    {"pivot_root", 155}, {"_sysctl", 156}, {"prctl", 157}, {"arch_prctl", 158}, {"adjtimex", 159},
    {"setrlimit", 160}, {"chroot", 161}, {"sync", 162}, {"acct", 163}, {"settimeofday", 164}, {"mount", 165},
    {"umount2", 166}, {"swapon", 167}, {"swapoff", 168}, {"reboot", 169}, {"sethostname", 170},
    {"setdomainname", 171}, {"iopl", 172}, {"ioperm", 173}, {"create_module", 174}, {"init_module", 175},
    {"delete_module", 176}, {"get_kernel_syms", 177}, {"query_module", 178}, {"quotactl", 179}, {"nfsservctl", 180},
    {"getpmsg", 181}, {"putpmsg", 182}, {"afs_syscall", 183}, {"tuxcall", 184}, {"security", 185}, {"gettid", 186},
    {"readahead", 187}, {"setxattr", 188}, {"lsetxattr", 189}, {"fsetxattr", 190}, {"getxattr", 191},
    {"lgetxattr", 192}, {"fgetxattr", 193}, {"listxattr", 194}, {"llistxattr", 195}, {"flistxattr", 196},
    {"removexattr", 197}, {"lremovexattr", 198}, {"fremovexattr", 199}, {"tkill", 200}, {"time", 201},
    {"futex", 202}, {"sched_setaffinity", 203}, {"sched_getaffinity", 204}, {"set_thread_area", 205},
    {"io_setup", 206}, {"io_destroy", 207}, {"io_getevents", 208}, {"io_submit", 209}, {"io_cancel", 210},
    {"get_thread_area", 211}, {"lookup_dcookie", 212}, {"epoll_create", 213}, {"epoll_ctl_old", 214},
    {"epoll_wait_old", 215}, {"remap_file_pages", 216}, {"getdents64", 217}, {"set_tid_address", 218},
    {"restart_syscall", 219}, {"semtimedop", 220}, {"fadvise64", 221}, {"timer_create", 222}, {"timer_settime", 223},
    {"timer_gettime", 224}, {"timer_getoverrun", 225}, {"timer_delete", 226}, {"clock_settime", 227},
    {"clock_gettime", 228}, {"clock_getres", 229}, {"clock_nanosleep", 230}, {"exit_group", 231},
    {"epoll_wait", 232}, {"epoll_ctl", 233}, {"tgkill", 234}, {"utimes", 235}, {"vserver", 236}, {"mbind", 237},
    {"set_mempolicy", 238}, {"get_mempolicy", 239}, {"mq_open", 240}, {"mq_unlink", 241}, {"mq_timedsend", 242},
    {"mq_timedreceive", 243}, {"mq_notify", 244}, {"mq_getsetattr", 245}, {"kexec_load", 246}, {"waitid", 247},
    {"add_key", 248}, {"request_key", 249}, {"keyctl", 250}, {"ioprio_set", 251}, {"ioprio_get", 252},
    {"inotify_init", 253}, {"inotify_add_watch", 254}, {"inotify_rm_watch", 255}, {"migrate_pages", 256},
    {"openat", 257}, {"mkdirat", 258}, {"mknodat", 259}, {"fchownat", 260}, {"futimesat", 261}, {"newfstatat", 262},
    {"unlinkat", 263}, {"renameat", 264}, {"linkat", 265}, {"symlinkat", 266}, {"readlinkat", 267},
    {"fchmodat", 268}, {"faccessat", 269}, {"pselect6", 270}, {"ppoll", 271}, {"unshare", 272},
    {"set_robust_list", 273}, {"get_robust_list", 274}, {"splice", 275}, {"tee", 276}, {"sync_file_range", 277},
    {"vmsplice", 278}, {"move_pages", 279}, {"utimensat", 280}, {"epoll_pwait", 281}, {"signalfd", 282},
    {"timerfd_create", 283}, {"eventfd", 284}, {"fallocate", 285}, {"timerfd_settime", 286},
    {"timerfd_gettime", 287}, {"accept4", 288}, {"signalfd4", 289}, {"eventfd2", 290}, {"epoll_create1", 291},
    {"dup3", 292}, {"pipe2", 293}, {"inotify_init1", 294}, {"preadv", 295}, {"pwritev", 296},
    {"rt_tgsigqueueinfo", 297}, {"perf_event_open", 298}, {"recvmmsg", 299}, {"fanotify_init", 300},
    {"fanotify_mark", 301}, {"prlimit64", 302}, {"name_to_handle_at", 303}, {"open_by_handle_at", 304},
    {"clock_adjtime", 305}, {"syncfs", 306}, {"sendmmsg", 307}, {"setns", 308}, {"getcpu", 309},
    {"process_vm_readv", 310}, {"process_vm_writev", 311}, {"kcmp", 312}, {"finit_module", 313},
    {"sched_setattr", 314}, {"sched_getattr", 315}, {"renameat2", 316}, {"seccomp", 317}, {"getrandom", 318},
    {"memfd_create", 319}, {"kexec_file_load", 320}, {"bpf", 321}, {"execveat", 322}, {"userfaultfd", 323},
    {"membarrier", 324}, {"mlock2", 325}, {"copy_file_range", 326}, {"preadv2", 327}, {"pwritev2", 328},
    {"pkey_mprotect", 329}, {"pkey_alloc", 330}, {"pkey_free", 331}, {"statx", 332}, {"io_pgetevents", 333},
    {"rseq", 334}, {"pidfd_send_signal", 424}, {"io_uring_setup", 425}, {"io_uring_enter", 426},
    {"io_uring_register", 427}, {"open_tree", 428}, {"move_mount", 429}, {"fsopen", 430}, {"fsconfig", 431},
    {"fsmount", 432}, {"fspick", 433}, {"pidfd_open", 434}, {"clone3", 435}, {"close_range", 436}, {"openat2", 437},
    {"pidfd_getfd", 438}, {"faccessat2", 439}, {"process_madvise", 440}, {"epoll_pwait2", 441},
    {"mount_setattr", 442}, {"quotactl_fd", 443}, {"landlock_create_ruleset", 444}, {"landlock_add_rule", 445},
    {"landlock_restrict_self", 446}, {"memfd_secret", 447}, {"process_mrelease", 448}, {"futex_waitv", 449},
    {"set_mempolicy_home_node", 450}, {"cachestat", 451}, {"fchmodat2", 452}, {"map_shadow_stack", 453},
    {"futex_wake", 454}, {"futex_wait", 455}, {"futex_requeue", 456}, {"statmount", 457}, {"listmount", 458},
    {"lsm_get_self_attr", 459}, {"lsm_set_self_attr", 460}, {"lsm_list_modules", 461},
};

// 內建的擋單（使用者 11-26 定：預設就上、跟 Docker 預設的精神相近，但建 namespace、mount 那一族都不擋，好讓 proc 裡再起 daemon）。
// 一個一個為什麼見 README「seccomp」。號碼是 x86_64 的。
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
    // 重複的只留一個（過濾器最多 6＋2×373＋1 條，不會超過核心的 4096）
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
