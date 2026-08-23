cmake_minimum_required(VERSION 3.25)

# vcpkg 的 toolchain 必須在 project() 之前決定。優先順序：呼叫者自己給的
# CMAKE_TOOLCHAIN_FILE > 環境變數 VCPKG_ROOT > ~/dev/vcpkg。最後那條只是讓
# 本機不用設環境變數也能直接 configure，找不到就靜靜跳過。
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
    DESCRIPTION "POSIX 小工具的集合：每個小專案既是執行檔的一條子命令，也是一個可以被 include 的 C++23 函式庫"
    LANGUAGES C CXX
)

if(WIN32)
    message(FATAL_ERROR "aos supports POSIX platforms only")
endif()

list(APPEND CMAKE_MODULE_PATH ${CMAKE_CURRENT_SOURCE_DIR}/cmake)
include(AosSubproject)
include(GNUInstallDirs)
include(CMakePackageConfigHelpers)

option(AOS_BUILD_APP        "建置 aos 執行檔" ON)
option(AOS_BUILD_TESTS      "建置測試" ${PROJECT_IS_TOP_LEVEL})
option(AOS_BUILD_MERGED_LIB "額外產出一個把所有小專案合在一起的 libaos.so" OFF)
option(AOS_INSTALL          "產生 install 與 find_package 規則" ${PROJECT_IS_TOP_LEVEL})

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# -fvisibility=hidden 只管一般函式；inline 與樣板實體化是弱符號，要
# -fvisibility-inlines-hidden 才蓋得住。少了它，nlohmann 的樣板實體會出現在
# 共享庫的動態符號表上，這個 .so 就變成「只給用同一版 nlohmann 的人用」。
set(CMAKE_C_VISIBILITY_PRESET hidden)
set(CMAKE_CXX_VISIBILITY_PRESET hidden)
set(CMAKE_VISIBILITY_INLINES_HIDDEN ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)

# 讓裝好的 aos 執行檔找得到同一次安裝的 libaos_*.so，不必靠 LD_LIBRARY_PATH。
set(CMAKE_BUILD_RPATH_USE_ORIGIN ON)
set(CMAKE_INSTALL_RPATH "$ORIGIN/../${CMAKE_INSTALL_LIBDIR}")

find_package(nlohmann_json CONFIG REQUIRED)
if(AOS_BUILD_TESTS)
    find_package(Catch2 3 CONFIG REQUIRED)
    enable_testing()
endif()

# common 要最先，其餘小專案都相依它。
add_subdirectory(common)

# ── 小專案 ─────────────────────────────────────────────────────────────
# 新增一個小專案：複製 inst/ 的結構，然後在這裡加一行。
add_subdirectory(inst)
# ───────────────────────────────────────────────────────────────────────

# app 必須排在所有小專案之後：它要讀取大家登記好的子命令表。
if(AOS_BUILD_APP)
    add_subdirectory(app)
endif()

get_property(aos_subprojects GLOBAL PROPERTY AOS_SUBPROJECTS)

# 傘狀 target：aos::aos 一次連上全部小專案。想挑著用就直接連 aos::inst。
add_library(aos_umbrella INTERFACE)
add_library(aos::aos ALIAS aos_umbrella)
set_target_properties(aos_umbrella PROPERTIES EXPORT_NAME aos)
foreach(subproject IN LISTS aos_subprojects)
    target_link_libraries(aos_umbrella INTERFACE aos::${subproject})
endforeach()

# 合併版：想單檔部署的人用，預設不建。內容與各 aos_<name>.so 相同，只是併成一個。
if(AOS_BUILD_MERGED_LIB)
    set(aos_merged_objects "")
    foreach(subproject IN LISTS aos_subprojects)
        list(APPEND aos_merged_objects $<TARGET_OBJECTS:aos_${subproject}_objects>)
    endforeach()

    get_property(aos_public_deps GLOBAL PROPERTY AOS_PUBLIC_DEPS)
    get_property(aos_private_deps GLOBAL PROPERTY AOS_PRIVATE_DEPS)
    get_property(aos_include_dirs GLOBAL PROPERTY AOS_INCLUDE_DIRS)
    foreach(list_var aos_public_deps aos_private_deps aos_include_dirs)
        if(${list_var})
            list(REMOVE_DUPLICATES ${list_var})
        endif()
    endforeach()

    add_library(aos_merged SHARED ${aos_merged_objects})
    add_library(aos::merged ALIAS aos_merged)
    target_link_libraries(aos_merged
        PUBLIC aos::common ${aos_public_deps}
        PRIVATE ${aos_private_deps}
    )
    # 與各小專案的共享庫同樣的理由：私有相依不要外流到匯出介面。
    set_property(TARGET aos_merged PROPERTY
        INTERFACE_LINK_LIBRARIES aos::common ${aos_public_deps}
    )
    foreach(include_dir IN LISTS aos_include_dirs)
        target_include_directories(aos_merged PUBLIC
            $<BUILD_INTERFACE:${include_dir}>
        )
    endforeach()
    target_include_directories(aos_merged PUBLIC
        $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>
    )
    set_target_properties(aos_merged PROPERTIES
        OUTPUT_NAME aos
        EXPORT_NAME merged
        VERSION ${PROJECT_VERSION}
        SOVERSION ${PROJECT_VERSION_MAJOR}
    )
endif()

if(AOS_INSTALL)
    set(aos_install_targets aos_umbrella)
    if(AOS_BUILD_MERGED_LIB)
        list(APPEND aos_install_targets aos_merged)
    endif()
    install(TARGETS ${aos_install_targets}
        EXPORT aos-targets
        LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
        ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
        RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
    )

    install(EXPORT aos-targets
        FILE aos-targets.cmake
        NAMESPACE aos::
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/aos
    )

    # 只有公開相依需要讓使用者的 find_package(aos) 一併找出來；私有相依已經在
    # aos_add_subproject() 裡從匯出介面剝掉了。
    get_property(aos_public_packages GLOBAL PROPERTY AOS_PUBLIC_PACKAGES)
    if(aos_public_packages)
        list(REMOVE_DUPLICATES aos_public_packages)
    endif()
    set(AOS_FIND_DEPENDENCIES "")
    foreach(package IN LISTS aos_public_packages)
        string(APPEND AOS_FIND_DEPENDENCIES "find_dependency(${package} CONFIG)\n")
    endforeach()

    configure_package_config_file(
        ${CMAKE_CURRENT_SOURCE_DIR}/cmake/aos-config.cmake.in
        ${CMAKE_CURRENT_BINARY_DIR}/aos-config.cmake
        INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/aos
    )
    write_basic_package_version_file(
        ${CMAKE_CURRENT_BINARY_DIR}/aos-config-version.cmake
        COMPATIBILITY SameMajorVersion
    )
    install(FILES
        ${CMAKE_CURRENT_BINARY_DIR}/aos-config.cmake
        ${CMAKE_CURRENT_BINARY_DIR}/aos-config-version.cmake
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/aos
    )
endif()
