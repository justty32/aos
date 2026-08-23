#include "../src/run.hpp"

#include <catch2/catch_test_macros.hpp>

TEST_CASE("llms CLI accepts S4 stream syntax without going online") {
    char program[] = "aos llms";
    char ask[] = "ask";
    char stream[] = "--stream";
    char preset[] = "--preset";
    char missing[] = "does-not-exist";
    char prompt[] = "hello";
    char *stream_argv[] = {program, ask, stream, preset, missing, prompt};
    /* 未知 preset 是執行期錯誤 1；若 --stream 沒進語法，會先回 usage 的 2。 */
    CHECK(aos::llms::cli_run(6, stream_argv) == 1);

    char *missing_argv[] = {program, ask};
    CHECK(aos::llms::cli_run(2, missing_argv) == 2);
}
