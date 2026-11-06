// write.cpp：【cmd】寫入值——set、batch、del、append、merge。
//
// 共用流程：找位置（locate；沒 --follow 時路上經過指示詞＝FollowMissing）→ 在記憶體裡改 → 有變的檔才寫回（save_file，原子）。
#include "cmd/edit.hpp"

#include "help/help.hpp"

namespace aos::json {

// set [--follow] [--parents] [--str] 檔#/指標 [值]
int cmd_set(const Args& args) {
    Cli cli = parse_args(args, {}, {{"--check", "check"}, {"--follow", "follow"}, {"--parents", "parents"}, {"--str", "str"}}, "set");
    if (cli.rest.empty()) {
        throw usage_error(code::ArgumentsBad, "wrong number of arguments", cli_usage("set"));
    }
    Json v = read_value(cli.rest, 1, cli.opts.count("str") > 0);
    bool follow = cli.opts.count("follow") > 0;
    Edit ed;
    if (cli.opts.count("check")) {
        ed.check_file = parse_spec(cli.rest[0]).file;
    }
    Place p = place(ed, cli.rest[0], follow, follow, true);
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

// del [--follow] 檔#/指標：刪掉那個 key／元素。--follow＝路上穿過 $ref；$ref 陣列合起來的 key 每一份有的都刪（刪到指不到為止）。
int cmd_del(const Args& args) {
    Cli cli = parse_args(args, {}, {{"--follow", "follow"}}, "del");
    if (cli.rest.size() != 1) {
        throw usage_error(code::ArgumentsBad, "wrong number of arguments", cli_usage("del"));
    }
    bool follow = cli.opts.count("follow") > 0;
    Edit ed;
    for (int round = 0; round < 1000; ++round) {
        Place p = place(ed, cli.rest[0], follow, false);
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
        if (par.is_object()) {
            par.erase(p.toks.back());
        } else {
            par.erase(std::stoull(p.toks.back()));
        }
        ed.step();
        if (!follow) {
            break;
        }
    }
    ed.save();
    return 0;
}

// append [--follow] [--str] 檔#/指標 [值]：那個位置要是陣列，接在尾巴。
int cmd_append(const Args& args) {
    Cli cli = parse_args(args, {}, {{"--check", "check"}, {"--follow", "follow"}, {"--str", "str"}}, "append");
    if (cli.rest.empty()) {
        throw usage_error(code::ArgumentsBad, "wrong number of arguments", cli_usage("append"));
    }
    Json v = read_value(cli.rest, 1, cli.opts.count("str") > 0);
    bool follow = cli.opts.count("follow") > 0;
    Edit ed;
    if (cli.opts.count("check")) {
        ed.check_file = parse_spec(cli.rest[0]).file;
    }
    Place p = place(ed, cli.rest[0], follow, follow);
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

}  // namespace aos::json
