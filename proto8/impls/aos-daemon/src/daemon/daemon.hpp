// daemon.hpp：【daemon】Daemon＝aos-loop 的 Loop 子類別＋一張子 loop 的表（10-21 傍晚）。內部標頭。
//
//   daemon.cpp   建構子（AOS_STACK、loops、adopt 的檢查）、adopt、tend（對表：收多的、看誰結束、起少的）、
//                term／settle（收子項不等：SIGTERM 後照常巡，每次 tend 看一眼，退了標 stopped、滿 10 秒還在就 SIGKILL 整群；
//                10-23 壓測後改，原本原地等滿 10 秒）、finish（收掉全部、等它們退，等的時候每秒寫一份 phase stopping 的 state；
//                最後一次之後才自己結束的標 done，D7）、
//                info（loops 表）、check_ctl（ctl 的 loops）、taken_names／check_names（子項名字跟自己的 ctl／state 撞名，10-22）
//
// daemon.json＝loop.json 的超集：exec、max、interval_ms、ctl、state 同 aos-loop，但 exec 選填、max 沒寫＝不限、
// interval_ms 沒寫＝200；多兩個 key——loops＝{名字: aos-exec 的目標（字串或 [目標, 參數...]）或 loop 設定（物件）}
// （要拆成好幾份檔就寫 {"$ref": ["loops-1.json", …]}，aos-directive 照順序合起來，read_loops）、adopt（布林，沒寫＝true）。
// ctl 多認三個 key（N-54；10-23 晚加後兩個）：loops＝整份名單、loops_added＝名單上要多這些（寫法同 loops）、
// loops_removed＝名單上要少這些（名字的陣列）；期望表＝（ctl 的 loops，沒寫＝daemon.json 的）＋loops_added－loops_removed。
// state 的 loops 表超過 PART_ROWS（100）列就切檔：loops 寫成 {"$ref": ["<state 檔名去副檔名>_loops/<雜湊>.json", …]}（write_parts）。
#pragma once

#include "child/child.hpp"

#include <list>
#include <set>
#include <unordered_map>
#include <string>
#include <utility>
#include <vector>

namespace aos::daemon {

// 讀一份 loops（daemon.json 的 loops，ctl 的 loops、loops_added 共用；10-23 晚）：回 {名字: 子項}（照寫的順序）。
//   寫法：物件 {名字: 子項}（拆成好幾份檔＝{"$ref": [檔, …]}，aos-directive 合物件、同名後面的蓋前面的；10-23 使用者，
//   取代原本的「物件的陣列＝分檔」）。
//   指示詞（base＝v 裡相對 $ref 的起點）：loops 本身、每個子項本身先換一層（resolve_shallow；子項的起點＝它來自的那份檔的）；子項是字串或陣列
//   （aos-exec 的目標）就整個解；是物件（loop 設定）就只解 daemon 要寫進小格的 loop key（exec、max、interval_ms、ctl、state），
//   其他 key（body…）原樣交給子 loop——相對 $ref 搬進小格就會從小格算，所以 loop key 由 daemon 先解。
//   exec 是單子（物件，10-24）：只換一層、裡面不解（留給子 loop 跑的時候解，那時 AOS_CF／AOS_CO 設好了），
//   裡面相對的 $ref 檔名照它來自的那份檔轉成絕對（abs_refs）——搬進小格之後才不會從小格算。
//   名字非空、不含 /、不含 #（會被 aos-exec 當成指標的開頭）、不以 . 開頭；子項是字串、陣列或物件（loop key 以外不驗）。
// 壞丟 Error{CfgBad, 原因}（key＝訊息裡的名字）；指示詞解不開丟 DirectiveBad。
Json read_loops(const Json& v, const std::string& base, const std::string& key);

// 把 v 裡每個 $ref 指示詞的相對檔名接在 base 後面（`檔#/…` 只動 `#` 前面；$ref 陣列每個元素都轉；絕對的、只有 `#/…` 的不動）。
// 不解任何指示詞。給 read_loops 處理內嵌單子用（10-24）。
Json abs_refs(const Json& v, const std::string& base);

// 小格 $AOS_STACK/<名字>/ 會撞到的名字（使用者 10-22）：ctl、state（paths，空＝沒開）落在 $AOS_STACK 底下時相對路徑的第一段
// （"state.json"、"w/c.json" 的 "w"）；落在外面的不算。照 bin 的 taken_names（abspath 整理 `.`、`..`，不解捷徑）。
std::set<std::string> taken_names(const std::string& stack, const std::vector<std::string>& paths);

// loops（read_loops 讀好的）的名字在 taken 裡＝回原因。起來時撞＝CfgBad、退 1；ctl 撞＝那份 ctl 不採用。
std::optional<std::string> check_names(const Json& v, const std::set<std::string>& taken);

class Daemon : public aos::loop::Loop {
public:
    Daemon(const std::map<std::string, std::string>& opts, const std::string& spec);

protected:
    void tend(const Json& ctl) override;
    void finish() override;
    Json info() override;
    std::optional<std::string> check_ctl(Json& doc, const aos::Resolved& where) override;

private:
    using Table = std::list<std::pair<std::string, Child>>;

    void adopt();
    void add(const std::string& name, const Child& c);
    void term(Child& c, bool removing);   // 送 SIGTERM、phase stopping、記期限（不等）
    bool settle(Child& c);                // 收的途中看一眼：退了＝stopped、回 true；過了期限還在＝SIGKILL 整群（只送一次）
    Json write_parts(Json rows);      // state 的 loops 欄：≤ PART_ROWS 列原樣；多了就寫分檔、回 {"$ref": [分檔, …]}

    Json loops_;                                         // daemon.json 的 loops
    std::string cwd_;                                    // 子 loop 的 cwd＝daemon 起來時的 cwd
    std::set<std::string> taken_;                        // 自己的 ctl／state／分檔資料夾用掉的名字（taken_names）
    std::string parts_dir_;                              // state 分檔的資料夾（沒開 state＝空）
    std::set<std::string> parts_prev_;                   // 上一次寫的 state 用到的分檔檔名（清舊分檔時留著）
    bool parts_wrote_ = false;                           // 這個行程寫過 state 了沒（第一次不清：磁碟上的主檔可能還指著舊的）
    Table table_;                                        // 照加入的順序（state 的 loops 也照這個順序）
    std::unordered_map<std::string, Table::iterator> index_;   // 名字 → 表上那一列（10-23 壓測：原本逐列找，N 個名字 N×N）
};

}  // namespace aos::daemon
