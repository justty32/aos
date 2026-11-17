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

// 搬走的值裡的相對 $ref，從 from 改成從 to 算（同一個資料夾就不用動）。`#/…`（＝原本那份檔 self）搬到別的檔時改寫成
// 「到 self 的相對路徑#/…」，仍指原本那份檔（搬進同一份檔＝不動）。`#./…`、`#../…`（11-13，從所在物件算）：指到的地方也在搬走的值裡面＝不動
// （整段一起搬，相對位置不變）；指到外面＝換成原本那個位置的 `#/…`（再照上一條）。loc＝v 原本在 self 裡的位置（token，跳脫後）；
// root＝搬走的那一格原本的位置。路徑寫壞的照留（讀的時候才報）。
static void rebase(Json& v, const std::string& from, const std::string& to, const std::string& self, bool same_file,
                   const std::vector<std::string>& loc, const std::vector<std::string>& root) {
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
            if (path.empty() && hash != std::string::npos && s.size() > hash + 1 && s[hash + 1] == '.') {
                std::optional<RefSpot> spot;
                try {
                    spot = aos::ref_spot(s, RefBase{from, self, loc});
                } catch (const Error&) {
                    continue;
                }
                std::vector<std::string> t = aos::pointer_tokens(spot->pointer);
                if (t.size() >= root.size() && std::equal(root.begin(), root.end(), t.begin())) {
                    continue;   // 指到搬走的值裡面：一起搬，不動
                }
                s = "#" + spot->pointer;
                if (spot->pointer.empty()) {
                    s = "#";
                }
                hash = 0;
                *x = s;
            }
            if (path.starts_with("/") || (path.empty() && same_file)) {
                continue;
            }
            std::string abs = path.empty() ? self : aos::abspath(aos::join(from, path));
            std::string rel = std::filesystem::path(abs).lexically_relative(to).string();
            *x = rel + (hash == std::string::npos ? "" : s.substr(hash));
        }
    }
    if (v.is_object()) {
        for (auto& [k, x] : v.items()) {
            std::vector<std::string> l = loc;
            l.push_back(aos::token_of(k));
            rebase(x, from, to, self, same_file, l, root);
        }
    } else if (v.is_array()) {
        for (size_t i = 0; i < v.size(); ++i) {
            std::vector<std::string> l = loc;
            l.push_back(std::to_string(i));
            rebase(v[i], from, to, self, same_file, l, root);
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
        throw Error{code::ValueBad, "target " + target + " is not a $ref form (FILE, FILE#/POINTER, #/POINTER, #./KEY, #../KEY)"};
    }
    bool parents = cli.opts.count("parents") > 0;
    Edit ed;
    Place src = place(ed, spec, false, false);
    if (cli.opts.count("move")) {
        Json moved = existing(src, spec);
        std::vector<std::string> root = aos::pointer_tokens(pointer_of(src.toks));
        std::optional<RefSpot> got = aos::ref_spot(target, RefBase{src.at.at.base, src.file->real, root});   // `#/…`、`#./…`＝搬進同一份檔；`x.json#/…`＝別份
        if (!got) {
            throw Error{code::ValueBad, "target " + target + " cannot be placed"};
        }
        RefSpot spot = *got;
        const std::string& dest = spot.file;
        const std::string& ptr = spot.pointer;
        std::string dir = aos::dirname(aos::abspath(dest));
        std::error_code ec;
        std::string real_dir = std::filesystem::canonical(dir, ec).string();
        if (ec) {
            throw Error{code::FileMissing, "target directory not found: " + dir};
        }
        rebase(moved, src.at.at.base, real_dir, src.file->real, std::filesystem::weakly_canonical(aos::abspath(dest)).string() == src.file->real,
               root, root);
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
