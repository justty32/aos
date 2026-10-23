// aos/exec.hpp：aos-exec 的公開介面——在工作區執行一個 aos 程式（定工作區、找入口、設環境變數、cd 進去、讀 .env、開跑）。
//
//   run_cli       等同命令列 `aos-exec [旗標...] XXX [args...]`（10-21 起；src/cli/）：可執行檔／argv 陣列＝exec（成功不回來）；
//                 inst 單子＝行程內跑、回子程式的碼；自己的錯 stderr 一行「aos-exec: 代號 原因」、回 1   ← 會動行程全域狀態
//   run_inst      行程內跑一張 inst 單子（交給 impls/inst 的 libaos；aos-exec 留在行程裡當監工）
//   argv0         argv[0] 帶 / 又 exec 不了（資料夾、沒 +x 的檔、不在、帶 #/）＝前面插 aos-exec（10-20 ideas D3）
//
// 命令列（src/main.cpp）只叫 run_cli；aos-loop／aos-fsm 的每次、aos-daemon 的子 loop 在 fork 出來的子行程裡叫 run_cli
// （等同 bin 版起一支 `aos-exec -- 目標 參數...`）。規則見 aos-exec/README.md。
// 10-21 晚以前的 find_entry／resolve_ws／prepare_env／apply_env／launch 五步拆不開了（.env 要在挑入口之前讀、
// 每走進一層都要 cd 和 setenv），收進 run_cli，不再公開。
// 錯一律丟 aos::Error{code, msg}（aos-util 的 aos/error.hpp）；run_cli 自己接住印出來。
#pragma once

#include "aos/error.hpp"
#include "aos/io.hpp"

#include <string>
#include <vector>

namespace aos::exec {

// 錯誤代號（全家共用的在 aos-util 的 aos::code；這裡只加 aos-exec 自己會吐的）
namespace code {
using namespace aos::code;   // ArgumentsBad、FlagUnknown、MkdirFailed、LaunchFailed、Internal…
inline constexpr const char* WsMissing = "WsMissing";               // WS 不是資料夾
inline constexpr const char* EntryMissing = "EntryMissing";         // 入口找不到（檔、.json 補找、指標指不到、多段路徑中間不是資料夾）
inline constexpr const char* EntryBad = "EntryBad";                 // 找到了但跑不了（種類不對、# 寫錯、繞圈、單子欄位型別不對）
inline constexpr const char* DotenvBad = "DotenvBad";               // .env 讀不到（權限、是資料夾；原因開頭「.env 讀不到」）、.env 壞
                                                                    // （格式不合、${名字} 沒設、不是 UTF-8；JSON 的 .env key 指示詞解不開、
                                                                    // 名字不合；原因開頭「.env 壞」）。只印位置、不印值
}  // namespace code

// 等同 `aos-exec args...`（args 不含程式名）。見上面。
int run_cli(const std::vector<std::string>& args);

// 行程內跑一張 inst 單子的結果（子程式回幾號、被逾時收掉都算正常跑完）。
struct Result {
    int code = 0;
    int signal = 0;
    bool timed_out = false;
    long pid = 0;
    unsigned long long ms = 0;
    int received = 0;   // 跑的期間收到、轉給子程式的第一個訊號（SIGINT／SIGTERM／SIGHUP；0＝沒有）。給 loop／fsm 這種
                        // 「收完這次再以 128＋N 結束」的呼叫者用（訊號被 run_inst 的 signalfd 讀走了，呼叫者自己看不到）
};

// 行程內跑一張 inst 單子：doc＝單子（先解指示詞 $env／$ref，再驗 10 個 key，其他 key 忽略）、
// base_dir＝相對路徑的基準（CLI 給 entry.dir）、args 接在 argv 尾、ref_base＝$ref 相對檔名的起點（寫著單子的檔所在的資料夾；
// 空＝base_dir）。argv[0] 帶 / 又 exec 不了＝前面插 aos-exec（argv0，從解出來的 cwd 看；aos-exec 照子程式的 PATH 找）。
// 串流沒寫＝接呼叫者的 fd 0／1／2。子程式自成行程群組；跑的期間 SIGINT／SIGTERM／SIGHUP 不打斷呼叫者、
// 轉給整個群組，轉過之後過 grace_ms 還沒結束就 SIGKILL 整群；timeout_ms 由 libaos 管（逾時也是整群收）。
// 回 Result（子程式回幾號、被逾時收掉都算正常跑完；被訊號停掉 code＝128＋N；轉過訊號 received＝第一個）。
// 單子壞 EntryBad、指示詞壞或 $env 沒設 DirectiveBad、起不來 LaunchFailed（訊息開頭是 libaos 的名字）、收不到結果 Internal。
// 訊號遮罩：進來時擋住三個訊號、出去時還原（單執行緒的呼叫者什麼都不用做；多執行緒的呼叫者要在開執行緒前
// 自己把三個訊號擋在每條執行緒上，不然訊號可能送到別條執行緒去）。會讀 environ（環境變數要先設好）。
Result run_inst(const Json& doc, const std::string& base_dir, const std::vector<std::string>& args,
                const std::string& ref_base = "");

// argv[0] 帶 / 又 exec 不了（join(cwd, argv[0]) 不是有 +x 的一般檔：資料夾、沒 +x、不在；或帶 #/）→ 前面插 "aos-exec"；
// 其他原樣（10-20 ideas D3～D5：["tools/stamp", "a"]＝["aos-exec", "tools/stamp", "a"]；10-21 起 a 是 args）。
std::vector<std::string> argv0(const std::vector<std::string>& argv, const std::string& cwd);

}  // namespace aos::exec
