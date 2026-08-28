#define _POSIX_C_SOURCE 200809L

// handoff 層的第四個公開動作：投遞（SPEC §D-1 三步協定的第一步、§D-3）。
// 投遞是唯一由外部生產者執行的協定步驟，所以協定細節全部內建在這裡——唯一檔名、
// 先 `.temp` 後排他 rename、canonical 位元組——生產者不必（也不能）自己手刻。
// 與 handoff.cpp 同層、同樣只依賴 inst＋format：不印訊息、不執行 instruction。
// 路徑推導與低階檔案存取仍然在 handoff_fs.hpp／.cpp。

#include <aos/inst.hpp>

#include "handoff_fs.hpp"

#include <cerrno>
#include <cstddef>
#include <string>
#include <vector>

#include <sys/stat.h>
#include <unistd.h>

namespace aos {
namespace {

// 換名重試的上限。同一行程內 next_delivery_name() 單調遞增、必不重複，會撞名只有
// 一種來路：pid 重用之後撞上別的行程留下的殘檔（§D-2）。撞一次換一個序號就過了；
// 連撞這麼多次代表收件匣有系統性問題（例如被人塞滿同名檔），這時回報比空轉好。
constexpr int kMaxPublishAttempts = 8;

}  // namespace

HandoffState deliver_instructions(const std::string &instruction_path,
                                  const std::string &document,
                                  DeliverResult &result) {
    result = DeliverResult{};
    detail::HandoffPaths paths;
    if (!detail::derive_paths(instruction_path, paths)) {
        return HandoffState::InvalidArgument;
    }
    result.inbox = paths.inbox;

    // ① 驗證走唯一 parser（§D-3）：整批讀進來，壞掉就整批拒收，一個檔都不寫。
    std::vector<inst_t> batch;
    std::size_t error_record = 0;
    const char empty = '\0';
    const char *data = document.empty() ? &empty : document.data();
    const InstState state =
        read_all(data, document.size(), batch, &error_record);
    if (state != InstState::Ok) {
        result.inst_state = state;
        result.error_record = error_record;
        return HandoffState::DeliveryInvalid;
    }
    result.count = batch.size();

    // ② 發布的位元組是 canonical 的（§D-3）：往返格式層一次，跟彙整對每份投遞做的
    // 事情一樣（§C-4），所以「投遞了什麼」與「彙整讀到什麼」不會有兩套位元組。
    // 未解析的指示詞照原樣寫回，round-trip 保證它們不會被吃掉。
    std::string canonical;
    if (write_all(batch, canonical, nullptr) != InstState::Ok) {
        result.path = paths.inbox;
        result.error = EINVAL;
        return HandoffState::PublishWriteFailed;
    }

    // ③ 收件匣必須已經存在：deliver 不建世界（§D-3），建世界是 aos init 的事。
    struct stat status {};
    if (stat(paths.inbox.c_str(), &status) != 0) {
        result.path = paths.inbox;
        result.error = errno;
        return HandoffState::InboxReadFailed;
    }
    if (!S_ISDIR(status.st_mode)) {
        result.path = paths.inbox;
        result.error = ENOTDIR;
        return HandoffState::InboxReadFailed;
    }

    for (int attempt = 0; attempt < kMaxPublishAttempts; ++attempt) {
        // ④ 唯一名（§D-2）＋ O_EXCL 建 `.temp`：名字被別人佔走就換下一個序號，
        // 絕不覆蓋——被覆蓋的可能正是另一個生產者寫到一半的投遞。
        const std::string name = detail::next_delivery_name() + ".json";
        const std::string ready = detail::join_path(paths.inbox, name);
        const std::string temp = ready + ".temp";
        int error = 0;
        if (!detail::write_file_exclusive(temp, canonical, error)) {
            if (error == EEXIST) continue;
            unlink(temp.c_str());  // 寫到一半的殘骸是自己的，收乾淨（同 aggregate）
            result.path = temp;
            result.error = error;
            return HandoffState::PublishWriteFailed;
        }
        // ⑤ 排他發布（§D-2）：rename 前 `.temp` 已經 fsync 過，收件匣裡不會出現
        // 「名字有了、內容還沒落盤」的投遞。撞名（EEXIST）換名重試；其他錯誤不重試。
        // 退階路徑（link＋unlink）的收尾 unlink 失敗**不算失敗**（#11）：那時 ready
        // 已經連好、內容完整、彙整一定會收，回報失敗只會讓生產者重投＝真的多出
        // 一份。errno 走 leftover 進 sync_error，與目錄 fsync 失敗同一條警告通道。
        int leftover = 0;
        if (!detail::publish_exclusive(temp, ready, error, &leftover)) {
            if (error == EEXIST) {
                unlink(temp.c_str());
                continue;
            }
            result.path = ready;
            result.error = error;
            return HandoffState::RenameFailed;
        }
        // ⑥ 目錄項落盤（§D-5 同一條耐久性要求）。失敗時投遞已經在收件匣裡了，
        // 缺的只是耐久性保證——比照彙整記 DirectorySyncFailed 續行的做法，回 Ok
        // 但把 errno 留在 sync_error 讓上層警告。謊報投遞失敗會讓生產者重投，
        // 那才真的多出一份。
        if (!detail::fsync_dir(paths.inbox, error)) result.sync_error = error;
        if (leftover != 0 && result.sync_error == 0) result.sync_error = leftover;
        result.name = name;
        return HandoffState::Ok;
    }
    result.path = paths.inbox;
    result.error = EEXIST;
    return HandoffState::RenameFailed;
}

}  // namespace aos
