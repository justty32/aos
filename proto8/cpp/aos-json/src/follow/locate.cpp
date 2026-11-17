// locate.cpp：【follow】從 `檔#/指標` 一格格往下走；路上遇到指示詞看 Mode 決定穿不穿。
//
// 穿過一個 $ref：
//   - 一份：換到那份檔的那個位置，接著走
//   - 陣列（幾份合成一份，N-45）：每份先各自追到不是 $ref 為止；都是物件＝下一格的 key 看「最後一份有它的」
//     （同名後蓋前，生效的就是它），都沒有＝最後一份（新 key 寫進最後一份才會生效）；都是陣列＝照索引算是第幾份的；
//     種類混在一起＝DirectiveBad（同 aos-directive「合不起來」）。份裡又是 $ref 陣列＝TargetBad（先不支援）
// $env 走不下去（換出來是字串）。
#include "follow/follow.hpp"

#include "aos/util/files.hpp"

namespace aos::json {

Cursor fetch(Docs& docs, const Cursor& at, const std::string& spec, Chain& chain) {
    const std::string& where = spec;
    // 字串→位置：跟 aos-directive 同一支（# 左邊檔案系統、右邊 json 內部；#./、#../ 從 at 這一格的上一層算）
    std::optional<RefSpot> got = aos::ref_spot(spec, RefBase{at.base, at.file, aos::pointer_tokens(pointer_of(at.toks))});
    if (!got) {
        throw Error{code::DirectiveBad, "$ref " + spec + " cannot be placed (which file it is in is not known)"};
    }
    RefSpot spot = *got;
    File* f = nullptr;
    try {
        f = &docs.open(spot.file, false);
    } catch (const Error& e) {
        throw Error{code::DirectiveBad, "$ref " + where + " cannot be read (" + e.msg + ")"};
    }
    std::pair<std::string, std::string> here{f->real, spot.pointer};
    for (const auto& seen : chain) {
        if (seen == here) {
            throw Error{code::DirectiveBad, "$ref cycle: " + shown(f->real, split_pointer(spot.pointer))};
        }
    }
    Cursor c{f->real, aos::dirname(f->real), split_pointer(spot.pointer), &f->doc};
    for (const std::string& t : c.toks) {
        c.node = child(*c.node, t);
        if (c.node == nullptr) {
            throw Error{code::DirectiveBad, "$ref points nowhere: " + shown(f->real, split_pointer(spot.pointer))};
        }
    }
    chain.push_back(here);
    return c;
}

// 一路穿過單份的 $ref，直到不是 $ref。
Cursor settle(Docs& docs, Cursor c, Chain& chain) {
    while (kind_of(*c.node) == Kind::Ref) {
        auto parts = ref_parts(*c.node);
        if (parts.size() != 1) {
            throw Error{code::TargetBad, shown(c.file, c.toks) + ": $ref array inside a $ref array, not supported by --follow yet"};
        }
        c = fetch(docs, c, parts[0], chain);
    }
    return c;
}

// 穿過 c 這個 $ref。want＝接著要走的那一格（沒有＝停在這裡，要的是值本身）。
static Cursor jump(Docs& docs, const Cursor& c, std::string* want, Chain& chain, bool& merged) {
    auto parts = ref_parts(*c.node);
    if (parts.size() == 1) {
        merged = false;
        return fetch(docs, c, parts[0], chain);
    }
    std::vector<Cursor> cs;
    bool objects = true;
    bool arrays = true;
    for (const std::string& path : parts) {
        Chain mine = chain;
        cs.push_back(settle(docs, fetch(docs, c, path, mine), mine));
        objects = objects && cs.back().node->is_object();
        arrays = arrays && cs.back().node->is_array();
    }
    if (!objects && !arrays) {
        throw Error{code::DirectiveBad, shown(c.file, c.toks) + ": $ref parts cannot be merged (must be all objects or all arrays)"};
    }
    size_t pick = cs.size() - 1;
    if (want != nullptr && objects) {
        for (size_t i = 0; i < cs.size(); ++i) {
            if (cs[i].node->contains(*want)) {
                pick = i;
            }
        }
    }
    if (want != nullptr && arrays && is_index(*want, (size_t)-1)) {
        unsigned long long idx = std::stoull(*want);
        for (size_t i = 0; i < cs.size(); ++i) {
            if (idx < cs[i].node->size()) {
                pick = i;
                *want = std::to_string(idx);
                break;
            }
            idx -= cs[i].node->size();
        }
    }
    merged = true;
    chain.push_back({cs[pick].file, pointer_of(cs[pick].toks)});
    return cs[pick];
}

Located locate(Docs& docs, const Spec& spec, Mode mode) {
    File& f = docs.open(spec.file, false);
    Located out;
    Cursor c{f.real, aos::dirname(f.given), {}, &f.doc};
    Chain chain;
    std::vector<std::string> toks = spec.toks;   // 穿過 $ref 陣列（接陣列）時索引會換算成那一份裡的
    size_t i = 0;
    while (i < toks.size()) {
        Kind k = kind_of(*c.node);
        if ((k == Kind::Ref || k == Kind::Env) && !mode.raw) {
            if (!mode.follow) {
                if (mode.strict) {
                    throw Error{code::FollowMissing, shown(c.file, c.toks) + " is a directive; add --follow to change what it points to, "
                                                     "or point at it directly to replace it whole"};
                }
                Json* lit = child(*c.node, toks[i]);
                if (lit == nullptr) {
                    throw Error{code::PointerMissing, "no such pointer: " + shown(f.real, spec.toks) + " (on the way, " +
                                                          shown(c.file, c.toks) + " is a directive; add --follow to go through it)"};
                }
                c.toks.push_back(toks[i]);
                c.node = lit;
                i += 1;
                continue;
            }
            if (k == Kind::Env) {
                throw Error{code::PointerMissing, shown(c.file, c.toks) + " is $env, which yields a string; cannot go further"};
            }
            out.hops.push_back(c);
            c = jump(docs, c, &toks[i], chain, out.merged);
            continue;
        }
        Json* n = child(*c.node, toks[i]);
        if (n == nullptr) {
            out.rest.assign(toks.begin() + (long)i, toks.end());
            break;
        }
        c.toks.push_back(toks[i]);
        c.node = n;
        out.merged = false;
        i += 1;
    }
    if (out.rest.empty() && mode.follow_final) {
        while (kind_of(*c.node) == Kind::Ref) {
            out.hops.push_back(c);
            c = jump(docs, c, nullptr, chain, out.merged);
        }
    }
    out.at = c;
    out.hops.push_back(c);
    return out;
}

}  // namespace aos::json
