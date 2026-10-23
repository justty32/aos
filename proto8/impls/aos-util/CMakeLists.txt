cmake_minimum_required(VERSION 3.21)

# aos-util：aos 這一家命令列工具共用的函式庫。只有一個產物 lib/libaos-util.a（沒有 src/main.cpp，所以沒有執行檔）。
# CMake 的共通設定（vcpkg、Release、compile_commands、PIC）在 ../cmake/settings.cmake，project() 之前先 include。
include(../cmake/settings.cmake)
project(aos-util CXX)

find_package(nlohmann_json CONFIG REQUIRED)

# src/ 底下除了 src/main.cpp 全是函式庫的程式碼（照 dcap 慣例；這裡沒有 main.cpp）。
# CONFIGURE_DEPENDS：每次 build 都重看一次，新加的檔不用手動重新 configure。
file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS src/*.cpp)
list(REMOVE_ITEM SOURCES ${CMAKE_CURRENT_SOURCE_DIR}/src/main.cpp)

# 函式庫 target＝專案名。STATIC（不照 dcap 的 SHARED）：執行檔把它靜態連進去，啟動時少載入 .so。
# 公開標頭（include/aos/*.hpp）用到 nlohmann，所以 nlohmann 是 PUBLIC。
add_library(aos-util STATIC ${SOURCES})
target_include_directories(aos-util PUBLIC include)
target_compile_features(aos-util PUBLIC cxx_std_20)
target_compile_options(aos-util PRIVATE -Wall -Wextra)
target_link_libraries(aos-util PUBLIC nlohmann_json::nlohmann_json)
set_target_properties(aos-util PROPERTIES
  ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/lib)

# 測試只在這個專案自己是主角時加（被別的專案 add_subdirectory 進去時不編）：ctest --test-dir build
if(PROJECT_IS_TOP_LEVEL)
  enable_testing()
  add_executable(util_cli tests/util_cli.cpp)   # 測試用的小程式（讀一份、原樣印），留在 build/，不進 bin/
  target_link_libraries(util_cli PRIVATE aos-util)
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  add_test(NAME test_cli
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_cli.py $<TARGET_FILE:util_cli>)

  # 函式庫：一個執行檔，第一個參數挑要跑哪一條（tests/test_lib.cpp）
  add_executable(test_lib tests/test_lib.cpp)
  target_link_libraries(test_lib PRIVATE aos-util)
  foreach(name split split_bad shebang escape missing cli text)
    add_test(NAME test_lib_${name} COMMAND test_lib ${name})
  endforeach()
endif()
