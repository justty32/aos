# llms：OpenAI 相容端點 client，含 SSE 串流。

file(READ ${CMAKE_CURRENT_SOURCE_DIR}/presets.json AOS_LLMS_PRESETS_JSON)
configure_file(
    src/presets_data.hpp.in
    ${CMAKE_CURRENT_BINARY_DIR}/generated/presets_data.hpp
    @ONLY
)

aos_add_subproject(llms
    SOURCES
        src/content.cpp
        src/params.cpp
        src/toolcalls.cpp
        src/toolset.cpp
        src/transport.cpp
        src/sse.cpp
        src/caps.cpp
        src/llm.cpp
        src/reply.cpp
        src/stream_reply.cpp
        src/bot.cpp
        src/presets.cpp
    HEADERS
        include/aos/llms.hpp
        include/aos/llms/transport.hpp
        include/aos/llms/caps.hpp
        include/aos/llms/tools.hpp
        include/aos/llms/llm.hpp
        include/aos/llms/bot.hpp
        include/aos/llms/presets.hpp
        include/aos/llms/content.hpp
    PRIVATE_DEPS
        CURL::libcurl
)
target_include_directories(aos_llms_objects PRIVATE
    ${CMAKE_CURRENT_BINARY_DIR}/generated
)

# CLI 只走公開 API；ask / models 會連外，所以 ctest 不呼叫成功路徑。
add_library(aos_llms_cli OBJECT src/run.cpp)
target_link_libraries(aos_llms_cli PUBLIC aos::llms)

aos_add_subcommand(
    NAME llms
    ENTRY aos_llms_cli_main
    LIBRARY aos_llms_cli
    SUMMARY "呼叫 OpenAI 相容端點並查詢模型能力"
)

aos_add_test(aos_llms_tests
    SOURCES
        tests/test_content_params.cpp
        tests/test_toolcalls.cpp
        tests/test_toolset_presets.cpp
        tests/test_caps.cpp
        tests/test_reply_errors.cpp
        tests/test_bot_turn.cpp
        tests/test_stream_split.cpp
        tests/test_stream_reply.cpp
        tests/test_run.cpp
    LINK aos_llms_cli aos_common_private
)
