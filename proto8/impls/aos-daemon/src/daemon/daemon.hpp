// daemon.hpp：【daemon】Daemon＝aos-loop 的 Loop 子類別＋一張子 loop 的表。照 proto8/bin/aos-daemon 的 Daemon（10-21 傍晚）。內部標頭。
//
//   daemon.cpp   建構子（AOS_STACK、children、adopt 的檢查）、adopt、tend（對表：收多的、看誰結束、起少的）、
//                stop（SIGTERM、等 10 秒、SIGKILL 整群）、finish（收掉全部；最後一圈之後才自己結束的也標 exited，D7）、
//                info（children 表）、check_ctl（ctl 的 children）
//
// daemon.json＝loop.json 的超集：run、max、interval_ms、ctl、state 同 aos-loop，但 run 選填、max 沒寫＝不限、
// interval_ms 沒寫＝200；多兩個 key——children＝{名字: aos-exec 的目標（字串或 [目標, 參數...]）或 loop 設定（物件）}、
// adopt（布林，沒寫＝true）。
#pragma once

#include "child/child.hpp"

#include <string>
#include <utility>
#include <vector>

namespace aos::daemon {

// children 的檢查（daemon.json 與 ctl 共用）：要是物件；名字非空、不含 /、不含 #（會被 aos-exec 當成指標的開頭）、不以 . 開頭；
// 值是字串、陣列或物件（內容不驗，交給子 loop）。
std::optional<std::string> check_children(const Json& v);

class Daemon : public aos::loop::Loop {
public:
    Daemon(const std::map<std::string, std::string>& opts, const std::string& spec);

protected:
    void tend(const Json& ctl) override;
    void finish() override;
    Json info() override;
    std::optional<std::string> check_ctl(const Json& doc) override;

private:
    void adopt();
    void stop(const std::vector<std::string>& names);
    Child* find(const std::string& name);

    Json children_;                                      // daemon.json 的 children
    std::string cwd_;                                    // 子 loop 的 cwd＝daemon 起來時的 cwd
    std::vector<std::pair<std::string, Child>> table_;   // 照加入的順序
};

}  // namespace aos::daemon
