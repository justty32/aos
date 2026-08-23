#include "../src/run.hpp"

#include <catch2/catch_test_macros.hpp>

TEST_CASE("llms CLI exposes only S3 non-stream syntax") {
    char program[] = "aos llms";
    char ask[] = "ask";
    char stream[] = "--stream";
    char prompt[] = "hello";
    char *stream_argv[] = {program, ask, stream, prompt};
    CHECK(aos::llms::cli_run(4, stream_argv) == 2);

    char *missing_argv[] = {program, ask};
    CHECK(aos::llms::cli_run(2, missing_argv) == 2);
}
