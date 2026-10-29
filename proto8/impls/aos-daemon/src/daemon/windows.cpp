// windows.cpp：【daemon】管轄那一對窗——loops_ctl.json（手把）、loops_state.json（狀態窗）（10-29 拆窗，medium-plan § 四 1；說明見 daemon.hpp）。
//
//   read_loops_ctl  每圈讀一次（tend 開頭）。同 aos-loop 的 read_ctl（N-06～N-08）：認 loops、loops_added、loops_removed、seq，其他 key 忽略；
//                   讀到壞的（讀不了、不是 JSON 物件、seq 不是非負整數、名單壞或撞名、指示詞解不開）整份不採用、維持上一份好的，
//                   原因記 lctl_warning_（loops_state 的 ctl_warning）；讀到好的清回 null；檔不在＝還沒人寫，維持上一份好的、不算問題
//   check_lists     loops、loops_added（read_loops＋撞名）、loops_removed（名字的陣列）；10-29 前是 ctl.json 的 check_ctl
//   write_more      loops_state 一份：{kind, ctl_seq, ctl_warning, loops, 心跳四欄}；Loop 每寫一份 state 就呼叫（心跳同一份值）
//   write_parts     loops 表超過 PART_ROWS 列就切檔（10-23 晚）
#include "daemon/daemon.hpp"

#include "aos/files.hpp"

#include <cerrno>
#include <cstdio>
#include <cstring>
#include <filesystem>

namespace aos::daemon {

static bool is_nat(const Json& v) {   // 非負整數（true／false、小數不算；同 aos-loop）
    return v.is_number_unsigned() || (v.is_number_integer() && v.get<long long>() >= 0);
}

void Daemon::read_loops_ctl() {
    if (lctl_path_.empty()) {
        return;
    }
    int err = 0;
    std::optional<std::string> text = aos::read_file(lctl_path_, err);
    if (!text) {
        if (err != ENOENT) {
            lctl_warning_ = std::string("loops_ctl 讀不了或不是 JSON：") + std::strerror(err);
        }
        return;
    }
    Json doc = Json::parse(*text, nullptr, false);
    if (doc.is_discarded()) {
        lctl_warning_ = "loops_ctl 讀不了或不是 JSON：" + lctl_path_;
        return;
    }
    std::optional<std::string> bad;
    try {   // 指示詞：相對 $ref 從 loops_ctl 所在的資料夾算；解不開＝整份不採用（N-08）
        aos::Resolved r = aos::loop::resolve_keys(doc, aos::dirname(lctl_path_), {"seq"});
        doc = std::move(r.value);
        if (!doc.is_object()) {
            bad = "要是 JSON 物件";
        } else if (doc.contains("seq") && !is_nat(doc["seq"])) {
            bad = "seq 要是非負整數";
        } else {
            bad = check_lists(doc, r);
        }
    } catch (const Error& e) {
        bad = "指示詞解不開：" + e.msg;
    }
    if (bad) {
        lctl_warning_ = "loops_ctl 不採用：" + *bad;
        return;
    }
    lctl_good_ = doc;
    lctl_warning_ = nullptr;
}

std::optional<std::string> Daemon::check_lists(Json& doc, const aos::Resolved& where) {
    // loops_ctl 改名單撞名、寫壞＝整份不採用（N-08；原因進 loops_state 的 ctl_warning）。指示詞解不開丟 DirectiveBad，read_loops_ctl 一樣當不採用。
    const char* lists[2] = {"loops", "loops_added"};
    for (const char* k : lists) {
        if (!doc.contains(k)) {
            continue;
        }
        try {
            doc[k] = read_loops(doc[k], where.dir_of(k), k);
        } catch (const Error& e) {
            if (e.code == code::DirectiveBad) {
                throw;
            }
            return e.msg;
        }
        std::optional<std::string> bad = check_names(doc[k], taken_);
        if (bad) {
            return bad;
        }
    }
    if (doc.contains("loops_removed")) {
        Json rm = aos::resolve(doc["loops_removed"], where.dir_of("loops_removed"));
        bool ok = rm.is_array();
        for (const Json& n : rm) {
            ok = ok && n.is_string();
        }
        if (!ok) {
            return std::string("loops_removed 要是名字（字串）的陣列");
        }
        doc["loops_removed"] = rm;
    }
    return std::nullopt;
}


static const size_t PART_ROWS = 100;   // loops_state 的 loops 表一份最多幾列（使用者 10-23「每個檔案一百個」；不開 key，C-56）

// FNV-1a 64 位元，16 個十六進位字：分檔檔名＝內容的雜湊（內容不變就沿用同一份、不重寫）。
static std::string fnv64(const std::string& text) {
    unsigned long long h = 1469598103934665603ULL;
    for (unsigned char c : text) {
        h ^= c;
        h *= 1099511628211ULL;
    }
    char buf[17];
    std::snprintf(buf, sizeof buf, "%016llx", h);
    return buf;
}

Json Daemon::write_parts(Json rows) {
    std::set<std::string> now;
    Json out;
    if (rows.size() > PART_ROWS) {
        std::error_code ec;
        std::filesystem::create_directories(parts_dir_, ec);
        if (ec) {
            throw Error{code::WriteFailed, "寫不了 " + parts_dir_ + "（" + ec.message() + "）"};
        }
        std::string rel = parts_dir_.substr(parts_dir_.rfind('/') + 1);
        Json refs = Json::array();
        Json page = Json::object();
        auto* vec = &static_cast<std::vector<std::pair<const std::string, Json>>&>(page.get_ref<Json::object_t&>());
        size_t i = 0;
        for (auto& [n, r] : rows.items()) {
            vec->emplace_back(n, r);   // 名字本來就不重複，直接接在尾巴（同 info）
            i += 1;
            if (page.size() == PART_ROWS || i == rows.size()) {
                std::string name = fnv64(aos::dumps(page)) + ".json";
                std::string path = aos::join(parts_dir_, name);
                if (!std::filesystem::exists(path, ec)) {   // 同名＝同內容（先寫 .名字 再改名，所以在就是完整的）
                    aos::loop::write_window(path, page);
                }
                now.insert(name);
                refs.push_back(rel + "/" + name);
                page = Json::object();
                vec = &static_cast<std::vector<std::pair<const std::string, Json>>&>(page.get_ref<Json::object_t&>());
            }
        }
        out = Json::object({{"$ref", refs}});   // {"$ref": ["loops_state_loops/<雜湊>.json", …]}：aos-directive 照順序合回整張表
    }
    // 清舊分檔：留這次與上一次的（磁碟上的主檔現在還指著上一次的）；這個行程第一次寫時不清（上一個行程的主檔可能還指著）。
    if (parts_wrote_ && !parts_dir_.empty()) {
        std::error_code ec;
        std::vector<std::filesystem::path> old;
        for (const auto& e : std::filesystem::directory_iterator(parts_dir_, ec)) {
            std::string f = e.path().filename().string();
            if (now.count(f) == 0 && parts_prev_.count(f) == 0) {
                old.push_back(e.path());
            }
        }
        for (const auto& f : old) {
            std::filesystem::remove(f, ec);
        }
        if (now.empty() && parts_prev_.empty()) {
            std::filesystem::remove(parts_dir_, ec);   // 空了就拿掉（不空就留著，remove 失敗不管）
        }
    }
    parts_prev_ = now;
    parts_wrote_ = true;
    if (out.is_null()) {
        return rows;   // 沒超過：原樣
    }
    return out;
}

void Daemon::write_more(const Json& hb) {
    if (lstate_path_.empty()) {
        return;
    }
    Json rows = Json::object();
    // ordered_json 的 rows[n] 每次都逐個比對 key（N 個就 N×N）；名字在表上本來就不重複，直接接在尾巴
    auto& vec = static_cast<std::vector<std::pair<const std::string, Json>>&>(rows.get_ref<Json::object_t&>());
    vec.reserve(table_.size());
    for (auto& [n, c] : table_) {
        vec.emplace_back(n, row(c));
    }
    Json doc = Json::object();
    doc["kind"] = "state";
    doc["ctl_seq"] = lctl_good_.contains("seq") ? lctl_good_["seq"] : Json();
    doc["ctl_warning"] = lctl_warning_;
    doc["loops"] = write_parts(std::move(rows));   // 分檔都寫好才寫主檔（主檔改名是唯一的提交點）
    for (auto& [k, v] : hb.items()) {
        doc[k] = v;
    }
    aos::loop::write_window(lstate_path_, doc);
}

}  // namespace aos::daemon
