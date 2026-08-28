#define _POSIX_C_SOURCE 200809L

// handoff 層的彙整動作：把收件匣裡的投遞攤平成一批、排他發布成 base，並在批旁邊
// 維護 header sidecar（§C-8）。取件／釋放／兩個 to_string 在 handoff.cpp。
// §D-6 的去重與 roll-forward 另外住在 handoff_dedup.hpp／.cpp——那是「同一批不會
// 執行兩次」這件事，跟這裡的「掃收件匣 → 發布」是兩件事。
// 路徑推導與低階檔案存取在 handoff_fs.*，header 的編解在 handoff_header.*。
// 只依賴 inst＋format：不印訊息、不執行 instruction。
//
// aggregate_instructions() 底下那幾個具名階段函式的順序，就是 §D-5 的發布順序表；
// 為什麼 header 仍然排在批前面、排他發布的落敗者留下什麼，見 docs/handoff.md。

#include <aos/inst.hpp>

#include "handoff_dedup.hpp"
#include "handoff_fs.hpp"
#include "handoff_header.hpp"
#include "handoff_issue.hpp"

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

using detail::add_issue;
using detail::sync_directory;

// 一輪彙整的工作狀態：路徑推導的結果，加上掃完收件匣之後算出來的東西。
// 把它們綁在一起，下面的階段函式才不必拖著一長串參數。
struct Round {
    detail::HandoffPaths paths;
    detail::HeaderPaths header;
    std::string directory;  // base 所在目錄：rename／unlink 之後要 fsync 的那個
    std::string stem;       // 兄弟唯一暫存的名字前綴（base 是 inst.json 時＝inst）
    std::vector<inst_t> combined;      // 攤平後的整批
    std::vector<std::string> accepted; // 本輪收下、發布後要刪的投遞
    std::string id;                    // 批 id（§D-6）
    std::string output;                // canonical 批位元組
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

const HandoffIssue *find_issue(const HandoffResult &result,
                               HandoffIssueKind kind) {
    for (const HandoffIssue &issue : result.issues) {
        if (issue.kind == kind) return &issue;
    }
    return nullptr;
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

// ① 列出收件匣裡算數的投遞名（排序後），順便對「以 .json 結尾卻形狀不合」的名字
// 記 DeliveryNameIgnored（#10）。收件匣不存在回 Missing——那是成功的 no-op。
ListOutcome list_deliveries(const std::string &inbox,
                            std::vector<std::string> &names,
                            HandoffResult &result) {
    detail::DirGuard guard;
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

// ① 逐份讀進來、驗過、攤平成一批，同時累積批 id 的摘要。
// 投遞出問題分三條路（§D-4／§B-1，三者後果完全不同，刻意不合併）：
// 內容無效→隔離成 `.bad`；讀不到→留在原地下一輪再試；非普通檔→跳過不讀。
void collect_deliveries(const std::vector<std::string> &names, Round &round,
                        HandoffResult &result) {
    detail::BatchDigest digest;
    for (const std::string &name : names) {
        const std::string path = detail::join_path(round.paths.inbox, name);

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
            isolate_delivery(path, round.paths.inbox, result);
            continue;
        }
        for (inst_t &instruction : delivery) {
            round.combined.push_back(std::move(instruction));
        }
        round.accepted.push_back(path);
        digest.add(name, document);
    }
    round.id = digest.id();
}

// ④／⑤ 去重命中：這一組投遞上一輪已經跨過提交點，只是投遞沒被清掉。
// 找得到錨就 roll forward（補完批的發布），找不到就只清投遞、不重發。
HandoffState publish_dedup_hit(const Round &round, HandoffResult &result) {
    std::string anchor;
    if (detail::find_rollforward_anchor(round.directory, round.stem,
                                        round.output, anchor)) {
        int error = 0;
        if (detail::publish_exclusive(anchor, round.paths.base, error)) {
            sync_directory(round.directory, result);
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
    if (remove_accepted_deliveries(round.accepted, round.paths.inbox, result)) {
        detail::mark_header_swept(round.header, round.id, round.directory,
                                  result);
    }
    return HandoffState::Ok;
}

// ⑥ 正常發布：唯一名寫批 → 寫 header 並 rename（提交點）→ 排他發布批 → 清投遞
// → 標 swept。這一段的順序就是 §D-5 那張表。
HandoffState publish_new_batch(const Round &round, HandoffResult &result) {
    // ⑥a 唯一名寫批（§D-5）：唯一名保證兩個彙整者不會共寫同一個檔。這一份就是
    // 最後要被 rename 成 base 的那一個——**沒有中間的共用槽位**。
    const std::string batch_temp = detail::unique_temp_path(round.paths.base);
    int error = 0;
    if (!detail::write_file(batch_temp, round.output, error)) {
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
    const std::string header_temp = detail::unique_temp_path(round.header.base);
    if (!detail::write_file(header_temp, detail::encode_header(round.id, false),
                            error)) {
        add_issue(result, HandoffIssueKind::HeaderWriteFailed, header_temp,
                  InstState::Ok, error);
        unlink(header_temp.c_str());
    } else if (rename(header_temp.c_str(), round.header.base.c_str()) != 0) {
        add_issue(result, HandoffIssueKind::HeaderWriteFailed,
                  round.header.base, InstState::Ok, errno);
        unlink(header_temp.c_str());
    } else {
        sync_directory(round.directory, result);
    }
    // ⑥c 批發布 MUST 排他（§D-5），來源是**我們自己的唯一暫存**——沒有中間的
    // 共用槽位，所以不可能發布到別人的批。目的檔已存在＝別的彙整者先發布了。
    if (!detail::publish_exclusive(batch_temp, round.paths.base, error)) {
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
    sync_directory(round.directory, result);
    result.published = true;

    // ⑥d 清投遞；全數成功且目錄落盤才標 swept（§C-8）。
    if (remove_accepted_deliveries(round.accepted, round.paths.inbox, result)) {
        detail::mark_header_swept(round.header, round.id, round.directory,
                                  result);
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
        result.path = round.header.base;
        result.error = header_issue->error;
        return HandoffState::PublishWriteFailed;
    }
    return HandoffState::Ok;
}

}  // namespace

HandoffState aggregate_instructions(const std::string &instruction_path,
                                    HandoffResult &result) {
    result = HandoffResult{};
    Round round;
    if (!detail::derive_paths(instruction_path, round.paths) ||
        !detail::derive_header_paths(instruction_path, round.header)) {
        return HandoffState::InvalidArgument;
    }
    round.directory = detail::parent_directory(round.paths.base);
    // 兄弟唯一暫存的名字前綴：base 是 `.aos/inst.json` 時 stem ＝ `inst`，
    // 兄弟就是 `.aos/inst-*.json.temp`。derive_paths 已保證 base 以 .json 結尾。
    const std::string base_name =
        round.paths.base.substr(round.paths.base.find_last_of('/') + 1);
    round.stem =
        base_name.substr(0, base_name.size() - std::string_view(".json").size());

    // ⓪ base 已經有一份沒被取走：本輪 MUST NOT 發布（§D-4），不覆蓋也不碰 inbox。
    // 這裡用 lstat（不跟隨 symlink）；claim_instruction 對「存在」的定義必須跟這裡
    // 對齊，見那邊的 #25 註解。
    struct stat status {};
    if (lstat(round.paths.base.c_str(), &status) == 0) return HandoffState::Ok;
    if (errno != ENOENT) {
        result.path = round.paths.base;
        result.error = errno;
        return HandoffState::InstructionReadFailed;
    }

    // ① 掃收件匣，把每份投遞讀進來攤平成一批。
    std::vector<std::string> names;
    const ListOutcome listed = list_deliveries(round.paths.inbox, names, result);
    if (listed != ListOutcome::Ok) {
        return listed == ListOutcome::Missing ? HandoffState::Ok
                                              : HandoffState::InboxReadFailed;
    }
    collect_deliveries(names, round, result);

    // ② 整批為空：沒有東西要發布，但投遞還是要清掉（§D-4 的三個例外之一），
    // 否則空投遞會永遠留在收件匣、每一輪被重新讀取。沒有批就沒有 header。
    if (round.combined.empty()) {
        remove_accepted_deliveries(round.accepted, round.paths.inbox, result);
        return HandoffState::Ok;
    }

    // ③ canonical 位元組提前算出來：去重分支要拿它跟兄弟暫存逐位元比對（#21）。
    if (write_all(round.combined, round.output, nullptr) != InstState::Ok) {
        result.path = round.paths.base;
        result.error = EINVAL;
        return HandoffState::PublishWriteFailed;
    }

    // ④／⑤ 去重（§D-6）。閘門是 swept（§C-8）：只有現任 header 的 swept 不成立
    // 才啟用比對——swept 成立代表上一批的清理已經走完，那時同名同內容的投遞是
    // 全新的一批，MUST 照常發布（#1）。id 相同 ＋ 未 swept ＝ 這一組投遞上一輪
    // 已經跨過提交點（header 的 rename），只是投遞沒被清掉。
    detail::HeaderFields current;
    if (detail::current_header(round.header.base, current, result) &&
        !current.swept && current.id == round.id) {
        return publish_dedup_hit(round, result);
    }

    // ⑥ 正常發布。
    return publish_new_batch(round, result);
}

}  // namespace aos
