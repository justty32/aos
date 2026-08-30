# agent：以資料夾回合驅動、會自我投遞的 LLM agent。

aos_add_subproject(agent
    SOURCES
        src/paths.cpp
        src/store.cpp
        src/deliver.cpp
        src/tools.cpp
        src/step.cpp
        src/init.cpp
    HEADERS
        include/aos/agent.hpp
    PRIVATE_DEPS
        aos::llm
)

add_library(aos_agent_cli OBJECT src/run.cpp)
target_link_libraries(aos_agent_cli PUBLIC aos::agent)

aos_add_subcommand(
    NAME agent
    ENTRY aos_agent_cli_main
    LIBRARY aos_agent_cli
    SUMMARY "建立並推進回合制資料夾 agent"
)

aos_add_test(aos_agent_tests
    SOURCES
        tests/test_agent_tools.cpp
        tests/test_agent_store.cpp
        tests/test_agent_step.cpp
    LINK aos_agent_cli
)

include(${CMAKE_CURRENT_SOURCE_DIR}/tests/fake_loop.cmake)
