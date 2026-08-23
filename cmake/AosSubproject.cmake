# 這個檔案定義「一個小專案長什麼樣」。新增小專案時照 inst/CMakeLists.txt 抄一份，
# 再去根目錄的 CMakeLists.txt 加一行 add_subdirectory() 就好，其餘不用碰。

include_guard(GLOBAL)

# aos_add_subproject(<name>
#     SOURCES      <實作檔…>
#     HEADERS      <公開標頭…>            # 會被安裝，路徑相對於本目錄
#     PUBLIC_DEPS      <公開標頭裡用到的相依…>
#     PRIVATE_DEPS     <這個小專案專屬、只有實作檔用到的相依…>
#     PUBLIC_PACKAGES  <PUBLIC_DEPS 是哪些 find_package 提供的…>
# )
#
# PUBLIC_DEPS 會出現在使用者的編譯行上，所以使用者的 find_package(aos) 也得先
# 把那些套件找出來——把對應的套件名列進 PUBLIC_PACKAGES，根目錄會據此在
# aos-config.cmake 產生 find_dependency()。PRIVATE_DEPS 則刻意不外流，理由見
# 下面「把私有相依從匯出介面剝掉」那段。
#
# 通用的私有相依（nlohmann_json 之類，多數小專案都會用到）不必寫在這裡：它們
# 集中宣告在 common/CMakeLists.txt 的 aos_common_private，本函式一律自動連上。
# PRIVATE_DEPS 只放這個小專案獨有的。
#
# 產出兩個 target：
#   aos_<name>_objects  OBJECT，給合併版 libaos.so 撿去用
#   aos_<name>          SHARED，別名 aos::<name>，安裝並匯出給外部 find_package
#
# 公開標頭一律放在 <name>/include/aos/ 底下，所以外部與內部都寫成
# #include <aos/<name>.hpp>，兩邊看到的路徑一致。
function(aos_add_subproject name)
    cmake_parse_arguments(PARSE_ARGV 1 ARG
        ""
        ""
        "SOURCES;HEADERS;PUBLIC_DEPS;PRIVATE_DEPS;PUBLIC_PACKAGES"
    )
    if(ARG_UNPARSED_ARGUMENTS)
        message(FATAL_ERROR "aos_add_subproject(${name}): 不認得的參數 ${ARG_UNPARSED_ARGUMENTS}")
    endif()
    if(NOT ARG_SOURCES)
        message(FATAL_ERROR "aos_add_subproject(${name}): 需要 SOURCES")
    endif()

    set(objects aos_${name}_objects)
    set(library aos_${name})
    set(include_dir ${CMAKE_CURRENT_SOURCE_DIR}/include)

    # OBJECT library 只負責編譯。共享版與合併版都是撿它的 .o，不會編兩次。
    add_library(${objects} OBJECT ${ARG_SOURCES})
    target_include_directories(${objects} PUBLIC ${include_dir})
    target_link_libraries(${objects}
        PUBLIC aos::common ${ARG_PUBLIC_DEPS}
        PRIVATE aos_common_private ${ARG_PRIVATE_DEPS}
    )

    # 用 $<TARGET_OBJECTS:> 當來源而不是 link，這樣 aos_<name> 沒有指向
    # aos_<name>_objects 的相依邊，install(EXPORT) 才不會要求把 OBJECT
    # library 也塞進匯出集合。
    add_library(${library} SHARED $<TARGET_OBJECTS:${objects}>)
    add_library(aos::${name} ALIAS ${library})
    target_link_libraries(${library}
        PUBLIC aos::common ${ARG_PUBLIC_DEPS}
        PRIVATE aos_common_private ${ARG_PRIVATE_DEPS}
    )
    # 把私有相依從匯出介面剝掉。
    #
    # target_link_libraries(... PRIVATE x) 會在 INTERFACE_LINK_LIBRARIES 留下
    # $<LINK_ONLY:x>，匯出後使用者的 find_package(aos) 就得先找得到 x，否則
    # configure 直接失敗——即使 x 是 header-only、即使符號全被 hidden 蓋掉、
    # 即使使用者根本用不到它。對共享庫來說這層要求是多餘的：實際的連結需求
    # 已經記在 .so 的 DT_NEEDED 裡了。所以這裡直接把介面重設成只剩公開的部分；
    # LINK_LIBRARIES（真正連結 .so 時用的那份）不受影響。
    set_property(TARGET ${library} PROPERTY
        INTERFACE_LINK_LIBRARIES aos::common ${ARG_PUBLIC_DEPS}
    )

    set_target_properties(${library} PROPERTIES
        OUTPUT_NAME aos_${name}
        # 沒有這行，匯出後外部看到的會是 aos::aos_inst 而不是 aos::inst。
        EXPORT_NAME ${name}
        VERSION ${PROJECT_VERSION}
        SOVERSION ${PROJECT_VERSION_MAJOR}
    )
    if(ARG_HEADERS)
        target_sources(${library} PUBLIC
            FILE_SET HEADERS
            BASE_DIRS ${include_dir}
            FILES ${ARG_HEADERS}
        )
    endif()

    # 合併版與傘狀 target 在根目錄組裝，這裡只留下線索。
    set_property(GLOBAL APPEND PROPERTY AOS_SUBPROJECTS ${name})
    set_property(GLOBAL APPEND PROPERTY AOS_INCLUDE_DIRS ${include_dir})
    set_property(GLOBAL APPEND PROPERTY AOS_PUBLIC_DEPS ${ARG_PUBLIC_DEPS})
    set_property(GLOBAL APPEND PROPERTY AOS_PUBLIC_PACKAGES ${ARG_PUBLIC_PACKAGES})
    set_property(GLOBAL APPEND PROPERTY AOS_PRIVATE_DEPS ${ARG_PRIVATE_DEPS})

    if(AOS_INSTALL)
        install(TARGETS ${library}
            EXPORT aos-targets
            FILE_SET HEADERS
            LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
            ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
            RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
        )
    endif()
endfunction()

# aos_add_subcommand(
#     NAME    <子命令名稱>       # 使用者打的字：aos <name> …
#     ENTRY   <C 進入點符號>     # extern "C" int <entry>(int, char **)
#     LIBRARY <target>           # 提供該符號、要被 aos 執行檔連進去的 target
#     SUMMARY "<一行說明>"       # 印在 aos --help 裡
# )
#
# 只是把資訊登記到全域屬性；app/ 會在所有小專案都加完之後，把整張表產生成
# 一個 X-macro 標頭。所以新增子命令不需要動 app/ 底下的任何檔案。
#
# NAME 與 ENTRY 都會被檢查字集與唯一性——這兩件事沒做的話，錯誤要嘛在編譯期
# 以難懂的形式爆開，要嘛根本不會爆（見下面重名那段）。
function(aos_add_subcommand)
    cmake_parse_arguments(PARSE_ARGV 0 ARG "" "NAME;ENTRY;LIBRARY;SUMMARY" "")
    foreach(required NAME ENTRY LIBRARY)
        if(NOT ARG_${required})
            message(FATAL_ERROR "aos_add_subcommand(): 需要 ${required}")
        endif()
    endforeach()

    # 名稱會出現在使用者的命令列與產生出來的表格裡。限制成保守字集，順便擋掉
    # `-h` 這種會跟旗標混淆的名字。
    if(NOT ARG_NAME MATCHES "^[a-z][a-z0-9-]*$")
        message(FATAL_ERROR
            "aos_add_subcommand(): NAME 必須符合 ^[a-z][a-z0-9-]*$，收到 '${ARG_NAME}'")
    endif()
    if(NOT ARG_ENTRY MATCHES "^[A-Za-z_][A-Za-z0-9_]*$")
        message(FATAL_ERROR
            "aos_add_subcommand(): ENTRY 必須是合法的 C 識別字，收到 '${ARG_ENTRY}'")
    endif()

    # 重名一定要在這裡擋下來。兩個小專案登記同一個 NAME 的話，configure 過、
    # 編譯過、`aos --help` 還會把兩筆都列出來，但分派是線性掃描取第一個相符，
    # 所以後註冊的那個實作永遠叫不到——而且完全沒有任何訊息。
    string(REPLACE "-" "_" key "${ARG_NAME}")
    get_property(registered_names GLOBAL PROPERTY AOS_SUBCOMMAND_NAMES)
    if(ARG_NAME IN_LIST registered_names)
        get_property(owner GLOBAL PROPERTY AOS_SUBCOMMAND_OWNER_${key})
        message(FATAL_ERROR
            "aos_add_subcommand(): 子命令 '${ARG_NAME}' 已經由 ${owner} 登記過了")
    endif()

    # 同一個 ENTRY 被兩個小專案定義的話，錯誤會延到連結期才以 multiple
    # definition 的形式出現，訊息跟「子命令」八竿子打不著。這裡先擋。
    get_property(registered_entries GLOBAL PROPERTY AOS_SUBCOMMAND_ENTRIES)
    if(ARG_ENTRY IN_LIST registered_entries)
        message(FATAL_ERROR
            "aos_add_subcommand(): 進入點 '${ARG_ENTRY}' 已經被別的子命令用掉了")
    endif()

    # SUMMARY 是自由文字，可能含分號——放進 CMake list 會被當成分隔符把記錄
    # 拆散。所以名稱走 list，其餘欄位一項一個屬性，屬性值不吃 list 語意。
    set_property(GLOBAL APPEND PROPERTY AOS_SUBCOMMAND_NAMES ${ARG_NAME})
    set_property(GLOBAL APPEND PROPERTY AOS_SUBCOMMAND_ENTRIES ${ARG_ENTRY})
    set_property(GLOBAL PROPERTY AOS_SUBCOMMAND_ENTRY_${key} "${ARG_ENTRY}")
    set_property(GLOBAL PROPERTY AOS_SUBCOMMAND_SUMMARY_${key} "${ARG_SUMMARY}")
    set_property(GLOBAL PROPERTY AOS_SUBCOMMAND_OWNER_${key} "${CMAKE_CURRENT_SOURCE_DIR}")
    set_property(GLOBAL APPEND PROPERTY AOS_SUBCOMMAND_LIBRARIES ${ARG_LIBRARY})
endfunction()

# aos_add_test(<name> SOURCES <…> LINK <…> LANGUAGE <C|CXX>)
#
# LANGUAGE CXX（預設）會連上 Catch2::Catch2WithMain；LANGUAGE C 的測試自帶 main。
function(aos_add_test name)
    cmake_parse_arguments(PARSE_ARGV 1 ARG "" "LANGUAGE" "SOURCES;LINK")
    if(NOT AOS_BUILD_TESTS)
        return()
    endif()
    if(NOT ARG_LANGUAGE)
        set(ARG_LANGUAGE CXX)
    endif()

    add_executable(${name} ${ARG_SOURCES})
    target_link_libraries(${name} PRIVATE ${ARG_LINK})
    if(ARG_LANGUAGE STREQUAL "C")
        set_target_properties(${name} PROPERTIES
            C_STANDARD 99
            C_STANDARD_REQUIRED ON
            C_EXTENSIONS OFF
        )
    else()
        target_link_libraries(${name} PRIVATE Catch2::Catch2WithMain)
    endif()
    add_test(NAME ${name} COMMAND ${name})
endfunction()
