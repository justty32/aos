cmake_minimum_required(VERSION 3.21)

# aos-fsm：`aos-fsm fsm.json`——一次只跑一格。兩個產物：lib/libaos-fsm.a、bin/aos-fsm。
# CMake 的共通設定（vcpkg、Release、compile_commands、PIC、AOS_STATIC_PIE）在 ../cmake/settings.cmake。
# 照 aos-loop 的 CMakeLists.txt 改名。
include(../cmake/settings.cmake)
# 也開 C：經 aos-exec 連進來的 inst 是 C 專案
project(aos-fsm C CXX)

# 用到的兄弟專案（包一層 if(NOT TARGET)，全家都這樣寫）。
#   aos-loop   公開 API（aos/loop.hpp）：跑一格＝run_once（格的 val 跟 loop.json 的 run 同一套寫法）、擋訊號。
#              它又帶進 aos-exec、inst、aos-util、aos-directive
if(NOT TARGET aos-loop)
  add_subdirectory(../aos-loop aos-loop-build)
endif()

# src/ 底下除了 src/main.cpp 全是函式庫的程式碼。
file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS src/*.cpp)
list(REMOVE_ITEM SOURCES ${CMAKE_CURRENT_SOURCE_DIR}/src/main.cpp)

# 函式庫 target＝專案名，STATIC。沒有公開標頭（沒有別的專案要用 fsm 的庫；之後真有人要再開 include/）。
add_library(aos-fsm STATIC ${SOURCES})
target_include_directories(aos-fsm PRIVATE src)
target_compile_features(aos-fsm PUBLIC cxx_std_20)
target_compile_options(aos-fsm PRIVATE -Wall -Wextra)
target_link_libraries(aos-fsm PUBLIC aos-loop)
set_target_properties(aos-fsm PROPERTIES
  ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/lib)

# 執行檔與測試只在這個專案自己是主角時。
if(PROJECT_IS_TOP_LEVEL)
  add_executable(aos-fsm_main src/main.cpp)
  target_link_libraries(aos-fsm_main PRIVATE aos-fsm)
  target_include_directories(aos-fsm_main PRIVATE src)
  target_link_options(aos-fsm_main PRIVATE ${AOS_STATIC_PIE})
  set_target_properties(aos-fsm_main PROPERTIES
    OUTPUT_NAME aos-fsm
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/bin)

  enable_testing()
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  add_test(NAME test_cli
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_cli.py $<TARGET_FILE:aos-fsm_main>)
  # 整合：demo 的 agent-bob、agent-ann 在 impls 線（aos-exec／aos-loop／aos-fsm 三支的 bin/）跑，跟 proto8/bin 線比。
  # 要先建好 ../aos-exec、../aos-loop 自己的 bin/（這個 build 只編它們的庫）
  add_test(NAME test_demo
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_demo.py)
endif()
