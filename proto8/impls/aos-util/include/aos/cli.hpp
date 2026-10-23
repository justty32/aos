// aos/cli.hpp：【aos-util】10-21 起的命令列（aos-exec、aos-loop、aos-fsm、aos-daemon 共用）。
//
//     程式 [旗標...] 位置參數...
//
//   parse_cli   第一個不是旗標的參數（不以 - 開頭，或就是 -）起全部是 rest（之後原樣，不再解析旗標）；
//               `--` 結束旗標（位置參數可以 - 開頭）。旗標都帶一個值：`--x V` 或 `--x=V`（`--x=` 是空字串），
//               重複給＝最後一個算。不帶值的旗標（開關，10-22 `--dotenv-override`）另給一張表 switches：給了＝opts[值] 是 "1"，
//               重複給＝一樣，寫 `--x=V`＝Error{Usage}。不認得的旗標、旗標缺值＝Error{Usage}；rest 夠不夠由呼叫者自己判斷。
//   load_cfg    設定檔（aos-loop、aos-fsm、aos-daemon 的唯一位置參數）：`檔` 或 `檔#/指標`，回那個位置的值（不驗是不是物件）。
//               讀不到 ReadFailed、不是 JSON JsonSyntax、`#` 後不是 `/`、指不到 FieldType。第一行 `#!` 跳過（同 read_json_at）。
//
// 對應 proto8/bin/aos_flags.py 的 parse、load_cfg（10-21 ideas § 3、10-21 傍晚 § 9）。
// 跟 aos/flags.hpp（10-16～17 那代：旗標＝key 原名、值當 JSON 解、設定從 stdin）是兩套（那套目前沒有程式在用，留著）。
#pragma once

#include "aos/io.hpp"

#include <map>
#include <string>
#include <vector>

namespace aos {

struct Cli {
    std::map<std::string, std::string> opts;   // 旗標表的值 → 字串（{"ws": "/x"}）
    std::vector<std::string> rest;             // 位置參數（第一個起原樣）
};

// argv 不含程式名。flags：旗標名（"--ws"）→ 存進 opts 的名字（"ws"）；switches：不帶值的旗標名 → 存進 opts 的名字。
Cli parse_cli(const std::vector<std::string>& argv, const std::map<std::string, std::string>& flags,
              const std::map<std::string, std::string>& switches = {});

Json load_cfg(const std::string& spec);

}  // namespace aos
