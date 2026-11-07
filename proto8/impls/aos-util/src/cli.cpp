// cli.cpp：【aos-util】命令列旗標（含各支自定短名）與設定檔讀取（規則見 include/aos/util/cli.hpp）。
// 對應 proto8/py/aos_flags.py 的 parse、load_cfg。
#include "aos/util/cli.hpp"

#include "aos/util/error.hpp"
#include "aos/util/files.hpp"

#include <cerrno>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <stdexcept>

namespace aos {

// 常用短名預設；各呼叫端可另給自己的短名表，-h 隨 help 內建。
static const std::map<std::string, std::string> kShort = {
    {"-h", "--help"}, {"-j", "--json"}, {"-t", "--target"},
    {"-d", "--daemon"}, {"-n", "--name"}, {"-w", "--ws"},
    {"-s", "--stack"}, {"-f", "--follow"}, {"-y", "--yes"},
};

Cli parse_cli(const std::vector<std::string>& argv, const std::map<std::string, std::string>& flags,
              const std::map<std::string, std::string>& switches, const std::string& help,
              const std::vector<std::string>& short_flags,
              const std::map<std::string, std::string>& custom_short) {
    std::map<std::string, std::string> aliases;
    for (const std::string& short_flag : short_flags) {
        auto it = kShort.find(short_flag);
        if (it == kShort.end()) {
            throw std::invalid_argument("short flag " + short_flag + " is not in kShort");
        }
        if (short_flag != "-h" && !flags.count(it->second) && !switches.count(it->second)) {
            throw std::invalid_argument("short flag " + short_flag + " needs " + it->second);
        }
        aliases[short_flag] = it->second;
    }
    for (const auto& [name, long_name] : custom_short) {
        if (name.size() != 2 || name[0] != '-' || name[1] == '-') {
            throw std::invalid_argument("invalid short flag " + name);
        }
        if (long_name != "--help" && !flags.count(long_name) && !switches.count(long_name)) {
            throw std::invalid_argument("short flag " + name + " needs " + long_name);
        }
        aliases[name] = long_name;
    }
    if (!help.empty()) {
        aliases["-h"] = kShort.at("-h");
    }
    Cli out;
    size_t i = 0;
    while (i < argv.size()) {
        const std::string& a = argv[i];
        if (a == "--") {
            i += 1;
            break;
        }
        if (!a.starts_with("-") || a == "-") {
            break;
        }
        size_t eq = std::string::npos;
        if (a.starts_with("--")) {
            eq = a.find('=');
        }
        std::string name = a.substr(0, eq);
        std::string long_name = name;
        auto alias = aliases.find(name);
        if (alias != aliases.end()) {
            long_name = alias->second;
        }
        auto sw = switches.find(long_name);
        if (sw != switches.end()) {
            if (eq != std::string::npos) {
                throw Error{code::ArgumentsBad, name + " takes no value"};
            }
            out.opts[sw->second] = "1";
            i += 1;
            continue;
        }
        auto it = flags.find(long_name);
        if (long_name == "--help" && it == flags.end() && !help.empty()) {
            if (eq != std::string::npos) {
                throw Error{code::ArgumentsBad, name + " takes no value"};
            }
            std::fputs(help.c_str(), stdout);
            if (!help.ends_with("\n")) {
                std::fputc('\n', stdout);
            }
            std::fflush(stdout);
            std::exit(0);
        }
        if (it == flags.end()) {
            throw Error{code::FlagUnknown, "unknown flag " + name};
        }
        std::string val;
        if (eq != std::string::npos) {
            val = a.substr(eq + 1);
        } else {
            i += 1;
            if (i == argv.size()) {
                throw Error{code::ArgumentsBad, name + " needs a value"};
            }
            val = argv[i];
        }
        out.opts[it->second] = val;
        i += 1;
    }
    out.rest.assign(argv.begin() + (long)i, argv.end());
    return out;
}

Error usage_error(const std::string& code, const std::string& reason, const std::string& usage) {
    return Error{code, reason + " (usage: " + usage + ")"};
}

static Json read_json_at(const std::string& path, const std::string& pointer) {
    int err = 0;
    std::optional<std::string> text = read_file(path, err);
    if (!text) {
        // 11-05 第二輪：原本照 Python 的 OSError 寫（`[Errno 2] No such file or directory: 'x'`），C++ 程式印 Python 樣式、load_cfg 又包一層＝路徑印兩次
        throw Error{err == ENOENT ? code::CfgMissing : code::CfgBad, "cannot read " + path + ": " + std::strerror(err)};
    }
    // 第一行 #!：換成空行（留著換行，JSON 錯誤訊息的行號才對得上）
    if (text->starts_with("#!")) {
        size_t nl = text->find('\n');
        if (nl == std::string::npos) {
            text->clear();
        } else {
            text->erase(0, nl);
        }
    }
    Json doc = Json::parse(*text, nullptr, false);
    if (doc.is_discarded()) {
        throw Error{code::CfgBad, "not JSON: " + path};
    }
    if (pointer.empty()) {
        return doc;
    }
    try {
        return doc.at(Json::json_pointer(pointer));
    } catch (const nlohmann::json::exception& e) {
        throw Error{code::CfgMissing, "pointer not found: " + path + "#" + pointer + ": " + e.what()};
    }
}

Json load_cfg(const std::string& spec) {
    Spec s;
    try {
        s = split_hash(spec);
    } catch (const Error&) {
        throw Error{code::CfgBad, "config " + spec + ": # must be followed by /"};
    }
    // 檔不在 CfgMissing、其他讀不了或不是 JSON CfgBad；原因照 read_json_at（`cannot read X: 原因`／`not JSON: X`），不再包一層
    // （11-05 第二輪：原本 `cannot read or not JSON: X (not JSON: X)`，路徑印兩次）
    Json doc = read_json_at(s.path, "");
    if (s.pointer.empty()) {
        return doc;
    }
    try {
        return doc.at(Json::json_pointer(s.pointer));
    } catch (const nlohmann::json::exception&) {
        throw Error{code::CfgMissing, "config pointer not found: " + spec};
    }
}

}  // namespace aos
