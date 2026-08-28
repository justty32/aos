#define _POSIX_C_SOURCE 200809L

// CLI 回合層：`.aos/turn`（這台機器的 PC）的遞增（SPEC §B-3）。
// 從 run_exec.cpp 拆出來——那個檔已經過了 300 行門檻，而 turn 是一件獨立的事：
// 它只在 release_instruction 成功之後被呼叫一次，跟彙整／取件／執行都不耦合。
// 低階檔案存取的小 helper 各檔自己留一份（與 run_init.cpp／run_deliver.cpp 同款），
// 不跨檔共用——CLI 層沒有共用的檔案存取層，硬做一個反而多一層相依。

#include "run_internal.hpp"

#include <cerrno>
#include <charconv>
#include <climits>
#include <cstddef>
#include <cstdint>
#include <string>

#include <fcntl.h>
#include <signal.h>
#include <unistd.h>

namespace aos::detail {
namespace {

constexpr const char *kAosDir = ".aos";
constexpr const char *kTurnPath = ".aos/turn";
constexpr const char *kTurnTempPath = ".aos/turn.temp";

int open_retry(const char *path, int flags, mode_t mode = 0) {
    int fd;
    do {
        fd = open(path, flags, mode);
    } while (fd < 0 && errno == EINTR);
    return fd;
}

bool read_input(int fd, std::string &buffer, int &error) {
    char chunk[64 * 1024];
    for (;;) {
        ssize_t count;
        do {
            count = read(fd, chunk, sizeof(chunk));
        } while (count < 0 && errno == EINTR);
        if (count < 0) {
            error = errno;
            return false;
        }
        if (count == 0) return true;
        buffer.append(chunk, static_cast<std::size_t>(count));
    }
}

bool close_checked(int fd, int &error) {
    if (close(fd) == 0) return true;
    error = errno;
    return false;
}

// fsync 本身可能被訊號中斷（不像 close，重打 fsync 是安全的：fd 沒被回收）。
bool fsync_retry(int fd) {
    int rc;
    do {
        rc = fsync(fd);
    } while (rc != 0 && errno == EINTR);
    return rc == 0;
}

bool write_fully(int fd, const char *data, std::size_t size, int &error) {
    while (size != 0) {
        ssize_t count;
        do {
            count = write(fd, data, size);
        } while (count < 0 && errno == EINTR);
        if (count <= 0) {
            error = count < 0 ? errno : EIO;
            return false;
        }
        data += count;
        size -= static_cast<std::size_t>(count);
    }
    return true;
}

bool fsync_dir(const char *path, int &error) {
    const int fd = open_retry(path, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (fd < 0) {
        error = errno;
        return false;
    }
    bool ok = true;
    if (!fsync_retry(fd)) {
        error = errno;
        ok = false;
    }
    if (!close_checked(fd, error)) ok = false;
    return ok;
}

// 內容一律是 "<十進位整數>\n"；不是這個形狀一律當成解析失敗，不猜、不當成 0
// （§B-3 只保證「讀不到」視為 0，不保證「讀到壞內容」也視為 0）。
bool parse_turn(const std::string &content, std::uint64_t &value) {
    if (content.empty() || content.back() != '\n') return false;
    const std::size_t digits = content.size() - 1;
    if (digits == 0) return false;
    for (std::size_t index = 0; index < digits; ++index) {
        if (content[index] < '0' || content[index] > '9') return false;
    }
    const auto result =
        std::from_chars(content.data(), content.data() + digits, value);
    return result.ec == std::errc() && result.ptr == content.data() + digits;
}

// `ulimit -f` 觸頂時 `write` 會先送 SIGXFSZ，而它的預設處置是砍死行程（實測
// rc=153）——錯誤路徑一行都跑不到，`turn.temp` 的殘骸就這樣留下。範圍內把它忽略
// 掉，`write` 就會誠實回 EFBIG，走既有錯誤路徑並清掉 temp。
//
// 為什麼是 scoped 而不是在行程層級設一次 SIG_IGN：**被忽略的訊號處置會跨 `execve`
// 繼承**給子行程，等於偷偷改掉使用者程式的行為，違反 exec 層「凍結的矽」的精神。
// `advance_turn` 只在 `execute_batch` 把整批（含 parallel 的 thread）全部收屍之後
// 才呼叫，此時沒有任何 fork 在飛，範圍內忽略是安全的。
class XfszIgnored {
public:
    XfszIgnored() {
        struct sigaction ignore {};
        ignore.sa_handler = SIG_IGN;
        sigemptyset(&ignore.sa_mask);
        armed_ = sigaction(SIGXFSZ, &ignore, &saved_) == 0;
    }
    ~XfszIgnored() {
        if (armed_) sigaction(SIGXFSZ, &saved_, nullptr);
    }
    XfszIgnored(const XfszIgnored &) = delete;
    XfszIgnored &operator=(const XfszIgnored &) = delete;

private:
    struct sigaction saved_ {};
    bool armed_ = false;
};

// `.aos/turn`：讀不到（舊世界）視為 0（§B-3／裁-5，MUST NOT 拒絕、MUST NOT 動
// 版面版本），否則遞增後 temp→fsync→rename→fsync 目錄，與 handoff 的耐久性順序
// 同款寫法。只在 release_instruction 成功後呼叫（見 run_exec_once）。
bool advance_turn_body(int &error) {
    const XfszIgnored xfsz;
    std::uint64_t value = 0;
    const int fd = open_retry(kTurnPath, O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        if (errno != ENOENT) {
            error = errno;
            return false;
        }
    } else {
        std::string content;
        bool ok = read_input(fd, content, error);
        if (!close_checked(fd, error)) ok = false;
        if (!ok) return false;
        if (!parse_turn(content, value)) {
            error = EINVAL;
            return false;
        }
    }
    // `turn` 的其他每一種壞內容都是大聲拒絕，溢位也一樣：靜默回繞成 0 會讓
    // §E-4 那個「可攜的回合座標」無聲倒退，沒人知道。
    if (value == UINT64_MAX) {
        error = ERANGE;
        return false;
    }
    ++value;
    const std::string next = std::to_string(value) + "\n";

    const int temp_fd = open_retry(
        kTurnTempPath, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0666);
    if (temp_fd < 0) {
        error = errno;
        return false;
    }
    bool ok = write_fully(temp_fd, next.data(), next.size(), error);
    if (ok && !fsync_retry(temp_fd)) {
        error = errno;
        ok = false;
    }
    if (!close_checked(temp_fd, error)) ok = false;
    if (!ok) {
        // 殘骸不留給 M3 的 `aos recover`：這份 `turn.temp` 是本函式自己建的，
        // 失敗就自己清掉。unlink 再失敗也無話可說，回報原本那個 error。
        unlink(kTurnTempPath);
        return false;
    }

    if (rename(kTurnTempPath, kTurnPath) != 0) {
        error = errno;
        unlink(kTurnTempPath);
        return false;
    }
    // rename 之後 `turn.temp` 已經不存在，這一步（目錄項落盤）失敗沒有殘骸可清。
    return fsync_dir(kAosDir, error);
}
}  // namespace

bool advance_turn(int &error) { return advance_turn_body(error); }

}  // namespace aos::detail
