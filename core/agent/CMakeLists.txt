# agent：以資料夾回合驅動、由 every 常駐投遞的 LLM agent。

aos_add_subproject(agent
    SOURCES
        src/paths.cpp
        src/store.cpp
        src/deliver.cpp
        src/tools.cpp
        src/engine.cpp
        src/engine_pi.cpp
        src/step.cpp
        src/init.cpp
        src/user.cpp
    HEADERS
        include/aos/agent.hpp
    PUBLIC_DEPS
        aos::tool
    PRIVATE_DEPS
        aos::exec aos::llm aos::loop
)

add_library(aos_agent_cli OBJECT src/run.cpp src/run_top.cpp)
target_link_libraries(aos_agent_cli PUBLIC aos::agent)

aos_add_subcommand(
    NAME agent
    ENTRY aos_agent_cli_main
    LIBRARY aos_agent_cli
    SUMMARY "建立並推進回合制資料夾 agent"
)

aos_add_subcommand(
    NAME say
    ENTRY aos_say_cli_main
    LIBRARY aos_agent_cli
    SUMMARY "對這個資料夾的 agent 說一句話"
)

aos_add_subcommand(
    NAME listen
    ENTRY aos_listen_cli_main
    LIBRARY aos_agent_cli
    SUMMARY "跟讀這個資料夾 agent 的對話記錄"
)

aos_add_subcommand(
    NAME talk
    ENTRY aos_talk_cli_main
    LIBRARY aos_agent_cli
    SUMMARY "跟這個資料夾的 agent 逐行對話"
)

aos_add_subcommand(
    NAME state
    ENTRY aos_state_cli_main
    LIBRARY aos_agent_cli
    SUMMARY "印出這個資料夾 agent 的 status.json"
)

aos_add_test(aos_agent_tests
    SOURCES
        tests/test_agent_tools.cpp
        tests/test_agent_store.cpp
        tests/test_agent_step.cpp
        tests/test_agent_engine.cpp
        tests/test_agent_cli.cpp
        tests/test_agent_lifecycle.cpp
    LINK aos_agent_cli
)

include(${CMAKE_CURRENT_SOURCE_DIR}/tests/fake_loop.cmake)
