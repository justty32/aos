cmake_minimum_required(VERSION 3.21)

# aos-directive：解 JSON 裡的指示詞（$ref、$env）。兩個產物：lib/libaos-directive.a、bin/aos-directive。
# CMake 的共通設定（vcpkg、Release、compile_commands、PIC、AOS_STATIC_PIE）在 ../cmake/settings.cmake。
include(../cmake/settings.cmake)
project(aos-directive CXX)

# 用到的兄弟專案。同一個 build 裡別的專案可能已經 add 過，所以包一層 if(NOT TARGET)（全家都這樣寫）。
if(NOT TARGET aos-util)
  add_subdirectory(../aos-util aos-util-build)
endif()

# src/ 底下除了 src/main.cpp 全是函式庫的程式碼。
file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS src/*.cpp)
list(REMOVE_ITEM SOURCES ${CMAKE_CURRENT_SOURCE_DIR}/src/main.cpp)

# 函式庫 target＝專案名，STATIC。公開標頭 aos/directive.hpp 用到 aos-util 的標頭，所以 aos-util 是 PUBLIC。
add_library(aos-directive STATIC ${SOURCES})
target_include_directories(aos-directive PUBLIC include)
target_compile_features(aos-directive PUBLIC cxx_std_20)
target_compile_options(aos-directive PRIVATE -Wall -Wextra)
target_link_libraries(aos-directive PUBLIC aos-util)
set_target_properties(aos-directive PROPERTIES
  ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/lib)

# 執行檔只在這個專案自己是主角、或從 impls 頂層一次建（AOS_IMPLS_ALL）時：被別的專案 add_subdirectory 進去時，人家要的是函式庫。
if(PROJECT_IS_TOP_LEVEL OR AOS_IMPLS_ALL)
  add_executable(aos-directive_main src/main.cpp)
  target_link_libraries(aos-directive_main PRIVATE aos-directive)
  target_link_options(aos-directive_main PRIVATE ${AOS_STATIC_PIE})
  set_target_properties(aos-directive_main PROPERTIES
    OUTPUT_NAME aos-directive
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/bin)
endif()
