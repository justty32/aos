← [第二輪報告](round2.md)｜任務書：[review2-task.md](review2-task.md)

# astra 唯讀審查結果（第二輪，2026-09-24，審至 9b7ca32）

**必修**

1. **P1：舊 inst 重送能繞過 `NoAccess`，讓工具不關牢執行。**  
   位置：`proto5/lib/aos_agent_batch.py:209–243`。  
   舊版在沒有 access 表時寫好 `.inst.json`、尚未送出便崩潰；升級後因檔案已存在，直接跳過權限檢查再送。記憶體測例確認：`batch.access` 缺鍵或為 `null` 都會送出。  
   修法：在提交尚未送出的 act 工作前檢查 `NoAccess`，不能因 inst 已存在就略過；保留已提交工作的收尾流程，並補升級重送測試。

2. **P2：沒 access 表時，`check` 漏掉 `_jail:false` 的警告。**  
   位置：`proto5/lib/aos_agent_check.py:107–114、136–140`；`proto5/lib/test/test_agent_access.py:492–497`。  
   缺表分支提早返回，完全不會走到警告；記憶體測例確認沒有任何報告。測試註解說會警告，實際卻只驗「沒有 access 訊息」。  
   修法：先列出不關牢工具的警告，再處理缺表；測試明確斷言警告存在。

3. **P2：教使用者執行的補救指令沒有 shell 引號。**  
   位置：`proto5/lib/aos_agent_batch.py:23–26`；`proto5/lib/aos_agent_tools.py:228–231`。  
   家目錄含空白時，複製指令會拆成多個參數；含 shell 特殊字元時還可能執行非預期命令。  
   修法：對每個路徑參數使用 `shlex.quote()`，補空白、單引號與特殊字元測例。

4. **P2：`ReadOnly` 把所有 `EROFS` 都說成使用者在 access.json 設成唯讀，原因可能講錯。**  
   位置：`proto5/tools/base/_common.py:197–217`；`proto5/tools/README.md:59`。  
   不關牢時遇到主機唯讀檔案系統，也會回 `ReadOnly` 並指責 access.json；記憶體測例已確認。可寫 mount 裡原有的唯讀子掛載也有同樣問題。  
   修法：訊息先說「檔案系統或掛載為唯讀」，有依據才指出 access 設定；README 刪掉「只有關牢時會遇到」。一般子資料夾權限不足回 `EACCES → WriteFailed`，這部分正確。

5. **P2：規範與教程仍有會誤導操作的舊句子。**  
   位置與修法：
   - `proto5/spec/aos-agent/access.md:59`：仍把「沒 access 檔」列為不關牢情況；刪掉這個例外。
   - `proto5/tutorials/04b-access-and-tool-admin.md:51`：`access set self . --target $W/bob` 掛的是殼所在資料夾，不保證是 bob；改成 `self "$W/bob"`。
   - `proto5/tools/README.md:12、16`：`--root` 不保證改變牢內起點；補上改 access 表的指令。`aos-kernel check --agent` 改成現行的 `aos-agent check --target`。

**建議**

1. **補上目前漏掉的邊界測試，並避免把 jail 壞掉誤判成環境不支援而跳過。**  
   位置：`proto5/lib/test/test_access_round2.py:20–126`、`proto5/lib/test/test_jail.py:105–110`。  
   補符號連結、`/proc/self/root`、`/opt/tool`、明設 `AOS_TOOL_FENCE=/`、`EACCES`、舊 inst 重送，以及 `/tmp`／`/dev`／`/proc` 的真牢測試。環境探測應使用獨立的最小 bwrap 命令；目前直接用待測的 `build_argv()`，它若壞掉，整組測試可能全部 skip。

2. **舊 base 工具包需要明講重裝才會取得新範圍。**  
   位置：`proto5/lib/aos_agent_tools.py:179–198`、`proto5/tutorials/04b-access-and-tool-admin.md:85–94`。  
   已安裝的是程式副本，更新 aos 不會更新副本；舊 `_common.py` 忽略 fence，仍只允許起點範圍。教程補 `aos-agent tools add base --force --target …`。

3. **init 測試應驗證預設表真的能通過權限檢查。**  
   位置：`proto5/lib/test/test_agent_daily.py:36–48`、`proto5/lib/aos_agent_init.py:30–38`。  
   一般空白家目錄的 workspace 不與信任集合重疊，記憶體檢查通過；但現有測試只驗 JSON。建議再呼叫 `access.load()`，並補 `--force` 遇到既有 workspace 符號連結的情況。

**不用改但值得記**

- **一般路徑檢查未見新增的直接逃出方式。** `proto5/tools/base/_common.py:133–167` 先解 realpath，再驗 fence；一般 `..`、指向外面的連結、`/proc/self/root/etc/passwd`、`/opt/tool` 會被擋。既有路徑競態限制仍在，不必把這層宣稱成安全沙盒。

- **環境變數過濾正確，但 fence 不是不可修改的安全邊界。** `proto5/lib/aos_jail.py:120–126` 會過濾 `AOS_*` 並最後設定 fence，覆蓋測例通過；工具自己的程式仍能修改自身或子行程環境。這不會突破 bwrap，只可能放寬 base 的防手滑檢查。

- **合法舊快照繼續使用、think 批不關牢、非 bool `_jail` 被拒絕，都符合目前設計。** 位置：`proto5/lib/aos_agent_batch.py:49–68、183–211`、`proto5/lib/aos_agent_home.py:194–195`。需要修的是上述舊「未關牢 inst」重送缺口，不是重新讀取每件工作的 access 表。

- **測試中的 `_jail:false` 改動多半是在隔離原本要測的行為，未見直接把 `NoAccess` 斷言放水。** 但整合測試沒有 bwrap 就改走不關牢分支，不能算權限牆驗證；第 2 條所述警告測試確實漏驗。

- **驗證範圍：**審至 `9b7ca32`，全程未改檔；5 個純單元測試通過，另做記憶體測例。此環境 bwrap 因 `NETLINK_ROUTE socket: Operation not permitted` 失敗，未跑需建檔的完整測試，也未實證 `--remount-ro /` 對各掛載的真實效果。