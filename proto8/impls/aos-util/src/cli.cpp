// cli.cpp：【aos-util】10-21 起的命令列旗標與設定檔（規則見 include/aos/cli.hpp）。
// 對應 proto8/bin/aos_flags.py 的 parse、load_cfg。
#include "aos/cli.hpp"

#include "aos/error.hpp"
#include "aos/files.hpp"

namespace aos {

Cli parse_cli(const std::vector<std::string>& argv, const std::map<std::string, std::string>& flags) {
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
        auto it = flags.find(name);
        if (it == flags.end()) {
            throw Error{code::Usage, "不認得的旗標 " + name};
        }
        std::string val;
        if (eq != std::string::npos) {
            val = a.substr(eq + 1);
        } else {
            i += 1;
            if (i == argv.size()) {
                throw Error{code::Usage, name + " 缺值"};
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
        throw Error{code::FieldType, "設定檔 " + spec + " 的 # 後面要接 /"};
    }
    try {
        return read_json_at(s.path, s.pointer);
    } catch (const Error& e) {
        if (e.code == code::FieldType) {
            throw Error{code::FieldType, "設定檔指不到：" + spec};
        }
        throw Error{e.code, "讀不到或不是 JSON：" + s.path + "（" + e.msg + "）"};
    }
}

}  // namespace aos
