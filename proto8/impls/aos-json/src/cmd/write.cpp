// write.cpp：【cmd】寫——set、del、append、merge、env、ref。
//
// 共用流程：找位置（locate；沒 --follow 時路上經過指示詞＝FollowMissing）→ 在記憶體裡改 → 有變的檔才寫回（save_file，原子）。
// 動到兩份檔（ref --move）時先寫新的那份、再改原本那份：中途失敗頂多多一份沒人參照的檔，原本那份不會指到不存在的地方。
#include "cmd/cmd.hpp"

#include "follow/follow.hpp"

#include "aos/cli.hpp"
#include "aos/files.hpp"

#include <algorithm>
#include <filesystem>
#include <iostream>
#include <iterator>
#include <set>

namespace aos::json {

namespace {

// 要寫的值：參數有就用參數、沒有讀 stdin（整份）。--str＝字面字串（stdin 去掉結尾一個換行），不然當 JSON 解。
Json read_value(const std::vector<std::string>& rest, size_t idx, bool str) {
    if (rest.size() > idx + 1) {
        throw Error{code::ArgumentsBad, "多了參數 " + rest[idx + 1] + "（值有空白、是負數，記得加引號或寫在 -- 後面）"};
    }
    std::string text;
    if (rest.size() == idx + 1) {
        text = rest[idx];
    } else {
        text.assign(std::istreambuf_iterator<char>(std::cin), {});
        if (text.empty()) {
            throw Error{code::ValueMissing, "沒給值（參數沒有、stdin 是空的）"};
        }
        if (str && text.ends_with("\n")) {
            text.pop_back();
        }
    }
    if (str) {
        return text;
    }
    if (text.find_first_not_of(" \t\r\n") == std::string::npos) {
        throw Error{code::ValueMissing, "值是空的"};
    }
    Json v = Json::parse(text, nullptr, false);
    if (v.is_discarded()) {
        throw Error{code::ValueBad, "值不是一份 JSON（要寫字串就加 --str）：" + text};
    }
    return v;
}

// 一次寫入：每改一步（step）就把有變的檔的原文跟著更新（splice 一次只看一處變動，diff 才小），最後只寫有變的檔。
struct Edit {
    Docs docs;
    std::map<std::string, Json> snap;   // 上一步之後的值
    std::vector<std::string> order;     // 寫回的順序（第一次碰到的先寫）
    std::set<std::string> changed;

    File& touch(const std::string& real) {
        File& f = docs.files.at(real);
        if (!snap.count(real)) {
            snap[real] = f.doc;
            order.push_back(real);
        }
        return f;
    }
    void step() {
        for (const std::string& real : order) {
            File& f = docs.files.at(real);
            if (!f.exists || f.doc != snap[real]) {
                f.body = render_body(f, snap[real]);
                snap[real] = f.doc;
                changed.insert(real);
            }
        }
    }
    std::string check_file;   // --check：寫之前驗這份檔（從頭往下，含被 $ref 的），改完多出來的問題＝不寫、CheckFailed

    void save() {
        step();
        if (!check_file.empty()) {
            Docs disk;
            std::vector<std::string> old = problems_of(disk, check_file, false);
            Docs mine = docs;
            std::string added;
            for (const std::string& p : problems_of(mine, check_file, false)) {
                if (std::find(old.begin(), old.end(), p) == old.end()) {
                    added += (added.empty() ? "" : "；") + p;
                }
            }
            if (!added.empty()) {
                throw Error{code::CheckFailed, "改完會多出問題，沒寫：" + added};
            }
        }
        for (const std::string& real : order) {
            if (changed.count(real)) {
                save_file(docs.files.at(real));
            }
        }
    }
};

struct Place {
    File* file;
    std::vector<std::string> toks;   // 在那份檔裡的位置（可能還不存在）
    Located at;
};

// allow_new＝整份（沒有 #/）時檔可以還不在（set 建新檔）。
Place place(Edit& ed, const std::string& spec, bool follow, bool follow_final, bool allow_new = false) {
    if (allow_new && parse_spec(spec).toks.empty()) {
        ed.docs.open(parse_spec(spec).file, true);
    }
    Mode mode;
    mode.follow = follow;
    mode.follow_final = follow_final;
    mode.strict = true;
    Located at = locate(ed.docs, parse_spec(spec), mode);
    Place p{&ed.touch(at.at.file), at.at.toks, at};
    p.toks.insert(p.toks.end(), at.rest.begin(), at.rest.end());
    return p;
}

// toks 的上一層（parents＝路上沒有的物件 key 就建空物件，像 mkdir -p）。
Json& parent_of(Json& doc, const std::vector<std::string>& toks, bool parents, const std::string& spec) {
    Json* cur = &doc;
    for (size_t i = 0; i + 1 < toks.size(); ++i) {
        Json* n = child(*cur, toks[i]);
        if (n == nullptr && parents && cur->is_object()) {
            (*cur)[toks[i]] = Json::object();
            n = &(*cur)[toks[i]];
        }
        if (n == nullptr) {
            throw Error{code::PointerMissing, "指不到 " + spec + "（" + pointer_of({toks.begin(), toks.begin() + (long)i}) +
                                                  " 底下沒有 " + toks[i] + "；要建路上的物件加 --parents）"};
        }
        cur = n;
    }
    return *cur;
}

void put(Json& doc, const std::vector<std::string>& toks, const Json& v, bool parents, const std::string& spec) {
    if (toks.empty()) {
        doc = v;
        return;
    }
    Json& par = parent_of(doc, toks, parents, spec);
    const std::string& last = toks.back();
    if (par.is_object()) {
        par[last] = v;   // 有就原地換（位置不變）、沒有接在最後
    } else if (par.is_array() && is_index(last, par.size())) {
        par[std::stoull(last)] = v;
    } else if (par.is_array()) {
        throw Error{code::PointerMissing, spec + "：陣列只能改已經有的索引（要加在尾巴用 append）"};
    } else {
        throw Error{code::TargetBad, spec + "：上一層是 " + std::string(par.type_name()) + "，放不了東西"};
    }
}

Json& existing(Place& p, const std::string& spec) {
    if (!p.at.rest.empty()) {
        throw Error{code::PointerMissing, "指不到 " + spec};
    }
    return *p.at.at.node;
}

}  // namespace

// set [--follow] [--parents] [--str] 檔#/指標 [值]
int cmd_set(const Args& args) {
    Cli cli = parse_cli(args, {}, {{"--check", "check"}, {"--follow", "follow"}, {"--parents", "parents"}, {"--str", "str"}});
    if (cli.rest.empty()) {
        throw Error{code::ArgumentsBad, "用法：aos-json set [--check] [--follow] [--parents] [--str] 檔#/指標 [值]（沒給值讀 stdin）"};
    }
    Json v = read_value(cli.rest, 1, cli.opts.count("str") > 0);
    bool follow = cli.opts.count("follow") > 0;
    Edit ed;
    if (cli.opts.count("check")) {
        ed.check_file = parse_spec(cli.rest[0]).file;
    }
    Place p = place(ed, cli.rest[0], follow, follow, true);
    if (follow && p.at.merged && p.at.rest.empty()) {
        throw Error{code::TargetBad, cli.rest[0] + " 是幾份 $ref 合起來的，--follow 不能整個換（不加 --follow＝換掉原地的 $ref）"};
    }
    put(p.file->doc, p.toks, v, cli.opts.count("parents") > 0, cli.rest[0]);
    ed.save();
    return 0;
}

// batch [--follow] [--parents] 檔：stdin 一個物件 {"/指標": 值, …}（"" ＝整份），照順序一個個 set（規則同 set），
// 全部成功才寫回（每份檔一次原子寫入；有一個失敗＝一個都不寫）。一次給很多個值用這個。
int cmd_batch(const Args& args) {
    Cli cli = parse_cli(args, {}, {{"--check", "check"}, {"--follow", "follow"}, {"--parents", "parents"}});
    if (cli.rest.size() != 1) {
        throw Error{code::ArgumentsBad, "用法：aos-json batch [--follow] [--parents] 檔 < {\"/指標\": 值, …}"};
    }
    Json all = read_value({}, 0, false);
    if (!all.is_object()) {
        throw Error{code::ValueBad, "batch 的 stdin 要是物件 {\"/指標\": 值, …}"};
    }
    bool follow = cli.opts.count("follow") > 0;
    Edit ed;
    if (cli.opts.count("check")) {
        ed.check_file = parse_spec(cli.rest[0]).file;
    }
    for (auto& [ptr, v] : all.items()) {
        if (!ptr.empty() && !ptr.starts_with("/")) {
            throw Error{code::SpecBad, "batch 的 key 要是 JSON 指標（/ 開頭）：" + ptr};
        }
        std::string spec = cli.rest[0] + (ptr.empty() ? "" : "#" + ptr);
        Place p = place(ed, spec, follow, follow);
        if (follow && p.at.merged && p.at.rest.empty()) {
            throw Error{code::TargetBad, spec + " 是幾份 $ref 合起來的，--follow 不能整個換"};
        }
        put(p.file->doc, p.toks, v, cli.opts.count("parents") > 0, spec);
        ed.step();
    }
    ed.save();
    return 0;
}

// del [--follow] 檔#/指標：刪掉那個 key／元素。--follow＝路上穿過 $ref；$ref 陣列合起來的 key 每一份有的都刪（刪到指不到為止）。
int cmd_del(const Args& args) {
    Cli cli = parse_cli(args, {}, {{"--follow", "follow"}});
    if (cli.rest.size() != 1) {
        throw Error{code::ArgumentsBad, "用法：aos-json del [--follow] 檔#/指標"};
    }
    bool follow = cli.opts.count("follow") > 0;
    Edit ed;
    for (int round = 0; round < 1000; ++round) {
        Place p = place(ed, cli.rest[0], follow, false);
        if (!p.at.rest.empty()) {
            if (round == 0) {
                throw Error{code::PointerMissing, "指不到 " + cli.rest[0]};
            }
            break;
        }
        if (p.toks.empty()) {
            throw Error{code::TargetBad, "不刪整份檔（要刪檔自己 rm）"};
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
    Cli cli = parse_cli(args, {}, {{"--check", "check"}, {"--follow", "follow"}, {"--str", "str"}});
    if (cli.rest.empty()) {
        throw Error{code::ArgumentsBad, "用法：aos-json append [--follow] [--str] 檔#/指標 [值]"};
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
        throw Error{code::TargetBad, cli.rest[0] + " 不是陣列（是 " + std::string(t.type_name()) + "）"};
    }
    t.push_back(v);
    ed.save();
    return 0;
}

// merge [--follow] 檔#/指標 [物件]：淺層合 key，同名的換掉（同 $ref 陣列的合法：後蓋前、不往下層合；null 照字面放 null）。
int cmd_merge(const Args& args) {
    Cli cli = parse_cli(args, {}, {{"--check", "check"}, {"--follow", "follow"}});
    if (cli.rest.empty()) {
        throw Error{code::ArgumentsBad, "用法：aos-json merge [--follow] 檔#/指標 [物件]"};
    }
    Json v = read_value(cli.rest, 1, false);
    if (!v.is_object()) {
        throw Error{code::ValueBad, "merge 的值要是物件"};
    }
    bool follow = cli.opts.count("follow") > 0;
    Edit ed;
    if (cli.opts.count("check")) {
        ed.check_file = parse_spec(cli.rest[0]).file;
    }
    Place p = place(ed, cli.rest[0], follow, follow);
    Json& t = existing(p, cli.rest[0]);
    if (!t.is_object()) {
        throw Error{code::TargetBad, cli.rest[0] + " 不是物件（是 " + std::string(t.type_name()) + "）"};
    }
    for (auto& [k, x] : v.items()) {
        t[k] = x;
    }
    ed.save();
    return 0;
}

// env [--path 子路徑] [--prefix 前綴] [--parents] 檔#/指標 名字：那個位置換成 {"$env": 名字, …}。
int cmd_env(const Args& args) {
    Cli cli = parse_cli(args, {{"--path", "path"}, {"--prefix", "prefix"}}, {{"--parents", "parents"}});
    if (cli.rest.size() != 2 || cli.rest[1].empty()) {
        throw Error{code::ArgumentsBad, "用法：aos-json env [--path 子路徑] [--prefix 前綴] [--parents] 檔#/指標 名字"};
    }
    Json v = {{"$env", cli.rest[1]}};
    if (cli.opts.count("path")) {
        v["$path"] = cli.opts["path"];
    }
    if (cli.opts.count("prefix")) {
        v["$prefix"] = cli.opts["prefix"];
    }
    Edit ed;
    Place p = place(ed, cli.rest[0], false, false);
    put(p.file->doc, p.toks, v, cli.opts.count("parents") > 0, cli.rest[0]);
    ed.save();
    return 0;
}

// 搬走的值裡的相對 $ref，從 from 改成從 to 算（同一個資料夾就不用動）。
static void rebase(Json& v, const std::string& from, const std::string& to) {
    if (kind_of(v) == Kind::Ref) {
        Json& r = v["$ref"];
        std::vector<Json*> items;
        if (r.is_array()) {
            for (Json& x : r) {
                items.push_back(&x);
            }
        } else {
            items.push_back(&r);
        }
        for (Json* x : items) {
            std::string s = x->get<std::string>();
            size_t hash = s.find('#');
            std::string path = s.substr(0, hash);
            if (path.starts_with("/")) {
                continue;
            }
            std::string abs = aos::abspath(aos::join(from, path));
            std::string rel = std::filesystem::path(abs).lexically_relative(to).string();
            *x = rel + (hash == std::string::npos ? "" : s.substr(hash));
        }
    }
    if (v.is_object() || v.is_array()) {
        for (auto& [k, x] : v.items()) {
            (void)k;
            rebase(x, from, to);
        }
    }
}

// ref [--move] [--parents] 檔#/指標 目標：那個位置換成 {"$ref": 目標}（目標照 $ref 的寫法，從這份檔所在的資料夾算）。
// --move＝先把原本的值搬到目標（目標是整份檔＝檔不能已經在；是 檔#/指標＝檔要在、那個位置要還沒有），裡面的相對 $ref 跟著改。
int cmd_ref(const Args& args) {
    Cli cli = parse_cli(args, {}, {{"--move", "move"}, {"--parents", "parents"}});
    if (cli.rest.size() != 2) {
        throw Error{code::ArgumentsBad, "用法：aos-json ref [--move] [--parents] 檔#/指標 目標"};
    }
    const std::string& spec = cli.rest[0];
    const std::string& target = cli.rest[1];
    Json ref = {{"$ref", target}};
    if (kind_of(ref) != Kind::Ref) {
        throw Error{code::ValueBad, "目標 " + target + " 不是 $ref 的寫法（檔[#/指標]）"};
    }
    bool parents = cli.opts.count("parents") > 0;
    Edit ed;
    Place src = place(ed, spec, false, false);
    if (cli.opts.count("move")) {
        Json moved = existing(src, spec);
        auto [path, ptr] = ref_parts(ref)[0];
        std::string dest = aos::join(src.at.at.base, path);
        std::string dir = aos::dirname(aos::abspath(dest));
        std::error_code ec;
        std::string real_dir = std::filesystem::canonical(dir, ec).string();
        if (ec) {
            throw Error{code::FileMissing, "目標的資料夾不在：" + dir};
        }
        rebase(moved, src.at.at.base, real_dir);
        if (ptr.empty()) {
            File& f = ed.docs.open(dest, true);
            if (f.exists) {
                throw Error{code::TargetBad, "目標 " + target + " 已經有了（--move 不蓋掉現有的檔）"};
            }
            f.one_line = src.file->one_line;
            f.indent = src.file->indent;
            f.indent_char = src.file->indent_char;
            ed.touch(f.real);   // 新檔（exists＝false）save 一定會寫
            f.doc = moved;
        } else {
            ed.docs.open(dest, false);
            Place d = place(ed, dest + "#" + ptr, false, false);
            if (d.at.rest.empty()) {
                throw Error{code::TargetBad, "目標 " + target + " 那個位置已經有東西了"};
            }
            if (d.file == src.file && d.toks.size() >= src.toks.size() &&
                std::equal(src.toks.begin(), src.toks.end(), d.toks.begin())) {
                throw Error{code::TargetBad, "目標 " + target + " 在要搬的值裡面"};
            }
            put(d.file->doc, d.toks, moved, parents, target);
        }
        ed.step();
        // 先寫目標：把它排到最前面（同一份檔就只有一份）
        std::string first = ed.order.back();
        ed.order.pop_back();
        ed.order.insert(ed.order.begin(), first);
        src = place(ed, spec, false, false);   // 同一份檔改過了，重找一次
    }
    put(src.file->doc, src.toks, ref, parents, spec);
    ed.save();
    return 0;
}

}  // namespace aos::json
