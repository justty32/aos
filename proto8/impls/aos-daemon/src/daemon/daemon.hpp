// daemon.hpp：【daemon】Daemon＝aos-loop 的 Loop 子類別＋一張子 loop 的表（10-21 傍晚）。內部標頭。
//
//   daemon.cpp   建構子（AOS_STACK、loops、adopt、loops_ctl／loops_state 的檢查）、adopt、tend（對表：收多的、看誰結束、起少的）、
//                term／settle（收子項不等：SIGTERM 後照常巡，每次 tend 看一眼，退了標 stopped、滿 10 秒還在就 SIGKILL 整群＋它底下自成一群的單子；
//                10-23 壓測後改，原本原地等滿 10 秒）、finish（收掉全部、等它們退：先寫一份 phase stopping 的 state，之後每退一個寫一次 loops_state；
//                最後一次之後才自己結束的標 done，D7）、drop（子項結束：印 log 一行、從表上拿掉、本次執行不再起，11-02）、log_child、
//                check_ctl（ctl.json 的 loops* 不採用、過渡期提醒；10-22 的 taken_names／check_names〔子項名字跟自己的窗撞名〕11-02 拿掉：小格在 loops/<名字>/、撞不到）、
//                read_execs、merge_want、check_apart（10-30 execs）
//   windows.cpp  管轄那一對窗（10-29）：read_loops_ctl（loops_ctl.json）、check_lists、write_more（loops_state.json）、write_parts／clean_parts（切檔）
//   mailbox.cpp  信箱模式（10-29，medium-plan § 四 3、實作第 5 步）：open_mailbox（建四格、記下 cur/ 的殘骸）、take_letters（認領、
//                逐封驗、套進期望表）、apply_letter、done_letters（回信、收掉）
//
// daemon.json＝loop.json 的超集：exec、max、interval_ms、ctl、state 同 aos-loop，但 exec 選填、max 沒寫＝不限、
// interval_ms 沒寫＝200（ctl、state 寫 null＝不開，同沒寫）；多幾個 key——loops＝{名字: aos-exec 的目標（字串或 [目標, 參數...]）或 loop 設定（物件）}
// （要拆成好幾份檔就寫 {"$ref": ["loops-1.json", …]}，aos-directive 照順序合起來，read_loops）、adopt（布林，沒寫＝true）、
// loops_ctl、loops_state（10-29 拆窗：管轄的手把與狀態窗的檔名，在 $AOS_STACK 底下；沒寫＝loops_ctl.json、loops_state.json，寫 null＝不開）、
// loops_ctl_mailbox（11-02 晚原 loops_mailbox；沒寫、null＝不開）、execs（10-30）。命令列 `-- 參數...` 只接在 daemon 自己的 exec（Loop；沒 exec＝ArgumentsBad）。
// 兩個手把、兩扇狀態窗（10-29 medium-plan § 四）：ctl／state（慣用名 daemon_ctl.json／daemon_state.json，11-02；程式沒有預設名）只管 loop 面向（同 aos-loop：paused、stopped、max、interval_ms、seq）；
// loops_ctl.json 認（N-54；10-23 晚加 *_added／*_removed）：loops＝整份名單、loops_added＝名單上要多這些（寫法同 loops）、
// loops_removed＝名單上要少這些（名字的陣列）、execs（11-02 晚，整份的 execs，跟 loops 對稱）、execs_added、execs_removed、seq；
// 期望表＝（loops_ctl 的 loops，沒寫＝底的）＋loops_added－loops_removed，execs 同理。
// 底（11-02 晚，want_／want_execs_，記憶體裡）＝起來時 daemon.json 的 loops／execs（開了信箱再加 adopt 接回、不在上面的）＋信改過的。
// loops_state.json＝{ctl_seq（loops_ctl 的 seq）, ctl_warning（壞的 loops_ctl）, loops 表, execs 表（10-30）, pid, started_at_ticks, boot_id, updated_at}
// （11-02：kind、recorded_at 拿掉；有變才寫——表、ctl_seq、ctl_warning、mailbox_warning 跟上一份寫出去的一樣就不碰檔）；
// 信箱（10-29；11-02 晚 key 改名 loops_ctl_mailbox、跟 loops_ctl 共存，兩個都開、只開一個、都不開都行；都不開＝名單只看 daemon.json）：
// 每圈（stopped／paused 那圈不認領）把 new/ 的信全部認領（起來時 cur/ 的殘骸排在前面重做），照名字順序逐封套進底 want_
// （body 的 loops_added／loops_removed／execs_added／execs_removed，寫法同 loops_ctl；壞信丟掉、原因進 loops_state 的 mailbox_warning〔11-02 晚原 letter_warning〕），
// 全部套完再疊 loops_ctl、才對一次表；信收掉（不留 done/），有 reply_to 的好信回 {"applied": true}。開了信箱時底多 adopt 接回、不在 daemon.json 上的
// （設定記 null，留在名單上直到有信 loops_removed 它、或它結束；方向題 1）。信套完（疊上 loops_ctl 之後）loops 與 execs 同名＝壞信。
// loops 表超過 PART_ROWS（100）列就切檔：loops 寫成 {"$ref": ["<loops_state 檔名去副檔名>_loops/<雜湊>.json", …]}（write_parts）。
// 每圈先讀 ctl.json（Loop）、再讀 loops_ctl.json（tend 開頭），各自採用或不採用。ctl 的 stopped（這圈收工）或 paused（整圈暫停）時
// 不調表：不收多的、不起少的（loops_ctl 的變動等解除暫停那圈才生效），但照讀兩份 ctl、照寫兩扇 state、照收已送 SIGTERM 的、照記自己結束的。
// exec 型子項（10-30，thinking 2026-10-30-agent-lifecycle B-12 ②、N-28／N-54 的 10-30 補草稿）：daemon.json 多一個選填 key execs＝一次性的子項，
// 形狀同 loops（{名字: 目標} 或 {名字: {"exec": 目標}}；目標＝aos-exec 的目標，字串或 [目標, 參數...]），daemon 直接 aos-exec 它一次
// （spawn_exec：不包 aos-loop、不寫 loop.json、不補 ctl／state），退了＝done、不重起（同子 loop）。
// 11-02 晚（使用者「6.要」）：{"exec": 內嵌單子} 也收——寫成小格的 exec.json、`aos-exec -- 小格/exec.json#/exec` 跑一次（cwd 定成 daemon 的 cwd）。
// 子項結束後不留名單（11-02 使用者「改成子項結束後不留名單」；取代 10-30 方向題 2 的「列留著，名單拿掉才消失」）：loop 型、exec 型都一樣，
// 退了（自己結束 done、被收 stopped）印完 log 那行就從表上拿掉（loops_state 看不到它），小格 loops/<名字>/ 照留。自己結束（done）的
// 本次執行不再起（不然下一圈對表又起它，變成自動重起）：一律記進 ended_（名字＋種類），期望表扣掉它們，某一圈算出的期望表裡沒有它了
//（同種類）才從 ended_ 拿掉（之後名單再有它就照常起）。開了信箱再從底拿掉，而且下一圈套信之前不是 loops_ctl 疊上去的（from_ctl）就從 ended_ 放掉
//（之後再有信同名 *_added＝重新起；11-02 晚共存時的規則）。
// daemon 重起時 ended_ 是空的（照 daemon.json 再起），adopt 只接回活著的。被收掉（stopped）的不記：它本來就不在期望表上（或換了種類）。
// log（11-02，stdout；11-02 晚起同 aos-loop 預設不印、--enable-logs 才印）：子項起來一行、結束一行 {"at", "name", "table"（loops／execs）, "phase"（running／done／stopped）,
// "pid", "code", "signal", "ws"（有給才有）}（起來那行 code／signal 是 null；adopt 接回的也印一行 running；接回的不是自己的子行程，結束那行 code／signal 是 null）。
// 子項的 stdout 照舊丟掉（N-28），不會混進來；daemon 自己有身體時同 aos-loop 每跑完一次一行。
// execs 與 loops 共用名字空間（小格同一個資料夾）：同一個名字兩邊都在期望表上＝撞名（daemon.json＝CfgBad；loops_ctl＝不採用；信＝壞信）。
// loops_ctl 與信多認 execs_added／execs_removed（語意同 loops_added／loops_removed）；loops_ctl 另認整份的 execs（11-02 晚；信沒有整份的）。
// 表只有一張（table_，Child::once 分兩種），loops_state.json 寫成兩張：loops、execs；adopt 兩張都接。表上的種類跟期望表的不一樣
// （例 loops_removed bob＋execs_added bob）＝當成不在期望表上：收掉舊的、下一次起新的。
// 子項的工作區 ws（eca 10-30，thinking 2026-10-30-eca 衝突 1、N-28／N-54 補草稿）：loops、execs（daemon.json、loops_ctl 的 loops、*_added、信）的子項物件
// 多認選填 ws——解指示詞、從 daemon 的 cwd 轉絕對、留在期望表上；起子項時子行程設 AOS_WS（沒寫＝繼承 daemon 的）。loop 型的 ws 不寫進小格 loop.json。
// ws 改了＝設定變了，照 N-54「已在跑的不重起」；loops_state 的列起它時給了 ws 才多一欄 ws（起的那一刻的值；沒給不寫）。
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
//   物件的 ws（eca 10-30）：解指示詞、要是非空字串（null＝拿掉）、從 daemon 的 cwd 轉絕對（fix_ws）。
// 壞丟 Error{CfgBad, 原因}（key＝訊息裡的名字）；指示詞解不開丟 DirectiveBad。
Json read_loops(const Json& v, const std::string& base, const std::string& key);

// 把 v 裡每個 $ref 指示詞的相對檔名接在 base 後面（`檔#/…` 只動 `#` 前面；$ref 陣列每個元素都轉；絕對的、只有 `#/…` 的不動）。
// 不解任何指示詞。給 read_loops 處理內嵌單子用（10-24）。
Json abs_refs(const Json& v, const std::string& base);

// 讀一份 execs（daemon.json 的 execs，loops_ctl 與信的 execs_added 共用；10-30）：同 read_loops（名字規則、指示詞），再把每項收成目標——
// 字串、[目標, 參數...]（非空字串陣列）原樣；物件＝取它的 exec（要是上面兩種；其他 key 忽略）。單子物件、其他型別＝Error{CfgBad}。
// 例外（eca 10-30）：物件寫了 ws＝收成 {"exec": 目標, "ws": 絕對路徑}（spawn_exec 認這個形狀）。
Json read_execs(const Json& v, const std::string& base, const std::string& key);

// 期望表的一半（10-23 晚，10-30 抽出來給 loops、execs 共用）：base＋ctl[added]－ctl[removed]，先加後減（同一個名字兩邊都寫＝不要；
// 已在 base 上的換成 added 的設定、不在的接在尾巴）。ctl 兩個 key 都沒寫＝回 base 本身（不複製）；不然結果寫進 merged、回 merged。
const Json& merge_want(const Json& base, const Json& ctl, const char* added, const char* removed, Json& merged);

// loops 與 execs 兩份期望表有同一個名字＝回原因（共用名字空間，10-30）。
std::optional<std::string> check_apart(const Json& loops, const Json& execs);

class Daemon : public aos::loop::Loop {
public:
    Daemon(const std::map<std::string, std::string>& opts, const std::string& spec, const std::vector<std::string>& args = {});

protected:
    void tend(const Json& ctl) override;
    void finish() override;
    std::optional<std::string> check_ctl(Json& doc, const aos::Resolved& where) override;
    void write_more(const Json& me) override;   // loops_state.json（沒開＝不寫；有變才寫，11-02）

private:
    using Table = std::list<std::pair<std::string, Child>>;

    void adopt();
    void add(const std::string& name, const Child& c);   // 放上表＋印 log 一行（running）
    Table::iterator drop(Table::iterator it);             // 子項結束（done／stopped）：印 log 一行、done 的記成本次不再起（forget）、從表上拿掉；回下一列
    void log_child(const std::string& name, const Child& c);   // log 一行（見檔頭）
    void flush_table();                                   // 表變了：寫 loops_state（有變才寫）；寫不了丟 StateError
    void term(Child& c);                  // 送 SIGTERM、phase stopping、記期限（不等）
    bool settle(Child& c);                // 收的途中看一眼：退了＝stopped、回 true；過了期限還在＝SIGKILL 整群＋底下自成一群的（只送一次）
    void read_loops_ctl();                // 讀 loops_ctl.json：好的進 lctl_good_、清 lctl_warning_；壞的不採用、原因進 lctl_warning_；檔不在＝不動
    std::optional<std::string> check_lists(Json& doc, const aos::Resolved& where);   // loops_ctl 的 loops／loops_added／loops_removed／execs_added／execs_removed
    // loops_state 的 loops、execs 欄：≤ PART_ROWS 列原樣；多了就寫分檔、回 {"$ref": [分檔, …]}；用到的分檔名記進 now（兩張表同一個分檔資料夾）
    Json write_parts(Json rows, std::set<std::string>& now);
    void clean_parts(const std::set<std::string>& now);   // 兩張表都寫好之後：清掉這次與上一次都沒用到的分檔
    // ctl 模式的期望表（ctl＝一份驗過的 loops_ctl）：loops＝（ctl 的 loops，沒寫＝daemon.json 的）＋loops_added－loops_removed；
    // execs＝daemon.json 的 execs＋execs_added－execs_removed（10-30）。回的參照指向 base 或 lm／em。
    std::pair<const Json*, const Json*> ctl_want(const Json& ctl, Json& lm, Json& em) const;
    bool from_ctl(const std::string& name, bool once) const;   // 名字是 loops_ctl 疊上去的（它的 loops／execs 或 *_added 裡有；沒開 loops_ctl＝false）
    void reconcile(const Json& want, const Json& want_execs);   // 對表：收多的、看誰結束、起少的（10-30 起兩份：子 loop、exec 型子項）

    // 信箱（mailbox.cpp）
    using Letters = std::vector<std::pair<std::string, bool>>;   // 這圈的信（照處理順序）：{信號, 好信}
    void open_mailbox();                                     // 建四格（已在就沿用）、cur/ 的殘骸記進 redo_
    Letters take_letters();                                  // 認領、逐封驗；好信依序套進 want_
    std::optional<std::string> apply_letter(const Json& body);   // 驗 body、套進 want_；壞＝回原因、want_ 不動
    void done_letters(const Letters& got);                   // 好信有 reply_to 的回 applied；全部收掉

    Json loops_;                                         // daemon.json 的 loops
    Json execs_ = Json::object();                        // daemon.json 的 execs（10-30；{名字: 目標}，read_execs 收好的）
    std::string cwd_;                                    // 子 loop 的 cwd＝daemon 起來時的 cwd
    std::string lctl_path_;                              // loops_ctl.json（空＝不開）
    std::string lstate_path_;                            // loops_state.json（空＝不開）
    Json lctl_good_ = Json::object();                    // 最後一份好的 loops_ctl（一份都沒讀到過＝{}）
    Json lctl_warning_;                                  // null 或字串（loops_state 的 ctl_warning）
    std::string parts_dir_;                              // loops_state 分檔的資料夾（沒開 loops_state＝空）
    std::set<std::string> parts_prev_;                   // 上一次寫的 state 用到的分檔檔名（清舊分檔時留著）
    bool parts_wrote_ = false;                           // 這個行程寫過 state 了沒（第一次不清：磁碟上的主檔可能還指著舊的）
    std::string mbox_path_;                              // loops_ctl_mailbox（空＝不開；11-02 晚原 loops_mailbox）
    aos::post::Mailbox mbox_;
    std::vector<std::string> redo_;                      // 起來時 cur/ 裡的（上次做到一半死掉），第一個認領的圈排在 new/ 前面重做
    Json want_ = Json::object();                         // 底的 loops（11-02 晚；記憶體裡；重起時從 daemon.json＋adopt 重建；信改它）
    Json want_execs_ = Json::object();                   // 底的 execs（10-30；同 want_）
    Json mailbox_warning_;                               // null 或字串（loops_state 的 mailbox_warning：最後一封壞信；11-02 晚原 letter_warning）
    std::set<std::pair<std::string, bool>> ended_;       // 本次執行已自己結束的 {名字, 是不是 exec 型}（11-02，見檔頭）
    bool more_wrote_ = false;                            // 寫過 loops_state 沒（這個行程第一份一定寫）
    bool parts_stale_ = false;                           // 上一次寫完還留著「再上一次」的分檔：下一次沒變的那一下清（11-02）
    Json last_more_;                                     // 上一份寫出去的 loops_state（分檔前的表、不含 proc_fields／updated_at；比有沒有變用）
    Table table_;                                        // 照加入的順序（loops_state 的 loops 也照這個順序）
    std::unordered_map<std::string, Table::iterator> index_;   // 名字 → 表上那一列（10-23 壓測：原本逐列找，N 個名字 N×N）
};

}  // namespace aos::daemon
