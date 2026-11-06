// edit.hpp：【cmd】寫入共用的編輯狀態、位置與 helper 宣告，供 write.cpp、ref.cpp 使用。
//
//   edit.cpp   讀取輸入值、找寫入位置、找父節點與放入值
//   write.cpp  set、batch、del、append、merge
//   ref.cpp    env、ref（搬走的值重算相對 $ref）
#pragma once

#include "cmd/cmd.hpp"
#include "follow/follow.hpp"

#include <algorithm>
#include <set>

namespace aos::json {

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
                    added += (added.empty() ? "" : "; ") + p;
                }
            }
            if (!added.empty()) {
                throw Error{code::CheckFailed, "the change would add problems, not written: " + added};
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

Json read_value(const std::vector<std::string>& rest, size_t idx, bool str);
Place place(Edit& ed, const std::string& spec, bool follow, bool follow_final, bool allow_new = false);
Json& parent_of(Json& doc, const std::vector<std::string>& toks, bool parents, const std::string& spec);
void put(Json& doc, const std::vector<std::string>& toks, const Json& v, bool parents, const std::string& spec);
Json& existing(Place& p, const std::string& spec);

}  // namespace aos::json
