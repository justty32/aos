// launch.hpp：【launch】開跑（公開介面 run_inst、argv0 在 aos/exec.hpp）。內部標頭。
//
//   launch.cpp   cd 已在 hop 做完。可執行檔：execvp(入口, "./入口" args)；argv 陣列：解指示詞、argv0、execvp(argv[0], argv＋args)——
//                兩者 +x 沒 #! 都由 execvp 改用 /bin/sh 跑（ideas § 22）；inst 單子：run_inst（src/inst/）後回子程式的碼
// 對應 proto8/bin/aos-exec 的 launch。
#pragma once

#include "common/common.hpp"

#include <string>
#include <vector>

namespace aos::exec {

// Executable／Argv 是 exec（成功就不回來；失敗丟 LaunchFailed）；Inst 是 run_inst 後回子程式的碼。Redirect 不該進來。
int launch(const Found& found, const std::vector<std::string>& args);

}  // namespace aos::exec
