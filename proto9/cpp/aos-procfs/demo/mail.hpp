// mail.hpp：aos-procfs-demo 的信箱部分——擺出 mailbox/、ctl 的 take 與 refuse、status 裡的 mail_* 行、--mail-* 旗標。
#pragma once

#include "files.hpp"

#include <mutex>
#include <optional>
#include <string>

struct DemoMail {
    aos::procfs::MailLimits limits;
    aos::procfs::Mailbox* box = nullptr;
    std::mutex mu;
    bool refusing = false;
    std::string last_name;
    std::optional<long long> last_bytes;
};

// --mail-max-bytes N、--mail-max-letters N、--mail-max-total N、--mail-stale S：認得就吃掉值、回 true
bool demo_mail_flag(const std::string& flag, const std::string& value, DemoMail& dm);
bool demo_mail_wants_value(const std::string& flag);
// 擺出 mailbox/，在 ctl 註冊 take 與 refuse（要在 mount 之前叫）
void demo_mail_setup(aos::procfs::Fs& fs, aos::procfs::Ctl& ctl, DemoMail& dm);
// status 裡的非標準行（不帶 aos_，欄位表在 files.hpp）
DemoMailStatus demo_mail_status(DemoMail& dm);
