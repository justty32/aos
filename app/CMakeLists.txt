# 唯一的執行檔。它本身沒有任何業務邏輯：只把 argv[1] 對到某個小專案登記的進入點。

get_property(aos_subcommand_names GLOBAL PROPERTY AOS_SUBCOMMAND_NAMES)
get_property(aos_subcommand_libraries GLOBAL PROPERTY AOS_SUBCOMMAND_LIBRARIES)

if(NOT aos_subcommand_names)
    message(FATAL_ERROR
        "AOS_BUILD_APP 開著，但沒有任何小專案呼叫 aos_add_subcommand()。"
    )
endif()

# 把登記表攤成一份 X-macro 標頭。main.cpp 用兩次不同的 AOS_SUBCOMMAND 定義去
# include 它：一次產生 extern 宣告，一次產生表格內容。
set(aos_subcommands_content "")
foreach(subcommand_name IN LISTS aos_subcommand_names)
    string(REPLACE "-" "_" key "${subcommand_name}")
    get_property(subcommand_entry GLOBAL PROPERTY AOS_SUBCOMMAND_ENTRY_${key})
    get_property(subcommand_summary GLOBAL PROPERTY AOS_SUBCOMMAND_SUMMARY_${key})

    # 摘要是自由文字，會原樣落進一個 C 字串常值裡，所以反斜線、雙引號、換行
    # 都得先跳脫，否則產生出來的標頭編不過。名稱與進入點在登記時已經檢查過
    # 字集，不需要處理。
    string(REPLACE "\\" "\\\\" subcommand_summary "${subcommand_summary}")
    string(REPLACE "\"" "\\\"" subcommand_summary "${subcommand_summary}")
    string(REPLACE "\n" "\\n" subcommand_summary "${subcommand_summary}")

    string(APPEND aos_subcommands_content
        "AOS_SUBCOMMAND(\"${subcommand_name}\", ${subcommand_entry}, \"${subcommand_summary}\")\n"
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
