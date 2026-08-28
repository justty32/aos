#define _POSIX_C_SOURCE 200809L

// handoff 層的彙整動作：把收件匣裡的投遞攤平成一批、排他發布成 base，並在批旁邊
// 維護 header sidecar（§C-8）。取件／釋放／兩個 to_string 在 handoff.cpp。
// 路徑推導與低階檔案存取在 handoff_fs.hpp／.cpp，header 的編解在 handoff_header.*。
// 只依賴 inst＋format：不印訊息、不執行 instruction。
//
// 發布順序（§D-5）與各步驟的理由集中寫在 aggregate_instructions 裡；為什麼 header
// 仍然排在批前面、排他發布的落敗者留下什麼，見 docs/handoff.md。

#include <aos/inst.hpp>

#include "handoff_fs.hpp"
#include "handoff_header.hpp"

#include <algorithm>
#include <cerrno>
#include <cstddef>
#include <cstdio>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <dirent.h>
#include <sys/stat.h>
#include <unistd.h>

namespace aos {
namespace {

// add_issue／sync_directory 在 handoff.cpp 也有一份同樣的小 helper。它們要同時碰
// HandoffResult（公開型別）與 detail::fsync_dir（內部標頭），放不進 handoff_fs
// ——那個檔刻意不認識 HandoffResult——所以就讓兩個 .cpp 各留一份四行的私有複本，
// 不為此多開一個內部標頭。
void add_issue(HandoffResult &result, HandoffIssueKind kind,
               const std::string &path, InstState state, int error) {
    result.issues.push_back(HandoffIssue{kind, path, state, error});
}

// rename／unlink 之後把目錄項落盤（§D-5）。失敗只記 issue、不改變控制流：目錄項
// 本身已經換好了，少的是耐久性保證；為此讓整輪彙整失敗只會把世界卡住，更糟。
bool sync_directory(const std::string &directory, HandoffResult &result) {
    int error = 0;
    if (detail::fsync_dir(directory, error)) return true;
    add_issue(result, HandoffIssueKind::DirectorySyncFailed, directory,
              InstState::Ok, error);
    return false;
}

// opendir 與 closedir 之間有會配置記憶體的操作（std::string、push_back），而
// aggregate_instructions 不是 noexcept：例外穿出去時要保證 DIR* 與它的 fd 不洩漏
// （#18）。成功路徑仍然顯式 closedir 並檢查回傳值，guard 只在還沒顯式關掉時才關。
struct DirGuard {
    DIR *handle = nullptr;
    ~DirGuard() {
        if (handle != nullptr) closedir(handle);
    }
    int close() {
        DIR *const closing = handle;
        handle = nullptr;
        return closedir(closing);
    }
};

// 隔離一份**內容無效**的投遞（§D-4）。`.bad` 只給內容無效用（§B-1 的定義），
// 讀不到的投遞不走這裡（#8）。
// 排他發布：既有的 `.bad` 絕不覆蓋——§D-8 說彙整者 MUST NOT 自動刪 `.bad`，
// 而覆寫等同刪除，那會把上一份鑑識證據無聲銷毀（#7）。
void isolate_delivery(const std::string &path, const std::string &inbox,
                      HandoffResult &result) {
    int error = 0;
    if (detail::publish_exclusive(path, path + ".bad", error)) {
        sync_directory(inbox, result);  // #17：隔離也要把目錄項落盤
        return;
    }
    if (error != EEXIST) {
        add_issue(result, HandoffIssueKind::IsolationFailed, path, InstState::Ok,
                  error);
        return;
    }
    // 撞到既有的 `.bad`（前提是 pid 重用之後又撞名，§D-2）：換一個仍然符合 §B-1
    // 的唯一名再試一次，x.json → x-4711-3.json.bad。
    const std::string unique = detail::unique_bad_path(path);
    if (detail::publish_exclusive(path, unique, error)) {
        sync_directory(inbox, result);
        return;
    }
    add_issue(result, HandoffIssueKind::IsolationFailed, path, InstState::Ok,
              error);
}

// 刪掉本輪收下的投遞並把目錄項落盤。回傳「全數刪成功**且**目錄 fsync 成功」——
// 只有這時候才有資格把 header 標成 swept：有任何一個沒成功就代表殘留還在，
// 去重還要擋（§C-8）。
bool remove_accepted_deliveries(const std::vector<std::string> &accepted,
                                const std::string &inbox,
                                HandoffResult &result) {
    if (accepted.empty()) return false;
    bool removed = true;
    for (const std::string &path : accepted) {
        if (unlink(path.c_str()) != 0) {
            add_issue(result, HandoffIssueKind::DeliveryRemoveFailed, path,
                      InstState::Ok, errno);
            removed = false;
        }
    }
    return sync_directory(inbox, result) && removed;
}

// 現任 header 的兩個欄位。沒有 header、讀不到或讀不懂都回 false（後兩者記 issue），
// 呼叫端一律當作「沒有可比對的 id」，照常發布。
bool current_header(const std::string &path, detail::HeaderFields &fields,
                    HandoffResult &result) {
    std::string document;
    int error = 0;
    if (!detail::read_file(path, document, error)) {
        if (error != ENOENT) {
            add_issue(result, HandoffIssueKind::HeaderInvalid, path,
                      InstState::Ok, error);
        }
        return false;
    }
    if (!detail::decode_header(document, fields)) {
        add_issue(result, HandoffIssueKind::HeaderInvalid, path, InstState::Ok,
                  0);
        return false;
    }
    return true;
}

// 把 header 改寫成 swept:true（§C-8）：上一批的清理已經走完，去重 MUST NOT 再擋
// 任何投遞——同名同內容的**全新**投遞照常發布（#1）。
// 寫不成只記 issue 續行（不致命）：代價是下一輪少一次去重保證，跟 header 本身
// 寫不成同一個等級。
void mark_header_swept(const detail::HeaderPaths &header, const std::string &id,
                       const std::string &directory, HandoffResult &result) {
    const std::string temp = detail::unique_temp_path(header.base);
    int error = 0;
    if (!detail::write_file(temp, detail::encode_header(id, true), error)) {
        add_issue(result, HandoffIssueKind::HeaderWriteFailed, temp,
                  InstState::Ok, error);
        unlink(temp.c_str());
        return;
    }
    if (rename(temp.c_str(), header.base.c_str()) != 0) {
        add_issue(result, HandoffIssueKind::HeaderWriteFailed, header.base,
                  InstState::Ok, errno);
        unlink(temp.c_str());
        return;
    }
    sync_directory(directory, result);
}

// 以 .json 結尾、但形狀不合 is_delivery_name 的名字（a.b.json／.hidden.json／
// .json）：不收、不隔離，只出聲（#10）。x.json.temp／.bad／.runi 是狀況檔，
// 不以 .json 結尾，不會命中這裡，也就不會吵。
bool looks_like_json(const std::string &name) {
    constexpr std::string_view suffix = ".json";
    return name.size() >= suffix.size() &&
           name.compare(name.size() - suffix.size(), suffix.size(), suffix) == 0;
}

enum class ListOutcome { Ok, Missing, Failed };

// 列出收件匣裡算數的投遞名（排序後），順便對「以 .json 結尾卻形狀不合」的名字記
// DeliveryNameIgnored（#10）。收件匣不存在回 Missing——那是成功的 no-op，不是錯誤。
ListOutcome list_deliveries(const std::string &inbox,
                            std::vector<std::string> &names,
                            HandoffResult &result) {
    DirGuard guard;
    guard.handle = opendir(inbox.c_str());
    if (guard.handle == nullptr && errno == ENOENT) return ListOutcome::Missing;
    if (guard.handle == nullptr) {
        result.path = inbox;
        result.error = errno;
        return ListOutcome::Failed;
    }

    std::vector<std::string> ignored;
    errno = 0;
    while (dirent *entry = readdir(guard.handle)) {
        std::string name = entry->d_name;
        if (detail::is_delivery_name(name)) {
            names.push_back(std::move(name));
        } else if (looks_like_json(name)) {
            ignored.push_back(std::move(name));
        }
        errno = 0;
    }
    const int read_error = errno;
    const int close_error = guard.close() == 0 ? 0 : errno;
    if (read_error != 0 || close_error != 0) {
        result.path = inbox;
        result.error = read_error != 0 ? read_error : close_error;
        return ListOutcome::Failed;
    }
    // 目錄順序不保證（§D-4），排序讓批的內容與 issue 的順序都是確定的。
    std::sort(names.begin(), names.end());
    std::sort(ignored.begin(), ignored.end());
    for (const std::string &name : ignored) {
        add_issue(result, HandoffIssueKind::DeliveryNameIgnored,
                  detail::join_path(inbox, name), InstState::Ok, 0);
    }
    return ListOutcome::Ok;
}

// roll-forward 的錨：掃 base 所在目錄，找出**位元組跟本輪 output 完全相同**的兄弟
// 唯一暫存。兄弟＝檔名以 `<stem>-` 開頭、以 `.json.temp` 結尾（base 是
// `.aos/inst.json` 時 stem ＝ `inst`，所以找 `.aos/inst-*.json.temp`）；
// `<stem>-head-` 開頭的跳過——那是 header 的唯一 temp，位元組比對本來也會擋掉，
// 明著跳過比較便宜也比較好讀。名字排序後逐一讀，第一個對上的就是錨。
//
// **身分由內容決定，名字只是找得到它的索引**（跟 #21 的逐位元比對同一個原則）。
// 能通過比對的檔，內容就一定是「本輪這組投遞的 canonical 批」——不管它是我們自己
// 上一次崩掉留下的，還是併發同儕正在飛的：兩者是同一串位元組，誰把它 rename 到
// base 都是同一個結果，輸的那一邊拿 EEXIST 乾淨放棄。
//
// 這是刻意不用「固定 `.temp` 槽位」的原因：共用可變狀態會讓兩個彙整者互相覆蓋
// 對方寫進槽位的批，於是 A 可能發布 B 的批、卻只清掉 A 自己看到的那幾份投遞，
// 剩下的在下一輪被重新彙整＝重複執行。詳見 docs/handoff.md。
bool find_rollforward_anchor(const std::string &directory,
                             const std::string &stem, const std::string &output,
                             std::string &anchor) {
    DirGuard guard;
    guard.handle = opendir(directory.c_str());
    if (guard.handle == nullptr) return false;

    const std::string prefix = stem + "-";
    const std::string header_prefix = stem + "-head-";
    constexpr std::string_view suffix = ".json.temp";
    std::vector<std::string> candidates;
    while (dirent *entry = readdir(guard.handle)) {
        std::string name = entry->d_name;
        if (name.size() <= prefix.size() + suffix.size()) continue;
        if (name.compare(0, prefix.size(), prefix) != 0) continue;
        if (name.compare(0, header_prefix.size(), header_prefix) == 0) continue;
        if (name.compare(name.size() - suffix.size(), suffix.size(), suffix) !=
            0) {
            continue;
        }
        candidates.push_back(std::move(name));
    }
    std::sort(candidates.begin(), candidates.end());

    for (const std::string &name : candidates) {
        const std::string path = detail::join_path(directory, name);
        std::string committed;
        int error = 0;
        if (detail::read_file(path, committed, error) && committed == output) {
            anchor = path;
            return true;
        }
    }
    return false;
}

const HandoffIssue *find_issue(const HandoffResult &result,
                               HandoffIssueKind kind) {
    for (const HandoffIssue &issue : result.issues) {
        if (issue.kind == kind) return &issue;
    }
    return nullptr;
}

}  // namespace

HandoffState aggregate_instructions(const std::string &instruction_path,
                                    HandoffResult &result) {
    result = HandoffResult{};
    detail::HandoffPaths paths;
    detail::HeaderPaths header;
    if (!detail::derive_paths(instruction_path, paths) ||
        !detail::derive_header_paths(instruction_path, header)) {
        return HandoffState::InvalidArgument;
    }
    const std::string base_directory = detail::parent_directory(paths.base);
    // 兄弟唯一暫存的名字前綴：base 是 `.aos/inst.json` 時 stem ＝ `inst`，
    // 兄弟就是 `.aos/inst-*.json.temp`。derive_paths 已保證 base 以 .json 結尾。
    const std::string base_name =
        paths.base.substr(paths.base.find_last_of('/') + 1);
    const std::string stem =
        base_name.substr(0, base_name.size() - std::string_view(".json").size());

    // ⓪ base 已經有一份沒被取走：本輪 MUST NOT 發布（§D-4），不覆蓋也不碰 inbox。
    // 這裡用 lstat（不跟隨 symlink）；claim_instruction 對「存在」的定義必須跟這裡
    // 對齊，見那邊的 #25 註解。
    struct stat status {};
    if (lstat(paths.base.c_str(), &status) == 0) return HandoffState::Ok;
    if (errno != ENOENT) {
        result.path = paths.base;
        result.error = errno;
        return HandoffState::InstructionReadFailed;
    }

    // ① 掃收件匣。
    std::vector<std::string> names;
    const ListOutcome listed = list_deliveries(paths.inbox, names, result);
    if (listed != ListOutcome::Ok) {
        return listed == ListOutcome::Missing ? HandoffState::Ok
                                              : HandoffState::InboxReadFailed;
    }

    std::vector<inst_t> combined;
    std::vector<std::string> accepted;
    detail::BatchDigest digest;
    for (const std::string &name : names) {
        const std::string path = detail::join_path(paths.inbox, name);

        // 開檔之前先確認是普通檔（#3）。stat 跟隨 symlink，與 read_file 的 open
        // 同語意。沒有寫端的 FIFO 會讓 open 永久阻塞——那發生在取件之前，世界既
        // 沒被鎖也沒有任何診斷輸出，整台機器就這樣停擺。非普通檔一律跳過不讀、
        // 也不隔離（它不是「內容無效」，是根本不該讀），只出聲。
        struct stat entry_status {};
        if (stat(path.c_str(), &entry_status) != 0) {
            // ENOENT：檔在我們掃完目錄之後被別人清掉了，正常，靜默跳過（#8）。
            if (errno != ENOENT) {
                add_issue(result, HandoffIssueKind::DeliveryReadFailed, path,
                          InstState::Ok, errno);
            }
            continue;
        }
        if (!S_ISREG(entry_status.st_mode)) {
            add_issue(result, HandoffIssueKind::DeliveryNotRegular, path,
                      InstState::Ok, 0);
            continue;
        }

        std::string document;
        int error = 0;
        if (!detail::read_file(path, document, error)) {
            // 讀不到 ≠ 內容無效（#8）。一次暫時性的 EACCES／EIO 不該讓一份合法的
            // 工作被貼上 `.bad` 永久出局（`.bad` 不進彙整、又 MUST NOT 自動清）。
            // 留在原地、下一輪再試。
            if (error != ENOENT) {
                add_issue(result, HandoffIssueKind::DeliveryReadFailed, path,
                          InstState::Ok, error);
            }
            continue;
        }

        std::vector<inst_t> delivery;
        std::size_t error_record = 0;
        const char empty = '\0';
        const char *data = document.empty() ? &empty : document.data();
        const InstState state =
            read_all(data, document.size(), delivery, &error_record);
        if (state != InstState::Ok) {
            add_issue(result, HandoffIssueKind::InvalidDelivery, path, state, 0);
            isolate_delivery(path, paths.inbox, result);
            continue;
        }
        for (inst_t &instruction : delivery) {
            combined.push_back(std::move(instruction));
        }
        accepted.push_back(path);
        digest.add(name, document);
    }

    // ② 整批為空：沒有東西要發布，但投遞還是要清掉（§D-4 的三個例外之一），
    // 否則空投遞會永遠留在收件匣、每一輪被重新讀取。沒有批就沒有 header。
    if (combined.empty()) {
        remove_accepted_deliveries(accepted, paths.inbox, result);
        return HandoffState::Ok;
    }

    // ③ canonical 位元組提前算出來：去重分支要拿它跟兄弟暫存逐位元比對（#21）。
    const std::string id = digest.id();
    std::string output;
    if (write_all(combined, output, nullptr) != InstState::Ok) {
        result.path = paths.base;
        result.error = EINVAL;
        return HandoffState::PublishWriteFailed;
    }

    // ④／⑤ 去重（§D-6）。閘門是 swept（§C-8）：只有現任 header 的 swept 不成立
    // 才啟用比對——swept 成立代表上一批的清理已經走完，那時同名同內容的投遞是
    // 全新的一批，MUST 照常發布（#1）。id 相同 ＋ 未 swept ＝ 這一組投遞上一輪
    // 已經跨過提交點（header 的 rename），只是投遞沒被清掉。
    detail::HeaderFields current;
    if (current_header(header.base, current, result) && !current.swept &&
        current.id == id) {
        // roll-forward 的前提不是「某個 .temp 解析得出一批」，而是**位元組逐位元
        // 等於本輪重算的結果**（#21）：canonical 位元組是確定性的（§D-3），所以
        // 這個比對就足以證明「那一份正是這一組投遞的批」。只檢查「解析得出非空
        // 批次」的話，一份與這批毫無關係的殘骸會被扶正並執行掉。
        std::string anchor;
        if (find_rollforward_anchor(base_directory, stem, output, anchor)) {
            int error = 0;
            if (detail::publish_exclusive(anchor, paths.base, error)) {
                sync_directory(base_directory, result);
                result.published = true;
            } else if (error == EEXIST) {
                // 別的彙整者先發布了：本輪放棄（§D-5 的排他發布）。不清投遞、
                // 不重寫 header。**也不 unlink 那個錨**——它不見得是我們的檔，
                // 可能是同儕正在飛的那一份。
                return HandoffState::Ok;
            } else {
                result.path = anchor;
                result.error = error;
                return HandoffState::RenameFailed;
            }
        }
        // 找不到錨：上一輪已經發布完，批也已經被取走（或正在跑）。
        // 只清投遞、不重發——這正是「同一批不會執行兩次」的兜底。
        if (remove_accepted_deliveries(accepted, paths.inbox, result)) {
            mark_header_swept(header, id, base_directory, result);
        }
        return HandoffState::Ok;
    }

    // ⑥a 唯一名寫批（§D-5）：唯一名保證兩個彙整者不會共寫同一個檔。這一份就是
    // 最後要被 rename 成 base 的那一個——**沒有中間的共用槽位**。
    const std::string batch_temp = detail::unique_temp_path(paths.base);
    int error = 0;
    if (!detail::write_file(batch_temp, output, error)) {
        unlink(batch_temp.c_str());  // 寫到一半的殘骸是自己的，收乾淨
        result.path = batch_temp;
        result.error = error;
        return HandoffState::PublishWriteFailed;
    }
    // ⑥b 寫 header、rename——那一次 rename 就是**去重承諾的提交點**（§D-5），
    // 之後才發布批。為什麼 header 要先：崩在提交點與批發布之間會留下「header 是新
    // id ＋ 批還躺在我們的唯一暫存裡」——下一輪靠**位元組比對**認得出來，可以
    // roll forward。反過來（批先、header 後）崩掉只剩「批已發布、header 還是舊
    // id」，下一輪的第 ⓪ 步 lstat 直接早退，等這批跑完就會拿舊 header 比對而
    // 重新發布＝雙重執行。
    // header 寫不成不是致命傷：這一批照發，只是這一輪沒有去重保證，記 issue。
    const std::string header_temp = detail::unique_temp_path(header.base);
    if (!detail::write_file(header_temp, detail::encode_header(id, false),
                            error)) {
        add_issue(result, HandoffIssueKind::HeaderWriteFailed, header_temp,
                  InstState::Ok, error);
        unlink(header_temp.c_str());
    } else if (rename(header_temp.c_str(), header.base.c_str()) != 0) {
        add_issue(result, HandoffIssueKind::HeaderWriteFailed, header.base,
                  InstState::Ok, errno);
        unlink(header_temp.c_str());
    } else {
        sync_directory(base_directory, result);
    }
    // ⑥c 批發布 MUST 排他（§D-5），來源是**我們自己的唯一暫存**——沒有中間的
    // 共用槽位，所以不可能發布到別人的批。目的檔已存在＝別的彙整者先發布了。
    if (!detail::publish_exclusive(batch_temp, paths.base, error)) {
        if (error == EEXIST) {
            // 本輪放棄：不清投遞、不標 swept、published 維持 false。
            // batch_temp 是我們自己寫的檔，刪它絕對安全（不像 roll-forward 的錨，
            // 那個可能是同儕的）。
            unlink(batch_temp.c_str());
            return HandoffState::Ok;
        }
        result.path = batch_temp;
        result.error = error;
        // 刻意**保留** batch_temp：header 已經是新 id 了，這一份就是下一輪的
        // roll-forward 素材（靠位元組比對被認出來）。
        return HandoffState::RenameFailed;
    }
    sync_directory(base_directory, result);
    result.published = true;

    // ⑥d 清投遞；全數成功且目錄落盤才標 swept（§C-8）。
    if (remove_accepted_deliveries(accepted, paths.inbox, result)) {
        mark_header_swept(header, id, base_directory, result);
    }

    // ⑥e 兩個各自可容忍的降級疊在一起就不可容忍了（#26）：header 沒寫成代表下一輪
    // 沒有去重保證，投遞沒刪掉代表下一輪一定會再看到同一組——合起來就是無上限的
    // 副作用重播，每一輪重跑同一批，沒有任何機制會讓它停。升級為致命。
    // 借用既有的 PublishWriteFailed 而不是新增列舉值：aos_handoff_state 的 10／11／
    // 12 已經被 C ABI 專屬的 ALLOC_FAILED／READ_ERROR／BUFFER_TOO_SMALL 佔走，
    // C++ 端加第 10 個值會跟 C 端對不齊（見 inst.hpp 的註解）。
    if (const HandoffIssue *header_issue =
            find_issue(result, HandoffIssueKind::HeaderWriteFailed);
        header_issue != nullptr &&
        find_issue(result, HandoffIssueKind::DeliveryRemoveFailed) != nullptr) {
        result.path = header.base;
        result.error = header_issue->error;
        return HandoffState::PublishWriteFailed;
    }
    return HandoffState::Ok;
}

}  // namespace aos
