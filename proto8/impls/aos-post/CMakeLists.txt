cmake_minimum_required(VERSION 3.21)

# aos-post：投遞（N-16 信箱）——寄信、認領、處理完、撤回。兩個產物：lib/libaos-post.a、bin/aos-post。
# CMake 的共通設定（vcpkg、Release、compile_commands、PIC、AOS_STATIC_PIE）在 ../cmake/settings.cmake。
# 照 aos-directive 的 CMakeLists.txt 改名。
include(../cmake/settings.cmake)
project(aos-post CXX)

# 用到的兄弟專案（包一層 if(NOT TARGET)，全家都這樣寫）。
#   aos-util  錯誤、三扇門、旗標、路徑與原子寫入、/proc（started_at_ticks）
#   aos-lock  有順序的投遞（send --ordered）拿 <信箱>/order.lock/（N-15 的鎖）；它也帶進 aos-util
if(NOT TARGET aos-util)
  add_subdirectory(../aos-util aos-util-build)
endif()
if(NOT TARGET aos-lock)
  add_subdirectory(../aos-lock aos-lock-build)
endif()

# src/ 底下除了 src/main.cpp 全是函式庫的程式碼。
file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS src/*.cpp)
list(REMOVE_ITEM SOURCES ${CMAKE_CURRENT_SOURCE_DIR}/src/main.cpp)

# 函式庫 target＝專案名，STATIC。公開標頭 aos/post.hpp（aos-daemon 的信箱模式連它）用到 aos-util 的標頭，所以 aos-util 是 PUBLIC。
add_library(aos-post STATIC ${SOURCES})
target_include_directories(aos-post PUBLIC include PRIVATE src)
target_compile_features(aos-post PUBLIC cxx_std_20)
target_compile_options(aos-post PRIVATE -Wall -Wextra)
target_link_libraries(aos-post PUBLIC aos-util PRIVATE aos-lock)
set_target_properties(aos-post PROPERTIES
  ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/lib)

# 執行檔與測試只在這個專案自己是主角時。
if(PROJECT_IS_TOP_LEVEL)
  add_executable(aos-post_main src/main.cpp)
  target_link_libraries(aos-post_main PRIVATE aos-post)
  target_include_directories(aos-post_main PRIVATE src)
  target_link_options(aos-post_main PRIVATE ${AOS_STATIC_PIE})
  set_target_properties(aos-post_main PROPERTIES
    OUTPUT_NAME aos-post
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/bin)

  enable_testing()
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  add_test(NAME test_cli
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_cli.py $<TARGET_FILE:aos-post_main>)
endif()
