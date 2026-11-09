# common：所有小專案共用的東西——C++23 要求、warning 全開、通用私有相依（nlohmann_json）；沒有實作檔。
#
# aos::common 是 INTERFACE（不產出檔案），PUBLIC 連給每個小專案：目前只帶 C++23 要求。
# 之後跨小專案共享的標頭放 common/include/aos/，再把下面那行 target_include_directories 打開。
add_library(aos_common INTERFACE)
add_library(aos::common ALIAS aos_common)
target_compile_features(aos_common INTERFACE cxx_std_23)
# target_include_directories(aos_common INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/include)

# ── 通用私有相依 ────────────────────────────────────────────────────────
#
# 幾乎每個小專案的實作檔都會用到的東西放這裡，aos_add_subproject() 會自動
# PRIVATE 連上（函式庫、執行檔、測試都是），小專案自己的 CMakeLists 不必重寫。
# warning 也放這裡：PRIVATE 連，所以只管我們自己的檔；vcpkg 的標頭走 -isystem，不算我們的。
#
# 新增一項通用相依：在根 CMakeLists 加 find_package()，然後在這裡加一行。
add_library(aos_common_private INTERFACE)
target_link_libraries(aos_common_private INTERFACE
    nlohmann_json::nlohmann_json
)
target_compile_options(aos_common_private INTERFACE
    -Wall -Wextra -Wpedantic
    -Wshadow -Wconversion -Wsign-conversion
    -Wnon-virtual-dtor -Wold-style-cast -Woverloaded-virtual
    -Wnull-dereference -Wdouble-promotion -Wformat=2 -Wimplicit-fallthrough
    $<$<BOOL:${AOS_WERROR}>:-Werror>
)
