# inst：讀 JSON 指令檔，依序 fork/exec 執行。
#
# 這份檔案是「一個小專案長什麼樣」的範本 —— 新增小專案時整份抄過去改名字即可，
# 根目錄的 CMakeLists.txt 只需要多一行 add_subdirectory()。

aos_add_subproject(inst
    SOURCES
        src/inst.cpp
        src/format.cpp
        src/spawn_prep.cpp
        src/wait.cpp
        src/exec.cpp
        src/capi.cpp
        src/capi_instruction.cpp
        src/capi_io.cpp
    HEADERS
        include/aos/inst.hpp
        include/aos/inst.h
    PRIVATE_DEPS
        nlohmann_json::nlohmann_json
)

# CLI 層另外放：它是 aos 執行檔的一部分，不屬於函式庫的公開介面，所以不進
# aos::inst，也不被安裝。做成 OBJECT library 是為了讓執行檔與測試共用同一份
# 編譯結果。它只透過公開 API 使用 aos::inst，等於順便驗證公開介面夠不夠用。
add_library(aos_inst_cli OBJECT src/run.cpp)
target_link_libraries(aos_inst_cli PUBLIC aos::inst)

aos_add_subcommand(
    NAME inst
    ENTRY aos_inst_cli_main
    LIBRARY aos_inst_cli
    SUMMARY "依序執行一份 JSON 指令檔裡的每一筆指令"
)

aos_add_test(aos_inst_tests
    SOURCES
        tests/test_format_read.cpp
        tests/test_format_write.cpp
        tests/test_format_malformed.cpp
        tests/test_exec_streams.cpp
        tests/test_exec_path.cpp
        tests/test_exec_status.cpp
        tests/test_timeout.cpp
        tests/test_run.cpp
    LINK aos_inst_cli
)

# C ABI 的測試刻意用 C 編譯器建，這樣 <aos/inst.h> 一旦混進 C++ 才有的東西就會編不過。
aos_add_test(aos_inst_capi_tests
    LANGUAGE C
    SOURCES tests/test_capi.c
    LINK aos::inst
)
