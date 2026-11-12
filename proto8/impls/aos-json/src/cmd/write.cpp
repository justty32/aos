// write.cpp：【cmd】寫入值——set、batch、del、append、merge、add。
//
// 共用流程：找位置（locate；沒 --follow 時路上經過指示詞＝FollowMissing）→ 在記憶體裡改 → 有變的檔才寫回（save_file，原子）。
#include "cmd/edit.hpp"

#include "help/help.hpp"

#include <filesystem>
#include <iostream>

namespace aos::json {

// set [--follow|--raw] [--parents] [--str] 檔#/指標 [值]（--raw＝路上的指示詞物件當普通物件）
int cmd_set(const Args& args) {
    Cli cli = parse_args(args, {}, {{"--check", "check"}, {"--follow", "follow"}, {"--parents", "parents"}, {"--raw", "raw"}, {"--str", "str"}}, "set");
    if (cli.rest.empty()) {
        throw usage_error(code::ArgumentsBad, "wrong number of arguments", cli_usage("set"));
    }
    Json v = read_value(cli.rest, 1, cli.opts.count("str") > 0);
    bool follow = cli.opts.count("follow") > 0;
    Edit ed;
    if (cli.opts.count("check")) {
        ed.check_file = parse_spec(cli.rest[0]).file;
    }
    Place p = place(ed, cli.rest[0], follow, follow, true, raw_flag(cli, follow));
    if (follow && p.at.merged && p.at.rest.empty()) {
        throw Error{code::TargetBad, cli.rest[0] + " is merged from several $ref parts; --follow cannot replace it whole (without --follow the $ref itself is replaced)"};
    }
    put(p.file->doc, p.toks, v, cli.opts.count("parents") > 0, cli.rest[0]);
    ed.save();
    return 0;
}

// batch [--follow] [--parents] 檔：stdin 一個物件 {"/指標": 值, …}（"" ＝整份），照順序一個個 set（規則同 set），
// 全部成功才寫回（每份檔一次原子寫入；有一個失敗＝一個都不寫）。一次給很多個值用這個。
int cmd_batch(const Args& args) {
    Cli cli = parse_args(args, {}, {{"--check", "check"}, {"--follow", "follow"}, {"--parents", "parents"}}, "batch");
    if (cli.rest.size() != 1) {
        throw usage_error(code::ArgumentsBad, "wrong number of arguments", cli_usage("batch"));
    }
    Json all = read_value({}, 0, false);
    if (!all.is_object()) {
        throw Error{code::ValueBad, "batch stdin must be an object {\"/POINTER\": VALUE, ...}"};
    }
    bool follow = cli.opts.count("follow") > 0;
    Edit ed;
    if (cli.opts.count("check")) {
        ed.check_file = parse_spec(cli.rest[0]).file;
    }
    for (auto& [ptr, v] : all.items()) {
        if (!ptr.empty() && !ptr.starts_with("/")) {
            throw Error{code::SpecBad, "batch keys must be JSON pointers (starting with /): " + ptr};
        }
        std::string spec = cli.rest[0] + (ptr.empty() ? "" : "#" + ptr);
        Place p = place(ed, spec, follow, follow);
        if (follow && p.at.merged && p.at.rest.empty()) {
            throw Error{code::TargetBad, spec + " is merged from several $ref parts; --follow cannot replace it whole"};
        }
        put(p.file->doc, p.toks, v, cli.opts.count("parents") > 0, spec);
        ed.step();
    }
    ed.save();
    return 0;
}

// del [--follow|--raw] 檔#/指標：刪掉那個 key／元素。--follow＝路上穿過 $ref；$ref 陣列合起來的 key 每一份有的都刪（刪到指不到為止）。
int cmd_del(const Args& args) {
    Cli cli = parse_args(args, {}, {{"--follow", "follow"}, {"--raw", "raw"}}, "del");
    if (cli.rest.size() != 1) {
        throw usage_error(code::ArgumentsBad, "wrong number of arguments", cli_usage("del"));
    }
    bool follow = cli.opts.count("follow") > 0;
    Edit ed;
    bool raw = raw_flag(cli, follow);
    for (int round = 0; round < 1000; ++round) {
        Place p = place(ed, cli.rest[0], follow, false, false, raw);
        if (!p.at.rest.empty()) {
            if (round == 0) {
                throw Error{code::PointerMissing, "no such pointer: " + cli.rest[0]};
            }
            break;
        }
        if (p.toks.empty()) {
            throw Error{code::TargetBad, "will not delete a whole file (use rm)"};
        }
        Json& par = parent_of(p.file->doc, p.toks, false, cli.rest[0]);
        bool item = !par.is_object();
        if (item) {
            par.erase(std::stoull(p.toks.back()));
        } else {
            par.erase(p.toks.back());
        }
        ed.step();
        if (!follow || item) {   // 陣列元素刪一個就停（後面的往前移，同一個索引又指得到，不能再刪）
            break;
        }
    }
    ed.save();
    return 0;
}

// append [--follow|--raw] [--str] 檔#/指標 [值]：那個位置要是陣列，接在尾巴。
int cmd_append(const Args& args) {
    Cli cli = parse_args(args, {}, {{"--check", "check"}, {"--follow", "follow"}, {"--raw", "raw"}, {"--str", "str"}}, "append");
    if (cli.rest.empty()) {
        throw usage_error(code::ArgumentsBad, "wrong number of arguments", cli_usage("append"));
    }
    Json v = read_value(cli.rest, 1, cli.opts.count("str") > 0);
    bool follow = cli.opts.count("follow") > 0;
    Edit ed;
    if (cli.opts.count("check")) {
        ed.check_file = parse_spec(cli.rest[0]).file;
    }
    Place p = place(ed, cli.rest[0], follow, follow, false, raw_flag(cli, follow));
    Json& t = existing(p, cli.rest[0]);
    if (!t.is_array()) {
        throw Error{code::TargetBad, cli.rest[0] + " is not an array (it is " + std::string(t.type_name()) + ")"};
    }
    t.push_back(v);
    ed.save();
    return 0;
}

// merge [--follow] 檔#/指標 [物件]：淺層合 key，同名的換掉（同 $ref 陣列的合法：後蓋前、不往下層合；null 照字面放 null）。
int cmd_merge(const Args& args) {
    Cli cli = parse_args(args, {}, {{"--check", "check"}, {"--follow", "follow"}}, "merge");
    if (cli.rest.empty()) {
        throw usage_error(code::ArgumentsBad, "wrong number of arguments", cli_usage("merge"));
    }
    Json v = read_value(cli.rest, 1, false);
    if (!v.is_object()) {
        throw Error{code::ValueBad, "merge value must be an object"};
    }
    bool follow = cli.opts.count("follow") > 0;
    Edit ed;
    if (cli.opts.count("check")) {
        ed.check_file = parse_spec(cli.rest[0]).file;
    }
    Place p = place(ed, cli.rest[0], follow, follow);
    Json& t = existing(p, cli.rest[0]);
    if (!t.is_object()) {
        throw Error{code::TargetBad, cli.rest[0] + " is not an object (it is " + std::string(t.type_name()) + ")"};
    }
    for (auto& [k, x] : v.items()) {
        t[k] = x;
    }
    ed.save();
    return 0;
}

// add [--follow|--raw] [--parents] [--check] [--str] 檔#/指標 [值]：加一項新的，已有就報錯（json 工具 json_add 搬下來，11-12）。
//   父層是物件＝加新 key（已有＝KeyExists）；父層是陣列＝/N 插在第 N 項前面（0..長度）、/- 接尾巴；
//   整份（沒 #）＝檔已在 KeyExists、不在建新檔。成功印實際寫到的位置（照給的字面，- 換成真索引）。
int cmd_add(const Args& args) {
    Cli cli = parse_args(args, {}, {{"--check", "check"}, {"--follow", "follow"}, {"--parents", "parents"}, {"--raw", "raw"}, {"--str", "str"}}, "add");
    if (cli.rest.empty()) {
        throw usage_error(code::ArgumentsBad, "wrong number of arguments", cli_usage("add"));
    }
    const std::string& s = cli.rest[0];
    Json v = read_value(cli.rest, 1, cli.opts.count("str") > 0);
    bool follow = cli.opts.count("follow") > 0;
    bool raw = raw_flag(cli, follow);
    Spec spec = parse_spec(s);
    Edit ed;
    if (cli.opts.count("check")) {
        ed.check_file = spec.file;
    }
    std::string out = s;
    if (spec.toks.empty()) {
        if (std::filesystem::exists(spec.file)) {
            throw Error{code::KeyExists, spec.file + " already exists; use set to replace the whole file"};
        }
        Place p = place(ed, s, follow, follow, true, raw);
        put(p.file->doc, p.toks, v, false, s);
    } else if (spec.toks.back() == "-") {
        std::string ptr = s.substr(s.find('#') + 1);
        ptr = ptr.substr(0, ptr.rfind('/'));
        std::string parent = spec.file + (ptr.empty() ? "" : "#" + ptr);
        Place p = place(ed, parent, follow, follow, false, raw);
        if (!p.at.rest.empty()) {
            throw Error{code::PointerMissing, "no such pointer: " + parent + " (" + shown(p.at.at.file, p.at.at.toks) + " has no " + p.at.rest[0] + ")"};
        }
        Json& t = *p.at.at.node;
        if (!t.is_array()) {
            throw Error{code::TargetBad, parent + " is " + std::string(t.type_name()) + ", not an array; - only works at the end of an array path"};
        }
        out = s.substr(0, s.size() - 1) + std::to_string(t.size());
        t.push_back(v);
    } else {
        Place p = place(ed, s, follow, false, false, raw);
        const std::string& last = p.toks.back();
        if (p.at.rest.empty()) {   // 已在：父層是物件＝KeyExists；是陣列＝插在那一項前面
            Json& par = parent_of(p.file->doc, p.toks, false, s);
            if (par.is_object()) {
                throw Error{code::KeyExists, s + " already exists" + (par[last].is_array() ? "; to add an item to that array write " + s + "/-"
                                                                                          : std::string("; use set to change it"))};
            }
            par.insert(par.begin() + (long)std::stoull(last), v);
        } else if (p.at.rest.size() == 1) {   // 父層在
            Json& par = *p.at.at.node;
            if (par.is_object()) {
                par[last] = v;
            } else if (par.is_array() && (last == std::to_string(par.size()) || is_index(last, par.size()))) {
                par.insert(par.begin() + (long)std::stoull(last), v);
            } else if (par.is_array()) {
                throw Error{code::PointerMissing, s + ": array has " + std::to_string(par.size()) + " items; insert at 0.." +
                                                      std::to_string(par.size()) + " or write /- to append"};
            } else {
                throw Error{code::TargetBad, shown(p.at.at.file, p.at.at.toks) + " is " + std::string(par.type_name()) +
                                                 "; it cannot hold a key or item"};
            }
        } else {   // 中間層不在：--parents 建物件層（同 set --parents），不然 PointerMissing
            put(p.file->doc, p.toks, v, cli.opts.count("parents") > 0, s);
        }
    }
    ed.save();
    std::cout << out << "\n" << std::flush;
    return 0;
}

}  // namespace aos::json
