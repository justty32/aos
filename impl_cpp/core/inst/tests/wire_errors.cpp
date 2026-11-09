// wire_errors.cpp：Inst 解析的 Catch2 測試（搬自 aos-v1 的 core/wire/tests/test_errors.cpp，11-04 在 c90f86178 刪掉前的版本）。
#include <aos/wire.hpp>

#include <catch2/catch_test_macros.hpp>

#include <string>

TEST_CASE("wire 拒絕壞 JSON、缺 argv 與空 argv") {
    std::string error;

    CHECK_FALSE(aos::wire::parse_inst("{", "a", error).has_value());
    CHECK_FALSE(error.empty());

    CHECK_FALSE(aos::wire::parse_inst(R"({"id":"a"})", "a", error)
                    .has_value());
    CHECK_FALSE(error.empty());

    CHECK_FALSE(aos::wire::parse_inst(R"({"argv":[]})", "a", error)
                    .has_value());
    CHECK_FALSE(error.empty());
}
