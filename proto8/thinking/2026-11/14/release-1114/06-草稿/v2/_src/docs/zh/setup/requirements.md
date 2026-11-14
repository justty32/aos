# 需求清單與版本

需求很少：Linux、git、Python 3.11 以上、CMake、C++20 編譯器與 nlohmann-json；已在一台 Manjaro 上實測過 vcpkg 路線。

<!-- source: 「其他發行版」原為四種容器；「幾分鐘」批 0 無含乾淨建置的計時，不寫分鐘數；08-批0實測.md #1,#3,#3b,#4,#5,#7；表格「出處」欄：作業系統 批 0 #1；Python #5；建置 #3b；全靜態連結 #3b；不跑 install.sh #2；L1 #7；03-計劃.md 第 3 節；proto8/impls/CMakeLists.txt；proto8/impls/cmake/settings.cmake -->

## 已實測

| 項目 | 結果 |
|---|---|
| 作業系統 | Manjaro（Linux）上 L0 一條龍通過：從起 llm kernel 到假腦回話 6.4 秒（建置另算） |
| Python | 3.14（系統）與 3.11（uv 裝的）都通過 L0；**3.11 以上已實測** |
| 建置（vcpkg 路線） | 乾淨複本 `cmake -B build && cmake --build build -j` 約 28 秒；當時 vcpkg 已有快取，全新 vcpkg 要另加 bootstrap 時間 |
| 全靜態連結 | `-static-pie` 在 Manjaro 連結成功 |
| 不跑 `install.sh` | 只設 `AOS_HOME`、`PATH`、`PYTHONPATH` 三個變數即可 |
| L1 接 OpenAI 相容端點 | 通過：一個本機 proxy 端點回了預期的一個字。注意：出廠 `kernel.json` 裡的模型名是作者本機 proxy 上的名字，你要自己加一包。照「開始用」的擺法，檔案在 `~/aos-demo/llms/def/kernel.json`；完整步驟會在「接真腦」頁補上 |

## 待驗

| 項目 | 現況 |
|---|---|
| 系統套件的 nlohmann-json（不用 vcpkg） | **待驗**。`settings.cmake` 的寫法是：沒給 toolchain、沒有 `VCPKG_ROOT`、沒有 `~/dev/vcpkg` 就不設 vcpkg，之後走一般 `find_package`；理論上裝了系統套件就找得到，但沒實跑 |
| 其他發行版 | **待驗**，沒有跑過 |
| 編譯器與 CMake 的最低可用版本 | **待驗**。專案要求 CMake 3.21 以上、C++20（不開 GNU 擴充）；哪一版編譯器夠用沒有量過 |
| 全新 vcpkg 的安裝時間 | 未量 |
| WSL2 | 計劃列為支援，**未實跑** |
| L2（claude CLI、tmux） | 未實跑 |
| L3（bubblewrap、s6 等） | 實驗，未實跑；`aos-asuser` 要 Python 3.12 |
| 從頭到尾要幾分鐘 | 還沒量過（含乾淨建置的整條計時） |

## 建置會怎麼找 vcpkg

依序：你自己給的 `CMAKE_TOOLCHAIN_FILE`，其次環境變數 `VCPKG_ROOT`，再其次 `~/dev/vcpkg`。都沒有就不設。

<details>
<summary>為什麼是全靜態連結</summary>

執行檔用 `-static-pie` 連結（靜態、保留 ASLR），所以所在系統要能做靜態連結。若連結失敗，見[疑難排解](../manual/troubleshooting.md)。用 `-fsanitize` 建置時會改成一般動態連結。

</details>

下一步：[Get Started](../get-started.md)。
