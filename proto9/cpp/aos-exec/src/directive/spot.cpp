// directive/spot.cpp: ref_spot ($ref text to file + pointer), pointer tokens and RefBase::in (split out of proto8 aos-directive src/ref.cpp to keep files under 300 lines).
//
// 寫法（ref_spot，「字串→位置」，只看字面；11-13 晚使用者「他應該是以#作爲json內部尋址的標示」，thinking 2026-11/13/ref-path-rules）：
//    # 左邊一律檔案系統（從 base.dir 算）、右邊一律 json 內部：#/＝本檔根、#./＝所在物件、#../＝上一層；#、#/＝整份。
#include "internal.hpp"

#include <filesystem>

namespace aos {

// 「字串→位置」（說明見 aos/directive.hpp）。只看字面，不讀檔。
std::optional<RefSpot> ref_spot(const std::string& spec, const RefBase& base) {
    auto bad = [&](const std::string& why) -> std::optional<RefSpot> {
        throw Error{code::DirectiveBad, "$ref " + spec + ": " + why};
    };
    if (spec.empty()) {
        return bad("a path must be a non-empty string");
    }
    size_t hash = spec.find('#');
    std::string left = hash == std::string::npos ? spec : spec.substr(0, hash);
    std::string file;
    if (!left.empty()) {
        std::filesystem::path p = left.starts_with("/") ? std::filesystem::path(left) : std::filesystem::path(base.dir.empty() ? "." : base.dir) / left;
        file = p.lexically_normal().string();
        while (file.size() > 1 && file.ends_with("/")) {
            file.pop_back();
        }
    } else if (base.file.empty()) {
        return std::nullopt;   // `#…`＝寫著它的那份檔，但不知道是哪份
    } else {
        file = base.file;
    }
    if (hash == std::string::npos) {
        return RefSpot{file, ""};
    }
    std::string right = spec.substr(hash + 1);
    if (right.empty() || right == "/") {
        return RefSpot{file, ""};   // `#`、`#/`＝整份
    }
    if (right[0] == '/') {
        return RefSpot{file, right};   // RFC 6901，從根起算
    }
    if (right[0] != '.') {
        return bad("after # write /, ./ or ../ (e.g. #/key, #./key, #../key)");
    }
    if (!left.empty()) {
        return bad("#./ and #../ count from the object this $ref is written in, so they cannot follow a file name; write " + left + "#/POINTER");
    }
    std::vector<std::string> segs;
    for (size_t pos = 0;;) {
        size_t next = right.find('/', pos);
        segs.push_back(right.substr(pos, next == std::string::npos ? next : next - pos));
        if (next == std::string::npos) {
            break;
        }
        pos = next + 1;
    }
    size_t i = 0;
    size_t up = 0;
    while (i < segs.size() && (segs[i] == "." || segs[i] == "..")) {
        up += segs[i] == ".." ? 1 : 0;
        ++i;
    }
    if (i == 0) {
        return bad("after # write /, ./ or ../ (e.g. #/key, #./key, #../key)");
    }
    std::vector<std::string> rest(segs.begin() + static_cast<long>(i), segs.end());
    if (rest.size() == 1 && rest[0].empty()) {
        rest.clear();   // `#./`、`#../`＝那個物件整個
    }
    if (!base.placed) {
        return std::nullopt;   // 不知道這一格在檔裡哪裡
    }
    if (base.at.empty()) {
        return bad("the whole file is this $ref, so it sits in no object (#./ and #../ need one)");
    }
    std::vector<std::string> here(base.at.begin(), base.at.end() - 1);   // 所在物件＝這一格的上一層
    if (up > here.size()) {
        return bad("goes above the root of " + file);
    }
    here.resize(here.size() - up);
    std::string ptr;
    for (const std::string& t : here) {
        ptr += "/" + t;
    }
    for (const std::string& t : rest) {
        ptr += "/" + t;
    }
    return RefSpot{file, ptr};
}

std::vector<std::string> pointer_tokens(const std::string& ptr) {
    std::vector<std::string> toks;
    for (size_t pos = 0; pos < ptr.size();) {
        size_t next = ptr.find('/', pos + 1);
        toks.push_back(ptr.substr(pos + 1, next == std::string::npos ? next : next - pos - 1));
        pos = next;
    }
    return toks;
}

std::string token_of(const std::string& key) {
    std::string t;
    for (char c : key) {
        t += c == '~' ? "~0" : c == '/' ? "~1" : std::string(1, c);
    }
    return t;
}

RefBase RefBase::in(const std::string& key) const {
    RefBase b = *this;
    b.at.push_back(token_of(key));
    return b;
}

RefBase RefBase::in(size_t i) const {
    RefBase b = *this;
    b.at.push_back(std::to_string(i));
    return b;
}

}  // namespace aos
