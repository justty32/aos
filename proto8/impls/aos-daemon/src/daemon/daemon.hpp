// daemon.hpp：【daemon】Daemon 管普通 proc 表、stuck 判定、clock 設定展開、手把與狀態窗；aos-loop 的 Loop 子類別，內部標頭。
//
// 11-06（no-pid P6）：通用布林 auto_restart 讓任何 proc 常駐（可 stop／sleep、收工睡／開門醒），退了同一拍重起；連 3 次起後 3 秒內退＝stopped＋reason、要 start。
//   表上 auto_restart、restart_on_stuck 只在 true 時寫，不看子項型別。
// 11-06（no-pid P7）：stuck_after_cycles 每列選填正整數、預設 10，寫壞＝CfgBad；有效值寫回表供 adopt 保留。
//   任何 proc 都讀父設定的公開窗名或預設 ctl.json／state_flux.json，不認子程式身分。
//   只判內部 running 列；任一窗缺、state_flux 非物件、窗 null＝清 stuck 與期限、不判。
//   ctl mtime（UTC 截到毫秒）> responded_at（null 最舊），且 > 父這次起／接回基準＝刺激；首見記 deadline_after(cycles)，expired 後標 stuck。
//   stuck 是 bool，表上投影 phase／reason，不改內部生命週期；刺激消失清期限與標記，回 running；adopt 將 stuck 當 running 接回、重設基準。
//   restart_on_stuck=true 時同拍 SIGTERM，10 秒後 SIGKILL 整群，settle 後照表重起；父 paused 只標、不起停。
//   連 3 次卡住（起初一輪計入，最多實際重起 2 次）沒任何新回應＝收完留 stopped＋英文 reason、要人 start；起／接回後的新回應清連敗。
//   人工 stop／sleep／rm 優先於卡住重起；卡住重起收途中父收工，該列改留 sleeping。
// 11-06（T7）：clock 沒寫／null／false 不管時鐘；true 或 {file?, interval_ms?, name?} 在入口展開成第一列普通 loop proc。
//   預設 file＝daemon stack/clock、name＝_clock、interval_ms＝aos::clock_interval_ms()；exec 用內嵌單子 argv 跑 PATH 上的 aos-clock，auto_restart＝true。
//   名字與 daemon.json 的 procs 撞到、未知 key／型別／值壞＝CfgBad；指示詞同其他設定格。後續流程不辨認哪列是時鐘。
//   起任何子項／身體之前設 AOS_CLOCK＝file 絕對路徑；明寫 interval_ms 就設 AOS_CLOCK_INTERVAL（寫 1000 也設），沒寫就繼承。
//   改 clock 要整台 sleep 再改再 wake；兩份定義勿共用同一時鐘檔。pause 那列只停時間、工作照跑。
//   daemon.cpp   建構子、clock 展開與環境、stack 鎖；procs.cpp 解 procs 與合併名單
//   adopt.cpp    接回上次的表、尋找小格裡活著的子 loop
//   table.cpp    維護表、log 與 state 寫入結果
//   tend.cpp     term／halt／hold／settle／look／tend／finish；stuck.cpp 公開窗刺激、期限與重起
//   failure.cpp  整理停止原因；body.cpp 跑 daemon 身體
//   reconcile.cpp 依期望表起停子項；ctl.cpp 控制窗的名單與集合
//   windows.cpp  管轄那一對窗：read_procs_ctl（procs_ctl.json）、check_lists、write_more（procs_state.json）、write_parts／clean_parts（切檔）
//   mailbox.cpp  信箱（procs_ctl_mailbox）：open_mailbox、take_letters、apply_letter、done_letters
//
// daemon.json＝loop.json 的超集：exec、max、interval_ms、ctl、state 同 aos-loop，但 exec 選填、max 沒寫＝不限、interval_ms 沒寫＝200
// （ctl、state 寫 null＝不開）；多幾個 key——procs＝{名字: proc}（拆檔＝{"$ref": [檔, …]}）、adopt（布林，沒寫＝true）、
// procs_ctl、procs_state（在 $AOS_STACK 底下的檔名；沒寫＝procs_ctl.json、procs_state.json，null＝不開）、procs_ctl_mailbox（11-04 起沒寫＝procs_ctl_mailbox、null＝不開）、
// procs_loop、procs_exec、procs_stderr（11-04：小格裡 daemon 寫的三個檔名，沒寫＝loop.json、exec.json、stderr.txt；見 child.hpp 的 CellNames）。
// 舊名 loops、execs、loops_ctl、loops_state、loops_ctl_mailbox 不認（C-48，使用者 11-03「當沒看到」）。命令列 `-- 參數...` 只接在 daemon 自己的 exec。
// 每個 proc 怎麼起看寫法（沒有 kind，procs § 2）：字串、陣列、或 key 只有 exec（＋ws、stack、def、limits、auto_restart、restart_on_stuck、stuck_after_cycles）的物件＝exec 型（aos-exec 一次）；其他物件＝loop 型（包成子 aos-loop）。
// 物件的 stack（procs § 2b）：proc 的 stack（從 daemon 的 cwd 轉絕對、不在就 mkdir -p、不查不擋）；沒寫＝$AOS_STACK/procs/<名字>/。ws＝子行程的 AOS_WS。
// 物件的 def（11-04，aos-agent，使用者「那就b。」）：定義資料夾（從 daemon 的 cwd 轉絕對；不驗、只記進表的 def 欄，不灌進 loop.json）。
// 物件的 limits（11-05 feat-proto 件 5）：份額（child/limits.hpp；不灌進 loop.json）；daemon.json 頂層 limits＝沒寫的列用的預設。
//   子行程在 run_cli 之前 setrlimit／換身分（等同 s6-softlimit／s6-setuidgid，daemon 自己做、不 exec s6）；失敗＝小格 stderr.txt 一行 LimitBad、退 1。
// 兩個手把、兩扇狀態窗：ctl／state 只管 loop 面向（同 aos-loop：11-03 起 ctl 是一道指令 cmd＝pause／resume／stop）；
// procs_ctl.json 認（N-54）：procs＝整份名單、procs_added、procs_removed、procs_stopped（要停的名字）、procs_started（要起的名字）、seq。
// 期望表＝（procs_ctl 的 procs，沒寫＝底 want_）＋procs_added－procs_removed；stopped 集合＝底 stopped_＋procs_stopped－procs_started（同名兩邊都寫＝起）。
// 底（記憶體）：want_＝daemon.json 的 procs（開了信箱再加 adopt 接回、不在上面的，設定記 null）＋信改過的；stopped_＝adopt 接回的 stopped 列＋信改過的。
// 信（procs_ctl_mailbox）body 認 procs_added、procs_removed、procs_stopped、procs_started，改的是底；ping 必須是 true，只回信、不改底；壞信原因進 state_flux 的 mailbox_warning。
// procs_stopped／procs_started／procs_slept／procs_woken 適用所有 proc；不在期望表的名字＝不管。
// 四態（procs § 0、§ 2c；ctl-commands § 5）：running（表上、活著）、stopping（收的途中）、stopped（表上、行程不在、stack 留著）、表上沒有；
//   11-03 多一態 sleeping（procs § 8 sleep／wake）：daemon 收工（ctl 的 stop、SIGTERM／SIGINT）時 running 的 proc＝SIGTERM 收掉、列留成 sleeping
//   （pid null、stack 留著）；daemon 再開 adopt 接回、不進 stopped 集合＝第一圈用列上的 stack 再起（wake；暫停中的照它自己 state.json 的 paused 接著暫停）。
//   收工時 held 的照舊保留；stop 途中的留 stopped、sleep 繼續睡、rm 途中的移除；卡住重起收途中改留 sleeping。
//   收工途中 kill -9 再開也照 stopping 列的 stop_mode 接回；finishing 只用來補回仍記為 running 的列。
//   睡著時收到 stop（procs_stopped）＝改成 stopped、不 wake。kill -9 的 daemon 沒走收工，不在此列。
//   stop（名字在期望表又在 stopped 集合）＝往子 loop 的 ctl.json 寫 {"cmd": "stop", "seq": N}，等它跑完這次自己退（沒有時間上限）→列留成 stopped
//   （pid null）；add＋stop 同時＝直接一列 stopped、不起、stack 不建。start（拿出 stopped 集合）＝下一圈用列上的 stack 再起（不清 ctl：子 loop 比舊 state_flux 的 ctl_seq，已套用過的 stop 不重做）。
//   只有指令叫起：信來、procs_added 同名都不會把 stopped 的拉起來（同名 add＝設定換掉、停照停）。
//   其他退 0 的（跑滿、身體退 10、別人直接往子 loop 的 ctl 寫 stop）照 11-02 從表上拿掉（使用者 11-03「照舊拿掉」）；自己結束（done）的本次執行不再起（ended_）。
//   11-05（edge-agent 題 1、edge-daemon 題 2，使用者選「留表標 stopped」「一起改成留表」）：任何 proc 退非 0（含被訊號打掉）＝列留成 stopped＋reason、
//   進 stopped 集合（start 才再起）；退 0、接回的（拿不到碼）照舊拿掉。
//   同名改寫法：已在跑的不重起（N-54）。
// procs_state.json＝{procs_loop, procs_exec, procs_stderr, procs_ctl_mailbox（沒開信箱＝null）,
//   daemon（上一層的 AOS_DAEMON，根或指自己＝null）, procs 表, pid, started_at_ticks, boot_id, updated_at}，有變才寫。
// state_flux.json＝Loop 的 ctl 回音與 responded_at，再加 procs_ctl_seq、procs_ctl_warning、mailbox_warning（開了信箱才有）。
// responded_at 只在處理新 ctl、收到信、起或收子項時更新；穩定窗先寫、回音窗最後寫。
// 每列 {pid, started_at_ticks, phase（running／stuck／stopping／stopped／sleeping）, code, signal, stack, exec, def, reason, launch, stop_mode?（stopping 時）, ws?, limits?（11-05：生效的份額）}（exec 11-04 晚：起它時的目標，見 exec_of；def 11-04：見 def_of）；表超過 PART_ROWS（100）列就切檔到 procs_state_procs/。
// ctl 的 stop（這圈收工）或 pause（整圈暫停）時不調表：不收多的、不起少的、起停也等解除，但照讀兩份 ctl、照寫兩扇 state、照收已在收的、照記自己結束的。
// log（--enable-logs 才印到 stdout）：行程起來一行、結束一行 {"at", "name", "phase"（running／done／stopped／sleeping）, "pid", "code", "signal", "ws"?}。
// 11-05（portable-flow，見 docs/03「11-05 搬家相關」）：信／procs_ctl 多認 procs_slept、procs_woken（sleep＝現在就睡、列 sleeping，這一班 wake 才醒；daemon 重開 slept 集合空＝自己醒）；
//   表上 stack／ws／exec／def 存相對 daemon 的 stack（adopt 用 unrel 拼回）；wake／start 起來 REVIVE_MS 內就退＝列留 stopped＋reason（11-07 B 起任何 proc 退非 0 都留，REVIVE_MS 只分原因字樣）；
//   起來先 check_running：flock 鎖住 stack 資料夾（鎖到行程結束）；鎖不到＝同一個 stack 已有 daemon 活著＝DaemonExists。
// 11-05（edge-daemon 題 1，使用者「記一行、下一圈再跑 (Recommended)」）：身體（exec）由 daemon 自己在 tend 最後跑（run_body；Loop 當沒有身體），
//   退非 0、起不來＝不收工：stderr 一行（變了才印）、state 的 body_code、下一圈再跑；退 10＝收工（同 ctl stop）。aos-loop 本身照舊（P-20）。
#pragma once

#include "child/child.hpp"

#include "aos/post.hpp"

#include <chrono>
#include <list>
#include <map>
#include <set>
#include <unordered_map>
#include <string>
#include <utility>
#include <vector>

namespace aos::daemon {

inline constexpr int REVIVE_MS = 3000;   // 起後 3 秒內退出：原因字樣與 auto_restart 連敗計數共用

// 小格裡有活著的子 loop 時回 pid 與 ticks；adopt.cpp 與 reconcile.cpp 共用。
std::optional<std::pair<pid_t, long long>> live_in_cell(const std::string& cell, const std::string& loop_name);

// 讀一份 procs（daemon.json 的 procs，procs_ctl 的 procs、procs_added，信的 procs_added 共用）：回 {名字: proc}（照寫的順序）。
//   寫法：物件 {名字: proc}（拆成好幾份檔＝{"$ref": [檔, …]}，aos-directive 合物件、同名後面的蓋前面的）。
//   指示詞（base＝v 裡相對 $ref 的起點）：procs 本身、每個 proc 本身先換一層（子項的起點＝它來自的那份檔的）；字串或陣列（aos-exec 的目標）
//   就整個解、要是字串或非空字串陣列；物件只解 daemon 認的格（exec、max、interval_ms、ctl、state、state_flux、ws、stack、def、limits、auto_restart、restart_on_stuck、stuck_after_cycles），其他 key（body…）原樣交給子 loop。
//   exec 是單子（物件）：只換一層、裡面不解，相對的 $ref 檔名照它來自的那份檔轉成絕對（abs_refs）。
//   名字非空、不含 /、不含 #、不以 . 開頭。物件的 ws、stack、def：要是非空字串（null＝拿掉）、從 daemon 的 cwd 轉絕對（stack 結尾不帶 /）。
//   exec 型的物件（is_once）的 exec 要是目標或單子。
// 壞丟 Error{CfgBad, 原因}（key＝訊息裡的名字）；指示詞解不開丟 DirectiveBad。
Json read_procs(const Json& v, const std::string& base, const std::string& key);

// procs_state 列上的 exec 欄（11-04 晚，aos-agent 方向題 1，使用者「daemon表多一欄記下來」）：proc 設定裡的目標——
//   字串、陣列（取第一個）、物件的 exec（同前兩種）——相對的接在 cwd 後面（`檔#/…` 只動 # 前面；只有 `#/…` 的不動），其他照原字串；
//   內嵌單子、null（信箱接回只留名的）＝回 null。aos-daemon-ctl add 的 loop 型目標是 `<XXX>/loop.json#/exec`（或 loop.json 的 exec 轉絕對）、
//   exec 型是 XXX（都已絕對）。
Json exec_of(const Json& spec, const std::string& cwd);

// procs_state 列上的 def 欄（11-04，aos-agent，使用者「那就b。」）：proc 物件的 def（定義資料夾，read_procs 已轉絕對）；
//   沒寫、不是物件、null（信箱接回只留名的）＝回 null。aos-daemon-ctl add 一律送（XXX 的絕對路徑）。
Json def_of(const Json& spec);

// 通用布林：物件且值是 true 才回 true（read_procs 已驗 boolean／null）。
bool auto_restart_of(const Json& spec);
bool ros_of(const Json& spec);

// 只供起法與目標格式檢查：這個 proc 直接交 aos-exec 嗎（procs § 2）：字串、陣列，或 key 只有 exec（＋ws、stack、def、limits、auto_restart、restart_on_stuck、stuck_after_cycles）的物件＝是；其他（loop 設定、null）＝不是。
bool is_once(const Json& spec);
Json launch_of(const Json& spec, const std::string& cwd);   // 可重放設定：固定入口路徑、保留完整參數

// 把 v 裡每個 $ref 指示詞的相對檔名接在 base 後面（`檔#/…` 只動 `#` 前面；$ref 陣列每個元素都轉；絕對的、只有 `#/…` 的不動）。
// 不解任何指示詞。給 read_procs 處理內嵌單子用（10-24）。
Json abs_refs(const Json& v, const std::string& base);

// 期望表（10-23 晚）：base＋ctl[added]－ctl[removed]，先加後減（同一個名字兩邊都寫＝不要；
// 已在 base 上的換成 added 的設定、不在的接在尾巴）。ctl 兩個 key 都沒寫＝回 base 本身（不複製）；不然結果寫進 merged、回 merged。
const Json& merge_want(const Json& base, const Json& ctl, const char* added, const char* removed, Json& merged);

using Names = std::set<std::string>;

class Daemon : public aos::loop::Loop {
public:
    Daemon(const std::map<std::string, std::string>& opts, const std::string& spec, const std::vector<std::string>& args = {});

protected:
    void tend() override;
    void finish() override;
    void write_more(const Json& me) override;   // procs_state.json（沒開＝不寫；有變才寫，11-02）
    Json flux_more() override;            // state_flux 的 procs_ctl 回音與信箱警告
    Json info() override;                       // state 的 daemon（上一層）；有身體再加 body_code（最後一次的結束碼）
    // 11-05（edge-round2 題 1）：兩扇狀態窗寫不了＝stderr 一行（變了才印）、下一圈再寫，不收工；起來後一份都還沒寫成＝照舊退 1
    void write_state(const std::string& phase, const Json& code) override;

private:
    using Table = std::list<std::pair<std::string, Child>>;

    void adopt();
    void add(const std::string& name, const Child& c);   // 放上表＋印 log 一行（running；stopped 的列不印）
    Table::iterator drop(Table::iterator it);             // 從表上拿掉：行程結束的印 log 一行、done 的記成本次不再起；回下一列
    void log_child(const std::string& name, const Child& c);   // log 一行（見檔頭）
    void flush_table();                                   // 表變了：依最近 phase 先寫 state、再 procs_state、最後 state_flux（都有變才寫）；寫不了＝state_failed（起來後還沒寫成過＝丟 StateError）
    void state_failed(const Error& e);                    // 11-05：狀態窗寫不了（寫成過＝stderr 一行、下一圈再寫；沒寫成過＝丟 StateError）
    void state_ok();                                      // 11-05：寫成了（之前寫不了＝stderr 一行 written again）
    void term(Child& c);                  // 送 SIGTERM、phase stopping、記期限（不等）
    void halt(const std::string& name, Child& c);   // daemon 的 stop：往子 loop 的 ctl 寫 {"cmd": "stop", "seq": N}、phase stopping（寫不了也等自行退）
    void hold(const std::string& name, Child& c, const char* phase = "stopped", const char* log_phase = nullptr);   // 要留列的退了：印 log、列留成 phase；log_phase 可另指定
    bool settle(Child& c);                // 收的途中看一眼：退了＝phase stopped、回 true；SIGTERM 過了期限還在＝SIGKILL 整群＋底下自成一群的（只送一次）
    bool look(const std::string& name, Child& c, bool stop, bool watch = true);   // 不調表地看一眼（見 tend.cpp）；回 true＝結束了、要拿掉
    // stuck 是 running 列的公開投影；期限由父首見 ctl 刺激起算，任何回應重設連續重起次數。
    void check_stuck(const std::string& name, Child& c); // P7：只讀公開 ctl/state_flux 窗，paused 只標記
    void run_body();                      // 11-05：tend 最後跑身體一次（到時間才跑；失敗＝stderr 一行、下一圈再跑，見 body.cpp）
    std::string fail_reason(const Child& c) const;   // 11-05：出錯結束留成 stopped 的 reason（英文；起不來／跑到一半掛了＋碼＋小格 stderr 最後一行）
    Child start(const std::string& name, const Json& spec, const std::string& cell, const Json& kept_ws = Json(),
                const Json& kept_exec = Json(), const Json& kept_def = Json(),
                const Json& kept_limits = Json(), const Json& kept_launch = Json(), bool kept_auto_restart = false,
                bool kept_ros = false, long long kept_stuck_after_cycles = 10);   // 照寫法起（spawn／spawn_exec）；spec null 用列上記的 kept_*（含入口與兩個布林）
    Json limits_of(const Json& spec, const Json& kept) const;   // 11-05：生效的份額＝列的 limits，沒寫＝daemon 預設 limits_；spec null＝kept；{}＝null（不限）
    std::string cell_of(const std::string& name, const Json& spec) const;   // proc 的 stack：寫了 stack＝它，沒寫＝$AOS_STACK/procs/<名字>
    void read_procs_ctl();                // 讀 procs_ctl.json：好的進 pctl_good_、清 pctl_warning_；壞的不採用、原因進 pctl_warning_；檔不在＝不動
    std::optional<std::string> check_lists(Json& doc, const aos::Resolved& where);   // procs、procs_added、三個名字陣列
    // procs_state 的 procs 欄：≤ PART_ROWS 列原樣；多了就寫分檔、回 {"$ref": [分檔, …]}；用到的分檔名記進 now
    Json write_parts(Json rows, std::set<std::string>& now);
    void clean_parts(const std::set<std::string>& now);   // 寫好之後：清掉這次與上一次都沒用到的分檔
    // 期望表＝（ctl 的 procs，沒寫＝底 want_）＋procs_added－procs_removed（ctl＝一份驗過的 procs_ctl）；回的參照指向底、ctl 或 merged
    const Json& ctl_want(const Json& ctl, Json& merged) const;
    Names ctl_stopped(const Json& ctl) const;
    Names ctl_slept(const Json& ctl) const;     // 11-05 slept 集合＝底 slept_＋ctl 的 procs_slept－procs_woken
    Json unrel(const Json& v) const;            // 11-05：表上相對 daemon stack 的路徑拼回絕對（絕對的＝舊表，照用；# 片段照留）
    void check_running();                       // 11-05：flock 鎖 stack 資料夾；鎖不到＝已有 daemon 在跑＝丟 DaemonExists   // stopped 集合＝底 stopped_＋ctl 的 procs_stopped－procs_started
    bool from_ctl(const std::string& name) const;   // 名字是 procs_ctl 疊上去的（它的 procs 或 procs_added 裡有；沒開 procs_ctl＝false）
    void reconcile(const Json& want, const Names& stopped, const Names& slept);   // 對表：收多的、停要停的、看誰結束、起少的與要 start 的

    // 信箱（mailbox.cpp）
    using Letters = std::vector<std::pair<std::string, bool>>;   // 這圈的信（照處理順序）：{信件名稱, 好信}
    void open_mailbox();                                     // 建 tmp/ new/ cur/（已在就沿用）、cur/ 的殘骸記進 redo_
    Letters take_letters();                                  // 認領、逐封驗；好信依序套進底
    std::optional<std::string> apply_letter(const Json& body);   // 驗 body、套進 want_／stopped_；壞＝回原因、底不動
    void done_letters(const Letters& got);                   // 好信有 reply_to 的回 applied；全部收掉

    Json procs_ = Json::object();                        // daemon.json 的 procs
    Json limits_;                                        // daemon.json 頂層的 limits（沒寫 limits 的列用的預設；null＝不限；11-05 feat-proto 件 5）
    std::string cwd_;                                    // 子項的 cwd＝daemon 起來時的 cwd
    std::string dstack_;                                 // 給子項的 AOS_DAEMON＝stack_ 轉絕對、結尾 /；預設小格也從它拼
    Json parent_;                                        // 繼承的 AOS_DAEMON 字串；沒設、空或指自己＝null
    std::string pctl_path_;                              // procs_ctl.json（空＝不開）
    std::string pstate_path_;                            // procs_state.json（空＝不開）
    Json pctl_good_ = Json::object();                    // 最後一份好的 procs_ctl（一份都沒讀到過＝{}）
    Json pctl_warning_;                                  // null 或字串（state_flux 的 procs_ctl_warning）
    std::string parts_dir_;                              // procs_state 分檔的資料夾（沒開 procs_state＝空）
    std::set<std::string> parts_prev_;                   // 上一次寫的 state 用到的分檔檔名（清舊分檔時留著）
    bool parts_wrote_ = false;                           // 這個行程寫過 state 了沒（第一次不清：磁碟上的主檔可能還指著舊的）
    std::map<std::string, std::chrono::steady_clock::time_point> retired_;   // 11-05 第二輪：退役的分檔（不在這次／上一次）→ 退役那一刻；滿 PARTS_KEEP_MS 才刪
    std::string mbox_path_;                              // procs_ctl_mailbox（空＝不開）
    std::string mbox_name_;                              // daemon.json 寫的信箱名（沒寫＝procs_ctl_mailbox；procs_state 回報用）
    CellNames names_;                                    // 小格裡三個檔名（procs_loop／procs_exec／procs_stderr，11-04）
    aos::post::Mailbox mbox_;
    std::vector<std::string> redo_;                      // 起來時 cur/ 裡的（上次做到一半死掉），第一個認領的圈排在 new/ 前面重做
    Json want_ = Json::object();                         // 底的期望表（記憶體裡；重起時從 daemon.json＋adopt 重建；信改它）
    Names slept_;                                        // 底的 slept 集合（11-05 sleep 指令：要它睡著；daemon 重開＝空＝睡著的列自己醒）
    Names stopped_;                                      // 底的 stopped 集合（11-03；起來時＝adopt 接回的 stopped 列；信改它）
    long long stop_seq_ = 0;                             // 寫給子 loop 的 stop 指令的 seq（自己數、遞增，也比它 ctl 裡現有的大）
    Json mailbox_warning_;                               // null 或字串（state_flux 的 mailbox_warning：最後一封壞信）
    Names ended_;                                        // 本次執行已自己結束的名字（11-02，見檔頭）
    bool more_wrote_ = false;                            // 寫過 procs_state 沒（這個行程第一份一定寫）
    bool parts_stale_ = false;                           // 上一次寫完還留著「再上一次」的分檔：下一次沒變的那一下清（11-02）
    Json last_more_;                                     // 上一份寫出去的 procs_state（分檔前的表、不含 proc_fields／updated_at；比有沒有變用）
    bool was_paused_ = false;                            // 11-05 第二輪：上一圈是暫停的（resume 那圈先寫 state 再對表）
    std::string state_phase_ = "waiting";                // flush_table 先更新自身穩定窗，保留最近 phase（含收工 stopping）
    bool state_wrote_ = false;                           // 11-05：兩扇狀態窗寫成過沒（沒有＝寫不了照舊退 1：stack 不在、一起來就唯讀）
    std::string state_bad_;                              // 11-05：上一次寫不了的代號（空＝上一次好的；變了才印）
    int lock_fd_ = -1;                                   // check_running 鎖著的 stack 資料夾（不關，行程結束自己放）
    aos::loop::Target body_;                             // 11-05：daemon 自己的身體（設定檔的 exec；Loop 的 exec_ 收過來）
    bool has_body_ = false;
    long long body_runs_ = 0;                            // 身體跑過幾次（max 照算）
    std::chrono::steady_clock::time_point body_next_{};  // 下一次最早什麼時候跑（上一次結束＋interval_ms）
    std::string body_bad_;                               // 上一次失敗的「碼或錯」（空＝上一次好的；變了才印）
    Json body_code_;                                     // 最後一次的結束碼（state 的 body_code；null＝還沒跑過）
    Table table_;                                        // 照加入的順序（procs_state 的 procs 也照這個順序）
    std::unordered_map<std::string, Table::iterator> index_;   // 名字 → 表上那一列
};

}  // namespace aos::daemon
