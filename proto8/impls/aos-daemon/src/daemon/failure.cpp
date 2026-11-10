// failure.cpp：【daemon】從子項結束碼與 stderr 整理停止原因（說明見 daemon.hpp）。
#include "daemon/daemon.hpp"
#include "aos/util/files.hpp"

namespace aos::daemon {

using Clock = std::chrono::steady_clock;

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
        // 被截短過（copytruncate；檔比 err_off 短）＝整份，從檔頭讀
        size_t off = c.err_off > 0 && (size_t)c.err_off <= text->size() ? (size_t)c.err_off : 0;
        // 11-10：起點不在檔頭、前一個位元組也不是換行＝可能切在某行中間（截短後又長回超過 err_off）：從下一個換行之後開始；
        // 後面沒有非空的內容（半截就是最後一行）＝退回那一行的行首，取整行（不帶半截）
        if (off > 0 && (*text)[off - 1] != '\n') {
            size_t nl = text->find('\n', off);
            if (nl != std::string::npos && text->find_first_not_of(" \t\r\n", nl + 1) != std::string::npos) {
                off = nl + 1;
            } else {
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
