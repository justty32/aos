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
