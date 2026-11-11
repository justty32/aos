// aos/loop.hpp：aos-loop 的公開介面——跑「一次」、反覆跑的骨架、ctl／state／state_flux 公開格式與選開計數檔。
//
//   block_signals   轉交 aos-util，擋住 SIGINT／SIGTERM／SIGHUP（整支程式的壽命；要在第一次之前、開任何執行緒之前呼叫）
//   take_signal     轉交 aos-util；兩次之間：有排著的那三個訊號之一就取出來回它（0＝沒有）
//   parse_target    loop 的 exec、fsm 格的 exec 的寫法（10-21 傍晚 ideas § 9；10-24 加物件）：字串＝aos-exec 的目標；陣列＝[目標, 參數...]；
//                   物件＝內嵌單子（10-24 使用者「exec本來就應該要可以直接放內嵌單子吧」）
//   resolve_exec    exec 那格的指示詞：先換一層；換完是物件（單子）就不往裡面解（留到跑的時候、AOS_CF／AOS_CO 設好才解），不然整個解
//   place_inline    內嵌單子在哪：設定檔（AOS_CF）、在檔裡的指標（AOS_CO）、單子裡相對 $ref 的起點
//   config_file     設定檔的實際路徑（解開捷徑；同 aos-exec 的 AOS_CF）——設定檔裡相對 $ref 的起點與內嵌單子的 AOS_CF／AOS_CD 都從它算
//   run_once        跑一次：目標＝子行程裡 `aos-exec -- 目標 參數...`（aos-exec 的 run_cli）；單子＝行程內 aos-exec 的 run_inst；
//                   給 timeout_ms＝起停那兩格用的期限（11-11 on_start／on_stop）
//   loop_cli        命令列 `程式 [--max N] [--interval-ms N] [--ctl 檔] [--state 檔] [--state-flux 檔] [--enable-logs] [--enable-counters] 設定檔 [-- 參數...]`（aos-loop、aos-daemon 共用）
//   add_args        `-- 參數...` 接到 exec 後面（11-02 晚）
//   Loop            反覆跑的程式的骨架（aos-loop 直接用、aos-daemon 繼承；10-21 傍晚）：
//                   讀設定（旗標 ＞ 設定檔 ＞ 預設：exec／max／interval_ms／ctl／state／state_flux）、每次讀 ctl 窗（11-03 起一道指令、新的才照做）→ tend() → 跑一次 → 寫 state 窗（＋write_more；11-02 起有變才寫）、
//                   --enable-logs 時每跑完一次在 stdout 印一行 log（11-02；11-02 晚改預設不印）
//                   state_flux 的 responded_at 只在處理新 ctl（含拒用壞指令）、收到信、起或收子項時更新；已套用過的第一道、檔不在不算
//   write_window    透過 aos-util write_text 寫窗：先寫同資料夾的 .名字 再改名（N-05），一行 JSON
//   proc_fields     state 裡「這支程式是誰」的欄位 {pid, started_at_ticks, boot_id}（11-02 原 heartbeat：心跳拿掉、recorded_at 收掉）
//   resolve_keys    轉交 aos-directive；設定檔、ctl 的指示詞（10-23 晚：aos 讀的 JSON 都解）：整份先換一層，再把自己讀的那幾格整個解，其他 key 不碰
//
// 規則見 aos-loop/README.md。
// 錯一律丟 aos::Error{code, msg}（aos-util 的 aos/util/error.hpp）。
#pragma once

#include "aos/util/cli.hpp"
#include "aos/directive.hpp"
#include "aos/exec.hpp"

#include <chrono>
#include <map>
#include <optional>
#include <signal.h>
#include <string>
#include <vector>

namespace aos::loop {

// 錯誤代號：沿用 aos-exec 與 aos-util 的通用代號，再加本層的 RunFailed。
namespace code {
using namespace aos::exec::code;   // ArgumentsBad、FlagUnknown、CfgMissing、CfgBad、WriteFailed、EntryBad、DirectiveBad、LaunchFailed…
inline constexpr const char* RunFailed = "RunFailed";         // 身體那次退非 0（不是 10）：aos-loop 印這行、以那次的碼結束（11-05 stdio-unify D4）
}  // namespace code

// ctl／state／state_flux 的公開協議（C-52）：預設檔名與跨程式讀寫用的欄位／值只在這裡定義。
// 設定沒寫用 default_name；null＝不開。ctl 是一道指令，seq 是非負整數回音；
// state 用 pid＋started_at_ticks＋boot_id 判行程身份，phase＝done 表示自己做完（詳見 docs/02-窗.md）。
struct CtlWindow {
    static constexpr const char* config_key = "ctl";
    static constexpr const char* default_name = "ctl.json";
    static constexpr const char* cmd = "cmd";
    static constexpr const char* seq = "seq";
    static constexpr const char* pause = "pause";
    static constexpr const char* resume = "resume";
    static constexpr const char* stop = "stop";
};
struct StateWindow {
    static constexpr const char* config_key = "state";
    static constexpr const char* default_name = "state.json";
    static constexpr const char* phase = "phase";
    static constexpr const char* done = "done";
    static constexpr const char* pid = "pid";
    static constexpr const char* started_at_ticks = "started_at_ticks";
    static constexpr const char* boot_id = "boot_id";
};

// state_flux 是易變回音窗；沒有 updated_at，整份有變才寫。
struct StateFluxWindow {
    static constexpr const char* config_key = "state_flux";
    static constexpr const char* default_name = "state_flux.json";
    static constexpr const char* responded_at = "responded_at";
    static constexpr const char* ctl_seq = "ctl_seq";
    static constexpr const char* ctl_warning = "ctl_warning";
};

// 一次的結果（欄位名同 11-03 前 fsm 的 trace.jsonl 那一行，再多一個 received；aos-loop 的 log 那一行也用 code、signal、elapsed_ms，11-02）。沒有 timed_out（10-21：loop 看不到格裡有沒有逾時，C-52；
// 單子被逾時收掉＝跑它的 aos-exec 以 128＋N 正常結束：code 143、signal 0）。
struct Run {
    int code = 0;              // 那次的結束碼（被訊號停掉＝128＋N）
    int signal = 0;            // 停掉它的訊號（0＝不是被訊號停掉；log 裡寫 null）
    unsigned long long elapsed_ms = 0; // 花了幾毫秒（log 的 elapsed_ms）
    int received = 0;          // 跑的期間自己收到、轉給那次的第一個訊號（0＝沒有）；呼叫者收完這次要以 128＋它結束
    bool timed_out = false;    // 只有給了 timeout_ms 的目標（on_start／on_stop）：到時間被收掉
};

// 擋住三個訊號。之後它們不會打死這支程式，而是排著，由 run_once 轉給那次、或由 take_signal 取出。
void block_signals();

// 取出一個排著的 SIGINT／SIGTERM／SIGHUP（不等）；沒有回 0。
int take_signal();

// loop 的 exec、fsm 格的 exec：字串＝aos-exec 的目標（參數空）；陣列＝[目標, 參數...]（元素都要是字串、不能是空的）；
// 物件＝內嵌單子（10-24：恢復 10-21 前的寫法，使用者「exec本來就應該要可以直接放內嵌單子吧」；形狀不在這裡驗，跑的時候由 run_inst 驗）。
// 其他丟 CfgBad「<what> 要是 aos-exec 的目標（字串）、[目標, 參數...]（非空字串陣列）或單子（物件）」。
// 物件時呼叫者還要 place_inline 填好它在哪（cf、co、ref_base）。
struct Target {
    std::string target;               // 字串、陣列的第一個（物件時空）
    std::vector<std::string> args;
    std::optional<Json> inst;         // 內嵌單子（指示詞還沒解）
    std::string cf;                   // 物件：AOS_CF＝寫著它的設定檔（實際路徑）；AOS_CD＝它的資料夾＝單子相對路徑的基準
    std::string co;                   // 物件：AOS_CO＝它在那份檔裡的位置（JSON 指標，例 /exec、/states/think/exec）
    std::string ref_base;             // 物件：單子裡相對 $ref 的起點（exec 那格來自的那份檔的資料夾）
    std::string label() const;        // 訊息裡的「誰」：目標；物件＝「檔名#指標」（例 loop.json#/exec）
};
Target parse_target(const Json& v, const std::string& what);

// exec 那格的指示詞（10-24）：v 本身是指示詞就先換掉（resolve_shallow）；換完是物件＝單子，裡面不解（跑的時候 run_inst 才解，
// 那時 AOS_CF／AOS_CD／AOS_CO 已設成單子的位置，跟 aos-exec 跑 `檔#/指標` 的單子一樣）；字串、陣列整個解（同 10-23 晚）。
// 回解好的值與「它裡面相對 $ref 的起點」（base_dir）。錯同 resolve（DirectiveBad）。
aos::Resolved resolve_exec(const Json& v, const std::string& base_dir);

// 物件的 Target 填好位置：spec＝設定檔（`檔` 或 `檔#/指標`），sub＝exec 那格在 spec 指到的值裡的 JSON 指標（例 "/exec"），
// ref_base＝resolve_exec 回的 base_dir。cf＝config_file(spec)、co＝spec 的指標＋sub。不是物件不動。
void place_inline(Target& t, const std::string& spec, const std::string& sub, const std::string& ref_base);

// 設定檔（`檔` 或 `檔#/指標`，只看 # 前面）的實際路徑：解開捷徑的絕對路徑（解不開＝abspath，從 cwd 算）。
// 10-24 審後統一：設定檔裡相對 $ref 的起點（Loop、fsm 的 read_table）＝它的資料夾，內嵌單子的 AOS_CF＝它——
// 同 aos-exec 跑 `檔#/指標`（AOS_CF、cd、$ref 起點都走實際的資料夾），也同 aos-directive 被 $ref 進來的檔（解開捷徑後的資料夾）。
// 原本 $ref 起點不解捷徑、AOS_CF 解，捷徑設定檔兩個相對基準不一樣。
std::string config_file(const std::string& spec);

// JSON 指標的一段：~ → ~0、/ → ~1（RFC 6901）。
std::string pointer_escape(const std::string& key);

// 跑一次。
// 目標＝`aos-exec -- 目標 參數...`（`--` 讓 - 開頭的目標不被當旗標；相對路徑照 cwd，loop 不轉）：fork 一個子行程，
// 子行程裡用 restore_signals 還原成阻擋前的訊號遮罩、呼叫 aos::exec::run_cli（可執行檔／argv 陣列 exec 掉；單子在那個子行程裡跑、它當監工；
// 它自己的錯印一行「aos-exec: error: 代號 原因」、碼 1）——等同起一支 PATH 上的 aos-exec，只是不必在 PATH 上找。
// 子行程跟呼叫者同一個行程群組（不另開）；跑的期間收到的三個訊號 kill 給它（不另設 SIGKILL 期限）。fork 失敗丟 LaunchFailed。
// 單子（10-24）＝行程內呼叫 aos-exec 的 run_inst（aos-exec 跑單子用的同一套：aos-inst、timeout_ms／timeout_cycles 擇一、grace_ms、訊號轉給整群）：
// 跑的期間 AOS_CF／AOS_CD／AOS_CO 設成 t.cf、它的資料夾、t.co（跑完還原），相對路徑的基準＝t.cf 的資料夾，$ref 從 t.ref_base 算；
// AOS_WS、AOS_STACK 是相對路徑時以呼叫者的 cwd 轉成絕對（AOS_STACK 結尾補 /；跑完還原；不驗、不建——同 aos-exec 的 N-59 第 1 件，
// 10-24 審後補：原本原樣給，單子從設定檔的資料夾算，跟 loop 自己照 cwd 算的窗對不上）；其他環境照呼叫者現有的、不讀 .env。單子壞 EntryBad、指示詞壞 DirectiveBad、起不來 LaunchFailed
// （訊息開頭「inst cannot run: 」）；被逾時收掉＝code 128＋N、signal N。
// 呼叫前要先 block_signals()。
// timeout_ms（11-11，只給 on_start／on_stop 用；0＝不限，同身體）：目標＝到時間 SIGTERM 給那個子行程、再 1 秒還在就 SIGKILL，
// Run::timed_out＝true；單子＝單子自己沒寫 timeout_ms／timeout_cycles 時補上 timeout_ms（逾時照 run_inst 收整群）。
Run run_once(const Target& t, long long timeout_ms = 0);

// 命令列（10-21 傍晚 ideas § 9；規則同 aos-exec，aos-util 的 parse_cli）：唯一的位置參數＝設定檔（必給、只能一個；
// 可寫 `檔#/指標`）。旗標 --max、--interval-ms、--ctl、--state、--state-flux 帶值；--enable-logs、--enable-counters 是不帶值的開關，
// 給了＝對應 opts key 是 "1"；不是設定檔的 key。設定檔之後可接 `-- 參數...`：回的 rest＝[設定檔, 參數...]
// （那個 `--` 剝掉）；設定檔之後接的不是 `--`＝ArgumentsBad。不認得的旗標丟 FlagUnknown；旗標缺值、沒給設定檔丟 ArgumentsBad（msg＝「原因 (usage: <prog> [...] CONFIG.json [-- ARGS...])」，R5）。
// argv 不含程式名；回旗標（opts）與設定檔（rest[0]）。help＝`--help` 印的說明（英文，parse_cli 印到 stdout、退 0）。
// cfg_name：錯誤行 usage 裡設定檔的寫法（跟 help 一致；aos-daemon 給 "daemon.json"）。
aos::Cli loop_cli(const std::vector<std::string>& argv, const std::string& prog, const std::string& help,
                  const std::string& cfg_name = "CONFIG.json");

// 附加參數（loop_cli 的 rest[1:]）接到 exec 後面（11-02 晚；起跑時接一次＝每次都帶）：字串目標＝[目標, 參數...]、陣列＝接在最後、
// 內嵌單子＝接在單子 argv 的最後（argv 要直接是陣列；是指示詞、沒寫＝CfgBad）。args 空＝不動。ctl 改不了它們。
void add_args(Target& t, const std::vector<std::string>& args);

// write_state／write_flux 寫不了窗時丟的（代號 WriteFailed）。跟別的 Error 分開，是為了 tend 裡寫狀態窗寫不了時不被當成 tend 的錯、
// 再走一次收尾寫 state（那樣會多印一行）：一路丟到 serve，印一行、收尾、退 1。
struct StateError : Error {};

// 窗的寫法：先寫同資料夾的 `.名字`、再改名蓋過去（N-05）；內容是一行 JSON（排版同 Python json.dumps）＋換行。
// 寫不了丟 WriteFailed。
void write_window(const std::string& path, const Json& doc);

// aos-directive 的 aos::resolve_keys 轉接：doc 本身是指示詞就先換掉（aos::resolve_shallow，不往裡面走），
// 換完是物件就把 keys 裡有寫的那幾格整個解（aos::resolve）；其他 key（body、_entry…）原封不動，留給讀它的人（C-52）。
// base_dir＝doc 裡相對 $ref 的起點（設定檔、ctl＝那份檔所在的資料夾）。回解好的 doc 與它裡面各 key 的起點（dir_of(key)；
// doc 本身換過 $ref＝那份檔的資料夾，換的是 $ref 陣列＝每個 key 來自的那份檔的）。真的解不開丟 DirectiveBad（呼叫者決定算誰的錯：設定檔＝自己的錯退 1；ctl＝整份不採用）。
aos::Resolved resolve_keys(const Json& doc, const std::string& base_dir, const std::vector<std::string>& keys);

// 這支程式是誰：{"pid", "started_at_ticks"（/proc/<pid>/stat 第 22 欄）, "boot_id"}（N-17：判活著看這三個）。
// 11-02 原 heartbeat：心跳拿掉（使用者「心跳這塊就直接看pid就好」）、recorded_at 收掉；窗的時間欄改成真的寫那一刻才加的 updated_at。
Json proc_fields();

// 每種程式的預設值。
struct Defaults {
    std::string prog = "aos-loop";          // 錯誤一行的程式名
    std::optional<long long> max;           // nullopt＝不限（10-21 plan L8，原 10）
    long long interval_ms = 0;
    bool need_exec = true;                  // exec 必填
};

// 反覆跑的程式的骨架。設定檔（loop.json；daemon.json 是它的超集）的 key（旗標名＝key 名底線換連字號；起跑時 旗標 ＞ 設定檔 ＞ 預設）：
//   exec          每次跑的東西（10-23 改名，原 run）：字串或 [目標, 參數...]（parse_target；每次 `aos-exec -- 目標 參數...`）；
//                 物件＝內嵌單子（10-24；每次行程內 run_inst，AOS_CO＝設定檔的指標＋/exec）；
//                 need_exec 時必填（沒寫＝CfgBad「沒有東西可跑」）
//   max           最多幾次（非負整數；沒寫＝Defaults::max；寫 null 不行）
//   interval_ms   一次結束到下一次開始至少隔幾毫秒（非負整數；沒寫＝Defaults::interval_ms）
//   on_start, on_stop  起來、要退時各跑一次的東西（11-11，使用者選「aos-loop 自己加」；寫法同 exec；沒寫＝不跑）：
//                 on_start＝第一次之前（讀完舊 state、ctl 之前）；on_stop＝要退時（stop、跑滿、身體 10、身體失敗、訊號、自己的錯，
//                 finish() 之後、最後一份 state 之前；SIGKILL 跑不到）。on_stop 的環境多 AOS_LOOP_CODE（要退的碼）、AOS_LOOP_SIGNAL（收到的訊號號碼，
//                 沒有＝空字串）。退非 0、逾時、起不來＝一行 warning，不改 loop 的結束碼、不擋起跑。loop 不知道它們是什麼（C-52）
//   on_timeout_ms 上面兩格的期限（正整數，沒寫＝5000；aos-daemon 收工只給子項 10 秒）
//   ctl, state, state_flux 三扇窗的檔名，在 $AOS_STACK 底下（11-04 起沒寫＝ctl.json／state.json／state_flux.json、寫 null＝不開；要開卻沒設 AOS_STACK＝StackMissing）
// log 不是 key（11-02 使用者「把log輸出到stdout」；11-02 晚「應該要改成默認不印」）：預設不印，命令列 --enable-logs 才印到 stdout；不寫任何 log 檔。
// --enable-counters 也是命令列開關：開了 state 窗才每輪寫同資料夾的 counter_runs.txt（本行程起來後跑過幾次）；預設不碰檔。
// ctl、state、state_flux 寫 null＝不開（11-04 前沒寫也是不開，現在沒寫＝預設名）。
// 其他 key 忽略（body、_entry…）。設定壞丟 Error（CfgMissing、CfgBad、StackMissing；指示詞解不開 DirectiveBad）。
// 指示詞（10-23 晚）：設定檔整份先換一層，上面各格整個解（resolve_keys，起點＝設定檔的資料夾；exec 走 resolve_exec，單子裡面不解）；ctl 整份先換一層，
// cmd／max／interval_ms／seq 整個解（起點＝ctl 的資料夾），子類別多認的 key 在 check_ctl 裡自己解；ctl 解不開＝整份不採用。
// ctl＝一道指令（11-03 使用者「還是用指令吧」，thinking 2026-11-03-ctl-commands）：{"cmd": "pause"／"resume"／"stop", "max", "interval_ms", "seq"}，
// 都選填；max／interval_ms 寫了＝從現在起用它、null＝回設定檔（旗標）的值、沒寫＝不動；seq 只回音（state_flux 的 ctl_seq）。
// 新舊比內容：解完的那份跟上一次讀到的不一樣才照做一次；起來第一次僅在 seq 與舊 state_flux 的 ctl_seq 相同時略過，其餘照做；檔不見了＝之後寫的都算新的。
// 暫停中記在 paused_（state 的 paused）；起來時開了 state 窗、舊的 state.json 的 paused 是 true＝起來先暫停（11-03 代定「繼續暫停」）。
// 每次：有排著的訊號 → 結束 128＋N；讀 ctl（新的指令才照做）→ tend() →
// stop 過就結束（0）、跑滿就結束（0）→ 暫停中或還沒到時間就睡一下（最多 1 秒，收到訊號就醒）回頭再看 →
// 跑一次：0＝下一次、10＝結束（0）、其他非 0＝stderr 一行、以那個碼結束；跑的期間收到訊號＝收完以 128＋N 結束。
// 沒有身體（exec 沒寫，daemon 純監工）：一輪＝讀 ctl → tend → 算一次 → 寫一份 waiting → 睡到下一次，一輪只讀一次 ctl、
// 只 tend 一次、最多寫一次 state、不寫 running（那一刻沒東西在跑）；睡著的 daemon 窗不動（10-23 壓測）。
// state 只在兩次之間寫，而且有變才寫（11-02）：每次要寫先組好一份（不含 updated_at），跟上一份寫出去的比，
// phase 在 running／waiting 之間換不算變動（11-02 晚使用者「running/waiting確實不該算變動」；
// 寫出去的照帶當下的 phase）；一樣就不碰檔，不一樣才加 updated_at 寫。啟動後第一份、結束那份（帶 code）一定寫。
// state_flux 帶 responded_at（起來是 null）、ctl_seq、ctl_warning 與 flux_more()；整份有變才寫，state／write_more 後才寫。
// log（下面）預設不印，--enable-logs 才印。
// 心跳拿掉（11-02）：睡著時窗不動，判活著看 pid＋started_at_ticks＋boot_id。每次要寫 state 都接著呼叫 write_more（子類別自己的狀態窗，
// 有沒有變由它自己比）。
// log（11-02）：有身體時每跑完一次在 stdout 印一行 JSON {"started_at", "counter_runs", "code", "signal", "elapsed_ms"}（log_line）；
// 沒有身體不印。身體繼承這支程式的 stdout，所以身體的輸出跟 log 同一條（混在一起由使用者自己處理，11-02 晚使用者）。
// 結束前呼叫 finish()（不論為什麼結束）。呼叫前要先 block_signals()。
// 子類別可把已阻擋的喚醒訊號放入 wake_，nap 收到後呼叫 woke；回 true＝提前算一圈到時間。
// aos-loop 不設喚醒訊號；aos-daemon 用這個掛鉤接 poke（不當成收工訊號、不轉給身體）。
// $AOS_STACK 不在＝state 寫不了＝WriteFailed、退 1，不自己建（建 stack 只在 aos-exec 做，N-59 第 1 件）。
class Loop {
public:
    // opts＝命令列旗標（loop_cli 解出來的：max、interval_ms、ctl、state、state_flux、enable_logs、enable_counters），spec＝設定檔（`檔` 或 `檔#/指標`），
    // args＝`--` 後面的附加參數（add_args 接到 exec 後面；沒有 exec 卻給了＝ArgumentsBad）。
    Loop(const std::map<std::string, std::string>& opts, const std::string& spec, const Defaults& d,
         const std::vector<std::string>& args = {});
    virtual ~Loop() = default;
    Loop(const Loop&) = delete;
    Loop& operator=(const Loop&) = delete;

    // 跑到結束，回結束碼。自己的錯（tend、單子壞、窗寫不了）stderr 一行「程式名: error: 代號 原因」、先 finish() 再回 1；
    // 身體退非 0（不是 10）＝錯誤行 RunFailed、以那次的碼結束（11-05 stdio-unify D4）。
    int serve();

protected:
    // 子類別可覆寫以下掛鉤
    virtual void tend();                                             // 每次讀完 ctl 後（這時 paused_／stopping_ 已照新指令改好）
    virtual bool woke(int sig);                                     // nap 的喚醒訊號；true＝這一圈當作到時間了
    virtual void finish();                                           // 結束前（不論為什麼結束）
    virtual Json flux_more();                                        // 寫進 state_flux 的額外欄位（預設空物件）
    virtual Json info();                                             // 寫進 state 的額外欄位（物件）
    // ctl 多認的 key：解自己那幾格的指示詞（起點 base＝ctl 換完一層後的起點）、驗證，可以就地改寫 doc（回原因＝不採用；
    // 丟 DirectiveBad 也＝不採用）
    // where＝ctl 換完一層後各 key 的起點（where.dir_of(key)；ctl 整份是 $ref 陣列時每個 key 可能來自不同的檔）
    // 採用了、但要提醒一句的（10-29 daemon 的 loops* 搬家過渡期）：填 ctl_note_，這份採用後它就是 state_flux 的 ctl_warning。
    virtual std::optional<std::string> check_ctl(Json& doc, const aos::Resolved& where);
    // 子類別自己的狀態窗（10-29：aos-daemon 的 loops_state）：每次 write_state 都接著呼叫（state 窗這次寫沒寫、開沒開都照樣呼叫；
    // 11-02 起它自己比有沒有變、變了才寫），me＝proc_fields()。寫不了丟 Error（當成 state 寫不了：StateError）。
    virtual void write_more(const Json& me);

    int fail_line(const std::string& code, const std::string& msg);   // 錯誤行「程式名: error: 代號 原因」（aos::fail；回 1）
    void warn(const std::string& msg);                                // 提醒行「程式名: warning: 句子」（不退出；11-05 stdio-unify R1）
    void write_flux();                                              // 穩定窗落地後寫回音；第一份必寫，之後整份有變才寫，失敗丟 StateError
    void responded();                                               // 處理新 ctl、收到信、起或收子項時記下 UTC 毫秒時間

    // 要寫一份 state（沒開 state 窗就不寫；跟上一份一樣也不寫，見上）再依序呼叫 write_more、write_flux：phase＝這份的階段，code＝結束碼
    // （null＝還沒結束；非 null＝一定寫）。寫不了丟 StateError（WriteFailed）。
    // 11-02 拿掉 beat（心跳：離上一次滿 1 秒就寫一份）；daemon 起一大批、收工等子項退時改成表有變就寫 loops_state（daemon 自己呼叫 write_more）。
    // 11-05 virtual（edge-round2 題 1，使用者「記一行、下一圈再試 (Recommended)」）：aos-daemon 蓋它、寫不了時記一行下一圈再寫；aos-loop 自己照舊（寫不了＝退 1）。
    virtual void write_state(const std::string& phase, const Json& code);
    // log 一行（11-02）：doc 印成一行 JSON＋換行到 stdout（一次 write，不經 stdio 緩衝）。沒給 --enable-logs＝不印。印不了（stdout 是關掉的管子 EPIPE…）＝
    // 之後都不印、不退出；寫的那一下用 pthread_sigmask 擋著 SIGPIPE、排著的吃掉再還原遮罩（不改 SIGPIPE 的處置，子行程不受影響）。
    void log_line(const Json& doc);

    sigset_t wake_ = [] {           // 子類別額外的喚醒訊號（建構時先清空）
        sigset_t set;
        sigemptyset(&set);
        return set;
    }();
    Defaults d_;
    Json cfg_;                    // 設定檔整份（旗標已蓋上；子類別讀自己的 key，指示詞要自己解：resolve_keys）
    aos::Resolved cfg_dirs_;      // cfg_ 各 key 裡相對 $ref 的起點（cfg_dirs_.dir_of(key)；設定檔所在的資料夾，整份換過 $ref＝那份檔的；value 不用）
    bool has_exec_ = false;       // false＝沒有身體（daemon 純監工）
    Target exec_;
    std::optional<long long> max_;
    long long interval_ms_ = 0;
    std::string stack_;           // $AOS_STACK（沒設＝空）
    std::string ctl_path_;        // 空＝不開
    std::string state_path_;      // 空＝不開
    std::string state_flux_path_; // 空＝不開
    std::string ctl_note_;        // check_ctl 填：採用了但要提醒的一句（空＝沒有；read_ctl 每次呼叫 check_ctl 前清掉）
    bool log_ = false;            // 印 log（--enable-logs＝true；印不了變回 false）
    bool paused_ = false;         // 暫停中（ctl 的 pause／resume 改它；起來時可能從舊 state 接，11-03）
    bool stopping_ = false;       // 收到過 stop（這次跑完以 0 結束，11-03）
    std::optional<Target> on_start_;   // 11-11：起來時跑一次（沒寫＝nullopt）
    std::optional<Target> on_stop_;    // 11-11：要退時跑一次
    long long on_timeout_ms_ = 5000;   // 11-11：on_start／on_stop 的期限
    Json responded_at_;           // 最近一次有反應的時間（null＝起來後還沒有）

private:
    int main_loop();
    int end(int code, const std::string& phase);
    void read_ctl();              // 讀 ctl：新的指令才照做（改 paused_、stopping_、max_、interval_ms_、ctl_seq_）
    void read_old_state();       // 起來時：接回舊 state.json 的 paused 與舊 state_flux 的有效 ctl_seq（第一道去重用）
    void write_main(const std::string& phase, const Json& code, const Json& me);   // write_state 的 state 窗那份（有變才寫）
    void write_counter();         // 開旗標與 state 窗才寫 counter_runs.txt；失敗丟 StateError
    int signal_got();             // 第一個收到的訊號（記住；0＝沒有）
    void nap(double secs);        // 睡 secs 秒（最多 1 秒），收到訊號就提早醒
    void run_side(const std::optional<Target>& t, const char* key, int code);   // 跑 on_start（code<0）／on_stop；問題只 warning
    void stop_side(int code);     // on_stop 只跑一次（end、serve 的錯誤路徑都叫）
    bool served_ = false;         // main_loop 開始了沒（沒開始＝不跑 on_stop）
    bool stop_ran_ = false;

    long long runs_ = 0;
    bool counters_ = false;       // --enable-counters 才寫 counter_runs.txt
    std::optional<long long> max_base_;   // 設定檔（旗標）的 max：ctl 寫 null 回這個
    long long interval_base_ = 0;         // 設定檔（旗標）的 interval_ms：ctl 寫 null 回這個
    bool ctl_seen_ = false;       // 讀過第一次 ctl 沒（第一次比舊 state_flux 的 ctl_seq 去重）
    std::string ctl_last_;        // 上一次讀到的 ctl（比新舊用：好的＝解完那份的字串、壞的＝"!"＋原文、檔不在＝空）
    Json ctl_seq_;                // 最後一道照做的指令的 seq（null＝沒帶或還沒有）
    Json ctl_warning_;           // null 或字串
    int got_ = 0;
    bool due_ = false;
    bool wrote_ = false;          // 寫過 state 窗沒（啟動後第一份一定寫）
    bool wrote_flux_ = false;     // 啟動後第一份 state_flux 一定寫
    Json last_flux_;              // 上一份寫出去的完整 state_flux
    Json last_main_;              // 上一份寫出去的 state（不含 updated_at；比有沒有變用）
};

}  // namespace aos::loop
