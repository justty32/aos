// daemon.hpp：【daemon】Daemon＝aos-loop 的 Loop 子類別＋一張子 loop 的表（10-21 傍晚）。內部標頭。
//
//   daemon.cpp   建構子（AOS_STACK、loops、adopt、loops_ctl／loops_state 的檢查）、adopt、tend（對表：收多的、看誰結束、起少的）、
//                term／settle（收子項不等：SIGTERM 後照常巡，每次 tend 看一眼，退了標 stopped、滿 10 秒還在就 SIGKILL 整群＋它底下自成一群的單子；
//                10-23 壓測後改，原本原地等滿 10 秒）、finish（收掉全部、等它們退，等的時候每秒寫一份 phase stopping 的 state；
//                最後一次之後才自己結束的標 done，D7）、
//                check_ctl（ctl.json 的 loops* 不採用、過渡期提醒）、taken_names／check_names（子項名字跟自己的窗撞名，10-22）
//   windows.cpp  管轄那一對窗（10-29）：read_loops_ctl（loops_ctl.json）、check_lists、write_more（loops_state.json）、write_parts（切檔）
//   mailbox.cpp  信箱模式（10-29，medium-plan § 四 3、實作第 5 步）：open_mailbox（建四格、記下 cur/ 的殘骸）、take_letters（認領、
//                逐封驗、套進期望表）、apply_letter、done_letters（回信、收掉）
//
// daemon.json＝loop.json 的超集：exec、max、interval_ms、ctl、state 同 aos-loop，但 exec 選填、max 沒寫＝不限、
// interval_ms 沒寫＝200；多四個 key——loops＝{名字: aos-exec 的目標（字串或 [目標, 參數...]）或 loop 設定（物件）}
// （要拆成好幾份檔就寫 {"$ref": ["loops-1.json", …]}，aos-directive 照順序合起來，read_loops）、adopt（布林，沒寫＝true）、
// loops_ctl、loops_state（10-29 拆窗：管轄的手把與狀態窗的檔名，在 $AOS_STACK 底下；沒寫＝loops_ctl.json、loops_state.json，寫 null＝不開）。
// 兩個手把、兩扇狀態窗（10-29 medium-plan § 四）：ctl.json／state.json 只管 loop 面向（同 aos-loop：paused、stopped、max、interval_ms、seq）；
// loops_ctl.json 認三個 key（N-54；10-23 晚加後兩個）：loops＝整份名單、loops_added＝名單上要多這些（寫法同 loops）、
// loops_removed＝名單上要少這些（名字的陣列）、seq；期望表＝（loops_ctl 的 loops，沒寫＝daemon.json 的）＋loops_added－loops_removed。
// loops_state.json＝{kind, ctl_seq（loops_ctl 的 seq）, ctl_warning（壞的 loops_ctl）, loops 表, 心跳四欄（同 state.json）}；
// 信箱模式（10-29，選填 key loops_mailbox＝信箱的路徑，在 $AOS_STACK 底下；寫了就不開 loops_ctl，兩個都寫（loops_ctl 非 null）＝CfgBad）：
// 每圈（stopped／paused 那圈不認領）把 new/ 的信全部認領（起來時 cur/ 的殘骸排在前面重做），照名字順序逐封套進期望表 want_
// （body 的 loops_added／loops_removed，寫法同 loops_ctl；壞信丟掉、原因進 loops_state 的 letter_warning），全部套完才對一次表；
// 信收掉（不留 done/），有 reply_to 的好信回 {"applied": true}。期望表起來時＝daemon.json 的 loops＋adopt 接回、不在上面的
// （設定記 null，留在名單上直到有信 loops_removed 它；方向題 1）。
// loops 表超過 PART_ROWS（100）列就切檔：loops 寫成 {"$ref": ["<loops_state 檔名去副檔名>_loops/<雜湊>.json", …]}（write_parts）。
// 每圈先讀 ctl.json（Loop）、再讀 loops_ctl.json（tend 開頭），各自採用或不採用。ctl 的 stopped（這圈收工）或 paused（整圈暫停）時
// 不調表：不收多的、不起少的（loops_ctl 的變動等解除暫停那圈才生效），但照讀兩份 ctl、照寫兩扇 state、照收已送 SIGTERM 的、照記自己結束的。
#pragma once

#include "child/child.hpp"

#include "aos/post.hpp"

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

// 小格 $AOS_STACK/<名字>/ 會撞到的名字（使用者 10-22）：ctl、state、loops_ctl、loops_state、分檔資料夾（paths，空＝沒開）落在 $AOS_STACK 底下時相對路徑的第一段
// （"state.json"、"w/c.json" 的 "w"）；落在外面的不算。照 bin 的 taken_names（abspath 整理 `.`、`..`，不解捷徑）。
std::set<std::string> taken_names(const std::string& stack, const std::vector<std::string>& paths);

// loops（read_loops 讀好的）的名字在 taken 裡＝回原因。起來時撞＝CfgBad、退 1；loops_ctl 撞＝那份 loops_ctl 不採用。
std::optional<std::string> check_names(const Json& v, const std::set<std::string>& taken);

class Daemon : public aos::loop::Loop {
public:
    Daemon(const std::map<std::string, std::string>& opts, const std::string& spec);

protected:
    void tend(const Json& ctl) override;
    void finish() override;
    std::optional<std::string> check_ctl(Json& doc, const aos::Resolved& where) override;
    void write_more(const Json& hb) override;   // loops_state.json（沒開＝不寫）

private:
    using Table = std::list<std::pair<std::string, Child>>;

    void adopt();
    void add(const std::string& name, const Child& c);
    void term(Child& c, bool removing);   // 送 SIGTERM、phase stopping、記期限（不等）
    bool settle(Child& c);                // 收的途中看一眼：退了＝stopped、回 true；過了期限還在＝SIGKILL 整群＋底下自成一群的（只送一次）
    void read_loops_ctl();                // 讀 loops_ctl.json：好的進 lctl_good_、清 lctl_warning_；壞的不採用、原因進 lctl_warning_；檔不在＝不動
    std::optional<std::string> check_lists(Json& doc, const aos::Resolved& where);   // loops_ctl 的 loops／loops_added／loops_removed
    Json write_parts(Json rows);      // loops_state 的 loops 欄：≤ PART_ROWS 列原樣；多了就寫分檔、回 {"$ref": [分檔, …]}
    const Json& ctl_want(Json& merged);   // ctl 模式的期望表（loops_ctl 的 loops 或 daemon.json 的，＋loops_added－loops_removed）
    void reconcile(const Json& want);     // 對表：收多的、看誰結束、起少的

    // 信箱模式（mailbox.cpp）
    using Letters = std::vector<std::pair<std::string, bool>>;   // 這圈的信（照處理順序）：{信號, 好信}
    void open_mailbox();                                     // 建四格（已在就沿用）、cur/ 的殘骸記進 redo_
    Letters take_letters();                                  // 認領、逐封驗；好信依序套進 want_
    std::optional<std::string> apply_letter(const Json& body);   // 驗 body、套進 want_；壞＝回原因、want_ 不動
    void done_letters(const Letters& got);                   // 好信有 reply_to 的回 applied；全部收掉

    Json loops_;                                         // daemon.json 的 loops
    std::string cwd_;                                    // 子 loop 的 cwd＝daemon 起來時的 cwd
    std::string lctl_path_;                              // loops_ctl.json（空＝不開）
    std::string lstate_path_;                            // loops_state.json（空＝不開）
    Json lctl_good_ = Json::object();                    // 最後一份好的 loops_ctl（一份都沒讀到過＝{}）
    Json lctl_warning_;                                  // null 或字串（loops_state 的 ctl_warning）
    std::set<std::string> taken_;                        // 自己的窗／分檔資料夾用掉的名字（taken_names）
    std::string parts_dir_;                              // loops_state 分檔的資料夾（沒開 loops_state＝空）
    std::set<std::string> parts_prev_;                   // 上一次寫的 state 用到的分檔檔名（清舊分檔時留著）
    bool parts_wrote_ = false;                           // 這個行程寫過 state 了沒（第一次不清：磁碟上的主檔可能還指著舊的）
    std::string mbox_path_;                              // loops_mailbox（空＝ctl 模式）
    aos::post::Mailbox mbox_;
    std::vector<std::string> redo_;                      // 起來時 cur/ 裡的（上次做到一半死掉），第一個認領的圈排在 new/ 前面重做
    Json want_ = Json::object();                         // 信箱模式的期望表（記憶體裡；重起時從 daemon.json＋adopt 重建）
    Json letter_warning_;                                // null 或字串（loops_state 的 letter_warning：最後一封壞信）
    Table table_;                                        // 照加入的順序（loops_state 的 loops 也照這個順序）
    std::unordered_map<std::string, Table::iterator> index_;   // 名字 → 表上那一列（10-23 壓測：原本逐列找，N 個名字 N×N）
};

}  // namespace aos::daemon
