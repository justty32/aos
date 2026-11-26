// aos/procfs.hpp：aos-procfs 公開介面——讓一支行程用 FUSE（不靠 libfuse）把自己的目錄掛出來，照 aos proc 介面回答。
//
// 規矩（整個庫的設計都繞著它）：回答的線（讀寫 /dev/fuse 的執行緒）只用行程自己記憶裡的東西，
// 不做久的事、不碰任何檔案系統路徑，尤其不碰自己的掛載點——否則讀它的人會跟著卡住，而且殺不掉。
// 所以：只讀檔的內容由「當場產生字串」的 Producer 給（在回答的線上跑）；ctl 的指令交給另一條做事的線跑。
#pragma once

#include "aos/fields.hpp"

#include <cstdint>
#include <functional>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace aos::procfs {

// ---------- 「名稱: 值」文字 ----------

// 一行 "name: value\n"；值裡的換行換成空白，空值寫 "-"（草稿第 5 節）。
// 整個檔的內容請用欄位表（aos/fields.hpp 的 AOS_RECORD、to_text、to_json），每個欄位只宣告一次。
std::string kv_line(std::string_view name, std::string_view value);

// ---------- 指令檔（ctl、procs_ctl） ----------

// 回饋四行（草稿第 6 節）。放進 status 的欄位表時用 Embed、格名就是字首：F(aos::procfs::Feedback, aos_ctl_, Embed)
#define AOS_FEEDBACK_FIELDS(F)       \
    F(std::string, cmd, Always)      \
    F(std::string, state, Always)    \
    F(std::string, error, Always)    \
    F(long long, count, Always)
AOS_RECORD(Feedback, AOS_FEEDBACK_FIELDS)

struct Command {
    std::string line;                  // 收下的那一道（去掉行尾換行）
    std::vector<std::string> words;    // 依空白切開；words[0] 是字
};

// 做事的線跑完一道指令的結果。
struct Result {
    std::string error;                 // 空＝做成了（state done）；否則 "代號 原因"：state 記 failed、原因記進 *_error
    bool hold = false;                 // true＝不放鎖、state 停在 doing（stop：做完＝行程結束）

    static Result done() { return {}; }
    static Result failed(std::string code_and_reason) { return {std::move(code_and_reason), false}; }
    static Result hold_until_exit() { return {"", true}; }
};

// 在做事的線上跑（每個指令檔一條）；可以久、可以碰檔案。跑完才放鎖。
using Action = std::function<Result(const Command&)>;
// 在回答的線上跑：只看參數、只讀記憶體、不可阻塞。回 "" 收下；回 "代號 原因" 就拒（rejected、寫入失敗）。
using Check = std::function<std::string(const Command&)>;

class Ctl {
public:
    // 註冊一個字。要在 Fs::mount 之前註冊完（之後不再改表，回答的線讀它不用鎖）。
    void on(std::string word, Action action, Check check = {});
    // 「做完才回」：寫入要等 Action 跑完才回來——done＝寫入成功，failed＝寫入失敗 EIO（原因照舊在 *_error）；
    // hold_until_exit 在 Action 回來那刻就回成功。回答的線不等：那次 WRITE 的回覆留著，由做事的線做完時回。
    // 等的人收到訊號（Ctrl-C、kill）會當場拿到 EINTR 放開，指令照做、結果只在回饋裡；卸載時還沒回的拿到 ECONNABORTED。
    // 不叫＝原本的「寫回來＝收到」。要在 Fs::mount 之前叫。
    void reply_when_done(bool on = true);
    // 回饋四行的值（還沒收過＝空字串，寫出來是 "-"）；在 Producer 裡叫，只拿一下鎖、不阻塞。
    Feedback snapshot() const;
    // 同上，寫成四行純文字 <prefix>cmd／state／error／count。
    std::string feedback() const;
    bool locked() const;

    struct Impl;
    explicit Ctl(std::string prefix);
    ~Ctl();
    Ctl(const Ctl&) = delete;
    Ctl& operator=(const Ctl&) = delete;
    const std::shared_ptr<Impl>& impl() const { return impl_; }

private:
    // shared：做事的線手上也拿一份，結束時那道指令還在跑就讓它自己跑完，不卡住 unmount
    std::shared_ptr<Impl> impl_;
};

// ---------- 信箱資料夾 mailbox/（照 Maildir：先在 tmp/ 寫好，再搬進 new/；草稿第 9 節） ----------

// 上限（預設保守）。超過時那一步失敗：單封太大＝寫入 EFBIG；封數、總量＝ENOSPC。
struct MailLimits {
    size_t max_letter_bytes = 8u << 20;    // 一封（一個檔，或一個信夾裡全部的檔）最多幾 byte
    size_t max_letters = 4096;             // tmp/ 與 new/ 頂層合計最多幾項；在 tmp/ 開新的一項時查
    size_t max_total_bytes = 64u << 20;    // tmp/ 與 new/ 全部合計最多幾 byte
    size_t max_files = 64;                 // 一個信夾裡最多幾個檔（信夾裡不能再開夾）
    double stale_tmp_seconds = 36 * 3600;  // tmp/ 裡多久沒動就丟（Maildir 的 36 小時）
};

// 一封搬進 new/ 的信。內容是共用、不再變的記憶體（搬進 new/ 那刻就封住了）。
struct Letter {
    std::string name;
    bool folder = false;                                 // true＝一個夾（proto8 aos-post 的形狀：<名>/letter.json）
    std::shared_ptr<const std::string> bytes;            // 單檔＝它的內容；信夾＝裡面 letter.json 的內容（沒有＝空）
    std::vector<std::pair<std::string, std::shared_ptr<const std::string>>> files;   // 信夾裡每個檔（單檔＝空）
    size_t size = 0;                                     // 全部 byte
    uint32_t uid = 0, pid = 0;                           // 搬進 new/ 那次請求的發起者（FUSE 請求的表頭，核心填的）
    double arrived_at = 0;                               // 搬進 new/ 的時間（Unix 秒）
};

// accept 的答覆：err 0＝收；否則那次搬進 new/ 失敗、回這個 errno（EXDEV 會被換成 EPERM：mv 碰到 EXDEV 會改用複製）。
struct Refusal {
    int err = 0;
    std::string reason;   // 記進 MailStats::last_refusal
};
// 在回答的線上、搬進 new/ 那一刻叫（不拿著庫的鎖）：只看 Letter、只讀記憶體、不可阻塞（同 Check 的規矩）。
using Accept = std::function<Refusal(const Letter&)>;

struct MailStats {
    size_t waiting = 0;                  // new/ 裡幾封
    size_t writing = 0;                  // tmp/ 裡幾項
    size_t bytes = 0;                    // tmp/＋new/ 合計
    unsigned long long delivered = 0, taken = 0, refused = 0, dropped_stale = 0;
    std::string last_refusal;            // 最後一次拒收的原因（含被上限擋下的搬動）；沒有＝空
};

class Mailbox {
public:
    // 拿走 new/ 裡最早搬進來的一封；沒有回 nullopt。執行緒安全、只碰記憶體。拿走後 new/ 裡就沒有它了。
    std::optional<Letter> take();
    // eventfd（非阻塞、close-on-exec）：每搬進一封加 1。可讀＝有新信；讀掉 8 byte 清零，再 take() 到拿不到為止。
    int fd() const;
    MailStats stats() const;   // 順手丟掉過期的 tmp/；只碰記憶體，可以在 Producer 裡叫

    struct Impl;
    explicit Mailbox(std::unique_ptr<Impl> impl);
    ~Mailbox();
    Mailbox(const Mailbox&) = delete;
    Mailbox& operator=(const Mailbox&) = delete;
    Impl& impl() const { return *impl_; }

private:
    std::unique_ptr<Impl> impl_;
};

// ---------- 掛出來的目錄 ----------

// 在回答的線上跑：只用記憶體裡的東西組字串，不可阻塞、不可碰任何檔案系統路徑
//（連 localtime 都可能去讀 /etc/localtime，時間字串請先在別處算好）。
using Producer = std::function<std::string()>;

struct Options {
    std::string fsname = "aosproc";    // /proc/mounts 第一欄的字首；實際是 "<fsname>:<PID>"，收屍時靠 PID 認活不活
    int threads = 1;                   // 回答的線幾條；一條就夠，多開只為了很多人同時讀
    bool root_sockets = false;         // 根夾允許 bind unix socket（同 add_dir 的 sockets）
    std::function<void()> on_gone;     // 連線沒了（被卸、被 abort）時，從最後一條回答的線叫一次；別在裡面做久的事
};

class Fs {
public:
    explicit Fs(Options opt = {});
    ~Fs();   // 還掛著就 unmount()
    Fs(const Fs&) = delete;
    Fs& operator=(const Fs&) = delete;

    // 節點；path 用 "/" 分層、相對於掛載點根（例 "procs/kid1"），上層夾要先加。重名丟 std::runtime_error。
    void add_dir(const std::string& path, bool sockets = false);   // sockets＝允許在裡面 bind unix socket（MKNOD S_IFSOCK）
    void add_text(const std::string& path, Producer produce);     // 只讀純文字：開檔那刻產生一份，整次讀都讀那份
    void add_json(const std::string& path, std::string content);  // 只讀、內容不變（_metainfo.json）
    Ctl& add_ctl(const std::string& path, std::string prefix);    // 只寫指令檔；prefix 例 "aos_ctl_"、"aos_procs_ctl_"
    void add_symlink(const std::string& path, std::string target); // 隨時可加；名字不快取（entry_valid＝0）
    bool remove(const std::string& path);                         // 拿掉 symlink 或 socket 節點（其他種類不給拿）
    // 信箱資料夾：path/ 底下 tmp/（寄的人在這裡寫）、new/（搬進來＝寄到）、cur/（永遠是空的，只為了跟 Maildir 同形）。
    // 信存在記憶體裡；Mailbox 跟著 Fs 活。要在 mount 之前加。
    Mailbox& add_mailbox(const std::string& path, MailLimits limits = {}, Accept accept = {});

    // 掛上並起回答的線與每個 ctl 的做事的線。夾不在就建（unmount 時刪）。失敗丟 std::runtime_error。
    void mount(const std::string& mountpoint);
    // 正常結束：自己站在裡面先 chdir("/")、fusermount3 -u，失敗才 -u -z（此時順手 abort 連線好讓回答的線醒來）。
    void unmount();
    bool mounted() const;
    const std::string& mountpoint() const;

    struct Impl;

private:
    std::unique_ptr<Impl> impl_;
};

// ---------- daemon 交給它起的那一支的環境變數 ----------

// daemon 起一支底下的 proc 時給 AOS_NAME（名字路）、AOS_MOUNT（掛載點）與 AOS_NAME_PID（那一支的 PID，fork 之後、exec 之前填）。
// 孫子行程會原樣繼承這三個；只有 AOS_NAME_PID 等於 getpid() 時才回值，否則回 nullopt（當沒給）。
// 所以包一層殼的要 exec 真的程式（PID 不變），不然真的程式會不理這兩個變數。AOS_ROOT 不在此限，大家都該知道根。
struct EnvAssignment {
    std::string name;
    std::string mount;
};
std::optional<EnvAssignment> env_assignment();

// ---------- 給 daemon 用的 ----------

// /proc/self/mountinfo 裡掛在 path 的 FUSE 掛載的連線編號（=/sys/fs/fuse/connections/<編號>），沒有回 -1。
// 只讀 mountinfo、不碰 path 本身（碰卡住的掛載會跟著卡住）。
long connection_id(const std::string& path);

// 對 path 上的 FUSE 連線寫 abort：卡在裡面的人當場拿到錯誤放開，之後那個掛載只剩死殼（要再 cleanup）。
bool abort_connection(const std::string& path);

enum class Cleanup { NotMounted, Unmounted, Alive, Foreign, Failed };
// 清掉 path 上死掉的 aos-procfs 掛載（fusermount3 -u -z），給 daemon 收屍用。
// 從 fsname 認出伺服器 PID；那個 PID 還在（活著或被暫停；殭屍不算）就回 Alive 不動，force 才硬卸。
// 不是 aos-procfs 掛的（subtype 不是 aosproc）回 Foreign，一律不動。掛載點的空夾不刪，留給呼叫的人。
// 不碰 path 本身，所以伺服器卡住也不會拖住呼叫的人。
Cleanup cleanup_dead_mount(const std::string& path, bool force = false);

// 呼叫的線是不是 aos-procfs 的回答的線；庫裡會碰檔案系統的函數在回答的線上叫就丟 std::logic_error。
bool on_answer_thread();

}  // namespace aos::procfs
