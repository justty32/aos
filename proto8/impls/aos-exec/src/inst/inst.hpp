// inst.hpp：【inst】行程內跑一張 inst 單子（公開的 run_inst 在 aos/exec.hpp）。內部標頭，只給 src/ 自己用。
//
//   fields.cpp     單子（$env 已解）→ Inst：認 10 個 key、驗型別，其他 key 一律忽略（格式正本＝proto8/bin/aos_inst.py 的 parse）
//   lib_input.cpp  Inst → libaos 的單子（aos_inst_input_t）：相對路徑算成絕對、組環境、串流沒寫＝接呼叫者的（inherits）、
//                  一律自成行程群組（new_session）
//   signals.cpp    訊號：run_inst 進來擋住 INT／TERM／HUP、出去還原；跑的期間收下來轉給子程式的整個群組（killpg），
//                  第一次轉過之後過 grace_ms 還沒結束就 SIGKILL 整群
//   run.cpp        run_inst：解 $env（aos-directive）→ parse_inst → aos_inst_start → 工人執行緒 aos_inst_wait、
//                  主執行緒轉訊號 → Result；libaos 的錯換成 LaunchFailed／Internal
//
// 從 impls/aos-inst 的 src/json/fields.cpp、src/libaos/{lib_input,signals,run}.cpp 抄來改（aos-inst 本身不動）。
// 跟 aos-inst 不同：key 只認 10-19 的 10 個（沒有 id、envs_clear、*_mkdir、stderr_merge）、串流沒寫＝接呼叫者的、
// 整群送訊號、錯誤代號不一個個鏡射 libaos。
#pragma once

#include "common/common.hpp"

#include "aos.h"   // impls/inst 的公開標頭（C 的 libaos）

#include <map>
#include <optional>
#include <string>
#include <vector>

#include <signal.h>
#include <sys/types.h>

namespace aos::exec {

// 驗好的一張單子（相對路徑還沒算成絕對）。
struct Inst {
    std::vector<std::string> argv;               // 已接上 args
    std::optional<std::string> cwd;
    std::map<std::string, std::string> envs;
    std::optional<std::string> paths[3];         // stdin、stdout、stderr；沒寫＝接呼叫者的
    bool appends[3] = {false, false, false};     // [1]stdout_append、[2]stderr_append
    unsigned long long timeout_ms = 0;           // 0＝不限（單子上是 null 或沒寫）
    unsigned long long grace_ms = 2000;
};

// doc（$env 已解）→ Inst；args 接在 argv 後面。型別不對丟 EntryBad。
Inst parse_inst(const Json& doc, const std::vector<std::string>& args);

// 給 libaos 的單子，連同它指到的字串（單子裡都是 char*，字串要有人留著）。
// 欄位彼此指來指去，所以不能複製、不能搬：宣告一個，交給 build_lib_input 填。
struct LibInput {
    std::string cwd;                            // 絕對路徑
    std::optional<std::string> paths[3];        // 絕對路徑
    std::vector<const char*> argv;              // 指到 Inst::argv 的字串，NULL 結尾
    std::vector<std::string> env_strings;       // "K=V"
    std::vector<const char*> envp;              // 指到 env_strings，NULL 結尾
    aos_inst_input_t in{};                      // 真正交給 libaos 的那張

    LibInput() = default;
    LibInput(const LibInput&) = delete;
    LibInput& operator=(const LibInput&) = delete;
};

// 算絕對路徑、組環境、填好 out.in。inst 要活得比 out 久（out.argv 指到 inst 的字串）。
void build_lib_input(const Inst& inst, const std::string& base_dir, LibInput& out);

// 那三個要轉的訊號（SIGINT、SIGTERM、SIGHUP）。
sigset_t forwarded_signals();

// 開一個 signalfd 收那三個訊號（要先擋住）。失敗回 -1。
int open_signal_fd();

// 一直把訊號轉給 pgid 這個行程群組，直到 done_fd 有東西（工人做完了）。回轉過的第一個訊號（沒有＝0）。
int forward_signals_until_done(pid_t pgid, unsigned long long grace_ms, int sig_fd, int done_fd);

}  // namespace aos::exec
