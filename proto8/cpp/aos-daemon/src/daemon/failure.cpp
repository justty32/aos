// failure.cpp：【daemon】從子項結束碼與 stderr 整理停止原因（說明見 daemon.hpp）。
#include "daemon/daemon.hpp"
#include "aos/util/files.hpp"

#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

#include <cerrno>

namespace aos::daemon {

using Clock = std::chrono::steady_clock;

namespace {

// 11-19（體檢 P1）：reason 只取最後一行（最多 300 位元組），原本卻把整份 stderr.txt 讀進記憶體，1 GB 的檔吃約 2 GB、記憶體受限時 daemon 自己倒。
// 改成只讀檔尾 ERR_TAIL：最後一行加上其後的空白行在 64 KB 內綽綽有餘，不管檔多大用量固定。代價：最後一行比 64 KB 還長時，取到的是那一行的後段。
constexpr size_t ERR_TAIL = 64 * 1024;

// 讀 path 最後 max_bytes 個位元組（檔較小就整份）；start 回傳讀到那段在檔中的起點。打不開、讀錯＝nullopt。
std::optional<std::string> read_tail(const std::string& path, size_t max_bytes, size_t& start) {
    int fd = open(path.c_str(), O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        return std::nullopt;
    }
    struct stat st {};
    if (fstat(fd, &st) != 0 || !S_ISREG(st.st_mode)) {
        close(fd);
        return std::nullopt;
    }
    size_t size = (size_t)st.st_size;
    start = size > max_bytes ? size - max_bytes : 0;
    std::string text(size - start, '\0');
    size_t got = 0;
    while (got < text.size()) {   // 檔在讀的時候還在長：只讀到 fstat 那一刻的長度
        ssize_t n = pread(fd, text.data() + got, text.size() - got, (off_t)(start + got));
        if (n < 0 && errno == EINTR) {
            continue;
        }
        if (n < 0) {
            close(fd);
            return std::nullopt;
        }
        if (n == 0) {   // 讀的時候被截短
            break;
        }
        got += (size_t)n;
    }
    close(fd);
    text.resize(got);
    return text;
}

}  // namespace

// 11-05：出錯結束留成 stopped 的原因（英文，使用者 11-05「全都用英文吧」）：起來（add／wake／start）後 REVIVE_MS 內退＝起不來，其他＝跑到一半掛了；
// 加結束碼（被訊號打掉多寫訊號）與小格 stderr 最後一行（最多 300 位元組）。
// 11-05 第二輪：只看這一支起來之後寫的（err_off 之後；stderr.txt 是附加的，原本會挖到前幾輩子的話）；控制字元（CR、ESC…）換成空白
// （ls 印到終端不會上色、蓋字）；切 300 時不切在 UTF-8 字的中間。
std::string Daemon::fail_reason(const Child& c) const {
    std::string code = aos::dumps(c.code);
    if (c.signal.is_number_integer()) {
        code += ", signal " + aos::dumps(c.signal);
    }
    bool quick = c.revived && Clock::now() - c.revived_at < std::chrono::milliseconds(REVIVE_MS);
    std::string why = quick ? "failed to start: exited within " + std::to_string(REVIVE_MS / 1000) + "s of wake/start (code " + code + ")"
                            : "failed while running: exited with code " + code;
    size_t start = 0;
    std::optional<std::string> text = read_tail(aos::join(c.stack, names_.err), ERR_TAIL, start);
    if (text) {
        // 被截短過（copytruncate；檔比 err_off 短）＝整份，從檔頭讀
        size_t size = start + text->size();
        size_t base = c.err_off > 0 && (size_t)c.err_off <= size ? (size_t)c.err_off : 0;
        // 11-19：err_off 在檔尾那段之前＝檔尾切掉了前面；那段的開頭不知是不是行首，當成切在某行中間
        bool cut = base < start;
        size_t off = cut ? 0 : base - start;
        // 11-10：起點不在檔頭、前一個位元組也不是換行＝可能切在某行中間（截短後又長回超過 err_off）：從下一個換行之後開始；
        // 後面沒有非空的內容（半截就是最後一行）＝退回那一行的行首，取整行（不帶半截；行首在檔尾那段之前就從那段開頭取）
        if (off > 0 ? (*text)[off - 1] != '\n' : cut) {
            size_t nl = text->find('\n', off);
            if (nl != std::string::npos && text->find_first_not_of(" \t\r\n", nl + 1) != std::string::npos) {
                off = nl + 1;
            } else if (off > 0) {
                size_t prev = text->rfind('\n', off - 1);
                off = prev == std::string::npos ? 0 : prev + 1;
            }
        }
        std::string t = text->substr(off);
        for (char& ch : t) {
            unsigned char u = (unsigned char)ch;
            if ((u < 0x20 && ch != '\n') || u == 0x7f) {
                ch = ' ';
            }
        }
        // 只取最後非空行，不認下層程式或錯誤字句（C-52）。
        std::string last, rest = t;
        while (!rest.empty()) {
            size_t nl = rest.rfind('\n');
            std::string line = rest.substr(nl == std::string::npos ? 0 : nl + 1);
            rest = nl == std::string::npos ? "" : rest.substr(0, nl);
            while (!line.empty() && line.back() == ' ') {
                line.pop_back();
            }
            if (line.empty()) {
                continue;
            }
            last = line;
            break;
        }
        if (last.size() > 300) {
            size_t cut = 300;
            while (cut > 0 && ((unsigned char)last[cut] & 0xC0) == 0x80) {
                cut -= 1;
            }
            last = last.substr(0, cut) + "...";
        }
        if (!last.empty()) {
            why += ": " + last;
        }
    }
    return why;
}


}  // namespace aos::daemon
