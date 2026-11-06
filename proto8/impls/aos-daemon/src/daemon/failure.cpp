// failure.cpp：【daemon】從子項結束碼與 stderr 整理停止原因（說明見 daemon.hpp）。
#include "daemon/daemon.hpp"
#include "aos/util/files.hpp"

namespace aos::daemon {

using Clock = std::chrono::steady_clock;

static const int REVIVE_MS = 3000;  // 11-05（衝突 3）：wake／start 起來這麼久內就退＝原因寫「起不來」（11-05 晚起出錯結束一律留 stopped，3 秒只分原因字樣）
// 子 loop 自己的包裝行「X: run N: … failed with exit code C」（aos-loop 身體退非 0 時印的）。11-05 第二輪：原本用 std::regex_match，
// libstdc++ 的 regex 是遞迴回溯，stderr 一行 30 KB 就把堆疊撐爆、整台 daemon SIGSEGV（139）；改手寫比對。
static bool is_wrap(const std::string& line) {
    size_t p = line.find(": run ");
    if (p == std::string::npos || p == 0 || line.find(':') != p) {
        return false;
    }
    size_t q = p + 6, d = q;
    while (d < line.size() && line[d] >= '0' && line[d] <= '9') {
        d += 1;
    }
    if (d == q || line.compare(d, 2, ": ") != 0) {
        return false;
    }
    static const std::string tail = " failed with exit code ";
    size_t t = line.rfind(tail);
    if (t == std::string::npos || t < d) {
        return false;
    }
    size_t n = t + tail.size();
    if (n < line.size() && line[n] == '-') {
        n += 1;
    }
    if (n >= line.size()) {
        return false;
    }
    for (; n < line.size(); n += 1) {
        if (line[n] < '0' || line[n] > '9') {
            return false;
        }
    }
    return true;
}

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
    int err = 0;
    std::optional<std::string> text = aos::read_file(aos::join(c.stack, names_.err), err);
    if (text) {
        // 被截短過（copytruncate）＝整份
        std::string t = c.err_off > 0 && (size_t)c.err_off <= text->size() ? text->substr((size_t)c.err_off) : *text;
        for (char& ch : t) {
            unsigned char u = (unsigned char)ch;
            if ((u < 0x20 && ch != '\n') || u == 0x7f) {
                ch = ' ';
            }
        }
        // 跳過子 loop 自己的包裝行，取它前面那行＝身體自己說的真正原因（只往前看這一支寫的）；都是包裝行才用它
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
            if (last.empty()) {
                last = line;
            }
            if (!is_wrap(line)) {
                last = line;
                break;
            }
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
