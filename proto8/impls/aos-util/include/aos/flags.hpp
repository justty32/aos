// aos/flags.hpp：【aos-util】命令列旗標——aos 這一家工具的旗標規則，一份。
//
//   工具 [--key 值 ...] [-- 其餘...]
//
// - 旗標名＝設定 JSON 的 key 原名（底線：`--timeout_ms 100`，不收減號寫法 `--timeout-ms`）。
//   只認 keys 裡的名字（通常＝欄位表裡的純量 key），其他＝FlagUnknown。
// - 每個旗標都要帶一個值（少了＝ArgumentsBad）；值先當 JSON 解（3、null、true），解不了就當字串。
// - `--`：後面整段原封不動放進 rest（aos-inst 拿去蓋 argv；aos-loop 不收，看到 rest 有值就報 ArgumentsBad）。
// - 其他（位置參數，含 `-`）＝ArgumentsBad：設定一律從 stdin 讀，沒有 TARGET。
// 旗標刻意用 key 原名（底線不換減號）。
#pragma once

#include "aos/io.hpp"

#include <optional>
#include <string>
#include <vector>

namespace aos {

// 命令列拆完的樣子。
struct Flags {
    Json values = Json::object();                   // --timeout_ms 100 → {"timeout_ms": 100}
    std::optional<std::vector<std::string>> rest;   // `--` 後面整段；沒寫 `--`＝nullopt
};

// prog＝錯誤訊息裡的程式名（"aos-inst"）。
Flags parse_flags(int argc, char** argv, const std::vector<std::string>& keys, const std::string& prog);

}  // namespace aos
