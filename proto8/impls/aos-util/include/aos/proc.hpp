// aos/proc.hpp：【aos-util】子程序——起、看結束了沒、整群送訊號、收屍、/proc、memfd。loop 起 aos-inst、daemon 起 loop 都用這組。
//
// 三個要先懂的 Linux 名詞（白話）：
//   - 行程群組／session：起子程序時讓它「自成一個 session」（setsid），它就是一個新群組的組長，
//     群組號碼＝它的 pid。它再起的孫程式預設都在同一群組，所以「對整群送訊號」（killpg）能一次清掉一整串。
//   - 收屍（reap）：子程序結束後，kernel 留著它的結束碼等父行程來拿（waitpid）；拿走之前它是殭屍，
//     pid 也還被佔著、不會分給別人。所以先「看結束了沒但不收屍」（WNOWAIT），趁 pid／群組號碼還不會被重用，
//     對整群補一發 SIGKILL 清孫程式，最後才收屍——不會誤殺到別人。
//   - memfd：一個只活在記憶體裡、沒有檔名的檔。拿來當子程序的 stdin（先把要灌的 JSON 寫進去）和 stdout／stderr
//     （子程序寫完再讀回來）。好處：不用管道（pipe），就不用開執行緒讀、也不會遇到「對方先死了寫入就收到 SIGPIPE」。
// 對應 Python aos_proc.py（_exited、_killpg、reap、stop）與 subprocess.Popen(start_new_session=True)。
#pragma once

#include <optional>
#include <string>
#include <vector>

#include <sys/types.h>

namespace aos {

// 子程序的三個串流：給一個 fd，-1＝沿用我們自己的。
struct Stdio {
    int in = -1;
    int out = -1;
    int err = -1;
};

// 起一個子程序（posix_spawn）。new_session＝自成一個 session（群組號碼＝它的 pid）。
// 子程序的訊號遮罩一律清空（我們自己擋著的訊號不會傳給它）。起不來丟 Error{LaunchFailed}。
pid_t spawn(const std::vector<std::string>& argv, Stdio io, bool new_session);

// 結束了沒（不收屍，WNOWAIT）。
bool has_exited(pid_t pid);

// 等到它結束（不收屍）。
void wait_exited(pid_t pid);

// 對整群送訊號；群組不在、沒權限都不管。
void signal_group(pid_t pgid, int sig);

// 已經結束（還沒收屍）的子程序：對整群補 SIGKILL 清孫程式，再收屍。回退出碼；被訊號停掉＝負的訊號號碼（同 Python）。
int reap(pid_t pid);

// 整群 SIGTERM，等它自己結束（aos-inst 保證過它的 grace_ms 會收掉子程式並結束），收屍，回退出碼。
int stop(pid_t pid);

// 收屍、不碰群組（daemon 跑策略格那種不自成 session 的）。
int wait_plain(pid_t pid);

// 一個行程的啟動時間（/proc/<pid>/stat 第 22 欄，clock ticks）；pid 0＝自己。讀不到＝nullopt。
// pid＋啟動時間對得上＝同一個行程（pid 會被重用，啟動時間不會一樣）。
std::optional<long long> proc_started_at_ticks(pid_t pid);

// 開機 id（/proc/sys/kernel/random/boot_id）；讀不到＝nullopt。
std::optional<std::string> boot_id();

// 現在的 UTC 時間，ISO 8601 到毫秒（毫秒無條件捨去），同 Python
// datetime.now(timezone.utc).isoformat(timespec="milliseconds")：2026-10-23T01:58:45.123+00:00
// （10-23 命名統合：state 的 at、fsm trace 的 at 都用這一種寫法）。
std::string utc_now_ms();

// 兄弟專案的執行檔：自己是 impls/X/bin/X，就回 impls/<name>/bin/<name>（全家找執行檔的規則，不看 PATH）。
std::string sibling_tool(const std::string& name);

// memfd：裝著 text 的記憶體檔（讀寫位置在開頭），或空的一個。都帶 CLOEXEC（不會漏給不相干的子程序）。
int memfd_with(const std::string& text);
int memfd_empty();

// 從頭讀完一個 fd 的內容。
std::string read_all(int fd);

}  // namespace aos
