# impl_cpp 的建置總表：骨架取自 archive/aos-v1（toolchain 找法、common、小專案模式），C++23 照原樣、改成靜態庫、ninja preset。
#
# 平常用 preset（CMakePresets.json）：
#   cmake --preset debug && cmake --build --preset debug && ctest --preset debug
# 不用 preset 也行：cmake -B build && cmake --build build（沒指定 build type 時是 Release，跟 proto8 一樣）。
# 自成一體：不 include proto8 或 archive 的任何檔。
cmake_minimum_required(VERSION 3.25)

# vcpkg 的 toolchain 必須在 project() 之前決定。優先順序：呼叫者自己給的
# CMAKE_TOOLCHAIN_FILE > 環境變數 VCPKG_ROOT > ~/dev/vcpkg。最後那條只是讓
# 本機不用設環境變數也能直接 configure，找不到就靜靜跳過（之後 find_package 會報錯）。
# manifest 就是同一層的 vcpkg.json；configure 時 vcpkg 把相依裝進 <build>/vcpkg_installed/。
if(NOT DEFINED CMAKE_TOOLCHAIN_FILE)
    if(DEFINED ENV{VCPKG_ROOT})
        set(aos_vcpkg_root "$ENV{VCPKG_ROOT}")
    elseif(EXISTS "$ENV{HOME}/dev/vcpkg/scripts/buildsystems/vcpkg.cmake")
        set(aos_vcpkg_root "$ENV{HOME}/dev/vcpkg")
    endif()
    if(DEFINED aos_vcpkg_root)
        set(CMAKE_TOOLCHAIN_FILE "${aos_vcpkg_root}/scripts/buildsystems/vcpkg.cmake"
            CACHE FILEPATH "vcpkg toolchain")
    endif()
endif()

project(aos
    VERSION 0.1.0
    DESCRIPTION "aos core rewrite (impl_cpp)"
    LANGUAGES CXX
)

if(WIN32)
    message(FATAL_ERROR "aos supports POSIX platforms only")
endif()

# 沒指定 build type 就 Release（照 proto8）。preset 都會明寫，這段只管手打 cmake -B 的情況。
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release)
endif()

# C++23、不開 GNU 擴充（-std=c++23，不是 gnu++23），照 aos-v1（proto8 是 20）。
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# 給 clangd 看的 compile_commands.json（.clangd 指到 build/debug/）。
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# 產物集中放：執行檔在 <build>/bin，函式庫在 <build>/lib。
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)

# 想把 warning 當錯誤：configure 時加 -DAOS_WERROR=ON（warning 清單在 common/CMakeLists.txt）。
option(AOS_WERROR "treat warnings as errors" OFF)

list(APPEND CMAKE_MODULE_PATH ${CMAKE_CURRENT_SOURCE_DIR}/cmake)
include(AosSubproject)

enable_testing()

# 外部相依（vcpkg.json 裡列的）。要加新套件：vcpkg.json 加一項 → 這裡 find_package →
# 多數小專案都用的話加進 common/CMakeLists.txt 的 aos_common_private，否則寫在該小專案的 PRIVATE_DEPS。
find_package(nlohmann_json CONFIG REQUIRED)

# common 要最先，其餘小專案都相依它。
add_subdirectory(common)

# 小專案清單在 core/CMakeLists.txt；要新增一個是去改那份，不是改這裡。
add_subdirectory(core)
