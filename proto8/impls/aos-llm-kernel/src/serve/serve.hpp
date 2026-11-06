// serve.hpp：【serve】kernel 跑一次——讀設定、鎖信箱、收拾、排隊、認領、請 daemon 掛問腦 proc、收成品、回信。
//
//   config.cpp  讀設定、解指示詞與 endpoint 函數路徑
//   reply.cpp   寄送／撤回回信、記用量與刪信
//   proc.cpp    掛問腦 proc、收尾／重掛與收集在飛信件
//   scan.cpp    掃排隊信、查代號與解析能力包
//   serve.cpp   鎖信箱、收拾信件與每輪執行骨架
//
//   read_cfg   kernel.json（`檔` 或 `檔#/指標`；thinking 11-04 think-as-function 02 § 3）：
//                slots（同時在飛幾封，正整數；沒寫＝1）、aging_ticks（每幾格升一級，正整數；沒寫＝3）、budget（額度，budget.hpp；含每寄件人的 senders，相對路徑從 kernel 定義資料夾算）、
//                exec（必填：預設的 endpoint 函數＝aos-exec 目標，資料夾、檔、`檔#/指標`；相對的從 kernel 定義資料夾〔kernel.json 所在〕算、轉成絕對）、
//                endpoints（必填、非空物件：代號 → 一組 llm 設定＝一個能力包〔11-05 feat-proto，pack.hpp〕；一組裡 kernel 認 exec〔選填，這組改用別的
//                  endpoint 函數，相對的同上〕、slots、budget、speed，拿掉後其他鍵〔url／model／key／fixed／cost／context／summary…〕整個原樣交給 endpoint 函數）、
//                  endpoint（選填：預設代號，要在表裡）、timeout_ms（選填：問腦單子的上限，非負整數）；
//                其他 key 忽略。信箱固定 $AOS_STACK/requests/（11-05 kernel-daemon 07 § 2：AOS_LLM_KERNEL＝kernel 的 stack）。
//              指示詞：slots、aging_ticks、budget、exec、endpoint、timeout_ms 整格先解（aos-directive 的 resolve_keys）；endpoints 只換一層
//              （整張表可以 {"$ref": "endpoints.json#/"}），裡面每組到用的時候才解（解不開＝那封信回 DirectiveBad，kernel 照跑別封）。
//              壞了 CfgMissing／CfgBad／DirectiveBad
//   serve      跑一次（給 daemon 一次次拍，多半是 daemon.json 的身體），回結束碼（0；開始前收到訊號＝128＋N）。
//              11-05（kernel-daemon 03）起 kernel 不自己 fork 跑 endpoint 函數：每封請 daemon 掛成 max: 1 的 loop 型 proc，下一次收。
//                0. 找 daemon（daemon.hpp 的 find_host：沒 AOS_DAEMON＝DaemonMissing、沒 ctl 信箱＝MailboxMissing；有 AOS_KERNEL 掛信寄那裡）
//                1. 建信箱三格（tmp／new／cur）、flock 住 .flock（鎖不到＝LockFailed）；queue.json 的 counter_runs＋1；讀 daemon 的表；
//                   寫窗 $AOS_STACK/endpoints.json（包的屬性表，pack.hpp 的 window_of；有變才寫）
//                2. 收成品（collect）：cur/<id>/ 有 proc.json＝在飛，看表與 <id>/state.json（settle）：收尾 code 0＝reply.json 當回信（讀不懂＝ReplyBad）、
//                   其他碼＝EndpointFailed（reply.json 或 stderr.txt 第一行）、143／137 且過了 timeout_ms＝逾時；被收掉／死在半路＝重掛一次、第二次 EndpointFailed；
//                   表上沒列又沒 state.json＝daemon 還沒套（照算一格），mailbox_warning 提到掛信＝LaunchFailed；
//                   表上列 stopped 而 state.json 收尾了、或列上有 reason（11-05：問腦 loop 退非 0，daemon 留 stopped＋reason）＝收、寄 procs_removed 拔列；
//                   這種列要重掛＝proc.json 記 remount、等列拔了下一次才寄掛信。沒 proc.json 的：有 reply.json＝寄，沒有＝改名回 new/
//                3. 收拾（只看有 sender.flock 的信；沒有＝非同步寄的，不判存活）：tmp/ 裡寄信的人不在了（沒人鎖）的刪掉；
//                   new/ 裡寄信的人不在了的先改名回 tmp/ 再刪（不白跑）
//                   new/、cur/ 只看子資料夾（信＝資料夾，N-16；混進來的一般檔不理）
//                4. 看 new/：letter.json 讀不懂、body 不是物件、沒有 body.request、endpoint 不是字串、priority 壞＝回 LetterBad；
//                   request 不是物件、messages 不是陣列、stream 真＝RequestBad；代號：沒寫又沒預設＝EndpointMissing、表裡沒有＝EndpointUnknown；
//                   那組解指示詞失敗＝DirectiveBad、不是物件或 exec 不是非空字串、slots／budget／speed／fixed 形狀不對＝CfgBad；
//                   request 寫了包 fixed 裡的 key、或包有 model 而 request 寫 model＝RequestBad（C-56：釘死的不給蓋）；deadline 已過＝DeadlineBad（都不佔格）
//                5. 排隊（queue.hpp 的 order：級數＋aging → deadline → 包的 speed → 等得久 → 先寄）、補位到 slots（在飛＋新掛）：
//                   額度到頂（budget.hpp 的 spent）＝"refuse" 剩下的全回 BudgetMissing、"wait" 停整列留在 new/；
//                   包（11-05 feat-proto 件 3）：那包的 budget 到頂（spent_pack，數那包在飛＋新掛）＝"refuse" 那封回 BudgetMissing、"wait" 那封留在 new/、
//                   別包照跑（不降級換包）；寄件人（11-05 feat-proto 件 5）：budget.senders 列了信封 sender 而那人到頂（spent_of，數那人在飛＋新掛）＝同包的做法；
//                   那包在飛＋新掛已到它的 slots＝跳過、看下一封（不是停下）；都沒擋就認領（new → cur 改名；改不成＝寄信的剛撤信）、寫 request.json＝{"endpoint": 那組（指示詞已解、去掉 exec）,
//                   "request": body.request}、寄掛信（proc.json 記 endpoint＝代號、sender＝信封 sender） {"procs_added": {"llm_<id>": {"exec": {"argv": ["aos-exec", 函數], "cwd": 信資料夾,
//                   "stdin": "request.json", "stdout": "reply.json", "timeout_ms"?}, "max": 1, "stack": 信資料夾}}}、寫 proc.json；寄不進＝LaunchFailed
//                6. 回信（寄信的 sender.flock 已沒人鎖＝馬上撤回）、寄不出去 stderr 印一行；掛過的記進 used.json（含 packs.<代號>、senders.<寄件人>）；整封刪掉；寫 queue.json
//              endpoint 函數的環境＝daemon 給子項的（AOS_STACK＝信資料夾、AOS_DAEMON、daemon 的 AOS_WS），不是 kernel 的。
#pragma once

#include "budget/budget.hpp"
#include "common/common.hpp"
#include "daemon/daemon.hpp"
#include "pack/pack.hpp"
#include "queue/queue.hpp"

#include <map>
#include <optional>
#include <string>
#include <vector>
#include <unistd.h>

namespace aos::llm_kernel {

struct Cfg {
    std::string requests;   // $AOS_STACK/requests（11-05 固定）
    long long slots = 1;
    long long aging_ticks = 3;
    Budget budget;
    std::string exec;                                   // 預設的 endpoint 函數（絕對路徑，可帶 #/指標）
    Json endpoints = Json::object();                    // 代號 → 一組（只換過表這一層，每組裡的指示詞還沒解）
    std::map<std::string, std::string> endpoint_dirs;   // 代號 → 那組裡相對 $ref 的起點
    std::map<std::string, Pack> packs;                  // 代號 → 包的 slots／budget／speed（只解這幾格；pack.hpp 的 read_packs）
    std::optional<std::string> endpoint;                // 預設代號
    std::optional<long long> timeout_ms;
    std::string base;                                   // kernel 定義資料夾（相對的 exec 從這裡算）
};

Cfg read_cfg(const std::string& spec, const std::string& stack);
int serve(const Cfg& cfg, const std::string& stack);

// serve 元素各分檔共用的內部接縫。
std::string target_abs(const std::string& t, const std::string& base);
Json error_reply(const std::string& c, const std::string& msg);
extern const char* PROC_JSON;

class Server {
public:
    Server(const Cfg& cfg, const std::string& stack)
        : cfg_(cfg), mb_{cfg.requests}, slots_(cfg.slots), budget_(cfg.budget), stack_(stack) {}
    ~Server() {
        if (lock_fd_ >= 0) {
            close(lock_fd_);
        }
    }
    Server(const Server&) = delete;
    Server& operator=(const Server&) = delete;

    int run();

private:
    const Cfg& cfg_;
    Mailbox mb_;
    long long slots_;
    Budget budget_;
    std::string stack_;
    int lock_fd_ = -1;
    Queue q_;
    Used used_;
    Host host_;
    Table table_;
    long long busy_ = 0;   // 掛上去、還沒收的（在飛）
    std::map<std::string, long long> pack_busy_;   // 代號 → 這包在飛幾封（proc.json 的 endpoint；11-05 feat-proto）
    std::map<std::string, long long> sender_busy_; // 寄件人 → 這人在飛幾封（proc.json 的 sender；11-05 feat-proto 件 5）

    void lock();
    void collect();
    void sweep();
    std::vector<Waiting> scan(long long now_ms, std::optional<long long> now_tick);
    void refuse(const std::string& id, const Json& reply);
    std::optional<Json> pick(Waiting& w);
    void finish(const std::string& id, const Json& reply);
    void mount(const std::string& id, const std::string& exec, Json proc);
    std::optional<Json> settle(const std::string& id, Json proc);
};

}  // namespace aos::llm_kernel
