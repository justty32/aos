← [本輪報告](README.md)｜[任務書](review2-task.md)（codex exec -m gpt-6-astra -s read-only 原文；行號連結改成連到檔案）

發現 **3 項必修**。全程未改檔、未接觸模型服務；已用記憶體 mock 重現前兩項。`git diff --check` 通過；整合測試需要建立暫存家與啟動程序，本輪唯讀環境未執行。

**必修**

1. **[aos_kernel_check.py:353](../../lib/aos_kernel_check.py)：owner 比較與 daemon 不一致，會漏報撞名。**  
   `check` 用 `abspath(owner)`，daemon 的 `scale()` 卻直接比較原字串。已重現：K 是 `/review/K`、owner 是 `/review/K/.` 或 `/review/K/`，check 不報 bad，daemon 卻回 `NameTaken`。  
   **改法：**check 應比較實際送出的 owner 字串，與 daemon 保持一致；補尾斜線、`.`、相對路徑案例。symlink 別只在 check 用 `realpath` 放行，否則同樣會與 daemon 分歧。

2. **[aos_up.py:136](../../lib/aos_up.py)：停機前快照不能代表 `stop()` 的結果。**  
   已重現：`halt_status()` 看見 daemon 活著，隨後 daemon 消失；真正的 `stop()` 回「not running」、退 0，但輸出被吞掉，down 仍印「kernel 剛停」，帳本仍是 `running`。此外，`orphan` 也涵蓋「daemon 活著、只是沒有登記」，固定說「daemon 就不在了」亦不準確。  
   **改法：**讓 stop 回傳結構化結果及原因，由 down 據此印摘要；daemon stop 也採相同方式，避免它回「not running」卻被印成「剛停」。補兩次觀察間狀態改變的測試。

3. **[lifecycle.md:59](../../spec/daemon/lifecycle.md)、[教程 01:159](../../tutorials/01-daemon-kernel.md)：「被打斷的工作會重派」不符合實作。**  
   `aos_kernel_engine.py:158` 對 once 工作直接把 `Interrupted` 回給交件者並移除行程，不重派；反覆工作則累計失敗，也可能到達 `bad_after` 而停止。  
   **改法：**文件改成「kernel 收取 Interrupted；once 回報失敗，反覆工作依重試與失敗上限處理」。這次既然只補規範，不應為配合文字改變重試語意。

**建議**

1. **[aos_daemon.py:242](../../lib/aos_daemon.py)：Stopped 印在最後一次存檔之前。**  
   若 `owner.save()` 失敗或此處被殺，log 已說「正常停機」，state 卻仍保留舊 pid，下次 Boot 又說「沒正常停」。  
   **改法：**先成功存下 `pid=0`，再印 Stopped；加存檔失敗注入測試。

2. **[aos_daemon.py:230](../../lib/aos_daemon.py)：Boot 的歷史判定需要明確限定。**  
   壞 JSON／非物件 state 會在第 220 行讀取時直接 `ReadFailed`，不會印 Boot，也不會進入收孩子流程；合法物件但 pid 缺失或型別錯，則不會加「没正常停」。啟動途中、首次 save 前再崩潰，也無法靠 state 辨認這一任。  
   **改法：**文件說清楚這是「依有效舊 pid 推定」，未知情況可另印「無法判定」；補壞 JSON、缺 pid、錯型別測試。

3. **[test_play_one_boot.py:113](../../lib/test/test_play_one_boot.py)：測試涵蓋主要路徑，但不足以證明所有承諾。**  
   新 cpu 出現後才查舊 pid 已死，不能排除曾短暫重疊；此測試也沒有驗 once 最後收到什麼。另缺 `--keep-daemon`、多 daemon、搬池、symlink K、daemon 停著時撞名，以及上述競態案例。  
   **改法：**在新 cpu 啟動當下記錄舊 pid 是否仍活著，並驗收工作回音；其餘輸出分支可用 mock 小測試補齊。

**其餘面向**

- ack 在成功放單後才印提示，與非同步刪回音的實作一致。
- ls 的一般池摘要在 daemon 死亡後改標舊資料，kernel／tick 行也一致，JSON 未改。
- check 使用設定中的搬池目的地檢查撞名，方向正確；`pool_owner` 在 daemon 停著時仍可讀。
- down 的多 daemon 清單包含設定、帳本 ticker 與舊池位置；穩定狀態下 `--keep-daemon` 和逐 daemon 輸出分支合理。
- 新 daemon 先等舊 cpu 消失才接手的順序未被本次改動破壞。
- 教程以 `aos-daemon ls` 查指定 daemon、以 `$W` 篩 pgrep，符合本輪清場需求。