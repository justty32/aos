# llm：用 libcurl 呼叫 OpenAI 相容 chat completions 端點。

aos_add_subproject(llm
    SOURCES
        src/llm.cpp
        src/slot.cpp
    HEADERS
        include/aos/llm.hpp
        include/aos/slot.hpp
    PRIVATE_DEPS
        CURL::libcurl
)

add_library(aos_llm_cli OBJECT src/run.cpp)
target_link_libraries(aos_llm_cli PUBLIC aos::llm)

aos_add_subcommand(
    NAME llm
    ENTRY aos_llm_cli_main
    LIBRARY aos_llm_cli
    SUMMARY "call an OpenAI-compatible endpoint and print the text"
)
