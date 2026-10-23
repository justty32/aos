cmake_minimum_required(VERSION 3.21)

# aos-loop：`aos-loop loop.json`——每圈跑一次 run，看結束碼決定下一步。兩個產物：lib/libaos-loop.a、bin/aos-loop。
# CMake 的共通設定（vcpkg、Release、compile_commands、PIC、AOS_STATIC_PIE）在 ../cmake/settings.cmake。
# 照 aos-exec 的 CMakeLists.txt 改名。
include(../cmake/settings.cmake)
# 也開 C：經 aos-exec 連進來的 inst 是 C 專案
project(aos-loop C CXX)

# 用到的兄弟專案（包一層 if(NOT TARGET)，全家都這樣寫）。
#   aos-exec   公開 API（aos/exec.hpp）：字串 run 走它的 resolve_ws／find_entry／prepare_env／apply_env／launch，單子用 run_inst。
#              它又帶進 inst、aos-util、aos-directive
if(NOT TARGET aos-exec)
  add_subdirectory(../aos-exec aos-exec-build)
endif()

# src/ 底下除了 src/main.cpp 全是函式庫的程式碼。
file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS src/*.cpp)
list(REMOVE_ITEM SOURCES ${CMAKE_CURRENT_SOURCE_DIR}/src/main.cpp)

# 函式庫 target＝專案名，STATIC。公開標頭 aos/loop.hpp 用到 aos/exec.hpp，所以 aos-exec 是 PUBLIC。
add_library(aos-loop STATIC ${SOURCES})
target_include_directories(aos-loop PUBLIC include PRIVATE src)
target_compile_features(aos-loop PUBLIC cxx_std_20)
target_compile_options(aos-loop PRIVATE -Wall -Wextra)
target_link_libraries(aos-loop PUBLIC aos-exec)
set_target_properties(aos-loop PROPERTIES
  ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/lib)

# 執行檔與測試只在這個專案自己是主角時。
if(PROJECT_IS_TOP_LEVEL)
  add_executable(aos-loop_main src/main.cpp)
  target_link_libraries(aos-loop_main PRIVATE aos-loop)
  target_include_directories(aos-loop_main PRIVATE src)
  target_link_options(aos-loop_main PRIVATE ${AOS_STATIC_PIE})
  set_target_properties(aos-loop_main PROPERTIES
    OUTPUT_NAME aos-loop
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/bin)

  enable_testing()
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  add_test(NAME test_cli
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_cli.py $<TARGET_FILE:aos-loop_main>)
endif()
