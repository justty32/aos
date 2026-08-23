#include <aos/tooljson.hpp>

#include <catch2/catch_test_macros.hpp>

#include <string>

TEST_CASE("decode hides NUL-containing output as binary") {
    const char binary[] = {'a', '\0', 'b', '\n'};
    CHECK(aos::tooljson::decode_output(binary, sizeof(binary)) ==
          "(binary output, 4 bytes, not shown)");
    CHECK(aos::tooljson::decode_output(nullptr, 0).empty());
}

TEST_CASE("decode preserves UTF-8 and replaces invalid bytes") {
    const std::string utf8 = "正確 UTF-8";
    CHECK(aos::tooljson::decode_output(utf8.data(), utf8.size()) == utf8);

    const char invalid[] = {'a', static_cast<char>(0xff), 'b'};
    CHECK(aos::tooljson::decode_output(invalid, sizeof(invalid)) ==
          "a\xef\xbf\xbd" "b");
}

TEST_CASE("clip keeps the requested end and reports omitted characters") {
    CHECK(aos::tooljson::clip_output("abcdefghij", "head", 4) ==
          "abcd\n… [truncated, 6 more characters]");
    CHECK(aos::tooljson::clip_output("abcdefghij", "tail", 4) ==
          "… [truncated, 6 earlier characters]\nghij");
}

TEST_CASE("clip counts Unicode code points rather than UTF-8 bytes") {
    const std::string text = "甲乙丙丁戊";
    CHECK(aos::tooljson::clip_output(text, "head", 3) ==
          "甲乙丙\n… [truncated, 2 more characters]");
    CHECK(aos::tooljson::clip_output(text, "tail", 2) ==
          "… [truncated, 3 earlier characters]\n丁戊");
}
