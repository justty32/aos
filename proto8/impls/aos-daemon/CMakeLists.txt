cmake_minimum_required(VERSION 3.21)

# aos-daemon：`aos-daemon daemon.json`——一個 aos-loop（同一個骨架 aos::loop::Loop）＋一張子 loop 的表（10-20 重寫）。
# 兩個產物：lib/libaos-daemon.a、bin/aos-daemon。沒有要給別人用的公開 API，所以沒有 include/。
# CMake 的共通設定（vcpkg、Release、compile_commands、PIC、AOS_STATIC_PIE）在 ../cmake/settings.cmake。
include(../cmake/settings.cmake)
# 也開 C：間接連進來的 aos-inst是 C 專案，C 語言要在最上層就開好
project(aos-daemon C CXX)

# 用到的兄弟專案：aos-post（信箱模式）、aos-loop（骨架 Loop、ctl／state 窗；它再帶進 aos-exec、aos-inst、aos-util、aos-directive）。
# daemon＝一個 loop，所以直接繼承 aos-loop 的 aos::loop::Loop，不另寫一份；子 loop 也是 fork 之後在子行程裡跑同一個 Loop。
if(NOT TARGET aos-loop)
  add_subdirectory(../aos-loop aos-loop-build)
endif()
# 信箱模式（procs_ctl_mailbox，10-29 起；11-02 晚前叫 loops_mailbox）連 aos-post 的庫（公開標頭 aos/post.hpp：take_all、see、reply、done、sort_letters；它再帶進 aos-lock）。
if(NOT TARGET aos-post)
  add_subdirectory(../aos-post aos-post-build)
endif()

# src/ 底下除了 src/main.cpp 全是函式庫的程式碼（分成 daemon、child、common，見 README）。
set(SOURCES
  src/child/child.cpp
  src/child/refs.cpp
  src/child/limits.cpp
  src/daemon/daemon.cpp
  src/daemon/procs.cpp
  src/daemon/adopt.cpp
  src/daemon/table.cpp
  src/daemon/failure.cpp
  src/daemon/stuck.cpp
  src/daemon/tend.cpp
  src/daemon/body.cpp
  src/daemon/ctl.cpp
  src/daemon/reconcile.cpp
  src/daemon/windows.cpp
  src/daemon/mailbox.cpp
)

# 函式庫 target＝專案名，STATIC。
add_library(aos-daemon STATIC ${SOURCES})
target_include_directories(aos-daemon PRIVATE src)
target_compile_features(aos-daemon PUBLIC cxx_std_20)
target_compile_options(aos-daemon PRIVATE -Wall -Wextra)
target_link_libraries(aos-daemon PUBLIC aos-loop aos-post)
set_target_properties(aos-daemon PROPERTIES
  ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/lib)

if(PROJECT_IS_TOP_LEVEL OR AOS_IMPLS_ALL)
  add_executable(aos-daemon_main src/main.cpp)
  target_link_libraries(aos-daemon_main PRIVATE aos-daemon)
  target_include_directories(aos-daemon_main PRIVATE src)
  target_link_options(aos-daemon_main PRIVATE ${AOS_STATIC_PIE})
  set_target_properties(aos-daemon_main PROPERTIES
    OUTPUT_NAME aos-daemon
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/bin)
endif()
