// aos/schema.hpp：【aos-schema 的公開介面】拿一份 JSON Schema（draft-07）去驗一份 JSON，回「哪裡、哪裡不對」的清單。
//
// 這裡只露 nlohmann::json 與 std 型別；底下用哪個驗證器（目前是 pboettch/json-schema-validator）
// 只有 src/validate.cpp 知道，以後換實作只改那個檔。
//
//   nlohmann::json schema = aos::schema::load_file("inst.schema.json");
//   for (const Problem& p : aos::schema::validate(schema, doc)) { std::cout << p.pointer << ": " << p.message; }
//
// 「驗不過」是資料（回 Problem 清單），「工具自己出錯」才丟 aos::Error（aos-util 的 aos/error.hpp）。
// 注意這裡的 JSON 型別是 nlohmann::json（key 會照字母排序），不是全家用的 aos::Json（ordered_json）：
// 驗證器只收前者；aos::Json 傳進來會自動轉。
#pragma once

#include "aos/error.hpp"

#include <nlohmann/json.hpp>

#include <filesystem>
#include <string>
#include <vector>

namespace aos::schema {

using aos::Error;

namespace code {
using namespace aos::code;   // Usage、JsonSyntax、InputExtra、ReadFailed、Internal…
inline constexpr const char* SchemaBad = "SchemaBad";   // schema 不合 draft-07、或 $ref 指不到（只有 aos-schema 會吐）
}  // namespace code

// 一個驗不過的地方。pointer＝出事那一格的 JSON pointer（整份＝""），message＝驗證器的說明（英文）。
struct Problem {
    std::string pointer;
    std::string message;
};

// 讀一個 JSON 檔。讀不到＝Error{ReadFailed}，不是合法 JSON＝Error{JsonSyntax}。
nlohmann::json load_file(const std::filesystem::path& path);

// 用 schema 驗 doc，回所有驗不過的地方（空＝通過）。
// schema 本身壞掉（不合 draft-07、$ref 指不到）＝Error{SchemaBad}。$ref 只支援同一份檔內（"#/definitions/x"）。
std::vector<Problem> validate(const nlohmann::json& schema, const nlohmann::json& doc);

}  // namespace aos::schema
