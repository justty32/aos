// aos/text.hpp：【aos-util】UTF-8 字串的小工具（10-22 起 aos-exec 的 .env、aos-fsm 的 state 檔用）。
//
//   is_utf8                  嚴格的 UTF-8 檢查（同 Python 的 utf-8 解碼：不收過長編碼、代理區、超過 U+10FFFF）
//   space_at                 s[i] 起是不是一個空白字（照 Python str.isspace），是＝回它的位元組數
//   lstrip / rstrip / strip  去頭／尾／頭尾的空白（照 Python str.lstrip()／rstrip()／strip()，認 Unicode 空白）
//
// 空白＝Python str.isspace 那一套：ASCII 的 \t～\r、\x1c～\x1f、空格，與 U+0085、U+00A0、U+1680、U+2000～U+200A、
// U+2028、U+2029、U+202F、U+205F、U+3000。呼叫者要先確定字串是 UTF-8（不是的話照位元組走、不會壞，只是不準）。
#pragma once

#include <string>

namespace aos {

bool is_utf8(const std::string& s);

size_t space_at(const std::string& s, size_t i);

std::string lstrip(const std::string& s);
std::string rstrip(const std::string& s);
std::string strip(const std::string& s);

}  // namespace aos
