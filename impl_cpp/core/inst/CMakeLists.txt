# inst：跑一批指令的執行器（搬自 archive/aos-v1 的 core/exec＋core/wire 的 Inst 解析，行為不改）；只有函式庫 aos::inst，沒有執行檔。
#
# 兩塊：src/exec/（fork/exec 一批、統一等完、逾時、中斷；標頭 aos/exec.hpp）、
#       src/wire/（Inst 單子 JSON；標頭 aos/wire.hpp）。跟現行 proto8 aos-inst 差在哪見 差異.md。

aos_add_subproject(inst
    SOURCES
        src/exec/clock.cpp
        src/exec/tempfile.cpp
        src/exec/spawn_prep.cpp
        src/exec/interrupt.cpp
        src/exec/wait.cpp
        src/exec/start.cpp
        src/exec/wait_all.cpp
        src/wire/inst.cpp
    HEADERS
        include/aos/exec.hpp
        include/aos/wire.hpp
)

# aos-v1 原本的測試（Catch2；11-04 從 aos-v1 刪掉、這裡從 git 歷史搬回來）。全部編成一支、ctest 一個名字。
add_executable(aos_inst_tests
    tests/exec_run_one.cpp
    tests/exec_parallel.cpp
    tests/exec_timeout.cpp
    tests/exec_env_cwd.cpp
    tests/exec_interrupt.cpp
    tests/exec_ended_at.cpp
    tests/wire_inst.cpp
    tests/wire_errors.cpp
)
target_link_libraries(aos_inst_tests PRIVATE aos::inst aos_common_private Catch2::Catch2WithMain)
add_test(NAME inst.catch2 COMMAND aos_inst_tests)
# 測試用指定初始化子（{.argv = …}）只寫要的欄位，其餘照預設值——這是刻意的，GCC 的 -Wextra 會為此報 missing-field-initializers，這裡關掉。
target_compile_options(aos_inst_tests PRIVATE -Wno-missing-field-initializers)
