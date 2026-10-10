# 狀況頁快照（HTML）

← [notes](../README.md)

給人看的圖解頁，存的是某個時間點的樣子，不隨程式更新。最新版發布在 claude.ai artifact（網址見 wf/SESSION-LOG.md 10-10 那條），10-10 起在重寫成白話版。

| 檔案 | 標題 | 是哪個時間點 |
|---|---|---|
| [2026-10-09.html](2026-10-09.html) | aos 今日戰況 | 10-09 傍晚 |
| [proto7-2-status.html](proto7-2-status.html) | proto7-2 現況圖解 | 10-09 20:00 |
| [architecture.html](architecture.html) | aos 時空架構圖解 | 10-09 晚上（10-10 早上小修） |

## 快照之後變了的（2026-10-10 註）

- 測試數：頁中的 1061 項是 10-09 20:00 數的；10-10 實跑是 1308 項（見 [tests/README](../../tests/README.md)）。
- 跨信記憶（M1）頁中寫「還沒進 main」，後來已進 main（`modules/up/aos7_up_memory.py`，結案信存 `notes/done/`）。
- 頁中說 modules 總覽「還列著 llmdiag、usage 兩列」：總覽已改成只在「已移除的包」一行提到；[INDEX](../../INDEX.md) 的兩列說的是轉址 stub，stub 還在。
- 10-10 新增選單包 [packs/menu/](../../packs/menu/README.md)，三張頁都還沒有。
