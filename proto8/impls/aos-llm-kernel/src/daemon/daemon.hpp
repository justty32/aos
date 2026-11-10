// daemon.hpp：【daemon】kernel 請 daemon 掛問腦 proc——找 daemon、寄掛信／拔信、讀 daemon 的表（11-05 kernel-daemon 03）。
//
//   find_host   找掛到哪：要 $AOS_DAEMON（daemon 的 stack；沒設、空的、不是資料夾＝DaemonMissing）；
//               掛信寄 $AOS_KERNEL（有設、非空：「要掛 proc 往哪寄」的信箱，N-63）、
//               它的 new/ 不是資料夾＝每行程每路徑 warn 一次，仍用該信箱；真正寄不進的錯照舊交給 send_procs；
//               沒設＝$AOS_DAEMON/<procs_state.json 回報的 procs_requests>（窗沒有這欄＝預設 procs_requests；null＝MailboxMissing）
//   read_table  讀 daemon 的表 $AOS_DAEMON/procs_state.json：procs（切檔的 $ref 經 aos-directive 解回整張）；另從 $AOS_DAEMON/state_flux.json 讀 mailbox_warning；
//               各窗獨立讀；不在、讀不懂＝空表／空警告（daemon 剛起還沒寫）
//   send_procs  寄一封 procs_* 信進掛信信箱（aos-post 的 send，信件名稱照預設）；回信件名稱。寄不進丟 aos-post 的錯
//
// 不驗寄件人、不看 daemon 怎麼起（C-52）：kernel 只寄信、讀窗。
#pragma once

#include "common/common.hpp"

#include <string>

namespace aos::llm_kernel {

struct Host {
    std::string daemon;   // daemon 的 stack（絕對、結尾 /）
    std::string box;      // 掛信寄這裡（信箱根，絕對）
};

struct Table {
    Json procs = Json::object();   // {名字: 列}
    std::string warning;           // state_flux.json 的 mailbox_warning（沒有＝空）
};

Host find_host();
Table read_table(const Host& h);
std::string send_procs(const Host& h, const Json& body);

}  // namespace aos::llm_kernel
