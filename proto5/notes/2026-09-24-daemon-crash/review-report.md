靜態唯讀審查完成，未改檔、未執行測試。

**真 bug**
- 在規範限定的正常接手環境內，未確認新的產品 bug。`run()` 確實先等舊孩子消失、再對帳、最後公布空表；接手期間 SIGTERM 會記住停機要求。[aos_daemon.py:350](../../lib/aos_daemon.py#L350)
- `PermissionError` 並非無限等待：探活視為存在，但接著送 TERM 會拋錯、啟動失敗，舊表保留；不要把它描述成成功接手。[aos_daemon.py:53](../../lib/aos_daemon.py#L53)

**測試漏洞**
- **高：公布順序仍有競態。** `published()` 先輪詢 state、再讀收屍紀錄；錯誤實作可以先公布，孩子稍後才死，測試仍通過。WNOWAIT 只保證「記錄 → waitpid」，甚至紀錄出現時尚未收屍。應在測試 driver 寫新 state 的位置設同步檢查，搭配 HUB 暫停收屍。[test_daemon_crash.py:213](../../lib/test/test_daemon_crash.py#L213)、[同檔:49](../../lib/test/test_daemon_crash.py#L49)
- **中：無法抓到相同內容重寫回音。** 比 bytes、檔案數量不能證明只寫一次；重寫相同 `Interrupted` 仍通過，應記錄寫入次數。[test_daemon_crash.py:370](../../lib/test/test_daemon_crash.py#L370)
- **中：未證明沒有多拉孩子。** 最終空表及回音不等於 spawn 次數正確，多拉後退出／漏登記可能漏網；應記錄每次 spawn 的 PID。[test_daemon_crash.py:362](../../lib/test/test_daemon_crash.py#L362)

**Flaky／清理風險**
- **中：`responded` 案例缺 ready 同步。** 第二任可能在孩子安裝 `SIG_IGN` 前送 TERM，實際死因變成 15，卻斷言必為 9。[test_daemon_crash.py:333](../../lib/test/test_daemon_crash.py#L333)、[_daemon_util.py:17](../../lib/test/_daemon_util.py#L17)
- **中：失敗路徑不保證清乾淨。** 孩子只有取得閘門結果後才加入 `groups`；若此前失敗，HUB 只殺已知 PID／群組，未知且忽略 EOF 的孤兒可能存活，四秒後仍直接退出。[test_daemon_crash.py:255](../../lib/test/test_daemon_crash.py#L255)、[同檔:53](../../lib/test/test_daemon_crash.py#L53)
- **低：時間與 PID 假設。** 固定 `.2s` 不能證明持續存活；六秒期限在高負載可能誤報。歷史 PID 未移除，重用後可能誤比對或誤殺。正常父子關係下，HUB 與 unittest **沒有收屍衝突**。[test_daemon_crash.py:302](../../lib/test/test_daemon_crash.py#L302)、[_daemon_util.py:42](../../lib/test/_daemon_util.py#L42)

**確認／建議**
- 九個閘門位置符合目前路徑，模組替換有效；但 `go_sent` 精確而言是 `_send()` 返回，未普遍保證寫入成功。state 使用暫存檔＋replace，SIGKILL 不會留下半份正式 JSON。[test_daemon_crash.py:112](../../lib/test/test_daemon_crash.py#L112)、[aos_daemon.py:138](../../lib/aos_daemon.py#L138)、[aos_home.py:118](../../lib/aos_home.py#L118)
- **規範確實矛盾。** 我以 §6.1 的明確啟動流程為準：跨代清表、不收養；未完成請求對帳為 `Interrupted`，客戶另送 spawn 得新 PID。§2「崩潰後重送回原 PID」應修正為同一任仍持有 running 表項時的冪等性。[daemon.md:117](../../spec/daemon/README.md)、[同檔:228](../../spec/daemon/README.md)