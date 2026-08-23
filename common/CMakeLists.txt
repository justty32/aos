# 所有小專案共用的東西。目前只有 <aos/export.h>，之後跨小專案共享的標頭也放這裡。
# 沒有實作檔，所以是 INTERFACE library，不會產出 .so。

add_library(aos_common INTERFACE)
add_library(aos::common ALIAS aos_common)

set_target_properties(aos_common PROPERTIES EXPORT_NAME common)

target_compile_features(aos_common INTERFACE cxx_std_23)

target_sources(aos_common INTERFACE
    FILE_SET HEADERS
    BASE_DIRS ${CMAKE_CURRENT_SOURCE_DIR}/include
    FILES ${CMAKE_CURRENT_SOURCE_DIR}/include/aos/export.h
)

if(AOS_INSTALL)
    install(TARGETS aos_common
        EXPORT aos-targets
        FILE_SET HEADERS
    )
endif()

# ── 通用私有相依 ────────────────────────────────────────────────────────
#
# 幾乎每個小專案的實作檔都會用到的東西放這裡，`aos_add_subproject()` 會自動
# PRIVATE 連上，小專案自己的 CMakeLists 不必重複寫一次（漏寫的話下一個小專案
# 就會編不過，而且是在它已經寫了半天之後才發現）。
#
# 這個 target **不安裝、不匯出**，而且一律以 PRIVATE 連進去：放進來的東西不會
# 變成使用者 `find_package(aos)` 的義務。會出現在**公開標頭**上的相依不能放
# 這裡——那種要走 aos_add_subproject() 的 PUBLIC_DEPS + PUBLIC_PACKAGES，讓
# aos-config.cmake 產生對應的 find_dependency()。
#
# 新增一項通用相依：在根 CMakeLists 加 find_package()，然後在這裡加一行。
add_library(aos_common_private INTERFACE)
target_link_libraries(aos_common_private INTERFACE
    nlohmann_json::nlohmann_json
)
