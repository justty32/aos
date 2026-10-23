# proto8 參考筆記

← [proto8](../README.md)

**AI 寫的參考資料**：拿外面現成的東西跟 aos 對照、整理「可以借鏡的點」。這裡**不是規範、也不是討論紀錄**——不算數，條文以 [CONCEPTS](../CONCEPTS.md)、[NORMS](../NORMS.md) 為準；要採用哪一點由使用者決定（鐵律 5）。

為什麼不放 [thinking/](../thinking/README.md)：thinking 只收使用者原文、決定、結論（[user 03](../../wf/workflows/common/user/03-討論紀錄與規劃.md#討論紀錄只留原文決定結論2026-10-12-夜改)），整份 AI 產出不能放那裡；proto5、proto7 也各有 `notes/` 放這類參考，這裡照同一個樣子開。

| 筆記 | 內容 |
|---|---|
| [s6-runit.md](s6-runit.md) | aos（proto8）跟 s6、runit 的對照：chain loading、envdir 與 `.env`、服務監管、重啟、readiness、日誌、狀態檔、控制、訊號（2026-10-22） |
| [aos-exec-s6-runit.md](aos-exec-s6-runit.md) | aos-exec 能直接呼叫、或借形狀的 s6、runit 工具（fable 10-22 寫） |
| [dotenv-格式比較.md](dotenv-格式比較.md) | aos `.env` 要不要補拿掉變數、多行、引號：各家（docker、systemd、dotenv、envdir…）怎麼做、三項工作量、替代做法與最小可行建議（opus 10-22 寫） |
| [命名-老慣例查證.md](命名-老慣例查證.md) | 命名方法跟 Unix／Linux 老慣例的對照：man NAME 行、Pike／kernel／Go 的名字長短、單位後綴、`nr_`、epoch 秒、縮寫、`_` 開頭；逐字原文附出處（fable 10-23 深夜查） |
