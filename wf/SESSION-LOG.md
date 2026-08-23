# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡——過程細節交給 git log（若有「已落地功能目錄」則濃縮一句進去）。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔若過大，就在 repo 頂層新立 **`session_logs/`** 資料夾，按工作流／類別**拆檔 + 一個 index 導航**（照 [DEV-GUIDE「結構整理原則」](DEV-GUIDE.md)）。

本檔同時 ① 連到各工作流自己的 session-log（若該工作流已長出自己的），② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態 + 指向細節的連結**（設計決策/修了什麼落到該工作流的文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即整條刪除。

## 最新進度

- **monorepo 骨架已完成、尚未 commit**：C++23、`common/`＋`app/`＋`inst/`、`aos_add_subproject()` 樣板、install/export（外部 `find_package(aos CONFIG)` + `aos::inst` 已實測可用）。建置、測試、安裝、外部消費四項都驗過。整批改動還在 working tree，待使用者確認後才 commit。
- **C ABI 尚未補齊**：目前只有 `inst` 有 `<aos/inst.h>`；使用者明確表示這塊之後再慢慢加，現階段不動它。

## 各工作流 session-log

> 〔模板說明〕某工作流長出自己的 `session-log.md` 後，在這裡加一列。一開始是空表很正常。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
