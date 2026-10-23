// run.cpp：【run】run_once——跑一次（說明見 aos/loop.hpp）。
//
// 10-21 起只收 aos-exec 的目標（10-21 plan L11、F2；傍晚 ideas § 9 加 [目標, 參數...]）：交給 run_folder（folder.cpp），
// 在子行程裡 `aos-exec -- 目標 參數...`。原本物件＝行程內 run_inst 那條拿掉（要內嵌單子寫 `loop.json#/body`，由 aos-exec 跑）。
#include "run/run.hpp"

namespace aos::loop {

Run run_once(const std::string& target, const std::vector<std::string>& args) {
    std::vector<std::string> argv{"--", target};
    argv.insert(argv.end(), args.begin(), args.end());
    return run_folder(argv);
}

}  // namespace aos::loop
