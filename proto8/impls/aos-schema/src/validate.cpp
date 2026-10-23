// validate.cpp：整個專案唯一碰 pboettch/json-schema-validator 的檔。換驗證器只改這裡。
//
// 做法分三步，每次呼叫都從頭來（簡單；要省再說）：
//   1. 先拿 draft-07 的 meta-schema 驗 schema 本身——pboettch 編 schema 時不檢查這個，
//      `{"type": 5}` 會被默默吞掉，所以自己先擋。
//   2. 把 schema 編起來；編不起來（例如 $ref 指到不存在的地方）＝SchemaBad。
//   3. 驗 doc，用一個 error handler 把每個錯收成 Problem。驗的途中才發現 schema 有問題也算 SchemaBad。
#include "aos/schema.hpp"

#include <nlohmann/json-schema.hpp>

#include <exception>

namespace aos::schema {

namespace {

using nlohmann::json_schema::json_validator;

// 驗證器每找到一個錯就呼叫 error()；全部收起來，不中途停。
struct Collector : nlohmann::json_schema::basic_error_handler {
    std::vector<Problem> problems;
    void error(const nlohmann::json::json_pointer& ptr, const nlohmann::json& /*instance*/,
               const std::string& message) override {
        basic_error_handler::error(ptr, nlohmann::json(), message);   // 讓 handler 的 bool 也記得「有錯」
        problems.push_back({ptr.to_string(), message});
    }
};

// meta-schema 裡有 format（uri-reference、regex），不給 format checker 驗證器會丟例外；
// 這裡不細查 format，給一個什麼都放行的。
void accept_any_format(const std::string& /*format*/, const std::string& /*value*/) {}

// 第 1 步：schema 合不合 draft-07。meta-schema 驗證器只編一次（第一次呼叫時）。
void check_against_meta(const nlohmann::json& schema) {
    static const json_validator meta(nlohmann::json_schema::draft7_schema_builtin, nullptr, accept_any_format);
    Collector collector;
    meta.validate(schema, collector);
    if (collector.problems.empty()) {
        return;
    }
    const Problem& p = collector.problems[0];
    std::string where = p.pointer;
    if (where.empty()) {
        where = "/";
    }
    throw Error{code::SchemaBad, "schema 不合 draft-07：" + where + " " + p.message};
}

}  // namespace

std::vector<Problem> validate(const nlohmann::json& schema, const nlohmann::json& doc) {
    check_against_meta(schema);

    // 沒給 loader：外部 $ref 一律讀不到（會變 SchemaBad）。format 用驗證器內建的檢查（date-time、email…）。
    json_validator validator(nullptr, nlohmann::json_schema::default_string_format_check);
    try {
        validator.set_root_schema(schema);
    } catch (const std::exception& e) {
        throw Error{code::SchemaBad, e.what()};
    }

    Collector collector;
    try {
        validator.validate(doc, collector);
    } catch (const std::exception& e) {
        throw Error{code::SchemaBad, e.what()};
    }
    return collector.problems;
}

}  // namespace aos::schema
