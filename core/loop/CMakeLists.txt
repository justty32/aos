aos_add_subproject(loop
    SOURCES
        src/fs.cpp
        src/layout.cpp
        src/deliver.cpp
        src/aggregate.cpp
        src/state.cpp
        src/turn.cpp
    HEADERS include/aos/loop.hpp
    PUBLIC_DEPS aos::exec aos::wire
)

add_library(aos_loop_cli OBJECT
    src/run.cpp
    src/deliver_cli.cpp
)
target_link_libraries(aos_loop_cli PUBLIC aos::loop)

aos_add_subcommand(
    NAME run
    ENTRY aos_run_cli_main
    LIBRARY aos_loop_cli
    SUMMARY "推進一個資料夾 N 回合"
)

aos_add_subcommand(
    NAME deliver
    ENTRY aos_deliver_cli_main
    LIBRARY aos_loop_cli
    SUMMARY "把一條指令原子投遞進 inbox"
)

aos_add_test(aos_loop_tests
    SOURCES
        tests/test_deliver.cpp
        tests/test_turn.cpp
        tests/test_idle.cpp
        tests/test_parallel.cpp
        tests/test_running_state.cpp
        tests/test_agents.cpp
        tests/test_every.cpp
        tests/test_folder.cpp
        tests/test_run_cli.cpp
    LINK aos_loop_cli
)
