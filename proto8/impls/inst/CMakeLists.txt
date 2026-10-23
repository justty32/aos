cmake_minimum_required(VERSION 3.21)
project(inst C)

# 產物照慣例放在 lib/。這個專案沒有 src/main.c，所以只有函式庫、沒有執行檔：
#   lib/libinst.so  target inst         給 FFI（Python ctypes 等）載入
#   lib/libinst.a   target inst-static  給 aos-exec（和舊的 aos-inst）靜態連進去（啟動時少載入一個 .so）
# 編法照 dcap 的 C 模板，加了 libaos 自己需要的幾條（嚴格 C11、-Werror、預設 hidden、兩種函式庫、測試）。

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE Release)
endif()

# 給 clangd 看的 build/compile_commands.json（clangd 會自己去 build/ 底下找）
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# src/ 底下除了 src/main.c 全是函式庫的程式碼（這裡沒有 main.c）。
# CONFIGURE_DEPENDS：每次 build 都重看一次，新加的檔不用手動重新 configure。
file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS src/*.c)
list(REMOVE_ITEM SOURCES ${CMAKE_CURRENT_SOURCE_DIR}/src/main.c)

# 原始碼只編一次（OBJECT library：一堆 .o），再包成兩種函式庫。
# 嚴格 C11（-std=c11，不是 gnu11）；-fPIC（.so 要）；預設 hidden：只有 aos.h 標了 AOS_API 的四個函數
# 從 .so 匯出（nm -D lib/libinst.so 看得到）。靜態連結不看 hidden，連 .a 的程式照樣呼叫得到。
add_library(inst-objects OBJECT ${SOURCES})
target_include_directories(inst-objects PUBLIC include)
target_compile_features(inst-objects PUBLIC c_std_11)
target_compile_options(inst-objects PRIVATE
  $<$<COMPILE_LANG_AND_ID:C,GNU,Clang,AppleClang>:-Wall;-Wextra;-Werror>)
set_target_properties(inst-objects PROPERTIES
  C_STANDARD 11
  C_STANDARD_REQUIRED ON
  C_EXTENSIONS OFF
  C_VISIBILITY_PRESET hidden
  POSITION_INDEPENDENT_CODE ON)

# 函式庫 target 用專案名，兩個專案組在一起時才不會撞名——見檔尾。
# 為什麼不照 dcap 只出 SHARED：aos-exec（和舊的 aos-inst）連靜態版，啟動時少載入一個 .so；.so 留給 FFI。
add_library(inst SHARED $<TARGET_OBJECTS:inst-objects>)
add_library(inst-static STATIC $<TARGET_OBJECTS:inst-objects>)
foreach(t inst inst-static)
  target_include_directories(${t} PUBLIC include)
  set_target_properties(${t} PROPERTIES
    OUTPUT_NAME inst
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/lib
    ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/lib
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/bin)
endforeach()

# 測試只在這個專案自己是主角時加（被別的專案 add_subdirectory 進去時不編）。
#   ctest --test-dir build
if(PROJECT_IS_TOP_LEVEL)
  enable_testing()

  # C 測試：連 lib/libinst.so，走 pidfd＋poll 那條路
  add_executable(test_lib tests/test_lib.c)
  target_link_libraries(test_lib PRIVATE inst)
  add_test(NAME test_lib COMMAND test_lib)

  # 同一支測試再編一份：lib 的原始碼直接編進來、加 -DAOS_INST_NO_PIDFD，強制走「1 毫秒輪詢」那條退路
  add_executable(test_lib_nopidfd tests/test_lib.c ${SOURCES})
  target_include_directories(test_lib_nopidfd PRIVATE include)
  target_compile_definitions(test_lib_nopidfd PRIVATE AOS_INST_NO_PIDFD)
  add_test(NAME test_lib_nopidfd COMMAND test_lib_nopidfd)

  # Python ctypes 測試：載 lib/libinst.so
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  add_test(NAME test_ffi
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_ffi.py $<TARGET_FILE:inst>)

  # 兩支 C 測試跟函式庫一樣的旗標
  foreach(t test_lib test_lib_nopidfd)
    set_target_properties(${t} PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED ON C_EXTENSIONS OFF)
    target_compile_options(${t} PRIVATE -Wall -Wextra -Werror)
  endforeach()
endif()

# 別的專案要用它：add_subdirectory(../inst inst-build) 再連 inst（.so）或 inst-static（.a），
# 包在 if(NOT TARGET inst) 裡（寫法見 impls/README.md「建置」）。這個專案是純 C、不用 vcpkg，所以不 include ../cmake/settings.cmake。
