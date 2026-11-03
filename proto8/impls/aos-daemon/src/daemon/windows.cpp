// windows.cpp：【daemon】管轄那一對窗——procs_ctl.json（手把）、procs_state.json（狀態窗）（10-29 拆窗，medium-plan § 四 1；11-03 loops_* 改名 procs_*；說明見 daemon.hpp）。
//
//   read_procs_ctl  每圈讀一次（tend 開頭）。同 aos-loop 的 read_ctl 的不採用規則（N-06～N-08）：認 procs、procs_added、procs_removed、procs_stopped、procs_started、seq，
//                   其他 key 忽略（舊名 loops*／execs* 也是，C-48）；讀到壞的（讀不了、不是 JSON 物件、seq 不是非負整數、名單壞、指示詞解不開、
//                   procs_stopped／procs_started 有 exec 型）整份不採用、維持上一份好的，原因記 pctl_warning_（procs_state 的 ctl_warning）；
//                   讀到好的清回 null；檔不在＝還沒人寫，維持上一份好的、不算問題
//   check_lists     procs、procs_added（read_procs）、procs_removed／procs_stopped／procs_started（名字的陣列）；信也用
//   check_once      procs_stopped／procs_started 的名字是 exec 型（exec 型只有跑和拔，procs § 2c 第 5 條）＝回原因；信也用
//   write_more      procs_state 一份：{ctl_seq, ctl_warning, mailbox_warning（開了信箱才有）, procs, pid, started_at_ticks, boot_id, updated_at}。
//                   Loop 每次 write_state 都呼叫、daemon 表變了也呼叫（flush_table）；有變才寫（11-02）：先組好分檔前的那份（不含 proc_fields、updated_at）
//                   跟上一份寫出去的比，一樣就不碰檔，不一樣才寫分檔→清舊分檔→寫主檔（主檔改名是唯一的提交點）
//   write_parts     procs 表超過 PART_ROWS 列就切檔（10-23 晚）；clean_parts 寫好才清舊分檔
#include "daemon/daemon.hpp"

#include "aos/files.hpp"
#include "aos/proc.hpp"

#include <cerrno>
#include <cstdio>
#include <cstring>
#include <filesystem>

namespace aos::daemon {

static bool is_nat(const Json& v) {   // 非負整數（true／false、小數不算；同 aos-loop）
    return v.is_number_unsigned() || (v.is_number_integer() && v.get<long long>() >= 0);
}

void Daemon::read_procs_ctl() {
    if (pctl_path_.empty()) {
        return;
    }
    int err = 0;
    std::optional<std::string> text = aos::read_file(pctl_path_, err);
    if (!text) {
        if (err != ENOENT) {
            pctl_warning_ = std::string("procs_ctl 讀不了或不是 JSON：") + std::strerror(err);
        }
        return;
    }
    Json doc = Json::parse(*text, nullptr, false);
    if (doc.is_discarded()) {
        pctl_warning_ = "procs_ctl 讀不了或不是 JSON：" + pctl_path_;
        return;
    }
    std::optional<std::string> bad;
    try {   // 指示詞：相對 $ref 從 procs_ctl 所在的資料夾算；解不開＝整份不採用（N-08）
        aos::Resolved r = aos::loop::resolve_keys(doc, aos::dirname(pctl_path_), {"seq"});
        doc = std::move(r.value);
        if (!doc.is_object()) {
            bad = "要是 JSON 物件";
        } else if (doc.contains("seq") && !is_nat(doc["seq"])) {
            bad = "seq 要是非負整數";
        } else {
            bad = check_lists(doc, r);
        }
        if (!bad) {   // exec 型只有跑和拔：procs_stopped／procs_started 裡有 exec 型＝整份不採用（procs § 2c 第 5 條）
            Json merged;
            bad = check_once(doc, ctl_want(doc, merged));
        }
    } catch (const Error& e) {
        bad = "指示詞解不開：" + e.msg;
    }
    if (bad) {
        pctl_warning_ = "procs_ctl 不採用：" + *bad;
        return;
    }
    pctl_good_ = doc;
    pctl_warning_ = nullptr;
}

std::optional<std::string> Daemon::check_lists(Json& doc, const aos::Resolved& where) {
    // procs_ctl 改名單寫壞＝整份不採用（N-08；原因進 procs_state 的 ctl_warning）；信寫壞＝壞信。指示詞解不開丟 DirectiveBad（呼叫者當不採用）。
    for (const char* k : {"procs", "procs_added"}) {
        if (!doc.contains(k)) {
            continue;
        }
        try {
            doc[k] = read_procs(doc[k], where.dir_of(k), k);
        } catch (const Error& e) {
            if (e.code == code::DirectiveBad) {
                throw;
            }
            return e.msg;
        }
    }
    for (const char* k : {"procs_removed", "procs_stopped", "procs_started"}) {
        if (!doc.contains(k)) {
            continue;
        }
        Json rm = aos::resolve(doc[k], where.dir_of(k));
        bool ok = rm.is_array();
        for (const Json& n : rm) {
            ok = ok && n.is_string();
        }
        if (!ok) {
            return std::string(k) + " 要是名字（字串）的陣列";
        }
        doc[k] = rm;
    }
    return std::nullopt;
}

std::optional<std::string> Daemon::check_once(const Json& doc, const Json& want) const {
    for (const char* k : {"procs_stopped", "procs_started"}) {
        if (!doc.contains(k)) {
            continue;
        }
        for (const Json& j : doc[k]) {
            const std::string& n = j.get_ref<const std::string&>();
            if (!want.contains(n)) {
                continue;   // 不在期望表的名字＝不管（procs § 2c 第 6 條）
            }
            auto at = index_.find(n);   // 表上有＝看那列（跑著的是哪種）；不在表上＝看寫法
            bool once = at != index_.end() ? at->second->second.once : is_once(want[n]);
            if (once) {
                return "exec 型 " + aos::dumps(Json(n)) + " 沒有 stop／start（exec 型只有跑和拔）";
            }
        }
    }
    return std::nullopt;
}


static const size_t PART_ROWS = 100;   // procs_state 的 procs 表一份最多幾列（使用者 10-23「每個檔案一百個」；不開 key，C-56）

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

Json Daemon::write_parts(Json rows, std::set<std::string>& now) {
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
        out = Json::object({{"$ref", refs}});   // {"$ref": ["procs_state_procs/<雜湊>.json", …]}：aos-directive 照順序合回整張表
    }
    if (out.is_null()) {
        return rows;   // 沒超過：原樣
    }
    return out;
}

void Daemon::clean_parts(const std::set<std::string>& now) {
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
}

void Daemon::write_more(const Json& me) {
    if (pstate_path_.empty()) {
        return;
    }
    Json rows = Json::object();   // 11-03：一張表（loop 型、exec 型不分）
    // ordered_json 的 rows[n] 每次都逐個比對 key（N 個就 N×N）；名字在表上本來就不重複，直接接在尾巴
    auto& vec = static_cast<std::vector<std::pair<const std::string, Json>>&>(rows.get_ref<Json::object_t&>());
    vec.reserve(table_.size());
    for (auto& [n, c] : table_) {
        vec.emplace_back(n, row(c));
    }
    Json doc = Json::object();
    doc["ctl_seq"] = pctl_good_.contains("seq") ? pctl_good_["seq"] : Json();
    doc["ctl_warning"] = pctl_warning_;
    if (!mbox_path_.empty()) {
        doc["mailbox_warning"] = mailbox_warning_;   // 開了信箱才有：最後一封壞信（11-02 晚原 letter_warning）
    }
    doc["procs"] = rows;
    if (more_wrote_ && doc == last_more_) {
        // 有變才寫（11-02）：表、ctl_seq、ctl_warning、mailbox_warning 都一樣＝不碰檔。上一次寫時留著的「再上一次」的分檔
        // （讀的人可能剛讀了舊主檔）等到這一下（主檔已換過、隔了一次）才清——原本靠下一份心跳清，心跳拿掉後改在這裡
        if (parts_stale_) {
            std::set<std::string> keep = parts_prev_;
            clean_parts(keep);
            parts_stale_ = false;
        }
        return;
    }
    Json key = doc;
    std::set<std::string> now;
    doc["procs"] = write_parts(std::move(rows), now);   // 分檔都寫好才寫主檔（主檔改名是唯一的提交點）
    clean_parts(now);
    for (auto& [k, v] : me.items()) {
        doc[k] = v;
    }
    doc["updated_at"] = aos::utc_now_ms();
    aos::loop::write_window(pstate_path_, doc);
    more_wrote_ = true;
    parts_stale_ = true;
    last_more_ = std::move(key);
}

}  // namespace aos::daemon
