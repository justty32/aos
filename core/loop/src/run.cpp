#define _POSIX_C_SOURCE 200809L

#include <aos/loop.hpp>

#include "fs.hpp"

#include <cerrno>
#include <charconv>
#include <csignal>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <string>
#include <system_error>

#include <fcntl.h>
#include <signal.h>
#include <sys/file.h>
#include <time.h>
#include <unistd.h>

namespace {

volatile std::sig_atomic_t interrupted_signal = 0;

bool parse_number(const char *text, std::uint64_t &value) {
    if (text == nullptr || *text == '\0') return false;
    const char *end = text + std::strlen(text);
    const auto result = std::from_chars(text, end, value);
    return result.ec == std::errc{} && result.ptr == end;
}

/* .aos/run.pid：無限回合的 loop 才寫，退出時刪。內容只有一個 pid，
 * 讓 `aos stop`（以及之後的 home daemon）知道要對誰送訊號。
 * 「同一個世界只能有一條 loop」是由 .aos/run.lock 的 flock 保證的，不是這個檔。 */
class RunPidFile {
  public:
    bool write(const std::string &path, const char *program) {
        const std::string temporary = path + ".tmp";
        {
            std::ofstream output(temporary, std::ios::binary | std::ios::trunc);
            if (!output) {
                std::fprintf(stderr, "%s: cannot write %s\n", program,
                             temporary.c_str());
                return false;
            }
            output << static_cast<long long>(::getpid()) << '\n';
        }
        std::error_code code;
        std::filesystem::rename(temporary, path, code);
        if (code) {
            std::filesystem::remove(temporary, code);
            std::fprintf(stderr, "%s: cannot publish %s\n", program, path.c_str());
            return false;
        }
        path_ = path;
        return true;
    }
    ~RunPidFile() {
        if (path_.empty()) return;
        std::error_code code;
        std::filesystem::remove(path_, code);
    }

  private:
    std::string path_;
};

void usage(FILE *stream, const char *program) {
    std::fprintf(stream,
                 "usage: %s [folder] [--step N] [--interval MS] [--daemon]\n"
                 "\n"
                 "  [folder]       world folder to advance; default: search up from cwd\n"
                 "  --step N       advance N turns; 0 means run until interrupted\n"
                 "  --interval MS  max ms to wait between turns when nothing new\n"
                 "                 arrives; default 100, or 1000 with --daemon. New\n"
                 "                 inbox or say messages start the next turn at once\n"
                 "  --daemon       run detached in the background (implies --step 0);\n"
                 "                 output goes to .aos/run.log; stop it with aos stop\n"
                 "  -h, --help     show this full usage\n",
                 program);
}

bool has_help(int argc, char *argv[]) {
    if (argv == nullptr) return false;
    for (int index = 1; index < argc; ++index) {
        if (argv[index] != nullptr &&
            (std::strcmp(argv[index], "--help") == 0 ||
             std::strcmp(argv[index], "-h") == 0)) {
            return true;
        }
    }
    return false;
}

void wait_interval(std::uint64_t milliseconds) {
    timespec delay{};
    delay.tv_sec = static_cast<time_t>(milliseconds / 1000);
    delay.tv_nsec = static_cast<long>((milliseconds % 1000) * 1000000);
    ::nanosleep(&delay, nullptr);
}

void handle_interrupt(int signal_number) {
    interrupted_signal = signal_number;
    /* 正在等新投遞的話，讓它立刻回來，不要等滿 interval。 */
    aos::loop::detail::stop_requested = 1;
    aos::exec::interrupt_running(SIGTERM);
}

class SignalHandlers {
  public:
    bool install(std::string &error) {
        struct sigaction action {};
        action.sa_handler = handle_interrupt;
        sigemptyset(&action.sa_mask);
        sigaddset(&action.sa_mask, SIGINT);
        sigaddset(&action.sa_mask, SIGTERM);
        action.sa_flags = 0;
        if (::sigaction(SIGINT, &action, &old_int_) != 0) {
            error = std::string("cannot install SIGINT handler: ") +
                    std::strerror(errno);
            return false;
        }
        int_installed_ = true;
        if (::sigaction(SIGTERM, &action, &old_term_) != 0) {
            error = std::string("cannot install SIGTERM handler: ") +
                    std::strerror(errno);
            ::sigaction(SIGINT, &old_int_, nullptr);
            int_installed_ = false;
            return false;
        }
        term_installed_ = true;
        return true;
    }

    ~SignalHandlers() {
        if (term_installed_) ::sigaction(SIGTERM, &old_term_, nullptr);
        if (int_installed_) ::sigaction(SIGINT, &old_int_, nullptr);
    }

  private:
    struct sigaction old_int_ {};
    struct sigaction old_term_ {};
    bool int_installed_ = false;
    bool term_installed_ = false;
};

class RunLock {
  public:
    ~RunLock() {
        if (fd_ >= 0) ::close(fd_);
    }

    bool acquire(const std::string &path, const char *program) {
        fd_ = ::open(path.c_str(), O_CREAT | O_RDWR | O_CLOEXEC, 0644);
        if (fd_ < 0) {
            std::fprintf(stderr, "%s: cannot open lock %s: %s\n", program,
                         path.c_str(), std::strerror(errno));
            return false;
        }
        if (::flock(fd_, LOCK_EX | LOCK_NB) == 0) return true;

        const int lock_error = errno;
        if (lock_error == EWOULDBLOCK || lock_error == EAGAIN) {
            std::fprintf(
                stderr,
                "%s: another aos run is already advancing this world (lock: %s); only one loop per world at a time\n",
                program, path.c_str());
        } else {
            std::fprintf(stderr, "%s: cannot acquire lock %s: %s\n", program,
                         path.c_str(), std::strerror(lock_error));
        }
        return false;
    }

  private:
    int fd_ = -1;
};

void print_failures(const char *program,
                    const aos::loop::TurnSummary &summary) {
    for (const auto &failure : summary.failures) {
        if (failure.signal != 0) {
            std::fprintf(stderr, "%s: turn %llu: %s killed by signal %d\n",
                         program,
                         static_cast<unsigned long long>(summary.turn),
                         failure.id.c_str(), failure.signal);
        } else if (failure.exit == 127) {
            std::fprintf(
                stderr,
                "%s: turn %llu: %s failed: command %s not found (exit 127); it is not on PATH\n",
                program,
                static_cast<unsigned long long>(summary.turn),
                failure.id.c_str(), failure.argv0.c_str());
        } else if (failure.stderr_line.empty()) {
            std::fprintf(stderr, "%s: turn %llu: %s exited with %d\n",
                         program,
                         static_cast<unsigned long long>(summary.turn),
                         failure.id.c_str(), failure.exit);
        } else {
            std::fprintf(stderr,
                         "%s: turn %llu: %s exited with %d; %s\n",
                         program,
                         static_cast<unsigned long long>(summary.turn),
                         failure.id.c_str(), failure.exit,
                         failure.stderr_line.c_str());
        }
    }
}

int finish_interrupted(const char *program, const aos::loop::Layout &layout,
                       std::uint64_t turn) {
    aos::wire::State state;
    state.turn = turn;
    state.phase = "interrupted";
    state.agents = aos::loop::mirror_agents(layout);
    std::string error;
    if (!aos::loop::write_state(layout, state, error)) {
        std::fprintf(stderr, "%s: cannot record interrupted state: %s\n", program,
                     error.c_str());
    }
    std::fprintf(stderr,
                 "%s: interrupted; terminated all commands of turn %llu\n",
                 program, static_cast<unsigned long long>(turn));
    return 130;
}

}  // namespace

extern "C" int aos_run_cli_main(int argc, char *argv[]) {
    const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                              ? argv[0]
                              : "aos run";
    if (has_help(argc, argv)) {
        usage(stdout, program);
        return 0;
    }
    if (argv == nullptr) {
        usage(stderr, program);
        return 2;
    }

    std::string folder = aos::loop::current_folder();
    bool explicit_folder = false;
    int option_start = 1;
    if (argc > 1 && argv[1] != nullptr &&
        std::strncmp(argv[1], "--", 2) != 0) {
        folder = argv[1];
        explicit_folder = true;
        option_start = 2;
    }

    std::uint64_t steps = 1;
    std::uint64_t interval = 100;
    bool saw_step = false;
    bool saw_interval = false;
    bool daemon = false;
    for (int index = option_start; index < argc; index += 2) {
        if (argv[index] != nullptr &&
            std::strcmp(argv[index], "--daemon") == 0) {
            daemon = true;
            index -= 1;  /* --daemon 不吃值 */
            continue;
        }
        if (index + 1 >= argc || argv[index] == nullptr ||
            argv[index + 1] == nullptr) {
            usage(stderr, program);
            return 2;
        }
        if (std::strcmp(argv[index], "--step") == 0) {
            std::uint64_t value = 0;
            if (!parse_number(argv[index + 1], value)) {
                usage(stderr, program);
                return 2;
            }
            /* 重複的旗標不是靜默採用最後一個：講出來，並以**第一個**為準
             * ——歧義的參數要有一個可預期的答案，而不是看誰寫在後面。 */
            if (saw_step) {
                std::fprintf(stderr,
                             "%s: --step given more than once; keeping the first (%llu), ignoring %s\n",
                             program,
                             static_cast<unsigned long long>(steps),
                             argv[index + 1]);
            } else {
                steps = value;
                saw_step = true;
            }
        } else if (std::strcmp(argv[index], "--interval") == 0) {
            std::uint64_t value = 0;
            if (!parse_number(argv[index + 1], value)) {
                usage(stderr, program);
                return 2;
            }
            if (saw_interval) {
                std::fprintf(stderr,
                             "%s: --interval given more than once; keeping the first (%llu), ignoring %s\n",
                             program,
                             static_cast<unsigned long long>(interval),
                             argv[index + 1]);
            } else {
                interval = value;
                saw_interval = true;
            }
        } else {
            usage(stderr, program);
            return 2;
        }
    }

    if (daemon) {
        if (saw_step && steps != 0) {
            std::fprintf(stderr, "%s: --daemon can only be used with --step 0\n",
                         program);
            return 2;
        }
        steps = 0;
        if (!saw_interval) interval = 1000;
    }

    if (explicit_folder) {
        std::error_code code;
        const auto absolute = std::filesystem::absolute(folder, code)
                                  .lexically_normal();
        if (!code) folder = absolute.string();
        code.clear();
        const bool exists = std::filesystem::exists(folder, code);
        if (code) {
            std::fprintf(stderr, "%s: cannot check %s: %s\n", program,
                         folder.c_str(), code.message().c_str());
            return 1;
        }
        if (!exists) {
            std::fprintf(stderr, "%s: %s does not exist\n", program,
                         folder.c_str());
            return 1;
        }
        const bool is_directory = std::filesystem::is_directory(folder, code);
        if (code) {
            std::fprintf(stderr, "%s: cannot check %s: %s\n", program,
                         folder.c_str(), code.message().c_str());
            return 1;
        }
        if (!is_directory) {
            std::fprintf(stderr, "%s: %s is not a folder\n", program,
                         folder.c_str());
            return 1;
        }
    }

    const aos::loop::Layout layout = aos::loop::layout_of(folder);
    std::string error;
    if (!aos::loop::ensure_layout(layout, error)) {
        std::fprintf(stderr, "%s: %s\n", program, error.c_str());
        return 1;
    }

    /* 先脫離終端，鎖與 pid 都要記在真正跑迴圈的那個行程上。 */
    int notify_fd = -1;
    if (daemon) {
        const auto process =
            aos::loop::detail::daemonize(layout.aos + "/run.log", error);
        if (process.pid < 0) {
            std::fprintf(stderr, "%s: %s\n", program, error.c_str());
            return 1;
        }
        if (!process.child) {
            if (!aos::loop::detail::await_daemon(process, error)) {
                std::fprintf(stderr, "%s: %s\n", program, error.c_str());
                return 1;
            }
            std::printf("aos run: background loop started (pid %lld, log at "
                        ".aos/run.log; stop it with aos stop)\n",
                        static_cast<long long>(process.pid));
            return 0;
        }
        notify_fd = process.notify_fd;
    }

    RunLock lock;
    const std::string lock_path = layout.aos + "/run.lock";
    if (!lock.acquire(lock_path, program)) {
        aos::loop::detail::notify_daemon(notify_fd, false);
        return 1;
    }

    /* 無限回合才留 pid 檔：有限回合跑完就走，沒有人需要停它。 */
    RunPidFile pid_file;
    if (steps == 0 && !pid_file.write(layout.aos + "/run.pid", program)) {
        aos::loop::detail::notify_daemon(notify_fd, false);
        return 1;
    }
    aos::loop::detail::notify_daemon(notify_fd, true);

    interrupted_signal = 0;
    aos::loop::detail::stop_requested = 0;
    // 先解析 shared-library 符號，避免第一次呼叫落在 signal handler 裡。
    aos::exec::interrupt_running(0);
    SignalHandlers handlers;
    if (!handlers.install(error)) {
        std::fprintf(stderr, "%s: %s\n", program, error.c_str());
        return 1;
    }

    bool saw_failure = false;
    std::uint64_t last_turn = aos::loop::read_turn(layout);
    for (std::uint64_t completed = 0; steps == 0 || completed < steps;
         ++completed) {
        if (interrupted_signal != 0) {
            return finish_interrupted(program, layout, last_turn);
        }

        aos::loop::TurnSummary summary;
        if (!aos::loop::run_turn(layout, summary, error)) {
            if (interrupted_signal != 0) {
                const std::uint64_t turn = summary.turn == 0
                                               ? last_turn
                                               : summary.turn;
                return finish_interrupted(program, layout, turn);
            }
            std::fprintf(stderr, "%s: %s\n", program, error.c_str());
            return 1;
        }
        last_turn = summary.turn;
        if (interrupted_signal != 0) {
            return finish_interrupted(program, layout, summary.turn);
        }

        if (summary.count == 0) {
            std::printf("turn %llu: idle\n",
                        static_cast<unsigned long long>(summary.turn));
        } else if (summary.every_count > 0) {
            std::printf("turn %llu: %zu insts (%zu every), %llu ms\n",
                        static_cast<unsigned long long>(summary.turn),
                        summary.count, summary.every_count,
                        static_cast<unsigned long long>(summary.elapsed_ms));
        } else {
            std::printf("turn %llu: %zu insts, %llu ms\n",
                        static_cast<unsigned long long>(summary.turn),
                        summary.count,
                        static_cast<unsigned long long>(summary.elapsed_ms));
        }
        print_failures(program, summary);
        saw_failure = saw_failure || !summary.failures.empty();
        std::fflush(stdout);
        if (steps == 0 || completed + 1 < steps) {
            /* 空回合（只有 every 的常駐 step、inbox 沒東西）不必睡滿：
             * 盯著 inbox 與每個 agent 的 say 資料夾，一有新投遞就立刻開下一回合。 */
            if (summary.count == summary.every_count) {
                aos::loop::wait_for_delivery(layout, interval);
            } else {
                wait_interval(interval);
            }
            if (interrupted_signal != 0) {
                return finish_interrupted(program, layout, summary.turn);
            }
        }
    }
    return saw_failure ? 1 : 0;
}
