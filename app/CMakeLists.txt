# 唯一的執行檔。它本身沒有任何業務邏輯：只把 argv[1] 對到某個小專案登記的進入點。

get_property(aos_subcommands GLOBAL PROPERTY AOS_SUBCOMMANDS)
get_property(aos_subcommand_libraries GLOBAL PROPERTY AOS_SUBCOMMAND_LIBRARIES)

if(NOT aos_subcommands)
    message(FATAL_ERROR
        "AOS_BUILD_APP 開著，但沒有任何小專案呼叫 aos_add_subcommand()。"
    )
endif()

# 把登記表攤成一份 X-macro 標頭。main.cpp 用兩次不同的 AOS_SUBCOMMAND 定義去
# include 它：一次產生 extern 宣告，一次產生表格內容。
set(aos_subcommands_content "")
foreach(record IN LISTS aos_subcommands)
    string(REPLACE "\t" ";" fields "${record}")
    list(GET fields 0 subcommand_name)
    list(GET fields 1 subcommand_entry)
    list(LENGTH fields field_count)
    if(field_count GREATER 2)
        list(GET fields 2 subcommand_summary)
    else()
        set(subcommand_summary "")
    endif()
    string(APPEND aos_subcommands_content
        "AOS_SUBCOMMAND(${subcommand_name}, ${subcommand_entry}, \"${subcommand_summary}\")\n"
    )
endforeach()

set(aos_subcommands_header ${CMAKE_CURRENT_BINARY_DIR}/generated/aos_subcommands.inc)
file(CONFIGURE OUTPUT ${aos_subcommands_header} CONTENT "${aos_subcommands_content}" @ONLY)

add_executable(aos_app src/main.cpp)
set_target_properties(aos_app PROPERTIES OUTPUT_NAME aos)
target_include_directories(aos_app PRIVATE ${CMAKE_CURRENT_BINARY_DIR}/generated)
target_link_libraries(aos_app PRIVATE ${aos_subcommand_libraries})

if(AOS_INSTALL)
    install(TARGETS aos_app RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
endif()
