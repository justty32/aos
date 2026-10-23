// aos/loop.hpp：aos-loop 的公開介面——跑「一拍」（loop.json 的 val、fsm.json 格的 val，同一套寫法 C-55）。
//
//   block_signals   擋住 SIGINT／SIGTERM／SIGHUP（整支程式的壽命；要在第一拍之前、開任何執行緒之前呼叫）
//   take_signal     拍與拍之間：有排著的那三個訊號之一就取出來回它（0＝沒有）
//   parse_target    val 的寫法（10-21 傍晚 ideas § 9）：字串＝aos-exec 的目標；陣列＝[目標, 參數...]
//   run_beat        跑一拍：子行程裡 `aos-exec -- 目標 參數...`（aos-exec 的 run_cli）；只收目標，內嵌單子寫 `loop.json#/body`
//   loop_cli        命令列 `程式 [--max N] [--interval-ms N] [--ctl 檔] [--state 檔] 設定檔`（aos-loop、aos-daemon 共用）
//   Loop            反覆跑的程式的骨架（aos-loop 直接用、aos-daemon 繼承；照 proto8/bin/aos_loop.py 的 Loop，10-21 傍晚）：
//                   讀設定（旗標 ＞ 設定檔 ＞ 預設：val／max／interval_ms／ctl／state）、每拍讀 ctl 窗 → tend() → 跑一拍 → 寫 state 窗
//   write_window    窗的寫法：先寫同資料夾的 .名字 再改名（N-05），一行 JSON
//   heartbeat       state 的心跳欄位 {pid, start_ticks, boot_id, at}（N-32）
//
// 規則見 aos-loop/README.md。
// 錯一律丟 aos::Error{code, msg}（aos-util 的 aos/error.hpp）。
#pragma once

#include "aos/cli.hpp"
#include "aos/exec.hpp"

#include <map>
#include <optional>
#include <string>
#include <vector>

namespace aos::loop {

// 錯誤代號：沿用 aos-exec 的（它又沿用 aos-util 的 aos::code），加一個 StackMissing（aos-loop、aos-fsm、aos-daemon 共用）。
namespace code {
using namespace aos::exec::code;   // ArgumentsBad、FlagUnknown、CfgMissing、CfgBad、WriteFailed、EntryBad、DirectiveBad、LaunchFailed…
inline constexpr const char* StackMissing = "StackMissing";   // 要 $AOS_STACK 卻沒設（開了窗、fsm、daemon）
}  // namespace code

// 一拍的結果（欄位同 fsm 的 trace.jsonl 那一行，再多一個 received）。沒有 timed_out（10-21：拍看不到格裡有沒有逾時，C-52；
// 單子被逾時收掉＝跑它的 aos-exec 以 128＋N 正常結束：code 143、signal 0）。
struct Beat {
    int code = 0;              // 那拍的結束碼（被訊號停掉＝128＋N）
    int signal = 0;            // 停掉它的訊號（0＝不是被訊號停掉；trace 裡寫 null）
    unsigned long long elapsed_ms = 0; // 花了幾毫秒（trace 的 elapsed_ms）
    int received = 0;          // 跑的期間自己收到、轉給那拍的第一個訊號（0＝沒有）；呼叫者收完這拍要以 128＋它結束
};

// 擋住三個訊號。之後它們不會打死這支程式，而是排著，由 run_beat 轉給那拍、或由 take_signal 取出。
void block_signals();

// 取出一個排著的 SIGINT／SIGTERM／SIGHUP（不等）；沒有回 0。
int take_signal();

// val：字串＝aos-exec 的目標（參數空）；陣列＝[目標, 參數...]（元素都要是字串、不能是空的）。
// 其他（含物件：要內嵌單子寫 `loop.json#/body`）丟 CfgBad「<what> 要是 aos-exec 的目標（字串）或 [目標, 參數...]（非空字串陣列）」。
struct Target {
    std::string target;
    std::vector<std::string> args;
};
Target parse_target(const Json& v, const std::string& what);

// 跑一拍＝`aos-exec -- 目標 參數...`（`--` 讓 - 開頭的目標不被當旗標；相對路徑照 cwd，loop 不轉）：fork 一個子行程，
// 子行程裡解開那四個訊號、呼叫 aos::exec::run_cli（可執行檔／argv 陣列 exec 掉；單子在那個子行程裡跑、它當監工；
// 它自己的錯印一行「aos-exec: 代號 原因」、碼 1）——等同 bin 版起一支 PATH 上的 aos-exec，只是不必在 PATH 上找。
// 子行程跟呼叫者同一個行程群組（不另開）；跑的期間收到的三個訊號 kill 給它（不另設 SIGKILL 期限）。fork 失敗丟 LaunchFailed。
// 呼叫前要先 block_signals()。
Beat run_beat(const std::string& target, const std::vector<std::string>& args);

// 命令列（10-21 傍晚 ideas § 9；規則同 aos-exec，aos-util 的 parse_cli）：唯一的位置參數＝設定檔（必給、只能一個；
// 可寫 `檔#/指標`）。不認得的旗標丟 FlagUnknown；旗標缺值、沒給或多給設定檔丟 ArgumentsBad（msg＝「usage: <prog> [...] 設定檔.json（原因）」）。
// argv 不含程式名；回旗標（opts）與設定檔（rest[0]）。
aos::Cli loop_cli(const std::vector<std::string>& argv, const std::string& prog);

// 窗的寫法：先寫同資料夾的 `.名字`、再改名蓋過去（N-05）；內容是一行 JSON（排版同 Python json.dumps）＋換行。
// 寫不了丟 WriteFailed。
void write_window(const std::string& path, const Json& doc);

// 心跳欄位 {"pid", "start_ticks"（/proc/<pid>/stat 第 22 欄）, "boot_id", "at"（ISO 8601 UTC 到毫秒，aos::utc_now_ms）}（N-32）。
Json heartbeat();

// 每種程式的預設值（同 Python 版 Loop 的類別屬性）。
struct Defaults {
    std::string prog = "aos-loop";          // 錯誤一行的程式名
    std::optional<long long> max;           // nullopt＝不限（10-21 plan L8，原 10）
    long long interval_ms = 0;
    bool need_val = true;                   // val 必填
};

// 反覆跑的程式的骨架。設定檔（loop.json；daemon.json 是它的超集）的 key（旗標名＝key 名底線換連字號；起跑時 旗標 ＞ 設定檔 ＞ 預設）：
//   val           每拍跑的目標：字串或 [目標, 參數...]（parse_target；每拍 `aos-exec -- 目標 參數...`）；物件＝CfgBad；
//                 need_val 時必填（沒寫＝CfgBad「沒有東西可跑」）
//   max           最多幾拍（非負整數；沒寫＝Defaults::max；寫 null 不行）
//   interval_ms   一拍結束到下一拍開始至少隔幾毫秒（非負整數；沒寫＝Defaults::interval_ms）
//   ctl, state    兩扇窗的檔名，在 $AOS_STACK 底下（沒寫或 null＝不開；寫了卻沒設 AOS_STACK＝StackMissing）
// 其他 key 忽略（body、_exec…）。設定壞丟 Error（CfgMissing、CfgBad、StackMissing）。
// 每拍：有排著的訊號 → 結束 128＋N；讀 ctl（認 paused、stop、max、interval_ms、seq＋子類別多認的）→ tend() →
// stop 就結束（0）、拍滿就結束（0）→ paused 或還沒到時間就睡一下（最多 1 秒，收到訊號就醒）回頭再看 →
// 跑一拍：0＝下一拍、10＝結束（0）、其他非 0＝stderr 一行、以那個碼結束；拍中收到訊號＝收完以 128＋N 結束。
// state 只在拍與拍之間寫（心跳只在兩拍之間跳）。結束前呼叫 finish()（不論為什麼結束）。呼叫前要先 block_signals()。
class Loop {
public:
    // opts＝命令列旗標（loop_cli 解出來的：max、interval_ms、ctl、state），spec＝設定檔（`檔` 或 `檔#/指標`）。
    Loop(const std::map<std::string, std::string>& opts, const std::string& spec, const Defaults& d);
    virtual ~Loop() = default;
    Loop(const Loop&) = delete;
    Loop& operator=(const Loop&) = delete;

    // 跑到結束，回結束碼。自己的錯（tend、單子壞、窗寫不了）stderr 一行「程式名: 代號 原因」、先 finish() 再回 1。
    int serve();

protected:
    // 子類別蓋這四個
    virtual void tend(const Json& ctl);                              // 每拍讀完 ctl 後
    virtual void finish();                                           // 結束前（不論為什麼結束）
    virtual Json info();                                             // 寫進 state 的額外欄位（物件）
    virtual std::optional<std::string> check_ctl(const Json& doc);   // ctl 多認的 key 的驗證（回原因＝不採用）

    void say(const std::string& msg);   // stderr 一行「程式名: msg」

    Defaults d_;
    Json cfg_;                    // 設定檔整份（旗標已蓋上；子類別讀自己的 key）
    bool has_val_ = false;        // false＝沒有身體（daemon 純監工）
    Target val_;
    std::optional<long long> max_;
    long long interval_ms_ = 0;
    std::string stack_;           // $AOS_STACK（沒設＝空）
    std::string ctl_path_;        // 空＝不開
    std::string state_path_;      // 空＝不開

private:
    int main_loop();
    int end(int code, const std::string& phase);
    void write_state(const std::string& phase, const Json& code);
    Json read_ctl();
    int signal_got();             // 第一個收到的訊號（記住；0＝沒有）
    void nap(double secs);        // 睡 secs 秒（最多 1 秒），收到訊號就提早醒

    long long beats_ = 0;
    Json ctl_now_ = Json::object();
    Json ctl_good_ = Json::object();
    Json last_warning_;           // null 或字串
    int got_ = 0;
};

}  // namespace aos::loop
