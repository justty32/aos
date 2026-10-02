# daemon spec 與程式一致性 審查（astra，2026-10-02）

## 一段話結論

主要功能對得上，但重讀設定有兩個實際 bug：壞設定可能套用一半；移除帳號模組設定，可能讓任務換帳號。其餘集中在文件承諾過頭、舊規則殘留，以及 schema 與「模組沒掛就忽略」不一致。建議修這些落差，不擴充 POC 的異常處理。

## 必修

1. **重讀失敗，舊設定已經被改了。**  
   [reload.md:15](../../../../proto6/spec/daemon/reload.md) 承諾「整份不套用」。但 [aos_daemon_reload.py:112](../../../../proto6/src/py/lib/aos_daemon_reload.py) 先改欄位，再計算週期。把已跑完的項目改成 `"interval_ms":"oops"`，會先改壞記憶體才報錯，沒有還原。  
   建議：先驗完、算好排程，再改舊清單。另 [同檔:24](../../../../proto6/src/py/lib/aos_daemon_reload.py) 明說已寫入的 cgroup 上限不還原；文件也要列明這個限制。

2. **重讀時移除 `modules.account`，會讓任務換成預設帳號。**  
   [reload.md:14](../../../../proto6/spec/daemon/reload.md) 說 `modules` 改了不套用。但 [aos_daemon_config.py:162](../../../../proto6/src/py/lib/aos_daemon_config.py) 依新設定決定是否讀每項帳號；模組拿掉後全部變成 `None`，再由 [aos_daemon_reload.py:117](../../../../proto6/src/py/lib/aos_daemon_reload.py) 套入。  
   建議：重讀每項帳號時，依啟動時是否掛帳號模組判斷。

3. **帳號篇的「主程式被攻破也拿不到 root」保證過強。**  
   [account.md:14](../../../../proto6/spec/daemon/account.md) 說最多只能開名單准許的帳號。但 [aos_daemon_root.py:80](../../../../proto6/src/py/lib/aos_daemon_root.py) 在降權前，依請求提供的 `frame` 開檔寫入。被攻破的主程式可利用 `cgroup.procs` 符號連結，讓 root 截斷、覆寫其他檔案。  
   建議：POC 先縮成「拒絕以 UID 0 執行任務」，不要宣稱完整隔離。這裡確認的是 root 寫檔能力，沒有聲稱已取得 root shell。

4. **cgroup「省略＝不設限」不準確。**  
   [protocol/daemon/cgroup.md:23](../../../../proto6/spec/protocol/daemon/cgroup.md) 這樣寫，但 [aos_daemon_cgroup.py:113](../../../../proto6/src/py/lib/aos_daemon_cgroup.py) 只寫有列出的鍵。重讀刪掉上限，或重啟沿用舊框，都會保留原值。  
   建議：改成「省略＝不寫；既有框保留舊值」。

5. **帳號名單漏寫預設帳號的例外。**  
   [account.md:15](../../../../proto6/spec/daemon/account.md) 說都沒比到就不准。但 [aos_daemon_account.py:79](../../../../proto6/src/py/lib/aos_daemon_account.py) 直接允許預設帳號，[測試:83](../../../../proto6/src/py/tests/test_account_policy.py) 也明確驗這件事。  
   建議：補「預設帳號不受 allow 限制；deny 比到仍是設定錯」。

6. **MQ 重讀時，並不檢查新的門定義。**  
   [protocol/daemon/mq.md:23](../../../../proto6/spec/protocol/daemon/mq.md) 把門定義錯誤也列成「重讀時整份不套用」。實際 [aos_daemon_config.py:173](../../../../proto6/src/py/lib/aos_daemon_config.py) 使用啟動時的門，略過新門定義。例如改成 `modules.mq: {}`，仍可套用新週期，只警告模組要重開。  
   建議：文字分清「啟動驗門定義」與「重讀按原有門驗訂閱」。

7. **schema 沒落實「模組沒掛時忽略」。**  
   [daemon-core-config.schema.json:174](../../../../proto6/spec/protocol/schemas/daemon-core-config.schema.json) 無條件限制每項 `cgroup`、`account`、`mq` 的型別。但 [test_mq_send.py:224](../../../../proto6/src/py/tests/test_mq_send.py) 明確要求：没掛 MQ 時，`"mq":5` 也照常跑。  
   建議：schema 改成有掛對應模組，才限制該項欄位。

8. **指示詞展開說明混用了兩套規則。**  
   [core.md:14](../../../../proto6/spec/daemon/core.md) 的 tasks「只展到 tasks 那層」已過時。[conventions.md:65](../../../../proto6/spec/conventions.md) 又把陌生鍵、`_metainfo` 不展開的例外套到 daemon；但 [aos_daemon_config.py:70](../../../../proto6/src/py/lib/aos_daemon_config.py) 會遞迴所有鍵，只保留 `$opt` 物件。  
   建議：分開寫 daemon 與 tasks 的展開範圍，刪掉舊比較。

9. **持久檔通則與 daemon state 相反。**  
   [conventions.md:17](../../../../proto6/spec/conventions.md) 要求版本欄位、保留陌生欄位。但 [protocol/daemon/state.md:29](../../../../proto6/spec/protocol/daemon/state.md) 明說陌生欄位下次消失；[aos_daemon_state.py:39](../../../../proto6/src/py/lib/aos_daemon_state.py) 也只重建 `insts` 與兩個狀態。  
   建議：通則明列 state 的例外，不為配合文字新增版本機制。

10. **JSON 通則宣稱會拒絕，daemon 實際沒有拒絕。**  
    [protocol/README.md:11](../../../../proto6/spec/protocol/README.md) 說拒絕重複鍵、非有限數。但 [控制解析:99](../../../../proto6/src/py/lib/aos_daemon_ctl.py)、[訊息解析:75](../../../../proto6/src/py/lib/aos_daemon_mq.py) 都直接用 `json.loads`：重複鍵取最後一個，`NaN` 也能進訊息。  
    建議：改成輸入格式要求，別寫成 POC 已實作的拒絕保證。

## 建議

- **刪狀態檔要補「重開」。** [state.md:15](../../../../proto6/spec/daemon/state.md) 容易讓人以為在線刪檔就能恢復；[測試:106](../../../../proto6/src/py/tests/test_daemon_state.py) 實際是停機、刪檔、重開。

- **`kill`／`restart` 成功只代表請求已接受。** [control.md:43](../../../../proto6/spec/protocol/daemon/control.md) 寫「送出 SIGTERM 就回」；[程式:168](../../../../proto6/src/py/lib/aos_daemon_ctl.py) 則是開背景執行緒後直接回。改準文字即可。

- **`--help` 導引改準。** [control.md:79](../../../../proto6/spec/protocol/daemon/control.md)、[mq.md:77](../../../../proto6/spec/protocol/daemon/mq.md) 都指向 `--help`；但 [aos_ctl.py:42](../../../../proto6/src/py/lib/aos_ctl.py)、[aos_mq.py:33](../../../../proto6/src/py/lib/aos_mq.py) 會把它當用法錯，回 1。保留原始碼導引就好。

- **測試檔頭還有舊說法。** [test_daemon_kill.py:4](../../../../proto6/src/py/tests/test_daemon_kill.py) 說第二個 daemon 警告後照跑；[同檔:95](../../../../proto6/src/py/tests/test_daemon_kill.py) 驗的卻是退出 1。改註解即可。

## 疑問

**跨下一層 daemon，是否還要沿用父層控制環境？**

[control.md:14](../../../../proto6/spec/daemon/control.md) 說各層繼承。但 [give_env:158](../../../../proto6/src/py/lib/aos_daemon_run.py) 只覆蓋自己掛的 socket，控制或 MQ 任一掛了就換 `AOS_DAEMON_INST`。

因此「上層有控制、下層只有 MQ」會混成「上層控制 socket＋下層 inst」。`aos-ctl wake` 可能找不到項目，撞名時可能叫錯。

我的建議：同一 daemon 底下的 exec／tick 照常繼承；進入下一個 daemon 時，重新建立成組的環境。父層若仍要保留，另外明確指定。

## 看過的範圍

- `proto6/spec/daemon/`、`proto6/spec/protocol/daemon/` 全部。
- 四份現行 `daemon-*` schema；相關範例與驗證器。
- 四支 bin 入口；全部 `aos_daemon*.py`、`aos_ctl.py`、`aos_mq.py`。
- 核心、控制、訊息、重讀、狀態、帳號、cgroup、kill 相關測試與輔助檔。
- 交叉核對共用慣例、JSON 通則與 tick 展開程式。

全程只讀。未改檔、未 commit、未執行測試；以上是靜態審查結果。