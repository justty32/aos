aos_add_subproject(tick
    SOURCES src/paths.cpp src/clock.cpp src/ids.cpp src/table.cpp src/due.cpp src/log.cpp src/tick.cpp src/init.cpp
    HEADERS include/aos/tick.hpp
    PUBLIC_DEPS aos::loop
    PRIVATE_DEPS aos::agent
)

add_library(aos_tick_cli OBJECT src/cli_common.cpp src/tick_cli.cpp src/heartbeat_cli.cpp src/routine_cli.cpp src/schedule_cli.cpp)
target_link_libraries(aos_tick_cli PUBLIC aos::tick)

aos_add_subcommand(NAME tick      ENTRY aos_tick_cli_main      LIBRARY aos_tick_cli SUMMARY "跑一次心跳：到期的投進 inbox 或交給 agent")
aos_add_subcommand(NAME heartbeat ENTRY aos_heartbeat_cli_main LIBRARY aos_tick_cli SUMMARY "在資料夾裝上心跳（every/tick.json）")
aos_add_subcommand(NAME routine   ENTRY aos_routine_cli_main   LIBRARY aos_tick_cli SUMMARY "登記／列出／移除固定循環的事務")
aos_add_subcommand(NAME schedule  ENTRY aos_schedule_cli_main  LIBRARY aos_tick_cli SUMMARY "登記／列出／移除一次性行程")

aos_add_test(aos_tick_tests
    SOURCES tests/test_clock.cpp tests/test_table.cpp tests/test_due.cpp tests/test_tick.cpp tests/test_cli.cpp
    LINK aos_tick_cli
)
