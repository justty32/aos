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
find_package(CURL REQUIRED)  # LLM 呼叫走 HTTP

# 共用的警告設定。放成 INTERFACE target，函式庫跟兩個執行檔才會拿到同一套。
add_library(aos_warnings INTERFACE)
target_compile_options(aos_warnings INTERFACE
  # -Wmissing-field-initializers 對 designated initializer 是誤報：沒寫的欄位
  # 會拿到類別裡宣告的預設值，那正是我們要的寫法，不是漏了。
  $<$<COMPILE_LANG_AND_ID:CXX,GNU,Clang,AppleClang>:-Wall;-Wextra;-Wpedantic;-Wshadow;-Wnon-virtual-dtor;-Wno-missing-field-initializers>)

# src/core/ 專門放共用實作，新增的 .cpp（含子目錄）會自動加入。
file(GLOB_RECURSE AOS_CORE_SOURCES CONFIGURE_DEPENDS
  "${CMAKE_CURRENT_SOURCE_DIR}/src/core/*.cpp")

add_library(aos_core STATIC ${AOS_CORE_SOURCES})

target_include_directories(aos_core
  PUBLIC include
  # src/core/ 底下的內部標頭（commands.hpp、connection.hpp…）只給自己用。
  PRIVATE src/core)
target_compile_features(aos_core PUBLIC cxx_std_23)
target_link_libraries(aos_core
  PUBLIC asio::asio Threads::Threads
  PRIVATE nlohmann_json::nlohmann_json CURL::libcurl aos_warnings)
set_target_properties(aos_core PROPERTIES CXX_EXTENSIONS OFF)

add_executable(aos_cli src/cli/main.cpp)
target_link_libraries(aos_cli PRIVATE aos_core aos_warnings)
set_target_properties(aos_cli PROPERTIES
  OUTPUT_NAME aos
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/bin")

add_executable(aos_daemon src/daemon/main.cpp)
target_link_libraries(aos_daemon PRIVATE aos_core aos_warnings)
set_target_properties(aos_daemon PROPERTIES
  OUTPUT_NAME aos-daemon
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/bin")

include(CTest)
if(BUILD_TESTING)
  # 純函式層：JSON 編解碼，不碰 socket。
  add_executable(aos_protocol_test tests/protocol_test.cpp)
  target_link_libraries(aos_protocol_test PRIVATE aos_core aos_warnings)
  add_test(NAME protocol COMMAND aos_protocol_test)

  # 訊框在真 socket 上的往返，以及命令的「邊讀邊寫」行為。
  add_executable(aos_streaming_test tests/streaming_test.cpp)
  target_link_libraries(aos_streaming_test PRIVATE aos_core aos_warnings)
  add_test(NAME streaming COMMAND aos_streaming_test)

  # LLM 這一層的純函式：payload 怎麼組、SSE 與回應怎麼拆。不連任何端點。
  add_executable(aos_llm_test tests/llm_test.cpp)
  # 這個測試要自己讀 JSON 來檢查組出來的 payload，所以它也需要 nlohmann。
  target_link_libraries(aos_llm_test
    PRIVATE aos_core aos_warnings nlohmann_json::nlohmann_json)
  add_test(NAME llm COMMAND aos_llm_test)

  # tooljson 的規範層：載入期驗證與 argv 展開，同樣不連網路。
  add_executable(aos_tooljson_test tests/tooljson_test.cpp)
  target_link_libraries(aos_tooljson_test PRIVATE aos_core aos_warnings)
  add_test(NAME tooljson COMMAND aos_tooljson_test)

  # 真的把 daemon 跑起來，用 CLI 打它。這是唯一能證明串流端到端可用的測試。
  add_test(NAME end_to_end
    COMMAND "${CMAKE_CURRENT_SOURCE_DIR}/tests/e2e.sh"
            "$<TARGET_FILE:aos_daemon>" "$<TARGET_FILE:aos_cli>")
endif()
