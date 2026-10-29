cmake_minimum_required(VERSION 3.21)

# aos-lock：鎖（N-15）——mkdir <目標>/.lock/ 或 <目標>.lock/、名牌 holder.json、判死活、收屍。兩個產物：lib/libaos-lock.a、bin/aos-lock。
# CMake 的共通設定（vcpkg、Release、compile_commands、PIC、AOS_STATIC_PIE）在 ../cmake/settings.cmake。
# 照 aos-directive 的 CMakeLists.txt 改名。
include(../cmake/settings.cmake)
project(aos-lock CXX)

# 用到的兄弟專案（包一層 if(NOT TARGET)，全家都這樣寫）。
#   aos-util  錯誤、三扇門、旗標、路徑、/proc（started_at_ticks、boot_id）、utc_now_ms
if(NOT TARGET aos-util)
  add_subdirectory(../aos-util aos-util-build)
endif()

# src/ 底下除了 src/main.cpp 全是函式庫的程式碼。
file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS src/*.cpp)
list(REMOVE_ITEM SOURCES ${CMAKE_CURRENT_SOURCE_DIR}/src/main.cpp)

# 函式庫 target＝專案名，STATIC。公開標頭 aos/lock.hpp（aos-post 的有順序投遞連它）用到 aos-util 的標頭，所以 aos-util 是 PUBLIC。
add_library(aos-lock STATIC ${SOURCES})
target_include_directories(aos-lock PUBLIC include PRIVATE src)
target_compile_features(aos-lock PUBLIC cxx_std_20)
target_compile_options(aos-lock PRIVATE -Wall -Wextra)
target_link_libraries(aos-lock PUBLIC aos-util)
set_target_properties(aos-lock PROPERTIES
  ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/lib)

# 執行檔與測試只在這個專案自己是主角時。
if(PROJECT_IS_TOP_LEVEL)
  add_executable(aos-lock_main src/main.cpp)
  target_link_libraries(aos-lock_main PRIVATE aos-lock)
  target_include_directories(aos-lock_main PRIVATE src)
  target_link_options(aos-lock_main PRIVATE ${AOS_STATIC_PIE})
  set_target_properties(aos-lock_main PROPERTIES
    OUTPUT_NAME aos-lock
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/bin)

  enable_testing()
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  add_test(NAME test_cli
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_cli.py $<TARGET_FILE:aos-lock_main>)
endif()
