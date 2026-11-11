// run.cpp：【run】run_once——跑一次（說明見 aos/loop.hpp）。
//
// 目標（字串、[目標, 參數...]）：交給 run_folder（folder.cpp），在子行程裡 `aos-exec -- 目標 參數...`（10-21 plan L11；傍晚 ideas § 9 加陣列）。
// 單子（物件，10-24 恢復）：交給 run_inline（inline.cpp），行程內呼叫 aos-exec 的 run_inst。
// 11-11：timeout_ms 只給 on_start／on_stop（身體照舊不限）。
// 10-21～10-23 只收目標、內嵌單子要寫 `loop.json#/body` 繞一圈；10-24 使用者「exec本來就應該要可以直接放內嵌單子吧」，改回來。
#include "run/run.hpp"

namespace aos::loop {

Run run_once(const Target& t, long long timeout_ms) {
    if (t.inst) {
        // 11-11 on_start／on_stop：單子自己沒寫期限＝補上 timeout_ms（寫了照它的）
        if (timeout_ms > 0 && t.inst->is_object() && !t.inst->contains("timeout_ms") && !t.inst->contains("timeout_cycles")) {
            Target u = t;
            (*u.inst)["timeout_ms"] = timeout_ms;
            return run_inline(u);
        }
        return run_inline(t);
    }
    std::vector<std::string> argv{"--", t.target};
    argv.insert(argv.end(), t.args.begin(), t.args.end());
    return run_folder(argv, timeout_ms);
}

}  // namespace aos::loop
