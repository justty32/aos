cmake_minimum_required(VERSION 3.21)

# aos-llm-kernel：`aos-llm-kernel kernel.json`——LLM kernel 跑一次（挑信、跑、回信）。兩個產物：lib/libaos-llm-kernel.a、bin/aos-llm-kernel。
# 公開標頭 aos/llm_kernel.hpp（信箱與信的格式）也給 aos-llm-send 用。
# CMake 的共通設定（vcpkg、Release、compile_commands、PIC、AOS_STATIC_PIE）在 ../cmake/settings.cmake。
# 照 aos-fsm 的 CMakeLists.txt 改名。
include(../cmake/settings.cmake)
# 也開 C：經 aos-exec 連進來的 inst 是 C 專案
project(aos-llm-kernel C CXX)

# 用到的兄弟專案（包一層 if(NOT TARGET)，全家都這樣寫）。
#   aos-loop   公開 API（aos/loop.hpp）：擋訊號、設定檔的指示詞（resolve_keys）；它又帶進 aos-exec（跑單子＝run_inst）、inst、aos-util、aos-directive
if(NOT TARGET aos-loop)
  add_subdirectory(../aos-loop aos-loop-build)
endif()

# src/ 底下除了 src/main.cpp 全是函式庫的程式碼。
file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS src/*.cpp)
list(REMOVE_ITEM SOURCES ${CMAKE_CURRENT_SOURCE_DIR}/src/main.cpp)

# 函式庫 target＝專案名，STATIC。公開標頭 aos/llm_kernel.hpp 用到 aos/loop.hpp，所以 aos-loop 是 PUBLIC。
add_library(aos-llm-kernel STATIC ${SOURCES})
target_include_directories(aos-llm-kernel PUBLIC include PRIVATE src)
target_compile_features(aos-llm-kernel PUBLIC cxx_std_20)
target_compile_options(aos-llm-kernel PRIVATE -Wall -Wextra)
target_link_libraries(aos-llm-kernel PUBLIC aos-loop)
set_target_properties(aos-llm-kernel PROPERTIES
  ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/lib)

# 執行檔與測試只在這個專案自己是主角時。
if(PROJECT_IS_TOP_LEVEL)
  add_executable(aos-llm-kernel_main src/main.cpp)
  target_link_libraries(aos-llm-kernel_main PRIVATE aos-llm-kernel)
  target_include_directories(aos-llm-kernel_main PRIVATE src)
  target_link_options(aos-llm-kernel_main PRIVATE ${AOS_STATIC_PIE})
  set_target_properties(aos-llm-kernel_main PROPERTIES
    OUTPUT_NAME aos-llm-kernel
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/bin)

  enable_testing()
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  add_test(NAME test_cli
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_cli.py $<TARGET_FILE:aos-llm-kernel_main>)
endif()
