# 02 nlohmann json：現在怎麼拿到、怎麼脫離 vcpkg

← [入口](../外部依賴.md)｜上一份 [01-實況總表](01-實況總表.md)｜下一份 [03-cmake-或-makefile](03-cmake-或-makefile.md)

**結論**：把官方 release 的單一標頭 `json.hpp`（v3.12.0，953 KB）和 `LICENSE.MIT` 收進 repo，`aos-util` 的 CMakeLists 改兩行，就不需要 vcpkg 也不需要 `find_package`。11-17 實測全家 11 個專案編過、0 個警告、執行檔照樣是 static-pie、`aos-json --help` 跑得動。

## 現在怎麼拿到

| 項目 | 實況 |
|---|---|
| 取得方式 | **vcpkg manifest 模式**：`impls/vcpkg.json`（頂層一次建）與 10 份專案自己的 `vcpkg.json`（單獨建用）都只列 `nlohmann-json` 一個依賴；`aos-inst` 是純 C，沒有 `vcpkg.json` |
| vcpkg 在哪 | `impls/cmake/settings.cmake`：呼叫者給的 `CMAKE_TOOLCHAIN_FILE` > 環境變數 `VCPKG_ROOT` > `~/dev/vcpkg`，三個都沒有就不設 toolchain（然後下一步找不到套件而失敗） |
| 怎麼接進來 | 只有 `aos-util/CMakeLists.txt` 寫 `find_package(nlohmann_json CONFIG REQUIRED)`，再 `target_link_libraries(aos-util PUBLIC nlohmann_json::nlohmann_json)`；其他專案經 `aos-util` 的 PUBLIC 連結間接拿到 |
| 程式怎麼用 | 一律 `#include <nlohmann/json.hpp>`，沒有用 `json_fwd.hpp` |
| 版本 | **3.12.0**（`builtin-baseline b781af66…`；`aos-util/build/vcpkg-manifest-install.log` 寫 `nlohmann-json:x64-linux@3.12.0#2`）。vcpkg 裝的是多標頭版（`include/nlohmann/` 一整夾） |
| 誰用 | 全部 C++ 專案（`aos-inst` 除外） |
| 系統套件 | 公司 WSL 沒有 `/usr/include/nlohmann`（沒裝 `nlohmann-json3-dev`） |
| repo 裡有沒有一份 | 沒有（只有各 `build/vcpkg_installed/` 的副本，不進 git） |

C++ 沒有別的外部函式庫：其他 include 全是標準庫與 Linux 系統標頭（11-17 掃 `src/`、`include/` 的全部 `#include <…>`）。

## 四種脫離 vcpkg 的做法

| 選項 | repo 多大 | 更新怎麼做 | 離線能裝？ | 授權 | 其他後果 |
|---|---|---|---|---|---|
| **A 單檔收進 repo（推薦）**：`json.hpp`＋`LICENSE.MIT` | +0.95 MB（一個檔；gzip -9 後 139 KB，git 存的大小差不多這個量級） | 去官方 release 換掉一個檔、改版本註記，一個 commit | **能**（clone 下來就全有） | MIT：散佈時要附著作權聲明與授權全文，放 `LICENSE.MIT` 就滿足 | 編譯時每個 .cpp 都吃一個 95 萬字元的標頭，跟現在多標頭版差不多；版本釘死在 repo 裡，沒有「哪台機器裝了哪版」的問題 |
| B git submodule（指向 nlohmann/json） | repo 本身幾乎不變；clone 時要多抓整個上游 repo（數百 MB 歷史，可 `--depth 1`，**沒量**） | `cd` 進 submodule 切 tag、commit 指標 | clone 時要網路；之後能 | 上游自帶 | 使用者要記得 `git clone --recursive` 或 `git submodule update --init`，忘了就編不過；更新流程「`git pull` 再重跑安裝」要多一步 submodule 更新 |
| C 安裝腳本下載 | 不變 | 改腳本裡的版本號與 sha256 | **不能**（第一次一定要網路） | 下載來的檔要一起保留授權 | 要寫下載與驗 sha256 的程式；GitHub 擋、公司防火牆都會讓安裝失敗 |
| D 用系統套件（`nlohmann-json3-dev`、`nlohmann-json`） | 不變 | 跟著發行版 | 能（套件已裝的話） | 發行版處理 | 版本不受控（印象中 Ubuntu 24.04 是 3.11.3，**沒查**證，其他發行版也沒查）；要 sudo 裝；不同機器版本不同，3.11 與 3.12 行為差異**沒細看** |

另一種組合：A 為主、D 當覆寫（安裝腳本看到使用者給了 `--json-include=…` 就用他的）。多寫幾行，**沒推薦**，等真有人要再加。

## 放哪

照 `cpp-py-改名` 的主案，`include/` 是安裝產物、不進 git，所以**不能放 `include/`**。建議放原始碼那邊：`cpp/third_party/nlohmann/json.hpp`、`cpp/third_party/nlohmann/LICENSE.MIT`，再放一個一行的 `VERSION`（`3.12.0 sha256 aaf127c0…`）。程式裡的 `#include <nlohmann/json.hpp>` 一個字都不用改，只要 include 路徑指到 `cpp/third_party`。

## 實測（11-17，公司 WSL，`~/.aos/scratch/deps-1117/`）

| 步驟 | 結果 |
|---|---|
| 下載 | 只從官方 release：`github.com/nlohmann/json/releases/download/v3.12.0/json.hpp`（953,436 bytes，sha256 `aaf127c04cb31c406e5b04a63f1ae89369fccde6d8fa7cdda1ed4f32dfc5de63`）與同版 `json.tar.xz`（114 KB，裡面有 `json/LICENSE.MIT`，開頭「MIT License / Copyright (c) 2013-2025 Niels Lohmann」）；放在 `dl-nlohmann/`，沒有執行任何下載來的東西 |
| 改法 | 只改複本裡 `aos-util/CMakeLists.txt` 兩行：拿掉 `find_package`；`target_link_libraries(… nlohmann_json::nlohmann_json)` 換成 `target_include_directories(aos-util SYSTEM PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/../../third_party)` |
| 設定 | `unset VCPKG_ROOT`、`cmake -S . -B build -DCMAKE_TOOLCHAIN_FILE=`（空值讓 `settings.cmake` 不去找 `~/dev/vcpkg`）：configure 7.3 秒，成功 |
| 編譯 | `cmake --build build -j8`：159.8 秒，退 0，**0 個 warning**；11 個專案的 `bin/`、`lib/` 全部產出（含 `libaos-inst.so`） |
| 跑 | `aos-json --help` 正常；`file` 顯示 `static-pie linked` |

沒測：用 vcpkg 編的原版要多久（怕寫進 `~/dev/vcpkg` 的快取，沒跑）；家機 Manjaro；把單檔版換成多標頭版的差異。
