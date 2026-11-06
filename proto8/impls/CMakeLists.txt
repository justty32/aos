cmake_minimum_required(VERSION 3.21)

# proto8/impls 頂層：一次 configure、一次 build 出全家的 bin（11-05 大重構 S3）。
#   cd proto8/impls && cmake -B build && cmake --build build
# 產物照舊寫回各專案自己的 <專案>/bin、<專案>/lib（install.sh 照舊掃 impls/*/bin/*）。
# 各專案仍可單獨 cmake（cd aos-exec && cmake -B build && cmake --build build）；兩種建法擇一，不要同時跑（寫同一個 bin/、lib/ 會互蓋）。
# 共通設定在 cmake/settings.cmake；vcpkg manifest 只看這一層的 vcpkg.json（全家相依合併）。
include(cmake/settings.cmake)
project(aos-impls C CXX)

# 各專案的執行檔條件是 if(PROJECT_IS_TOP_LEVEL OR AOS_IMPLS_ALL)：從這裡建時每個專案都不是 top level，靠它打開。
option(AOS_IMPLS_ALL "build every project's bin from the impls top level" ON)

# 照依賴序 add（各專案裡的 if(NOT TARGET) 守衛看到已經有了就不再 add）。
foreach(p
    inst aos-util aos-directive aos-exec aos-json aos-loop
    aos-lock aos-post aos-fsm aos-daemon aos-llm-kernel aos-llm)
  if(NOT TARGET ${p})
    add_subdirectory(${p})
  endif()
endforeach()
