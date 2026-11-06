// proc.cpp：【aos-util】整群送訊號、/proc 身分資訊、UTC 時間與唯一名稱（說明見 include/aos/util/proc.hpp）。
#include "aos/util/error.hpp"
#include "aos/util/files.hpp"
#include "aos/util/proc.hpp"

#include <cerrno>
#include <chrono>
#include <cstdio>
#include <ctime>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <sstream>
#include <vector>

#include <signal.h>
#include <unistd.h>

namespace aos {

void signal_group(pid_t pgid, int sig) {
    if (pgid > 0) {
        killpg(pgid, sig);   // 群組不在（ESRCH）、沒權限（EPERM）都不管
    }
}

std::optional<long long> proc_started_at_ticks(pid_t pid) {
    std::string path = "/proc/" + std::to_string(pid) + "/stat";
    if (pid == 0) {
        path = "/proc/self/stat";
    }
    // 用 read(2) 讀、出錯就 nullopt：行程在 open 與 read 之間結束時 read 回 ESRCH，ifstream＋istreambuf_iterator 會把它丟成
    // ios_base::failure（basic_filebuf::underflow），daemon 巡表時看子 loop 死活就會整支以 Internal 退 1（10-23 查 ctest 偶發失敗）。
    int err = 0;
    std::optional<std::string> got = aos::read_file(path, err);
    if (!got) {
        return std::nullopt;
    }
    const std::string& text = *got;
    // 第 2 欄是程式名，用括號包著、裡面可能有空白，所以從最後一個 ')' 之後開始數：之後第 1 個是第 3 欄……第 20 個是第 22 欄
    size_t close_paren = text.rfind(')');
    if (close_paren == std::string::npos) {
        return std::nullopt;
    }
    std::istringstream rest(text.substr(close_paren + 1));
    std::string field;
    for (int i = 0; i < 20; ++i) {
        if (!(rest >> field)) {
            return std::nullopt;
        }
    }
    try {
        return std::stoll(field);
    } catch (const std::exception&) {
        return std::nullopt;
    }
}

std::string utc_now_ms() {
    return utc_ms_at(utc_now_ns());
}

long long utc_now_ns() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
               std::chrono::system_clock::now().time_since_epoch()).count();
}

std::string utc_ms_at(long long ns) {
    time_t sec = (time_t)(ns / 1000000000LL);
    long ms = (long)((ns / 1000000LL) % 1000LL);
    std::tm tm{};
    gmtime_r(&sec, &tm);
    char day[32];
    std::strftime(day, sizeof day, "%Y-%m-%dT%H:%M:%S", &tm);
    char buf[80];
    std::snprintf(buf, sizeof buf, "%s.%03ld+00:00", day, ms);
    return buf;
}

std::string identity() {
    std::string cwd;
    auto get_cwd = [&cwd]() -> const std::string& {
        if (cwd.empty()) {
            std::vector<char> buf(4096);
            while (getcwd(buf.data(), buf.size()) == nullptr) {
                if (errno != ERANGE) {
                    throw Error{code::Internal, std::string("cannot get cwd: ") + std::strerror(errno)};
                }
                buf.resize(buf.size() * 2);
            }
            cwd = buf.data();
        }
        return cwd;
    };
    for (const char* key : {"AOS_WS", "AOS_STACK", "AOS_CF"}) {
        const char* v = std::getenv(key);
        if (v != nullptr && v[0] != '\0') {
            return abspath(v[0] == '/' ? std::string(v) : get_cwd() + "/" + v);
        }
    }
    return abspath(get_cwd());
}

std::string unique_id() {
    return unique_id(utc_now_ns());
}

std::string unique_id(long long ns) {
    std::optional<long long> ticks = proc_started_at_ticks(0);
    char buf[96];
    std::snprintf(buf, sizeof buf, "%020lld.%ld.%lld", ns, (long)getpid(), ticks ? *ticks : -1LL);
    return buf;
}

std::optional<std::string> boot_id() {
    std::ifstream f("/proc/sys/kernel/random/boot_id");
    std::string id;
    if (!(f >> id)) {
        return std::nullopt;
    }
    return id;
}

}  // namespace aos
