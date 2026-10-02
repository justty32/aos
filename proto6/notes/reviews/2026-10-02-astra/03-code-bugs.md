# proto6 Python 程式 審查（astra，2026-10-02）

## 一段話結論

必修集中在 daemon：root 端寫檔越權、停止任務的競態、重讀設定污染舊狀態，以及特殊 JSON 打掉服務。tick／exec 未找到可確定列為必修的程式 bug。以下都是讀碼判斷；全程未改檔、未 commit、未跑測試。

## 必修

1. **root 端能被要求覆寫不該碰的檔案。**  
   [aos_daemon_root.py:80](/home/guanyu/projs/aos/proto6/src/py/lib/aos_daemon_root.py:80) 直接用 root 開啟請求指定的 `frame/cgroup.procs`，之後才降權。被攻破的主程序可提供假目錄，讓 `cgroup.procs` 符號連結指向受保護檔案，造成截斷與覆寫。這違反 [account.md:14](/home/guanyu/projs/aos/proto6/spec/daemon/account.md:14) 的安全承諾。  
   **改法：** root 端固定可信的 cgroup 根目錄，只接受子項識別值；開檔時禁止跳出目錄及追蹤符號連結。

2. **一筆特殊 JSON 可以讓 socket 永久停止服務。**  
   傳入 `{"status":"\ud800"}` 加換行，解析會成功，但 [aos_daemon_ctl.py:93](/home/guanyu/projs/aos/proto6/src/py/lib/aos_daemon_ctl.py:93) 回覆時會發生 UTF-8 編碼錯誤。[第 69 行](/home/guanyu/projs/aos/proto6/src/py/lib/aos_daemon_ctl.py:69) 只捕捉 `OSError`，唯一的接線執行緒因此退出。MQ 共用這套服務，也受影響。  
   **改法：** 回覆使用 ASCII escaping；在單條連線內處理解析、編碼錯誤，保持接線迴圈存活。過深 JSON 引發的 `RecursionError` 也應留在這個邊界內。

3. **舊的 kill／restart 請求可能殺到下一次執行。**  
   [aos_daemon_ctl.py:168](/home/guanyu/projs/aos/proto6/src/py/lib/aos_daemon_ctl.py:168) 另開執行緒送訊號；[aos_daemon_kill.py:60](/home/guanyu/projs/aos/proto6/src/py/lib/aos_daemon_kill.py:60) 尚未核對執行序號就送 TERM。舊任務若剛好結束、補跑已啟動，就會殺錯。第 68–71 行的 KILL 也有「核對後放鎖，再取目前程序」的空檔。  
   **改法：** 兩階段都綁定原本那次的序號及 PID／請求 ID；程序登記、清除、核對與送訊號要共同同步。

4. **移除正在跑的項目，再加回，可能互相誤殺。**  
   [aos_daemon_reload.py:81](/home/guanyu/projs/aos/proto6/src/py/lib/aos_daemon_reload.py:81) 為加回的項目建框；[aos_daemon_cgroup.py:101](/home/guanyu/projs/aos/proto6/src/py/lib/aos_daemon_cgroup.py:101) 沿用相同路徑，讓新舊執行共用 cgroup。先結束的一次會在 [aos_daemon_run.py:55](/home/guanyu/projs/aos/proto6/src/py/lib/aos_daemon_run.py:55) 清框，把另一次正常執行殺掉。  
   **改法：** 留住尚未結束的舊項目；同一 inst 等舊次清框完成，再啟動新次。

5. **重讀壞週期值，會把舊設定一起改壞。**  
   [aos_daemon_config.py:185](/home/guanyu/projs/aos/proto6/src/py/lib/aos_daemon_config.py:185) 未驗週期型別。[aos_daemon_reload.py:113](/home/guanyu/projs/aos/proto6/src/py/lib/aos_daemon_reload.py:113) 先覆蓋舊值，第 121 行才做除法。例如改成 `"1000"`，雖然回報重讀失敗，舊值已受污染；也可能等任務結束才讓排程執行緒死亡。  
   **改法：** 先驗完所有待套用值，再修改現行清單。這是現行明訂「壞設定整份不採用」的例外，不是要求替 POC 全面補防禦。

6. **重讀移除帳號模組，任務會偷偷換帳號。**  
   [aos_daemon_config.py:162](/home/guanyu/projs/aos/proto6/src/py/lib/aos_daemon_config.py:162) 依新設定決定是否解析每項帳號。拿掉 `modules.account` 後，帳號變成 `None`，再由 [aos_daemon_reload.py:117](/home/guanyu/projs/aos/proto6/src/py/lib/aos_daemon_reload.py:117) 覆蓋現行項目。程式雖警告需要重開，下一次卻已改用預設帳號。  
   **改法：** 重讀時，依啟動時仍有效的帳號模組解析各項；模組變更只警告。

7. **daemon 會誤解本來應忽略的頂層資料。**  
   [aos_daemon_config.py:149](/home/guanyu/projs/aos/proto6/src/py/lib/aos_daemon_config.py:149) 展開整份內容，第 73 行遞迴所有鍵。陌生頂層欄位內的 `$ref` 也會被執行，可能造成啟動失敗。這與 [conventions.md:65](/home/guanyu/projs/aos/proto6/spec/conventions.md:65)「陌生鍵與 `_metainfo` 不解」矛盾。  
   **改法：** 只展開認得的頂層欄位；`modules` 內仍照既有規則完整展開。

## 建議

- **跨帳號執行前，恢復訊號預設值。**  
  [aos_daemon_root.py:107](/home/guanyu/projs/aos/proto6/src/py/lib/aos_daemon_root.py:107) 忽略 SIGINT／SIGHUP，但 [child:76](/home/guanyu/projs/aos/proto6/src/py/lib/aos_daemon_root.py:76) 未恢復就執行任務。普通任務因此可能和預設帳號有不同反應。建議在 child 恢復預設值。現行 kill／restart 使用 TERM／KILL，不受這點影響。

## 疑問

- **root 私有 socket 是否確實沒有傳進跨帳號程序？**  
  [aos_daemon_account.py:129](/home/guanyu/projs/aos/proto6/src/py/lib/aos_daemon_account.py:129) 用 `pass_fds` 傳入；[aos_daemon_root.py:102](/home/guanyu/projs/aos/proto6/src/py/lib/aos_daemon_root.py:102) 包裝後，child 直接 `execve`，未見關閉或設為不可繼承。若持續被繼承，helper 被殺時，主程序可能因其他程序仍持有 socket 而收不到 EOF。底層 socket 實作未讀到，這次不當已證實必修。**建議明確設不可繼承，dup2 後關掉多餘 fd。**

- **人手 Ctrl-C 結束 aos-exec，是否也刻意讓子任務繼續跑？**  
  [aos_exec_run.py:130](/home/guanyu/projs/aos/proto6/src/py/lib/aos_exec_run.py:130) 讓子任務另開 session；[aos_exec.py:242](/home/guanyu/projs/aos/proto6/src/py/lib/aos_exec.py:242) 沒有訊號轉送。長任務因此可能留在背景，`exit` 檔也不會寫。tick 已明說不清孩子，exec 沒有相同說明。**建議人手執行的 exec 轉送訊號並等待結束；若刻意保留，補一句原則即可。**

## 看過的範圍

- `proto6/src/py/bin/` 全部入口，以及 `lib/aos_*.py` 全部模組。
- 相關 account、control、MQ、reload、state、cgroup、kill、tick、exec、directives 測試與現行 spec。
- 已排除既定設計：socket 666、跨項控制、MQ 不驗取件人，以及 POC 不保證當機恢復。