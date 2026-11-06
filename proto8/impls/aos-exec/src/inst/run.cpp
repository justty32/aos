// run.cpp：【inst】run_inst——行程內跑一張 inst 單子（公開介面見 aos/exec.hpp）。
//
//   1. aos::resolve        解單子裡的指示詞（$env、$ref，$path／$prefix；aos-directive；$ref 從 ref_base 算）。要在 apply_env
//                          之後呼叫，單子才讀得到 aos-exec 剛設的 AOS_STACK／AOS_CF／AOS_CD
//   2. parse_inst          驗 10 個 key（fields.cpp）；argv0（帶 / 又 exec 不了＝前面插 aos-exec，launch.cpp）；
//                          build_lib_input 組 aos-inst 的單子（lib_input.cpp）
//   3. 擋住三個訊號（SigMask，出去還原）、開 signalfd／eventfd
//   4. aos_inst_start      起子程式，同步拿到 pid（失敗＝LaunchFailed，訊息帶 aos-inst 的名字）
//   5. 工人執行緒          aos_inst_wait：卡到子程式結束（含 timeout／grace 整群收掉），回來敲一下 done_fd
//      主執行緒            forward_signals_until_done：把訊號轉給整群，直到 done_fd 響（signals.cpp）
//   6. join 之後讀結果（wait 失敗＝Internal）
//
// 為什麼要兩條執行緒：aos_inst_wait 一呼叫就卡到子程式結束，卡著的時候沒辦法同時收訊號。
// 執行緒之間沒有共用會同時讀寫的變數：pid 在開工人之前就拿到了；proc、out、rc 開工人之後只有工人碰，
// 主執行緒 join 之後才讀。
// aos-inst 的錯誤代號不一個個鏡射（C-53 濃縮）；遮罩在這裡擋／還原、整群送。
#include "inst/inst.hpp"

#include "aos/directive.hpp"
#include "aos/files.hpp"

#include <cerrno>
#include <cstdint>
#include <cstring>
#include <thread>

#include <fcntl.h>
#include <pthread.h>
#include <sys/stat.h>
#include <sys/eventfd.h>
#include <unistd.h>

namespace aos::exec {

namespace {

// 進來時擋住三個訊號、出去時還原（單執行緒的呼叫者什麼都不用做）。
struct SigMask {
    sigset_t old;
    SigMask() {
        sigset_t set = forwarded_signals();
        pthread_sigmask(SIG_BLOCK, &set, &old);
    }
    ~SigMask() { pthread_sigmask(SIG_SETMASK, &old, nullptr); }
    SigMask(const SigMask&) = delete;
    SigMask& operator=(const SigMask&) = delete;
};

// 關 fd 的小包裝（-1 不關）。
struct Fd {
    int fd;
    explicit Fd(int f) : fd(f) {}
    ~Fd() {
        if (fd >= 0) {
            close(fd);
        }
    }
    Fd(const Fd&) = delete;
    Fd& operator=(const Fd&) = delete;
};

// aos-inst 只說「串流開不了」：這裡不動檔地再看一次是哪一個、為什麼（stdin 試開唯讀；stdout／stderr 檔在就試開寫、
// 不在就看上層資料夾），說得出來就說，說不出來照舊。
std::string open_failed_why(const LibInput& lib) {
    static const char* names[3] = {"stdin", "stdout", "stderr"};
    for (int i = 0; i < 3; ++i) {
        if (!lib.paths[i]) {
            continue;
        }
        const std::string& p = *lib.paths[i];
        int fd = -1;
        if (i == 0) {
            fd = open(p.c_str(), O_RDONLY | O_CLOEXEC);
        } else if (access(p.c_str(), F_OK) == 0) {
            fd = open(p.c_str(), O_WRONLY | O_CLOEXEC);
        } else {
            std::string up = dirname(p);
            struct stat st{};
            if (stat(up.c_str(), &st) != 0 || !S_ISDIR(st.st_mode)) {
                std::string hint = std::string(" (add ") + names[i] + "_mkdir: true to create it)";
                return std::string(names[i]) + " " + p + ": cannot open: parent directory does not exist" + hint;
            }
            if (access(up.c_str(), W_OK | X_OK) != 0) {
                return std::string(names[i]) + " " + p + ": cannot open: parent directory is not writable (" + std::strerror(errno) + ")";
            }
            continue;
        }
        if (fd < 0) {
            return std::string(names[i]) + " " + p + ": cannot open (" + std::strerror(errno) + ")";
        }
        close(fd);
    }
    return "cannot open a stream (one of stdin/stdout/stderr)";
}

// aos-inst 起不來的錯 → LaunchFailed（訊息開頭是 aos-inst 的名字，例「CommandMissing 找不到要跑的程式 x」）。
Error start_error(int rc, const LibInput& lib) {
    std::string name = aos_inst_strerror(rc);
    std::string prog = lib.argv[0];
    std::string why = "reported by aos-inst (" + prog + ")";
    if (rc == AOS_INST_ERR_CWD_MISSING) {
        why = "cwd " + lib.cwd + " is not a directory or cannot be entered";
    } else if (rc == AOS_INST_ERR_PATH_CONFLICT) {
        why = "stderr_merge is true and stderr is also set (pick one)";
    } else if (rc == AOS_INST_ERR_OPEN_FAILED) {
        why = open_failed_why(lib);
    } else if (rc == AOS_INST_ERR_COMMAND_MISSING) {
        why = "program not found: " + prog;
    } else if (rc == AOS_INST_ERR_COMMAND_BAD) {
        why = prog + " is not executable";
    } else if (rc == AOS_INST_ERR_LAUNCH_FAILED) {
        why = "cannot start " + prog;
    }
    return Error{code::LaunchFailed, name + " " + why};
}

}  // namespace

Result run_inst(const Json& doc, const std::string& base_dir, const std::vector<std::string>& args,
                const std::string& ref_base) {
    // 1～2. 單子
    std::string refs = ref_base;
    if (refs.empty()) {
        refs = base_dir;
    }
    Json resolved = aos::resolve(doc, refs);
    Inst inst = parse_inst(resolved, args);
    std::string cwd = base_dir;
    if (inst.cwd) {
        cwd = aos::join(base_dir, *inst.cwd);
    }
    inst.argv = argv0(inst.argv, cwd);   // 帶 / 又 exec 不了＝交給 PATH 上的 aos-exec（10-20 ideas D3）
    LibInput lib;
    build_lib_input(inst, base_dir, lib);

    // 3. 訊號：先擋住，再開 fd（都帶 CLOEXEC，不會漏給子程式）。子程式起來之後就不能半途丟下它，所以先開好
    SigMask mask;
    Fd sig_fd(open_signal_fd());
    Fd done_fd(eventfd(0, EFD_CLOEXEC));
    if (sig_fd.fd < 0 || done_fd.fd < 0) {
        throw Error{code::Internal, std::string("cannot set up signal forwarding: ") + std::strerror(errno)};
    }

    // 4. 起
    aos_inst_proc_t proc{};
    int rc = aos_inst_start(&lib.in, &proc);
    if (rc != AOS_INST_OK) {
        throw start_error(rc, lib);
    }
    pid_t pid = (pid_t)proc.pid;

    // 5. 工人等、主執行緒轉送訊號
    aos_inst_result_t out{};
    std::thread worker([&] {
        rc = aos_inst_wait(&proc, &out);   // 卡到子程式結束
        uint64_t one = 1;
        ssize_t n = write(done_fd.fd, &one, sizeof one);   // 敲一下，叫醒主執行緒
        (void)n;
    });
    int received = forward_signals_until_done(pid, inst.grace_ms, sig_fd.fd, done_fd.fd);
    worker.join();

    // 6. 結果
    if (rc != AOS_INST_OK) {
        throw Error{code::Internal, std::string(aos_inst_strerror(rc)) + " cannot get the result of child " + std::to_string(pid)};
    }
    Result r;
    r.code = out.code;
    r.signal = out.signal;
    r.timed_out = out.timed_out;
    r.pid = out.pid;
    r.ms = out.ms;
    r.received = received;
    return r;
}

}  // namespace aos::exec
