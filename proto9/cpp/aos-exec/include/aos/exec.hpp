// aos/exec.hpp: public interface of proto9 aos-exec -- run a folder program (fix the workspace, walk in, read .env, pick the entry, exec it).
//
//   run_cli       等同命令列 `aos-exec [旗標...] XXX [args...]`：可執行檔／argv 陣列＝exec（成功不回來）；
//                 自己的錯 stderr 一行「aos-exec: error: 代號 原因」、回 1   ← 會動行程全域狀態（chdir、setenv）
//   argv0         argv[0] 帶 / 又 exec 不了（資料夾、沒 +x 的檔、+x 的 JSON、不在、帶 #/）＝前面插 aos-exec（10-20 ideas D3）
//
// proto9 (11-25): no AOS_STACK (no --stack / --stack-lazy, never set, never created; an inherited one passes through
// untouched) and no inst sheets (a JSON object with "argv" is EntryBad), so run_inst and its Result are gone.
// Error codes live in src/common/common.hpp (internal); callers only see the exit code and the stderr line.
// 長命的呼叫者不在自己的行程裡叫 run_cli：fork 出來的子行程裡叫（等同起一支 `aos-exec -- 目標 參數...`）。規則見 README.md。
#pragma once

#include <string>
#include <vector>

namespace aos::exec {

// 等同 `aos-exec args...`（args 不含程式名）。見上面。
int run_cli(const std::vector<std::string>& args);

// argv[0] 帶 / 又 exec 不了（join(cwd, argv[0]) 不是看內容像程式的一般檔：資料夾、沒 +x、+x 的 JSON〔11-10 /mnt/c〕、不在；或帶 #/）
// → 前面插 "aos-exec"；其他原樣（["tools/stamp", "a"]＝["aos-exec", "tools/stamp", "a"]；a 是 args）。
std::vector<std::string> argv0(const std::vector<std::string>& argv, const std::string& cwd);

}  // namespace aos::exec
