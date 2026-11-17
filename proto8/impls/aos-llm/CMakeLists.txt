cmake_minimum_required(VERSION 3.21)

# aos-llm：`aos-llm send|recv|ask|regret|ls`——寄請求信進 LLM kernel 的信箱（$AOS_LLM_KERNEL）、收回信的基礎工具（11-04 由 aos-llm-send 改名）。
# 兩個產物：lib/libaos-llm.a、bin/aos-llm；公開標頭 aos/llm.hpp 宣告 LLM 信件協定。
# CMake 的共通設定（vcpkg、Release、compile_commands、PIC、AOS_STATIC_PIE）在 ../cmake/settings.cmake。
# 照 aos-fsm 的 CMakeLists.txt 改名。
include(../cmake/settings.cmake)
project(aos-llm CXX)

# 用到的兄弟專案（包一層 if(NOT TARGET)，全家都這樣寫）。
#   aos-util        共用型別、檔案與訊號。
if(NOT TARGET aos-util)
  add_subdirectory(../aos-util aos-util-build)
endif()
#   aos-post        公開 API（aos/post.hpp）：寄信（send／send_prepared）、認領（take）、回信信箱的建、收掉、撤信（regret）
if(NOT TARGET aos-post)
  add_subdirectory(../aos-post aos-post-build)
endif()

# src/ 底下除了 src/main.cpp 全是函式庫的程式碼。
file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS src/*.cpp)
list(REMOVE_ITEM SOURCES ${CMAKE_CURRENT_SOURCE_DIR}/src/main.cpp)

# 函式庫 target＝專案名，STATIC；公開標頭與 letter.cpp 只依賴 aos-util、aos-post。
add_library(aos-llm STATIC ${SOURCES})
target_include_directories(aos-llm PUBLIC include PRIVATE src)
target_compile_features(aos-llm PUBLIC cxx_std_20)
target_compile_options(aos-llm PRIVATE -Wall -Wextra)
target_link_libraries(aos-llm PUBLIC aos-util aos-post)
set_target_properties(aos-llm PROPERTIES
  ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/lib)

# 執行檔只在這個專案自己是主角、或從 impls 頂層一次建（AOS_IMPLS_ALL）時。
if(PROJECT_IS_TOP_LEVEL OR AOS_IMPLS_ALL)
  add_executable(aos-llm_main src/main.cpp)
  target_link_libraries(aos-llm_main PRIVATE aos-llm)
  target_include_directories(aos-llm_main PRIVATE src)
  target_link_options(aos-llm_main PRIVATE ${AOS_STATIC_PIE})
  set_target_properties(aos-llm_main PROPERTIES
    OUTPUT_NAME aos-llm
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/bin)
endif()
