// send.cpp：【send】找信箱、寄信（說明見 send.hpp）。
#include "send/send.hpp"

#include "aos/cli.hpp"
#include "aos/directive.hpp"
#include "aos/files.hpp"

#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>

extern char** environ;

namespace fs = std::filesystem;

namespace aos::gate {

Mailbox mailbox() {
    const char* k = std::getenv("AOS_KERNEL");
    if (k == nullptr || k[0] == '\0') {
        throw Error{code::MailboxMissing, "沒設定 AOS_KERNEL（kernel 的信箱資料夾）"};
    }
    std::error_code ec;
    if (!fs::is_directory(k, ec)) {
        throw Error{code::MailboxMissing, std::string("AOS_KERNEL 指的信箱不在：") + k};
    }
    return Mailbox{aos::abspath(k)};
}

static void make_dir(const std::string& dir) {
    std::error_code ec;
    fs::create_directories(dir, ec);
    if (ec || !fs::is_directory(dir)) {
        throw Error{code::MkdirFailed, "建不了 " + dir + (ec ? "：" + ec.message() : "")};
    }
}

std::string post(const Mailbox& mb, const std::string& spec) {
    // 1. 單子在哪
    aos::Spec s = aos::split_hash(spec);
    std::error_code ec;
    std::string cf = aos::abspath(s.path);
    fs::path real = fs::canonical(s.path, ec);   // 解開捷徑（同 aos-exec 的 AOS_CF）
    if (!ec) {
        cf = real.string();
    }
    std::string cd = aos::dirname(cf);
    setenv("AOS_CF", cf.c_str(), 1);
    setenv("AOS_CD", cd.c_str(), 1);
    setenv("AOS_CO", s.pointer.c_str(), 1);

    // 2. 讀、解指示詞
    Json doc = aos::load_cfg(spec);
    doc = aos::resolve(doc, cd);
    if (!doc.is_object()) {
        throw Error{code::CfgBad, spec + " 要是一張單子（JSON 物件），不是 " + aos::dumps(doc)};
    }
    // 3. priority
    Json priority = doc.value("priority", Json());
    aos::kernel_llm::parse_priority(priority);
    // 4. cwd 轉絕對
    Json cwd = doc.value("cwd", Json());
    if (cwd.is_null()) {
        doc["cwd"] = cd;
    } else if (cwd.is_string()) {
        doc["cwd"] = aos::abspath(aos::join(cd, cwd.get<std::string>()));
    }   // 其他型別原樣交過去，由 kernel 那邊的 run_inst 回 EntryBad
    // 5. 信
    Json env = Json::object();
    for (char** e = environ; *e != nullptr; ++e) {
        std::string kv = *e;
        size_t eq = kv.find('=');
        if (eq != std::string::npos) {
            env[kv.substr(0, eq)] = kv.substr(eq + 1);
        }
    }
    Json letter = Json::object();
    letter["inst"] = doc;
    letter["env"] = env;
    letter["priority"] = priority;

    make_dir(mb.tmp());
    make_dir(mb.fresh());
    std::string id = aos::kernel_llm::letter_id();
    std::string t = aos::join(mb.tmp(), id);
    make_dir(t);
    std::optional<std::string> err = aos::write_json(aos::join(t, "letter.json"), letter);
    if (err) {
        fs::remove_all(t, ec);
        throw Error{code::WriteFailed, *err};
    }
    std::string n = aos::join(mb.fresh(), id);
    if (std::rename(t.c_str(), n.c_str()) != 0) {
        int e = errno;
        fs::remove_all(t, ec);
        throw Error{code::WriteFailed, "改名不了 " + t + " → " + n + "：" + std::strerror(e)};
    }
    return id;
}

}  // namespace aos::gate
