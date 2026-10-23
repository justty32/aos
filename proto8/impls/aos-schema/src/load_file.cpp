// load_file.cpp：把一個檔讀成 nlohmann::json。分兩步，好讓錯誤代號分得清楚：
// 先整檔讀進字串（失敗＝ReadFailed），再解析（失敗＝JsonSyntax）。
#include "aos/schema.hpp"

#include <fstream>
#include <sstream>

namespace aos::schema {

nlohmann::json load_file(const std::filesystem::path& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        throw Error{code::ReadFailed, "讀不到 " + path.string()};
    }
    std::stringstream buf;
    buf << in.rdbuf();
    if (in.bad()) {
        throw Error{code::ReadFailed, "讀 " + path.string() + " 時出錯"};
    }
    try {
        return nlohmann::json::parse(buf.str());
    } catch (const nlohmann::json::parse_error& e) {
        throw Error{code::JsonSyntax, path.string() + " 不是合法 JSON：" + e.what()};
    }
}

}  // namespace aos::schema
