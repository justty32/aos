// classify.cpp：【find】實際的檔 → 種類（說明見 find.hpp）。對應 proto8/bin/aos-exec 的 find。
//
// 順序（§ 18 ②「有 argv 這個 key＝inst 單子，其餘照 KISS」；10-21 晚 § 6 一路往下）：
//   有 +x＝可執行檔（不讀內容；帶 #/＝EntryBad）。沒 +x 當 JSON 讀（第一行 #! 跳過；不是 JSON＝EntryBad；#/ 指不到＝EntryMissing）。
//   沒 argv 的物件＝資料夾：進去那一刻 $AOS_ENTRY 是 `.env`＝照做（`.env` 那格當入口、不當環境設定）；否則先套它的 `.env` key、
//   旗標蓋回，再照當下的 $AOS_ENTRY 取那格（沒有＝EntryBad），又是沒 argv 的物件就一路往下（挑的時候不解 $ref，走的是那棵樹）。
//   取到：字串＝轉向（交給下一跳）、物件（有 argv）＝單子、非空陣列＝argv；其他＝EntryBad。
//   繞圈：這條轉向鏈走過的（檔, 指標）再走到＝EntryBad。
#include "find/find.hpp"

#include "env/env.hpp"
#include "aos/files.hpp"

#include <cerrno>
#include <cstring>

#include <unistd.h>

namespace aos::exec {

// JSON pointer 的一段：~ → ~0、/ → ~1（RFC 6901）
static std::string escape(const std::string& key) {
    std::string out;
    for (char c : key) {
        if (c == '~') {
            out += "~0";
        } else if (c == '/') {
            out += "~1";
        } else {
            out += c;
        }
    }
    return out;
}

static Json read_doc(const std::string& file) {
    int err = 0;
    std::optional<std::string> text = read_file(file, err);
    if (!text) {
        throw Error{code::EntryBad, "入口讀不到：" + file + "（" + std::strerror(err) + "）"};
    }
    if (text->starts_with("#!")) {
        size_t nl = text->find('\n');
        if (nl == std::string::npos) {
            text->clear();
        } else {
            text->erase(0, nl);
        }
    }
    Json doc = Json::parse(*text, nullptr, false);
    if (doc.is_discarded()) {
        throw Error{code::EntryBad, "入口壞：沒有 +x、也不是 JSON：" + file};
    }
    return doc;
}

Classified classify(const std::string& file, const std::string& pointer, Chain& chain, const Layer& layer) {
    std::string spec = file;
    if (!pointer.empty()) {
        spec += "#" + pointer;
    }
    Classified out;
    if (access(file.c_str(), X_OK) == 0) {
        if (!pointer.empty()) {
            throw Error{code::EntryBad, "入口壞：可執行檔不能帶 #/：" + spec};
        }
        out.kind = Kind::Executable;
        return out;
    }
    std::string key = file + "#" + pointer;
    for (const std::string& k : chain.keys) {
        if (k == key) {
            std::string loop;
            for (const std::string& seen : chain.keys) {
                loop += seen + " → ";
            }
            throw Error{code::EntryBad, "入口壞：字串轉向繞圈：" + loop + key};
        }
    }
    chain.keys.push_back(key);

    Json doc = read_doc(file);
    if (!pointer.empty()) {
        try {
            doc = doc.at(Json::json_pointer(pointer));
        } catch (const nlohmann::json::exception&) {
            throw Error{code::EntryMissing, "入口不存在：" + file + "#" + pointer + " 指不到"};
        }
    }
    out.at = pointer;
    while (doc.is_object() && !doc.contains("argv")) {
        std::string here = file;
        if (!out.at.empty()) {
            here += "#" + out.at;
        }
        if (entry_name() != ".env" && doc.contains(".env")) {
            out.names = json_env(doc[".env"], here, dirname(file), layer.dotenv_override);   // 只留最後讀的那一份（10-21 ideas § 7）
            out.read_env = true;
            layer.apply();
        }
        std::string name = entry_name();
        if (!doc.contains(name)) {
            throw Error{code::EntryBad, "入口壞：" + here + " 不是單子、也沒有 " + name};
        }
        Json next = doc[name];
        doc = next;
        out.at += "/" + escape(name);
    }
    if (doc.is_string()) {
        out.kind = Kind::Redirect;
    } else if (doc.is_object()) {
        out.kind = Kind::Inst;
    } else if (doc.is_array() && !doc.empty()) {
        out.kind = Kind::Argv;
    } else {
        throw Error{code::EntryBad, "入口壞：" + file + " 不是單子、argv 陣列或路徑"};
    }
    out.doc = doc;
    return out;
}

}  // namespace aos::exec
