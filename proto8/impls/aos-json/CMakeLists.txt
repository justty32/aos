cmake_minimum_required(VERSION 3.21)

# aos-json：讀、改 aos 的 JSON 設定（`檔#/指標` 尋址，認得指示詞）。兩個產物：lib/libaos-json.a、bin/aos-json。
# CMake 的共通設定（vcpkg、Release、compile_commands、PIC、AOS_STATIC_PIE）在 ../cmake/settings.cmake。
# 照 aos-directive 的 CMakeLists.txt 改名。
include(../cmake/settings.cmake)
project(aos-json CXX)

# 用到的兄弟專案（全家都包一層 if(NOT TARGET)）：
#   aos-util       錯誤、三扇門、旗標（aos/cli.hpp）、路徑
#   aos-directive  --resolve 用它解指示詞（跟 aos-loop、aos-fsm、aos-exec 同一套）
if(NOT TARGET aos-util)
  add_subdirectory(../aos-util aos-util-build)
endif()
if(NOT TARGET aos-directive)
  add_subdirectory(../aos-directive aos-directive-build)
endif()

file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS src/*.cpp)
list(REMOVE_ITEM SOURCES ${CMAKE_CURRENT_SOURCE_DIR}/src/main.cpp)

# 函式庫 target＝專案名，STATIC。沒有要給別人用的公開標頭（元素的標頭從 src/ 互相 include）。
add_library(aos-json STATIC ${SOURCES})
target_include_directories(aos-json PRIVATE src)
target_compile_features(aos-json PUBLIC cxx_std_20)
target_compile_options(aos-json PRIVATE -Wall -Wextra)
target_link_libraries(aos-json PUBLIC aos-util aos-directive)
set_target_properties(aos-json PROPERTIES
  ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/lib)

if(PROJECT_IS_TOP_LEVEL)
  add_executable(aos-json_main src/main.cpp)
  target_include_directories(aos-json_main PRIVATE src)
  target_link_libraries(aos-json_main PRIVATE aos-json)
  target_link_options(aos-json_main PRIVATE ${AOS_STATIC_PIE})
  set_target_properties(aos-json_main PROPERTIES
    OUTPUT_NAME aos-json
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/bin)

  enable_testing()
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  add_test(NAME test_cli
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_cli.py $<TARGET_FILE:aos-json_main>)
  # 腦的工具（tools/json/）：要 aos-exec 已經建好（../aos-exec/bin/aos-exec）；沒建就跳過（退 0、印一行說跳過）
  add_test(NAME test_tool
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_tool.py $<TARGET_FILE:aos-json_main>)
endif()
