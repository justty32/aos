// windows.cpp：【daemon】管轄手把 procs_ctl 與有變才寫的 procs_state 狀態窗（說明見 daemon.hpp）。
//
//   read_procs_ctl  每圈讀一次（tend 開頭）。同 aos-loop 的 read_ctl 的不採用規則（N-06～N-08）：認 procs、procs_added、procs_removed、procs_stopped、procs_started、seq，
//                   其他 key 忽略（舊名 loops*／execs* 也是，C-48）；讀到壞的（讀不了、不是 JSON 物件、seq 不是非負整數、名單壞、指示詞解不開、
//                   ）整份不採用、維持上一份好的，原因記 pctl_warning_（state_flux 的 procs_ctl_warning）；
//                   讀到好的清回 null，跟上一份好的不同才更新 state_flux 的 responded_at；檔不在＝回初始值、不算問題
//   check_lists     procs、procs_added（read_procs）、procs_removed／procs_stopped／procs_started（名字的陣列）；信也用
//   flux_more       daemon 的回音：procs_ctl_seq、procs_ctl_warning、adopt_warning、mailbox_warning（開了信箱才有）。
//   write_more      procs_state 一份：{procs_loop, procs_exec, procs_stderr, procs_ctl_mailbox,
//                   daemon, procs, pid, started_at_ticks, boot_id, updated_at}；
//                   Loop 每次 write_state 都呼叫、daemon 表變了也呼叫（flush_table）；有變才寫（11-02）：先組好分檔前的那份（不含 proc_fields、updated_at）
//                   跟上一份寫出去的比，一樣就不碰檔，不一樣才寫分檔→清舊分檔→寫主檔（主檔改名是唯一的提交點）
//   write_parts     procs 表超過 PART_ROWS 列就切檔（10-23 晚）；clean_parts 寫好才清舊分檔
#include "daemon/daemon.hpp"

#include "aos/util/files.hpp"
#include "aos/util/proc.hpp"

#include <cerrno>
#include <cstdio>
#include <cstring>
#include <filesystem>

namespace aos::daemon {

void Daemon::read_procs_ctl() {
    if (pctl_path_.empty()) {
        return;
    }
    int err = 0;
    std::optional<std::string> text = aos::read_file(pctl_path_, err);
    if (!text) {
        if (err != ENOENT) {
            pctl_warning_ = std::string("procs_ctl: cannot read or not JSON: ") + std::strerror(err);
        } else {
            // 11-05 第二輪：檔不在＝什麼都沒宣告＝回初始值（N-06「沒寫的欄位＝回初始值，不是維持上一版」）。原本沿用最後一份好的：
            // 刪掉 procs_ctl.json，它的 procs_added 照留、rm 的信照被蓋回去，前一份 state_flux 的 procs_ctl_warning 也一直掛著
            pctl_good_ = Json::object();
            pctl_warning_ = nullptr;
        }
        return;
    }
    Json doc = Json::parse(*text, nullptr, false);
    if (doc.is_discarded()) {
        pctl_warning_ = "procs_ctl: cannot read or not JSON: " + pctl_path_;
        return;
    }
    std::optional<std::string> bad;
    try {   // 指示詞：相對 $ref 從 procs_ctl 所在的資料夾算；解不開＝整份不採用（N-08）
        aos::Resolved r = aos::loop::resolve_keys(doc, aos::dirname(pctl_path_), {"seq"});
        doc = std::move(r.value);
        if (!doc.is_object()) {
            bad = "must be a JSON object";
        } else if (doc.contains("seq") && !aos::is_count(doc["seq"])) {
            bad = "seq must be a non-negative integer";
        } else {
            bad = check_lists(doc, r);
        }
    } catch (const Error& e) {
        bad = "cannot resolve directives: " + e.msg;
    }
    if (bad) {
        pctl_warning_ = "procs_ctl rejected: " + *bad;
        return;
    }
    if (doc != pctl_good_) {
        responded();
    }
    pctl_good_ = doc;
    pctl_warning_ = nullptr;
}

std::optional<std::string> Daemon::check_lists(Json& doc, const aos::Resolved& where) {
    // procs_ctl 改名單寫壞＝整份不採用（N-08；原因進 state_flux 的 procs_ctl_warning）；信寫壞＝壞信。指示詞解不開丟 DirectiveBad（呼叫者當不採用）。
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
    for (const char* k : {"procs_removed", "procs_stopped", "procs_started", "procs_slept", "procs_woken"}) {
        if (!doc.contains(k)) {
            continue;
        }
        Json rm = aos::resolve(doc[k], where.dir_of(k));
        bool ok = rm.is_array();
        for (const Json& n : rm) {
            ok = ok && n.is_string();
        }
        if (!ok) {
            return std::string(k) + " must be an array of names (strings)";
        }
        doc[k] = rm;
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
            throw Error{code::WriteFailed, "cannot write " + parts_dir_ + " (" + ec.message() + ")"};
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
    if (!adopt_warning_.is_null()) {
        return;   // 留證的主檔可能還指著舊分檔；這一班不清分檔，避免破壞證據。
    }
    // 清舊分檔：留這次與上一次的（磁碟上的主檔現在還指著上一次的）；這個行程第一次寫時不清（上一個行程的主檔可能還指著）。
    // 11-05 第二輪：不在這兩次裡的先「退役」，退役滿 PARTS_KEEP_MS 才刪——daemon 一秒寫好幾次表時，讀的人剛讀到的主檔可能已是兩次以前的，
    // 原本它指的分檔已經刪了（aos-daemon-ctl ls 偶發 StateBad「No such file」）。
    if (parts_wrote_ && !parts_dir_.empty()) {
        static const auto PARTS_KEEP = std::chrono::milliseconds(2000);
        auto t = std::chrono::steady_clock::now();
        std::error_code ec;
        std::vector<std::filesystem::path> old;
        for (const auto& e : std::filesystem::directory_iterator(parts_dir_, ec)) {
            std::string f = e.path().filename().string();
            if (now.count(f) > 0 || parts_prev_.count(f) > 0) {
                retired_.erase(f);
                continue;
            }
            auto at = retired_.find(f);
            if (at == retired_.end()) {
                retired_.emplace(f, t);
            } else if (t - at->second >= PARTS_KEEP) {
                old.push_back(e.path());
                retired_.erase(at);
            }
        }
        for (const auto& f : old) {
            std::filesystem::remove(f, ec);
        }
        if (now.empty() && parts_prev_.empty() && retired_.empty()) {
            std::filesystem::remove(parts_dir_, ec);   // 空了就拿掉（不空就留著，remove 失敗不管）
        }
    }
    parts_prev_ = now;
    parts_wrote_ = true;
}

Json Daemon::flux_more() {
    Json doc = Json::object();
    doc["procs_ctl_seq"] = pctl_good_.contains("seq") ? pctl_good_["seq"] : Json();
    doc["procs_ctl_warning"] = pctl_warning_;
    doc["adopt_warning"] = adopt_warning_;
    if (!mbox_path_.empty()) {
        doc["mailbox_warning"] = mailbox_warning_;
    }
    return doc;
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
        vec.emplace_back(n, row(c, dstack_));
    }
    Json doc = Json::object();
    // 11-04（four-elements 題 6、題 5 後半）：回報小格裡三個檔名與信箱名（null＝沒開），讀小格的人（aos-daemon-ctl、aos-agent）從這裡拿、不寫死；欄名＝key 名
    doc["procs_loop"] = names_.loop;
    doc["procs_exec"] = names_.exec;
    doc["procs_stderr"] = names_.err;
    doc["procs_ctl_mailbox"] = mbox_path_.empty() ? Json() : Json(mbox_name_);
    doc["daemon"] = parent_;
    doc["procs"] = rows;
    if (more_wrote_ && doc == last_more_) {
        // 有變才寫：表、公開檔名、daemon 都一樣＝不碰檔。上一次寫時留著的「再上一次」的分檔
        // （讀的人可能剛讀了舊主檔）等到這一下（主檔已換過、隔了一次）才清——原本靠下一份心跳清，心跳拿掉後改在這裡
        if (parts_stale_) {
            std::set<std::string> keep = parts_prev_;
            clean_parts(keep);
            parts_stale_ = !retired_.empty();   // 還有退役沒滿時間的：之後沒變的那幾下接著清
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
