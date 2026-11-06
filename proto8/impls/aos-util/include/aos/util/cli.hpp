// aos/util/cli.hpp：【aos-util】10-21 起的命令列（aos-exec、aos-loop、aos-fsm、aos-daemon 共用）。
//
//     程式 [旗標...] 位置參數...
//
//   parse_cli   第一個不是旗標的參數（不以 - 開頭，或就是 -）起全部是 rest（之後原樣，不再解析旗標）；
//               `--` 結束旗標（位置參數可以 - 開頭）。旗標都帶一個值：`--x V` 或 `--x=V`（`--x=` 是空字串），
//               重複給＝最後一個算。不帶值的旗標（開關，10-22 `--dotenv-override`）另給一張表 switches：給了＝opts[值] 是 "1"，
//               重複給＝一樣，寫 `--x=V`＝Error{ArgumentsBad}。不認得的旗標＝Error{FlagUnknown}、旗標缺值＝Error{ArgumentsBad}；rest 夠不夠由呼叫者自己判斷。
//               `--help`（11-05 stdio-unify R3，內建開關）：在旗標的位置給了＝把 help（英文說明）印到 stdout、退 0（std::exit，不回來）；
//               help 是空的＝當成不認得的旗標。子命令程式：子命令前一次（全程式的說明）、子命令後各一次（那個子命令的說明）。
//   usage_error 錯誤行的 usage 位置（R5）：「原因 (usage: …)」——Error{code, reason + " (usage: " + usage + ")"}。
//   load_cfg    設定檔（aos-loop、aos-fsm、aos-daemon 的唯一位置參數）：`檔` 或 `檔#/指標`，回那個位置的值（不驗是不是物件）。
//               檔不在 CfgMissing、其他讀不了或不是 JSON CfgBad、`#` 後不是 `/` CfgBad、`#/` 指不到 CfgMissing（10-23 命名統合）。第一行 `#!` 跳過。
//
// 對應 proto8/py/aos_flags.py 的 parse、load_cfg（10-21 ideas § 3、10-21 傍晚 § 9）。
// 較早一代的 aos/flags.hpp（旗標＝key 原名、值當 JSON 解）11-04 已刪（沒人叫）。
#pragma once

#include "aos/util/io.hpp"

#include <map>
#include <string>
#include <vector>

namespace aos {

struct Cli {
    std::map<std::string, std::string> opts;   // 旗標表的值 → 字串（{"ws": "/x"}）
    std::vector<std::string> rest;             // 位置參數（第一個起原樣）
};

// argv 不含程式名。flags：旗標名（"--ws"）→ 存進 opts 的名字（"ws"）；switches：不帶值的旗標名 → 存進 opts 的名字。
// help：`--help`／`-h` 時印的說明（英文、印 stdout、退 0）。
// short_flags：從內建短名表挑選的短名，對應長名必須在 flags／switches；不黏值、不併、不帶 =。
// 表不合是呼叫端寫錯（std::invalid_argument）；命令列錯誤仍用 aos::Error。
Cli parse_cli(const std::vector<std::string>& argv, const std::map<std::string, std::string>& flags,
              const std::map<std::string, std::string>& switches = {}, const std::string& help = "",
              const std::vector<std::string>& short_flags = {});

Error usage_error(const std::string& code, const std::string& reason, const std::string& usage);

Json load_cfg(const std::string& spec);

}  // namespace aos
