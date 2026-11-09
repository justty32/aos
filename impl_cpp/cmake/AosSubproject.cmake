# AosSubproject：定義「一個小專案長什麼樣」的 aos_add_subproject()——一個零件一夾，函式庫、執行檔、測試一次登記。
#
# 新增小專案：照 core/hello/CMakeLists.txt 抄一份，再去 core/CMakeLists.txt 加一行
# add_subdirectory() 就好，其餘不用碰。（骨架取自 archive/aos-v1 的同名檔，拿掉了
# 共享庫、合併版、安裝匯出、子命令表；見 README「骨架取自 aos-v1，差在哪」。）

include_guard(GLOBAL)

# aos_add_subproject(<name>
#     SOURCES      <實作檔…>          # 有就產出靜態庫 aos_<name>（別名 aos::<name>）
#     HEADERS      <公開標頭…>        # 放 include/aos/ 底下，大家都寫 #include <aos/<name>.hpp>
#     PUBLIC_DEPS  <公開標頭裡用到的相依…>
#     PRIVATE_DEPS <只有實作檔用到、這個小專案專屬的相依…>
#     PROGRAM      <main.cpp>         # 有就產出執行檔 <build>/bin/aos-<name>
#     TESTS        <測試檔…>          # 每個檔一支測試執行檔，ctest 跑它，退 0＝過
# )
#
# 通用的私有相依（nlohmann_json、warning 全開）集中在 common/CMakeLists.txt 的
# aos_common_private，本函式一律自動 PRIVATE 連上，小專案不必重寫。
#
# target 名：
#   aos_<name>          STATIC 函式庫（別名 aos::<name>），別的小專案 PUBLIC_DEPS／PRIVATE_DEPS 寫 aos::<name>
#   aos_<name>_main     執行檔，檔名 aos-<name>
#   aos_<name>_<測試檔名>  測試執行檔，ctest 裡的名字是 <name>.<測試檔名>
function(aos_add_subproject name)
    cmake_parse_arguments(PARSE_ARGV 1 ARG
        ""
        "PROGRAM"
        "SOURCES;HEADERS;PUBLIC_DEPS;PRIVATE_DEPS;TESTS"
    )
    if(ARG_UNPARSED_ARGUMENTS)
        message(FATAL_ERROR "aos_add_subproject(${name}): unknown arguments ${ARG_UNPARSED_ARGUMENTS}")
    endif()
    if(NOT ARG_SOURCES AND NOT ARG_PROGRAM)
        message(FATAL_ERROR "aos_add_subproject(${name}): needs SOURCES or PROGRAM")
    endif()
    # common 被 aos::common 佔用了，讓它撞在這裡而不是撞在 ALIAS 重複定義上。
    if(name STREQUAL "common")
        message(FATAL_ERROR "aos_add_subproject(${name}): '${name}' is reserved")
    endif()

    set(library aos_${name})
    set(include_dir ${CMAKE_CURRENT_SOURCE_DIR}/include)

    # 執行檔與測試要連的東西：有函式庫就連函式庫（它會把 PUBLIC 的東西帶過來）。
    set(users_link aos::common aos_common_private ${ARG_PUBLIC_DEPS} ${ARG_PRIVATE_DEPS})

    if(ARG_SOURCES)
        add_library(${library} STATIC ${ARG_SOURCES})
        add_library(aos::${name} ALIAS ${library})
        target_include_directories(${library} PUBLIC ${include_dir}
            PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
        target_link_libraries(${library}
            PUBLIC aos::common ${ARG_PUBLIC_DEPS}
            PRIVATE aos_common_private ${ARG_PRIVATE_DEPS}
        )
        if(ARG_HEADERS)
            target_sources(${library} PUBLIC
                FILE_SET HEADERS
                BASE_DIRS ${include_dir}
                FILES ${ARG_HEADERS}
            )
        endif()
        set(users_link ${library} aos_common_private ${ARG_PRIVATE_DEPS})
    endif()

    if(ARG_PROGRAM)
        add_executable(${library}_main ${ARG_PROGRAM})
        set_target_properties(${library}_main PROPERTIES OUTPUT_NAME aos-${name})
        target_link_libraries(${library}_main PRIVATE ${users_link})
    endif()

    foreach(test_source IN LISTS ARG_TESTS)
        get_filename_component(test_stem ${test_source} NAME_WE)
        set(test_target ${library}_${test_stem})
        add_executable(${test_target} ${test_source})
        target_include_directories(${test_target} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
        target_link_libraries(${test_target} PRIVATE ${users_link})
        add_test(NAME ${name}.${test_stem} COMMAND ${test_target})
    endforeach()
endfunction()
