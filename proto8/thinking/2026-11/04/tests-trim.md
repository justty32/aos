# 2026-11-04 測試大刪：proto8/tests、impls 與 core 的 ctest 全刪

← [thinking README](../../README.md)｜月份表 [2026-11](../README.md)｜相關：[testing 工作流](../../../../wf/workflows/testing.md)、code map 02-tests、[AGENTS.md 鐵律](../../../../AGENTS.md)

本檔只記使用者原文（逐字）、決定、使用者裁定、執行結果（[user/03](../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。11-04 已執行完。

> 11-10 改讀（prefix-fixes 坑-55）：本頁記的是 11-04 當時的刪除決定與結果，不代表現在沒有測試。11-10 依現行檔名 `test_*.py` 盤點（排除封存、建置與隱藏副本）：repo 現役 56 支，含 proto8 48 支（`impls/` 10、`lib/` 30、`cmd/` 3、`templates/` 5）及 `wf/tools/` 8 支；另 `proto8/archive/` 有 7 支封存測試，不計入現役。

## 使用者原文（11-04，逐字）

> 話說，感覺proto8/test已經成為我們的負擔了，能夠精簡嗎？我希望能大刪特刪

> 據說有研究，說AI寫的test，百分之八十都沒啥用。

看到「激進版／溫和版」兩案的題目時：

> 激進版，不用說，甚至我希望整個刪掉也OK。

頂層再問 C++ 的 ctest：

> ctest也可以刪掉吧

頂層提醒這會動到鐵律 1：

> 這個鐵律刪掉，不用ctest

（鐵律 1 已由頂層在 AGENTS.md 刪掉、編號保留。）

## 決定

1. **`proto8/tests/` 整個刪**（含共用小程式、`spy_bin/`、`fixtures/`）。不出溫和版。
2. **C++ 的 ctest 也全刪**：repo 根 `core/*/tests`、`aos_add_test`／`enable_testing`／Catch2；`proto8/impls/*/tests` 與各 CMakeLists 的測試段；`CMakePresets.json` 的 test preset。
3. 刪完之後的驗證只剩「**build 得過**」（repo 根 `cmake --build --preset default`、proto8 照順序建 impls）。

### 使用者裁定（11-04，選項原文）

1. 要不要留一支冒煙腳本（`smoke.sh`）：「不留」——刪完後驗證只剩 build 得過。
2. `extras/langs/lua/examples/agent_ann.lua` 執行時讀 `tests/fixtures/agent-ann/`：「範例一起刪 (Recommended)」——跟 fixtures 一起刪（`clocks.lua` 不讀 fixtures，留著）。
3. `aos_add_test`：「整個刪 (Recommended)」——函式連說明一起刪、不留空殼。

## 執行結果（11-04）

- 刪掉 148 個進 git 的檔、約 24,700 行：`proto8/tests/`、13 個 `proto8/impls/*/tests/`、7 個 `core/*/tests/`、`extras/langs/lua/examples/agent_ann.lua`、`wf/workflows/testing/` 兩份分檔、code map `proto8/02-tests.md`。
- 建置設定的測試段（impls 與 core 的 CMakeLists、`cmake/AosSubproject.cmake`、根 `CMakeLists.txt`、`vcpkg.json` 的 `tests` feature、`CMakePresets.json` 的 test preset）一併拿掉；repo 根與 proto8 impls 乾淨 build 都過。
- 文件與程式註解裡指向測試、ctest、鐵律 1 的說法一律改成「build 得過」或刪掉（testing.md 重寫成「驗證＝build 得過」）；thinking、session_logs、archive 的舊紀錄不改。
