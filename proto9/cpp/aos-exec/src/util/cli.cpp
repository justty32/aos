// util/cli.cpp: command-line flags with per-tool short names (trimmed copy of proto8 aos-util src/cli.cpp; rules in util/cli.hpp).
#include "util/cli.hpp"

#include "util/error.hpp"

#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <stdexcept>

namespace aos {

// 常用短名預設；各呼叫端可另給自己的短名表，-h 隨 help 內建。
// proto9: only the two aos-exec uses are kept (-s/--stack went with AOS_STACK).
static const std::map<std::string, std::string> kShort = {
    {"-h", "--help"}, {"-w", "--ws"},
};

Cli parse_cli(const std::vector<std::string>& argv, const std::map<std::string, std::string>& flags,
              const std::map<std::string, std::string>& switches, const std::string& help,
              const std::vector<std::string>& short_flags,
              const std::map<std::string, std::string>& custom_short, size_t keep) {
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
        if (a == "--") {   // 位置參數前＝丟掉；之後＝連它原樣交出（CFG -- ARGS）
            out.rest.insert(out.rest.end(), argv.begin() + (long)(out.rest.empty() ? i + 1 : i), argv.end());
            return out;
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
        bool positional = !a.starts_with("-") || a == "-";
        if (!positional && !out.rest.empty() && !switches.count(long_name) && !flags.count(long_name) &&
            !(long_name == "--help" && !help.empty())) {
            bool number = a.size() > 1 && (std::isdigit((unsigned char)a[1]) || (a[1] == '.' && a.size() > 2 && std::isdigit((unsigned char)a[2])));
            bool space = name.find_first_of(" \t\n") != std::string::npos;
            positional = number || space;   // 位置參數後像負數或含空白＝照舊當位置參數（同 tool_io.tokenize_flags）
        }
        if (positional) {
            if (keep > 0 && out.rest.size() + 1 >= keep) {   // 第 keep 個位置參數起原樣交出
                out.rest.insert(out.rest.end(), argv.begin() + (long)i, argv.end());
                return out;
            }
            out.rest.push_back(a);
            i += 1;
            continue;
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
    return out;
}

Error usage_error(const std::string& code, const std::string& reason, const std::string& usage) {
    return Error{code, reason + " (usage: " + usage + ")"};
}

}  // namespace aos
