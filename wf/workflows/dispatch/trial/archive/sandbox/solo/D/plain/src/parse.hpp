#pragma once
#include <string>

namespace mini {

// 解析 "key=value"，失敗時回傳空字串（呼叫端分不出「失敗」與「值本來就是空的」）。
std::string parse(const std::string &line);

}  // namespace mini
