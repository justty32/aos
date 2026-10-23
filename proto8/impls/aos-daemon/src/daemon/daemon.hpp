// daemon.hpp：【daemon】Daemon＝aos-loop 的 Loop 子類別＋一張子 loop 的表。照 proto8/bin/aos-daemon 的 Daemon（10-21 傍晚）。內部標頭。
//
//   daemon.cpp   建構子（AOS_STACK、loops、adopt 的檢查）、adopt、tend（對表：收多的、看誰結束、起少的）、
//                stop（SIGTERM、等 10 秒、SIGKILL 整群；收掉的標 stopped）、finish（收掉全部；最後一次之後才自己結束的標 done，D7）、
//                info（loops 表）、check_ctl（ctl 的 loops）、taken_names／check_names（子項名字跟自己的 ctl／state 撞名，10-22）
//
// daemon.json＝loop.json 的超集：run、max、interval_ms、ctl、state 同 aos-loop，但 run 選填、max 沒寫＝不限、
// interval_ms 沒寫＝200；多兩個 key——loops＝{名字: aos-exec 的目標（字串或 [目標, 參數...]）或 loop 設定（物件）}、
// adopt（布林，沒寫＝true）。
#pragma once

#include "child/child.hpp"

#include <set>
#include <string>
#include <utility>
#include <vector>

namespace aos::daemon {

// loops 的檢查（daemon.json 與 ctl 共用）：要是物件；名字非空、不含 /、不含 #（會被 aos-exec 當成指標的開頭）、不以 . 開頭；
// 值是字串、陣列或物件（內容不驗，交給子 loop）。
std::optional<std::string> check_loops(const Json& v);

// 小格 $AOS_STACK/<名字>/ 會撞到的名字（使用者 10-22）：ctl、state（paths，空＝沒開）落在 $AOS_STACK 底下時相對路徑的第一段
// （"state.json"、"w/c.json" 的 "w"）；落在外面的不算。照 bin 的 taken_names（abspath 整理 `.`、`..`，不解捷徑）。
std::set<std::string> taken_names(const std::string& stack, const std::vector<std::string>& paths);

// loops（已過 check_loops）的名字在 taken 裡＝回原因。起來時撞＝CfgBad、退 1；ctl 撞＝那份 ctl 不採用。
std::optional<std::string> check_names(const Json& v, const std::set<std::string>& taken);

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

    Json loops_;                                         // daemon.json 的 loops
    std::string cwd_;                                    // 子 loop 的 cwd＝daemon 起來時的 cwd
    std::set<std::string> taken_;                        // 自己的 ctl／state 用掉的名字（taken_names）
    std::vector<std::pair<std::string, Child>> table_;   // 照加入的順序
};

}  // namespace aos::daemon
