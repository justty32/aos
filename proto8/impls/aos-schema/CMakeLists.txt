cmake_minimum_required(VERSION 3.21)

# aos-schema：用 JSON Schema（draft-07）驗 JSON 的函式庫＋命令列。兩個產物：lib/libaos-schema.a、bin/aos-schema。
# CMake 的共通設定（vcpkg、Release、compile_commands、PIC、AOS_STATIC_PIE）在 ../cmake/settings.cmake。
# 比全家多一個 vcpkg 依賴：json-schema-validator（vcpkg.json）。
include(../cmake/settings.cmake)
project(aos-schema CXX)

find_package(nlohmann_json CONFIG REQUIRED)
find_package(nlohmann_json_schema_validator CONFIG REQUIRED)

# 用到的兄弟專案。同一個 build 裡別的專案可能已經 add 過，所以包一層 if(NOT TARGET)。
if(NOT TARGET aos-util)
  add_subdirectory(../aos-util aos-util-build)
endif()

# src/ 底下除了 src/main.cpp 全是函式庫的程式碼。
file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS src/*.cpp)
list(REMOVE_ITEM SOURCES ${CMAKE_CURRENT_SOURCE_DIR}/src/main.cpp)

# 函式庫 target＝專案名，STATIC。
# 公開標頭露 nlohmann::json 與 aos::Error，所以 nlohmann、aos-util 是 PUBLIC；pboettch 的驗證器是 PRIVATE（只有 src/validate.cpp 用）。
add_library(aos-schema STATIC ${SOURCES})
target_include_directories(aos-schema PUBLIC include)
target_compile_features(aos-schema PUBLIC cxx_std_20)
target_compile_options(aos-schema PRIVATE -Wall -Wextra)
target_link_libraries(aos-schema
  PUBLIC nlohmann_json::nlohmann_json aos-util
  PRIVATE nlohmann_json_schema_validator::validator)
set_target_properties(aos-schema PROPERTIES
  ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/lib)

# 執行檔與測試只在這個專案自己是主角時：被別的專案 add_subdirectory 進去時，人家要的是函式庫。
if(PROJECT_IS_TOP_LEVEL)
  add_executable(aos-schema_main src/main.cpp)
  target_link_libraries(aos-schema_main PRIVATE aos-schema)
  target_link_options(aos-schema_main PRIVATE ${AOS_STATIC_PIE})
  set_target_properties(aos-schema_main PROPERTIES
    OUTPUT_NAME aos-schema
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/bin)

  enable_testing()
  find_package(Python3 REQUIRED COMPONENTS Interpreter)

  # 函式庫：一個執行檔，第一個參數挑要跑哪一條（tests/test_lib.cpp）
  add_executable(test_lib tests/test_lib.cpp)
  target_link_libraries(test_lib PRIVATE aos-schema)
  foreach(name valid missing_required wrong_type out_of_range local_ref schema_bad file_missing file_bad_json)
    add_test(NAME test_lib_${name}
      COMMAND test_lib ${name} ${CMAKE_CURRENT_SOURCE_DIR}/examples/inst.schema.json ${CMAKE_CURRENT_SOURCE_DIR}/tests/data)
  endforeach()

  # 命令列：餵 stdin、看輸出（tests/test_cli.py）
  add_test(NAME test_cli
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_cli.py $<TARGET_FILE:aos-schema_main>)
endif()
