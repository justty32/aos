// classify.cpp：【find】實際的檔 → 種類（說明見 find.hpp）。
//
// 順序（§ 18 ②「有 argv 這個 key＝inst 單子，其餘照 KISS」；10-21 晚 § 6 一路往下）：
//   有 +x 又像程式（is_program：開頭 #! 或 ELF，或整份不是 JSON）＝可執行檔（帶 #/＝EntryBad）。其餘當 JSON 讀（第一行 #! 跳過；
//   不是 JSON＝EntryBad；#/ 指不到＝EntryMissing）。11-10 two-machines：/mnt/c（drvfs 沒 metadata）每個檔都是 0777，光看 +x 會把
//   JSON 入口當程式跑，所以 +x 只是「能 exec」的條件、種類看內容；ext4 上結果不變（+x 的純 JSON 本來就跑不起來）。
//   沒 argv 的物件＝資料夾：進去那一刻 $AOS_ENTRY 是 `.env`＝照做（`.env` 那格當入口、不當環境設定）；否則先套它的 `.env` key、
//   旗標蓋回，再照當下的 $AOS_ENTRY 取那格（沒有＝EntryBad），又是沒 argv 的物件就一路往下（挑的時候不解 $ref，走的是那棵樹）。
//   取到：字串＝轉向（交給下一跳）、物件（有 argv）＝單子、非空陣列＝argv；其他＝EntryBad。
//   繞圈：這條轉向鏈走過的（檔, 指標）再走到＝EntryBad。
#include "find/find.hpp"

#include "env/env.hpp"
#include "aos/util/files.hpp"

#include <cerrno>
#include <cstring>

#include <fcntl.h>
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

bool is_program(const std::string& file) {
    if (access(file.c_str(), X_OK) != 0) {
        return false;
    }
    char head[4] = {0, 0, 0, 0};
    ssize_t n = 0;
    int fd = open(file.c_str(), O_RDONLY | O_CLOEXEC);
    if (fd >= 0) {
        n = read(fd, head, sizeof head);
        close(fd);
    }
    if (n < 0 || fd < 0) {
        return true;   // 讀不了：交給 exec 去說為什麼（照舊）
    }
    if (n >= 2 && head[0] == '#' && head[1] == '!') {
        return true;
    }
    if (n == 4 && head[0] == 0x7f && head[1] == 'E' && head[2] == 'L' && head[3] == 'F') {
        return true;
    }
    int err = 0;
    std::optional<std::string> text = read_file(file, err);
    if (!text) {
        return true;
    }
    return Json::parse(*text, nullptr, false).is_discarded();   // 是 JSON＝不是程式；不是＝沒 #! 的腳本，照舊交 sh
}

static Json read_doc(const std::string& file) {
    int err = 0;
    std::optional<std::string> text = read_file(file, err);
    if (!text) {
        throw Error{code::EntryBad, "cannot read entry: " + file + " (" + std::strerror(err) + ")"};
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
        throw Error{code::EntryBad, "bad entry: not executable (+x) and not JSON: " + file};
    }
    return doc;
}

Classified classify(const std::string& file, const std::string& pointer, Chain& chain, const Layer& layer) {
    std::string spec = file;
    if (!pointer.empty()) {
        spec += "#" + pointer;
    }
    Classified out;
    if (is_program(file)) {
        if (!pointer.empty()) {
            throw Error{code::EntryBad, "bad entry: an executable cannot take #/: " + spec};
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
            throw Error{code::EntryBad, "bad entry: redirect loop: " + loop + key};
        }
    }
    chain.keys.push_back(key);

    Json doc = read_doc(file);
    if (!pointer.empty()) {
        try {
            doc = doc.at(Json::json_pointer(pointer));
        } catch (const nlohmann::json::exception&) {
            throw Error{code::EntryMissing, "entry not found: " + file + "#" + pointer + " (pointer not found)"};
        }
    }
    out.at = pointer;
    while (doc.is_object() && !doc.contains("argv")) {
        std::string here = file;
        if (!out.at.empty()) {
            here += "#" + out.at;
        }
        if (entry_name() != ".env" && doc.contains(".env")) {
            out.names = json_env(doc[".env"], here, aos::RefBase{dirname(file), file}, layer.dotenv_override);   // 只留最後讀的那一份（10-21 ideas § 7）
            out.read_env = true;
            layer.apply();
        }
        std::string name = entry_name();
        if (!doc.contains(name)) {
            throw Error{code::EntryBad, "bad entry: " + here + " is not an inst and has no " + name};
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
        std::string here = file;
        if (!out.at.empty()) {
            here += "#" + out.at;
        }
        throw Error{code::EntryBad, "bad entry: " + here + " is not an inst, an argv array or a path"};
    }
    out.doc = doc;
    return out;
}

}  // namespace aos::exec
