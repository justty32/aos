// env.cpp：{"$env": "NAME"}——換成環境變數 NAME 的值（字串）。對應 proto8/bin/aos_inst.py 的 _env。
//
// NAME 不是字串或是空字串＝寫法不合，回 nullopt（物件原封不動留著，10-20 ideas D15）；
// 環境裡沒有這個變數＝DirectiveBad（設成空字串的變數算有，值就是 ""）。$path／$prefix 由 resolve.cpp 接。
#include "internal.hpp"

#include <cstdlib>

namespace aos::directive {

std::optional<Json> resolve_env(const Json& d) {
    const Json& name = d["$env"];
    if (!name.is_string() || name.get<std::string>().empty()) {
        return std::nullopt;
    }
    const char* val = std::getenv(name.get<std::string>().c_str());
    if (val == nullptr) {
        throw Error{code::DirectiveBad, "環境變數 " + name.get<std::string>() + " 沒設定"};
    }
    return Json(val);
}

}  // namespace aos::directive
