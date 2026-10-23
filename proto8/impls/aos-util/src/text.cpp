// text.cpp：【aos-util】UTF-8 字串的小工具（說明見 include/aos/text.hpp）。
// is_utf8 原在 aos-exec 的 dotenv.cpp；空白那幾個 10-22 為 .env 的值照 python-dotenv 認 Unicode 空白而寫，aos-fsm 的 state 也用。
#include "aos/text.hpp"

namespace aos {

// 嚴格的 UTF-8 檢查（同 Python 的 utf-8 解碼：不收過長編碼、代理區、超過 U+10FFFF）。
bool is_utf8(const std::string& s) {
    size_t i = 0;
    while (i < s.size()) {
        unsigned char c = (unsigned char)s[i];
        size_t n = 0;
        unsigned int cp = 0;
        if (c < 0x80) {
            i += 1;
            continue;
        } else if (c >= 0xC2 && c <= 0xDF) {
            n = 1;
            cp = c & 0x1F;
        } else if (c >= 0xE0 && c <= 0xEF) {
            n = 2;
            cp = c & 0x0F;
        } else if (c >= 0xF0 && c <= 0xF4) {
            n = 3;
            cp = c & 0x07;
        } else {
            return false;
        }
        for (size_t k = 1; k <= n; ++k) {
            if (i + k >= s.size()) {
                return false;
            }
            unsigned char d = (unsigned char)s[i + k];
            if ((d & 0xC0) != 0x80) {
                return false;
            }
            cp = (cp << 6) | (d & 0x3F);
        }
        if ((n == 2 && cp < 0x800) || (n == 3 && cp < 0x10000) || cp > 0x10FFFF || (cp >= 0xD800 && cp <= 0xDFFF)) {
            return false;
        }
        i += n + 1;
    }
    return true;
}

size_t space_at(const std::string& s, size_t i) {
    if (i >= s.size()) {
        return 0;
    }
    unsigned char c = (unsigned char)s[i];
    if ((c >= 0x09 && c <= 0x0D) || (c >= 0x1C && c <= 0x20)) {
        return 1;
    }
    if (c < 0x80) {
        return 0;
    }
    size_t n = 1;
    unsigned int cp = 0;
    if (c >= 0xC2 && c <= 0xDF) {
        n = 2;
        cp = c & 0x1F;
    } else if (c >= 0xE0 && c <= 0xEF) {
        n = 3;
        cp = c & 0x0F;
    } else {
        return 0;   // 4 位元組的字沒有空白
    }
    if (i + n > s.size()) {
        return 0;
    }
    for (size_t k = 1; k < n; ++k) {
        cp = (cp << 6) | ((unsigned char)s[i + k] & 0x3F);
    }
    bool sp = cp == 0x85 || cp == 0xA0 || cp == 0x1680 || (cp >= 0x2000 && cp <= 0x200A) || cp == 0x2028 ||
              cp == 0x2029 || cp == 0x202F || cp == 0x205F || cp == 0x3000;
    if (sp) {
        return n;
    }
    return 0;
}

// 去開頭的空白（Unicode，同 Python str.lstrip()）。
std::string lstrip(const std::string& s) {
    size_t i = 0;
    while (true) {
        size_t n = space_at(s, i);
        if (n == 0) {
            break;
        }
        i += n;
    }
    return s.substr(i);
}

// 去結尾的空白（Unicode，同 Python str.rstrip()）：由前往後走，記住最後一個不是空白的字的結尾。
std::string rstrip(const std::string& s) {
    size_t i = 0;
    size_t end = 0;
    while (i < s.size()) {
        size_t n = space_at(s, i);
        if (n > 0) {
            i += n;
            continue;
        }
        unsigned char c = (unsigned char)s[i];
        size_t len = 1;
        if (c >= 0xF0) {
            len = 4;
        } else if (c >= 0xE0) {
            len = 3;
        } else if (c >= 0xC0) {
            len = 2;
        }
        i += len;
        end = i;
    }
    return s.substr(0, end);
}

std::string strip(const std::string& s) {
    return rstrip(lstrip(s));
}

}  // namespace aos
