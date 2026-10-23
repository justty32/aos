// flags.cpp：【aos-util】命令列旗標 --key 值（規則見 include/aos/flags.hpp）。
#include "aos/flags.hpp"

namespace aos {

// 旗標的值：先當 JSON 解，解不了就當字串。
static Json flag_value(const std::string& s) {
    Json v = Json::parse(s, nullptr, false);   // false＝不丟例外，壞的回 discarded
    if (v.is_discarded()) {
        return Json(s);
    }
    return v;
}

static bool known_key(const std::vector<std::string>& keys, const std::string& key) {
    for (const std::string& k : keys) {
        if (k == key) {
            return true;
        }
    }
    return false;
}

Flags parse_flags(int argc, char** argv, const std::vector<std::string>& keys, const std::string& prog) {
    Flags out;
    int i = 1;
    while (i < argc) {
        std::string a = argv[i];
        if (a == "--") {
            out.rest = std::vector<std::string>(argv + i + 1, argv + argc);
            break;
        }
        if (!a.starts_with("--")) {
            throw Error{code::Usage, prog + " 不收位置參數（設定從 stdin 讀），多了 " + a};
        }
        std::string key = a.substr(2);
        if (!known_key(keys, key)) {
            throw Error{code::FlagUnknown, "不認得的旗標 " + a};
        }
        if (i + 1 >= argc) {
            throw Error{code::Usage, a + " 少了值"};
        }
        out.values[key] = flag_value(argv[i + 1]);
        i += 2;
    }
    return out;
}

}  // namespace aos
