// cli.cpp：【aos-util】10-21 起的命令列旗標與設定檔（規則見 include/aos/cli.hpp）。
// 對應 proto8/bin/aos_flags.py 的 parse、load_cfg。
#include "aos/cli.hpp"

#include "aos/error.hpp"
#include "aos/files.hpp"

namespace aos {

Cli parse_cli(const std::vector<std::string>& argv, const std::map<std::string, std::string>& flags,
              const std::map<std::string, std::string>& switches) {
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
        size_t eq = a.find('=');
        std::string name = a.substr(0, eq);
        auto sw = switches.find(name);
        if (sw != switches.end()) {
            if (eq != std::string::npos) {
                throw Error{code::ArgumentsBad, name + " takes no value"};
            }
            out.opts[sw->second] = "1";
            i += 1;
            continue;
        }
        auto it = flags.find(name);
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
