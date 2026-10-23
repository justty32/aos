cmake_minimum_required(VERSION 3.21)

# aos-exec：在工作區執行一個 aos 程式（找入口、備好環境變數、cd 進去、開跑）。兩個產物：lib/libaos-exec.a、bin/aos-exec。
# CMake 的共通設定（vcpkg、Release、compile_commands、PIC、AOS_STATIC_PIE）在 ../cmake/settings.cmake。
# 照 aos-directive 的 CMakeLists.txt 改名。
include(../cmake/settings.cmake)
# 也開 C：連進來的 inst 是 C 專案，C 語言要在最上層就開好（不然 CMake 不認得 c_std_11）
project(aos-exec C CXX)

# 用到的兄弟專案。同一個 build 裡別的專案可能已經 add 過，所以包一層 if(NOT TARGET)（全家都這樣寫）。
#   inst           C 的 libaos：跑 inst 單子（起程式、等、限時整群收掉；連它的靜態版 inst-static）
#   aos-util       全家共用（錯誤、路徑、JSON）
#   aos-directive  解單子裡的 $env（與 $env＋path）
if(NOT TARGET inst)
  add_subdirectory(../inst inst-build)
endif()
if(NOT TARGET aos-util)
  add_subdirectory(../aos-util aos-util-build)
endif()
if(NOT TARGET aos-directive)
  add_subdirectory(../aos-directive aos-directive-build)
endif()
find_package(Threads REQUIRED)   # run_inst 的工人執行緒

# src/ 底下除了 src/main.cpp 全是函式庫的程式碼。
file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS src/*.cpp)
list(REMOVE_ITEM SOURCES ${CMAKE_CURRENT_SOURCE_DIR}/src/main.cpp)

# 函式庫 target＝專案名，STATIC。公開標頭 aos/exec.hpp（include/）；元素的內部標頭從 src/ 互相 include（PRIVATE）。
add_library(aos-exec STATIC ${SOURCES})
target_include_directories(aos-exec PUBLIC include PRIVATE src)
target_compile_features(aos-exec PUBLIC cxx_std_20)
target_compile_options(aos-exec PRIVATE -Wall -Wextra)
target_link_libraries(aos-exec PUBLIC aos-util PRIVATE inst-static aos-directive Threads::Threads)
set_target_properties(aos-exec PROPERTIES
  ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/lib)

# 執行檔與測試只在這個專案自己是主角時。
if(PROJECT_IS_TOP_LEVEL)
  add_executable(aos-exec_main src/main.cpp)
  target_link_libraries(aos-exec_main PRIVATE aos-exec)
  target_link_options(aos-exec_main PRIVATE ${AOS_STATIC_PIE})
  set_target_properties(aos-exec_main PROPERTIES
    OUTPUT_NAME aos-exec
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/bin)

  enable_testing()
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  add_test(NAME test_cli
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_cli.py $<TARGET_FILE:aos-exec_main>)
endif()
