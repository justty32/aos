// json.cpp：讀 add 用的那份 json（{"exec": [argv...], "env": {...}}）的最小解析器；只收字串，其餘的值認得、跳過。
#include "daemon.hpp"

#include <stdexcept>

namespace aosd {

namespace {

struct Parser {
    const std::string& s;
    size_t i = 0;

    [[noreturn]] void bad(const std::string& why) { throw std::runtime_error(why + " at byte " + std::to_string(i)); }
    void ws() {
        while (i < s.size() && (s[i] == ' ' || s[i] == '\t' || s[i] == '\n' || s[i] == '\r')) ++i;
    }
    bool eat(char c) {
        ws();
        if (i < s.size() && s[i] == c) {
            ++i;
            return true;
        }
        return false;
    }
    void need(char c) {
        if (!eat(c)) bad(std::string("expected '") + c + "'");
    }
    static void utf8(std::string& out, unsigned cp) {
        if (cp < 0x80) {
            out += static_cast<char>(cp);
        } else if (cp < 0x800) {
            out += static_cast<char>(0xC0 | cp >> 6);
            out += static_cast<char>(0x80 | (cp & 0x3F));
        } else if (cp < 0x10000) {
            out += static_cast<char>(0xE0 | cp >> 12);
            out += static_cast<char>(0x80 | (cp >> 6 & 0x3F));
            out += static_cast<char>(0x80 | (cp & 0x3F));
        } else {
            out += static_cast<char>(0xF0 | cp >> 18);
            out += static_cast<char>(0x80 | (cp >> 12 & 0x3F));
            out += static_cast<char>(0x80 | (cp >> 6 & 0x3F));
            out += static_cast<char>(0x80 | (cp & 0x3F));
        }
    }
    unsigned hex4() {
        if (i + 4 > s.size()) bad("short \\u escape");
        unsigned v = static_cast<unsigned>(std::stoul(s.substr(i, 4), nullptr, 16));
        i += 4;
        return v;
    }
    std::string str() {
        need('"');
        std::string out;
        while (i < s.size() && s[i] != '"') {
            char c = s[i++];
            if (c != '\\') {
                out += c;
                continue;
            }
            if (i >= s.size()) break;
            char e = s[i++];
            switch (e) {
            case 'n': out += '\n'; break;
            case 't': out += '\t'; break;
            case 'r': out += '\r'; break;
            case 'b': out += '\b'; break;
            case 'f': out += '\f'; break;
            case 'u': {
                unsigned cp = hex4();
                if (cp >= 0xD800 && cp < 0xDC00 && i + 1 < s.size() && s[i] == '\\' && s[i + 1] == 'u') {
                    i += 2;
                    cp = 0x10000 + ((cp - 0xD800) << 10) + (hex4() - 0xDC00);
                }
                utf8(out, cp);
                break;
            }
            default: out += e;   // \" \\ \/
            }
        }
        if (i >= s.size()) bad("unterminated string");
        ++i;
        return out;
    }
    // 不關心的值：認得形狀、整個跳過
    void skip() {
        ws();
        if (i >= s.size()) bad("unexpected end");
        char c = s[i];
        if (c == '"') {
            str();
        } else if (c == '{') {
            ++i;
            if (eat('}')) return;
            do {
                ws();
                str();
                need(':');
                skip();
            } while (eat(','));
            need('}');
        } else if (c == '[') {
            ++i;
            if (eat(']')) return;
            do skip();
            while (eat(','));
            need(']');
        } else {
            size_t b = i;
            while (i < s.size() && std::string(",}] \t\r\n").find(s[i]) == std::string::npos) ++i;
            if (i == b) bad("unexpected character");
        }
    }
};

}  // namespace

std::string parse_spec(const std::string& text, std::vector<std::string>& argv, std::vector<std::string>& env) {
    Parser p{text};
    try {
        p.need('{');
        if (!p.eat('}')) {
            do {
                p.ws();
                std::string k = p.str();
                p.need(':');
                if (k == "exec") {
                    p.need('[');
                    if (!p.eat(']')) {
                        do {
                            p.ws();
                            argv.push_back(p.str());
                        } while (p.eat(','));
                        p.need(']');
                    }
                } else if (k == "env") {
                    p.need('{');
                    if (!p.eat('}')) {
                        do {
                            p.ws();
                            std::string ek = p.str();
                            p.need(':');
                            p.ws();
                            std::string ev = p.str();
                            if (ek.empty() || ek.find('=') != std::string::npos) p.bad("bad env name");
                            env.push_back(ek + "=" + ev);
                        } while (p.eat(','));
                        p.need('}');
                    }
                } else {
                    p.skip();
                }
            } while (p.eat(','));
            p.need('}');
        }
        p.ws();
        if (p.i != text.size()) p.bad("trailing data");
    } catch (const std::exception& e) {
        return std::string("JsonBad ") + e.what();
    }
    if (argv.empty() || argv[0].empty()) return "JsonBad \"exec\" must be a non-empty array of strings";
    return "";
}

}  // namespace aosd
