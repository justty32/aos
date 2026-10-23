# settings.cmake：aos 這一家 C++ 專案共用的 CMake 設定。
#
# 每個 C++ 專案的 CMakeLists.txt 開頭、project() 之前：
#   include(../cmake/settings.cmake)
# 這裡只有 set()，沒有函數、沒有巨集——就是把每個專案都要寫的同一段收在一處。
# 被別的專案 add_subdirectory 進去時，這些變數人家已經設好了（同一個 build），再 set 一次也無妨。
#
# 1. vcpkg 的 toolchain（nlohmann-json 走 vcpkg，manifest＝各專案自己的 vcpkg.json）。
#    一定要在 project() 之前決定：呼叫者自己給的 CMAKE_TOOLCHAIN_FILE > 環境變數 VCPKG_ROOT > ~/dev/vcpkg。
if(NOT DEFINED CMAKE_TOOLCHAIN_FILE)
  if(DEFINED ENV{VCPKG_ROOT})
    set(CMAKE_TOOLCHAIN_FILE "$ENV{VCPKG_ROOT}/scripts/buildsystems/vcpkg.cmake")
  elseif(EXISTS "$ENV{HOME}/dev/vcpkg/scripts/buildsystems/vcpkg.cmake")
    set(CMAKE_TOOLCHAIN_FILE "$ENV{HOME}/dev/vcpkg/scripts/buildsystems/vcpkg.cmake")
  endif()
endif()

# 2. 沒指定就 Release。
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE Release)
endif()

# 3. 給 clangd 看的 build/compile_commands.json（clangd 會自己去 build/ 底下找）。
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# 4. 執行檔用 -static-pie 全靜態連結（為什麼：見 impls/README.md「建置」），
#    連進去的每顆靜態函式庫都得編成 PIC，所以整個 build 一開始就打開。
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# 5. 執行檔的連結旗標：-static-pie（靜態，但保留 ASLR）。
#    例外：用 -fsanitize（ASan 等）建的時候不能全靜態，那時照一般動態連結。
#    各專案寫 target_link_options(xxx_main PRIVATE ${AOS_STATIC_PIE})。
#    看 -DCMAKE_CXX_FLAGS=... 或環境變數 CXXFLAGS（sanitizer 建置是其中一種給法）。
if(CMAKE_CXX_FLAGS MATCHES "-fsanitize" OR "$ENV{CXXFLAGS}" MATCHES "-fsanitize")
  set(AOS_STATIC_PIE "")
else()
  set(AOS_STATIC_PIE "-static-pie")
endif()
