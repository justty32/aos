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
        src/inbox.cpp
        src/user.cpp
    HEADERS
        include/aos/agent.hpp
    PUBLIC_DEPS
        aos::tool
    PRIVATE_DEPS
        aos::exec aos::llm aos::loop
)

add_library(aos_agent_cli OBJECT
    src/run.cpp
    src/run_top.cpp
    src/inbox_cli.cpp
    src/chat_cli.cpp
)
target_link_libraries(aos_agent_cli PUBLIC aos::agent aos::loop)
target_link_libraries(aos_agent_cli PRIVATE nlohmann_json::nlohmann_json)

aos_add_subcommand(
    NAME agent
    ENTRY aos_agent_cli_main
    LIBRARY aos_agent_cli
    SUMMARY "create and advance a turn-based folder agent"
)

aos_add_subcommand(
    NAME say
    ENTRY aos_say_cli_main
    LIBRARY aos_agent_cli
    SUMMARY "say something to this folder's agent"
)

aos_add_subcommand(
    NAME listen
    ENTRY aos_listen_cli_main
    LIBRARY aos_agent_cli
    SUMMARY "follow this folder agent's conversation log"
)

aos_add_subcommand(
    NAME inbox
    ENTRY aos_inbox_cli_main
    LIBRARY aos_agent_cli
    SUMMARY "list and read messages the agent has not handled"
)

aos_add_subcommand(
    NAME talk
    ENTRY aos_talk_cli_main
    LIBRARY aos_agent_cli
    SUMMARY "chat line by line with this folder's agent"
)

aos_add_subcommand(
    NAME state
    ENTRY aos_state_cli_main
    LIBRARY aos_agent_cli
    SUMMARY "print this folder agent's status.json"
)

aos_add_subcommand(
    NAME chat
    ENTRY aos_chat_cli_main
    LIBRARY aos_agent_cli
    SUMMARY "one command: create a world, say something, wait for the reply"
)
