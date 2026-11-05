aos_add_subproject(loop
    SOURCES
        src/fs.cpp
        src/layout.cpp
        src/deliver.cpp
        src/aggregate.cpp
        src/state.cpp
        src/turn.cpp
        src/wake.cpp
    HEADERS include/aos/loop.hpp
    PUBLIC_DEPS aos::exec aos::wire
)

add_library(aos_loop_cli OBJECT
    src/run.cpp
    src/daemon.cpp
    src/deliver_cli.cpp
    src/stop_cli.cpp
)
target_link_libraries(aos_loop_cli PUBLIC aos::loop)

aos_add_subcommand(
    NAME run
    ENTRY aos_run_cli_main
    LIBRARY aos_loop_cli
    SUMMARY "advance a folder N turns"
)

aos_add_subcommand(
    NAME deliver
    ENTRY aos_deliver_cli_main
    LIBRARY aos_loop_cli
    SUMMARY "atomically deliver an instruction into inbox"
)

aos_add_subcommand(
    NAME stop
    ENTRY aos_stop_cli_main
    LIBRARY aos_loop_cli
    SUMMARY "stop this folder's background loop"
)
