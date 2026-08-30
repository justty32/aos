aos_add_subproject(tool
    SOURCES src/spec.cpp src/registry.cpp src/probe.cpp src/contacts.cpp
    HEADERS include/aos/tool.hpp
    PRIVATE_DEPS aos::exec aos::loop
)

add_library(aos_tool_cli OBJECT
    src/tool_cli.cpp
    src/contact_cli.cpp
    src/contact_status.cpp
)
target_link_libraries(aos_tool_cli PUBLIC aos::tool)
target_link_libraries(aos_tool_cli PRIVATE nlohmann_json::nlohmann_json)

aos_add_subcommand(NAME tool    ENTRY aos_tool_cli_main    LIBRARY aos_tool_cli SUMMARY "登記／列出／移除這個世界可用的工具")
aos_add_subcommand(NAME contact ENTRY aos_contact_cli_main LIBRARY aos_tool_cli SUMMARY "登記／列出／移除 agent 通訊錄")

aos_add_test(aos_tool_tests
    SOURCES tests/test_tool_spec.cpp tests/test_tool_registry.cpp tests/test_tool_probe.cpp tests/test_tool_contacts.cpp tests/test_tool_cli.cpp
    LINK aos_tool_cli
)
