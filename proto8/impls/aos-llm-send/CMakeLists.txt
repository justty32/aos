cmake_minimum_required(VERSION 3.21)

# aos-llm-send：`aos-llm-send 單子.json`——把一張單子寄進 kernel 的信箱（$AOS_KERNEL），等回信，結果原樣交回。
# 兩個產物：lib/libaos-llm-send.a、bin/aos-llm-send。
# CMake 的共通設定（vcpkg、Release、compile_commands、PIC、AOS_STATIC_PIE）在 ../cmake/settings.cmake。
# 照 aos-fsm 的 CMakeLists.txt 改名。
include(../cmake/settings.cmake)
# 也開 C：經 aos-exec 連進來的 inst 是 C 專案
project(aos-llm-send C CXX)

# 用到的兄弟專案（包一層 if(NOT TARGET)，全家都這樣寫）。
#   aos-llm-kernel  公開 API（aos/llm_kernel.hpp）：信箱與信的格式（信號、priority、回信）；
#                   它又帶進 aos-loop（擋訊號）、aos-exec、inst、aos-util、aos-directive（解指示詞）
if(NOT TARGET aos-llm-kernel)
  add_subdirectory(../aos-llm-kernel aos-llm-kernel-build)
endif()
#   aos-post        公開 API（aos/post.hpp）：回信信箱（<信箱>/reply/）的建、認領、收掉（10-30 回信改走 reply_to）
if(NOT TARGET aos-post)
  add_subdirectory(../aos-post aos-post-build)
endif()

# src/ 底下除了 src/main.cpp 全是函式庫的程式碼。
file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS src/*.cpp)
list(REMOVE_ITEM SOURCES ${CMAKE_CURRENT_SOURCE_DIR}/src/main.cpp)

# 函式庫 target＝專案名，STATIC。沒有公開標頭（沒有別的專案要用閘門的庫）。
add_library(aos-llm-send STATIC ${SOURCES})
target_include_directories(aos-llm-send PRIVATE src)
target_compile_features(aos-llm-send PUBLIC cxx_std_20)
target_compile_options(aos-llm-send PRIVATE -Wall -Wextra)
target_link_libraries(aos-llm-send PUBLIC aos-llm-kernel aos-post)
set_target_properties(aos-llm-send PROPERTIES
  ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/lib)

# 執行檔與測試只在這個專案自己是主角時。
if(PROJECT_IS_TOP_LEVEL)
  add_executable(aos-llm-send_main src/main.cpp)
  target_link_libraries(aos-llm-send_main PRIVATE aos-llm-send)
  target_include_directories(aos-llm-send_main PRIVATE src)
  target_link_options(aos-llm-send_main PRIVATE ${AOS_STATIC_PIE})
  set_target_properties(aos-llm-send_main PROPERTIES
    OUTPUT_NAME aos-llm-send
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/bin)

  enable_testing()
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  add_test(NAME test_cli
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_cli.py $<TARGET_FILE:aos-llm-send_main>)
endif()
