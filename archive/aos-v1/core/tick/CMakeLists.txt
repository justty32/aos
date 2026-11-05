aos_add_subproject(tick
    SOURCES src/paths.cpp src/clock.cpp src/ids.cpp src/table.cpp src/due.cpp src/log.cpp src/tick.cpp src/init.cpp
    HEADERS include/aos/tick.hpp
    PUBLIC_DEPS aos::loop
    PRIVATE_DEPS aos::agent
)

add_library(aos_tick_cli OBJECT src/cli_common.cpp src/tick_cli.cpp src/heartbeat_cli.cpp src/routine_cli.cpp src/schedule_cli.cpp)
target_link_libraries(aos_tick_cli PUBLIC aos::tick)

aos_add_subcommand(NAME tick      ENTRY aos_tick_cli_main      LIBRARY aos_tick_cli SUMMARY "run one heartbeat: deliver due items to inbox or the agent")
aos_add_subcommand(NAME heartbeat ENTRY aos_heartbeat_cli_main LIBRARY aos_tick_cli SUMMARY "install a heartbeat in a folder (every/tick.json)")
aos_add_subcommand(NAME routine   ENTRY aos_routine_cli_main   LIBRARY aos_tick_cli SUMMARY "add / list / remove recurring routines")
aos_add_subcommand(NAME schedule  ENTRY aos_schedule_cli_main  LIBRARY aos_tick_cli SUMMARY "add / list / remove one-off schedules")
