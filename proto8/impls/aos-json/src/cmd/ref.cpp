// ref.cpp：【cmd】寫入 env、ref 指示詞，ref --move 搬值並重算相對 $ref。
//
// 動到兩份檔（ref --move）時先寫新的那份、再改原本那份：中途失敗頂多多一份沒人參照的檔，原本那份不會指到不存在的地方。
#include "cmd/edit.hpp"

#include "help/help.hpp"
#include "aos/util/files.hpp"

#include <algorithm>
#include <filesystem>

namespace aos::json {

// env [--path 子路徑] [--prefix 前綴] [--parents] 檔#/指標 名字：那個位置換成 {"$env": 名字, …}。
int cmd_env(const Args& args) {
    Cli cli = parse_args(args, {{"--path", "path"}, {"--prefix", "prefix"}}, {{"--parents", "parents"}}, "env");
    if (cli.rest.size() != 2 || cli.rest[1].empty()) {
        throw usage_error(code::ArgumentsBad, "wrong number of arguments", cli_usage("env"));
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
    Cli cli = parse_args(args, {}, {{"--move", "move"}, {"--parents", "parents"}}, "ref");
    if (cli.rest.size() != 2) {
        throw usage_error(code::ArgumentsBad, "wrong number of arguments", cli_usage("ref"));
    }
    const std::string& spec = cli.rest[0];
    const std::string& target = cli.rest[1];
    Json ref = {{"$ref", target}};
    if (kind_of(ref) != Kind::Ref) {
        throw Error{code::ValueBad, "target " + target + " is not a $ref form (FILE[#/POINTER])"};
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
            throw Error{code::FileMissing, "target directory not found: " + dir};
        }
        rebase(moved, src.at.at.base, real_dir);
        if (ptr.empty()) {
            File& f = ed.docs.open(dest, true);
            if (f.exists) {
                throw Error{code::TargetBad, "target " + target + " already exists (--move does not overwrite a file)"};
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
                throw Error{code::TargetBad, "target " + target + " already has a value at that place"};
            }
            if (d.file == src.file && d.toks.size() >= src.toks.size() &&
                std::equal(src.toks.begin(), src.toks.end(), d.toks.begin())) {
                throw Error{code::TargetBad, "target " + target + " is inside the value being moved"};
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
