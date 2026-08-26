# tooljson：讀取跨語言 tool spec，驗證並把模型參數展開成 argv。

aos_add_subproject(tooljson
    SOURCES
        src/spec.cpp
        src/spec_parse.cpp
        src/spec_load.cpp
        src/registry.cpp
        src/exec_type.cpp
        src/exec_argv.cpp
        src/exec_io.cpp
        src/exec_limits.cpp
        src/args.cpp
        src/args_value.cpp
        src/text.cpp
        src/fingerprint.cpp
    HEADERS
        include/aos/tooljson.hpp
)

# CLI 只使用公開 API；S1 只提供不執行任何工具的 list 與 check。
add_library(aos_tooljson_cli OBJECT src/run.cpp)
target_link_libraries(aos_tooljson_cli PUBLIC aos::tooljson)

aos_add_subcommand(
    NAME tooljson
    ENTRY aos_tooljson_cli_main
    LIBRARY aos_tooljson_cli
    SUMMARY "讀取並檢查 tool JSON spec"
)

aos_add_test(aos_tooljson_tests
    SOURCES
        tests/test_spec.cpp
        tests/test_validation.cpp
        tests/test_registry.cpp
        tests/test_args.cpp
        tests/test_text.cpp
        tests/test_run.cpp
    LINK aos_tooljson_cli
)
