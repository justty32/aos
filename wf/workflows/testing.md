# testing — 跑測試（單檔工作流）

← [WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

> 〔模板說明〕本檔是「單檔工作流」的範例：一個 `.md` 同時是入口與內容。膨脹了就照 [DEV-GUIDE](../DEV-GUIDE.md) 升級成資料夾型。

**一律從 repo 根目錄跑**，子專案不可單獨 configure。

## 指令

- **設定**（第一次或 `CMakeLists.txt`／`vcpkg.json` 變動後）：`cmake --preset default`
- **快速驗證（Claude 自己跑、鐵律要求的那套）**：`cmake --build --preset default && ctest --preset default`
- **只跑某個小專案的測試**：`ctest --preset default -R '^aos_inst'`（或該小專案登記的測試名稱前綴）
- **完整驗證**：同上的 `ctest --preset default`——目前沒有額外分出「快速／完整」兩套，測試量還小

## 測試分類

目前沒有需要特殊環境（本機資產、外部服務、實機）才能跑的測試，全部測試都是離線、單機可跑：

| ctest 目標 | 小專案 | 涵蓋 |
|-----------|--------|------|
| `aos_inst_tests` | `core/inst/` | C++ 測試：format 層（JSON round trip／壞輸入）、exec 層（重導向／PATH／exit status／逾時）、CLI 層（`run()` 的整批剖析＋依序執行）——細節見 [code map](common/code-map.md) 的 `core/inst/tests/` 一節 |
| `aos_inst_capi_tests` | `core/inst/` | C ABI 往返測試（`core/inst/tests/test_capi.c`），獨立的 C 執行檔 |

日後新增小專案（`llm/`、`tooljson/`……）照同一個命名慣例掛自己的 `aos_<專案>_tests`，跑不了的環境依賴驗證才記 [WAIT_USER](../WAIT_USER.md)。
