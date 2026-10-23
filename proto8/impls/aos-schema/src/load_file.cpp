// load_file.cpp：把 SCHEMA檔 讀成 nlohmann::json。錯誤代號（10-23 命名統合）：檔不在＝SchemaMissing；
// 在但讀不了、或不是合法 JSON＝SchemaBad。
#include "aos/schema.hpp"

#include <filesystem>
#include <fstream>
#include <sstream>
#include <system_error>

namespace aos::schema {

nlohmann::json load_file(const std::filesystem::path& path) {
    std::error_code ec;
    if (!std::filesystem::exists(path, ec)) {
        throw Error{code::SchemaMissing, "沒有 " + path.string()};
    }
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        throw Error{code::SchemaBad, "讀不到 " + path.string()};
    }
    std::stringstream buf;
    buf << in.rdbuf();
    if (in.bad()) {
        throw Error{code::SchemaBad, "讀 " + path.string() + " 時出錯"};
    }
    try {
        return nlohmann::json::parse(buf.str());
    } catch (const nlohmann::json::parse_error& e) {
        throw Error{code::SchemaBad, path.string() + " 不是合法 JSON：" + e.what()};
    }
}

}  // namespace aos::schema
