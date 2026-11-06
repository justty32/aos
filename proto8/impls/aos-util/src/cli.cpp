// cli.cpp：【aos-util】10-21 起的命令列旗標與設定檔（規則見 include/aos/util/cli.hpp）。
// 對應 proto8/py/aos_flags.py 的 parse、load_cfg。
#include "aos/util/cli.hpp"

#include "aos/util/error.hpp"
#include "aos/util/files.hpp"

#include <cstdio>
#include <cstdlib>
#include <stdexcept>

namespace aos {

Cli parse_cli(const std::vector<std::string>& argv, const std::map<std::string, std::string>& flags,
              const std::map<std::string, std::string>& switches, const std::string& help,
              const std::vector<std::string>& short_flags) {
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
