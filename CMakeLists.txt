cmake_minimum_required(VERSION 3.25)
project(aos VERSION 0.1.0 LANGUAGES CXX)

if(NOT UNIX)
  message(FATAL_ERROR "aos 目前需要 Unix Domain Socket")
endif()

# 供 VS Code、clangd 等工具取得實際的編譯器參數與 include 路徑。
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Threads REQUIRED)
find_package(asio CONFIG REQUIRED)
find_package(nlohmann_json CONFIG REQUIRED)

# src/core/ 專門放共用實作，新增的 .cpp 會自動加入。
file(GLOB_RECURSE AOS_CORE_SOURCES CONFIGURE_DEPENDS
  "${CMAKE_CURRENT_SOURCE_DIR}/src/core/*.cpp")

add_library(aos_core STATIC ${AOS_CORE_SOURCES})

target_include_directories(aos_core PUBLIC include)
target_compile_features(aos_core PUBLIC cxx_std_23)
target_link_libraries(aos_core
  PUBLIC asio::asio Threads::Threads
  PRIVATE nlohmann_json::nlohmann_json)
set_target_properties(aos_core PROPERTIES CXX_EXTENSIONS OFF)
target_compile_options(aos_core PRIVATE
  $<$<COMPILE_LANG_AND_ID:CXX,GNU,Clang,AppleClang>:-Wall;-Wextra;-Wpedantic>)

add_executable(aos_cli src/cli/main.cpp)
target_link_libraries(aos_cli PRIVATE aos_core)
set_target_properties(aos_cli PROPERTIES
  OUTPUT_NAME aos
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/bin")

add_executable(aos_daemon src/daemon/main.cpp)
target_link_libraries(aos_daemon PRIVATE aos_core)
set_target_properties(aos_daemon PROPERTIES
  OUTPUT_NAME aos-daemon
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/bin")

include(CTest)
if(BUILD_TESTING)
  add_executable(aos_protocol_test tests/protocol_test.cpp)
  target_link_libraries(aos_protocol_test PRIVATE aos_core)
  add_test(NAME protocol_round_trip COMMAND aos_protocol_test)
endif()
