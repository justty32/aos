// run.cpp：【run】run_once——跑一次（說明見 aos/loop.hpp）。
//
// 目標（字串、[目標, 參數...]）：交給 run_folder（folder.cpp），在子行程裡 `aos-exec -- 目標 參數...`（10-21 plan L11；傍晚 ideas § 9 加陣列）。
// 單子（物件，10-24 恢復）：交給 run_inline（inline.cpp），行程內呼叫 aos-exec 的 run_inst。
// 10-21～10-23 只收目標、內嵌單子要寫 `loop.json#/body` 繞一圈；10-24 使用者「exec本來就應該要可以直接放內嵌單子吧」，改回來。
#include "run/run.hpp"

namespace aos::loop {

Run run_once(const Target& t) {
    if (t.inst) {
        return run_inline(t);
    }
    std::vector<std::string> argv{"--", t.target};
    argv.insert(argv.end(), t.args.begin(), t.args.end());
    return run_folder(argv);
}

}  // namespace aos::loop
