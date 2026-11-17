// edit.cpp：【cmd】寫入共用 helper：讀取值、找位置、找父節點與放入值。
#include "cmd/edit.hpp"

#include <iostream>
#include <iterator>

namespace aos::json {

// 要寫的值：參數有就用參數、沒有讀 stdin（整份）。--str＝字面字串（stdin 去掉結尾一個換行），不然當 JSON 解。
Json read_value(const std::vector<std::string>& rest, size_t idx, bool str) {
    if (rest.size() > idx + 1) {
        throw Error{code::ArgumentsBad, "extra argument " + rest[idx + 1] + " (quote a value with spaces; a negative number can follow FILE#/POINTER directly)"};
    }
    std::string text;
    if (rest.size() == idx + 1) {
        text = rest[idx];
    } else {
        aos::require_stdin_body();
        text.assign(std::istreambuf_iterator<char>(std::cin), {});
        if (text.empty()) {
            throw Error{code::ValueMissing, "no value given (no argument, stdin is empty)"};
        }
        if (str && text.ends_with("\n")) {
            text.pop_back();
        }
    }
    if (str) {
        return text;
    }
    if (text.find_first_not_of(" \t\r\n") == std::string::npos) {
        throw Error{code::ValueMissing, "value is empty"};
    }
    Json v = Json::parse(text, nullptr, false);
    if (v.is_discarded()) {
        throw Error{code::ValueBad, "value is not JSON (add --str to write a string): " + text};
    }
    return v;
}

// allow_new＝整份（沒有 #/）時檔可以還不在（set 建新檔）。
Place place(Edit& ed, const std::string& spec, bool follow, bool follow_final, bool allow_new, bool raw) {
    if (allow_new && parse_spec(spec).toks.empty()) {
        ed.docs.open(parse_spec(spec).file, true);
    }
    Mode mode;
    mode.follow = follow;
    mode.follow_final = follow_final;
    mode.strict = true;
    mode.raw = raw;
    Located at = locate(ed.docs, parse_spec(spec), mode);
    Place p{&ed.touch(at.at.file), at.at.toks, at};
    p.toks.insert(p.toks.end(), at.rest.begin(), at.rest.end());
    return p;
}

// --raw：指示詞物件當普通物件（set／append／del）；跟 --follow 互斥。
bool raw_flag(const aos::Cli& cli, bool follow) {
    bool raw = cli.opts.count("raw") > 0;
    if (raw && follow) {
        throw Error{code::ArgumentsBad, "--raw and --follow cannot be used together"};
    }
    return raw;
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
            // 父指標是根（空字串）就印 the root，不留一個空位（坑-87）
            std::string where = pointer_of({toks.begin(), toks.begin() + (long)i});
            if (where.empty()) {
                where = "the root";
            }
            throw Error{code::PointerMissing, "no such pointer: " + spec + " (" + where +
                                                  " has no " + toks[i] + "; add --parents to create objects along the way)"};
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
        throw Error{code::PointerMissing, spec + ": can only set an existing array index (use append to add at the end)"};
    } else {
        throw Error{code::TargetBad, spec + ": parent is " + std::string(par.type_name()) + ", cannot hold a value"};
    }
}

Json& existing(Place& p, const std::string& spec) {
    if (!p.at.rest.empty()) {
        throw Error{code::PointerMissing, "no such pointer: " + spec};
    }
    return *p.at.at.node;
}

}  // namespace aos::json
