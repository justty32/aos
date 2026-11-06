cmake_minimum_required(VERSION 3.21)
# 共通設定（Release、compile_commands、PIC…）跟全家一樣在 ../cmake/settings.cmake；純 C、沒有 vcpkg.json，toolchain 不裝任何東西。
include(../cmake/settings.cmake)
project(aos-inst C)

# 產物照慣例放在 lib/。這個專案沒有 src/main.c，所以只有函式庫、沒有執行檔：
#   lib/libaos-inst.so  target aos-inst         給 FFI（Python ctypes 等）載入
#   lib/libaos-inst.a   target aos-inst-static  給 aos-exec 靜態連進去（啟動時少載入一個 .so）
# 編法照 dcap 的 C 模板，加了 aos-inst 自己需要的幾條（嚴格 C11、-Werror、預設 hidden、兩種函式庫）。

# src/ 底下除了 src/main.c 全是函式庫的程式碼（這裡沒有 main.c）。
# CONFIGURE_DEPENDS：每次 build 都重看一次，新加的檔不用手動重新 configure。
file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS src/*.c)
list(REMOVE_ITEM SOURCES ${CMAKE_CURRENT_SOURCE_DIR}/src/main.c)

# 原始碼只編一次（OBJECT library：一堆 .o），再包成兩種函式庫。
# 嚴格 C11（-std=c11，不是 gnu11）；-fPIC（.so 要）；預設 hidden：只有 aos/inst.h 標了 AOS_API 的四個函數
# 從 .so 匯出（nm -D lib/libaos-inst.so 看得到）。靜態連結不看 hidden，連 .a 的程式照樣呼叫得到。
add_library(aos-inst-objects OBJECT ${SOURCES})
target_include_directories(aos-inst-objects PUBLIC include)
target_compile_features(aos-inst-objects PUBLIC c_std_11)
target_compile_options(aos-inst-objects PRIVATE
  $<$<COMPILE_LANG_AND_ID:C,GNU,Clang,AppleClang>:-Wall;-Wextra;-Werror>)
set_target_properties(aos-inst-objects PROPERTIES
  C_STANDARD 11
  C_STANDARD_REQUIRED ON
  C_EXTENSIONS OFF
  C_VISIBILITY_PRESET hidden
  POSITION_INDEPENDENT_CODE ON)

# 函式庫 target 用專案名，兩個專案組在一起時才不會撞名——見檔尾。
# 為什麼不照 dcap 只出 SHARED：aos-exec 連靜態版，啟動時少載入一個 .so；.so 留給 FFI。
add_library(aos-inst SHARED $<TARGET_OBJECTS:aos-inst-objects>)
add_library(aos-inst-static STATIC $<TARGET_OBJECTS:aos-inst-objects>)
foreach(t aos-inst aos-inst-static)
  target_include_directories(${t} PUBLIC include)
  set_target_properties(${t} PROPERTIES
    OUTPUT_NAME aos-inst
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/lib
    ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/lib
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/bin)
endforeach()

# 別的專案要用它：add_subdirectory(../aos-inst aos-inst-build) 再連 aos-inst（.so）或 aos-inst-static（.a），
# 包在 if(NOT TARGET aos-inst) 裡（寫法見 impls/README.md「建置」）。這個專案是純 C、不用 vcpkg（11-05 起照樣 include ../cmake/settings.cmake，只為共通設定）。
