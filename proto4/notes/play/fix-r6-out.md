## 完成

九項修正皆已落地，未碰 `playground/`，未打真 LLM、未開 agent、未 commit／push。

### 修改內容

1. `aos-kernel rm` 現在會清除 `done/`、`bad/` 同名舊紀錄，並印出清除位置。
2. `add --name` 只撞到舊紀錄時，會在新 inst 驗證成功後清除舊檔並重新排入。
3. `aos-kernel ls` 分清 daemon 家不存在、正常收工、pid 已死；RUNS 缺值顯示 `-`，PROC 動態對齊。
4. JSON／Python／Lua 執行成功皆在 stderr 印出 `第 N 格 ok（步驟名）`。
5. Python 例外摘要改用 traceback 最後一個位於 PROG 的 frame 行號。
6. Agent 每次 idle 只取最舊的一封信；陣列信仍整封算一題，其餘保留為 unread。
7. state 新增 `epoch`；reset 寫回乾淨狀態並遞增 epoch，請求名改為 `<name>-e<epoch>-q<q>-s<s>`。
8. `listen --once` 透過 `.listen-seen` 只印新回話，沒有時印 `（沒有新回話）`；其他模式維持原語意。
9. 兩種 stuck 回話已統一成指定文字。

### 修改檔案

- proto4-3：[README.md](/home/lorkhan/repo/simple_tools/aos/proto4-3/README.md)、[aos_kernel_add.py](/home/lorkhan/repo/simple_tools/aos/proto4-3/aos_kernel_add.py)、[aos_kernel_syscall.py](/home/lorkhan/repo/simple_tools/aos/proto4-3/aos_kernel_syscall.py)、[aos_kernel_status.py](/home/lorkhan/repo/simple_tools/aos/proto4-3/aos_kernel_status.py)、[kernel.md](/home/lorkhan/repo/simple_tools/aos/proto4-3/docs/kernel.md)、[files.md](/home/lorkhan/repo/simple_tools/aos/proto4-3/docs/files.md)、[test_kernel.py](/home/lorkhan/repo/simple_tools/aos/proto4-3/test/test_kernel.py)、[test_kernel_fix_r6.py](/home/lorkhan/repo/simple_tools/aos/proto4-3/test/test_kernel_fix_r6.py)
- proto4-6：[README.md](/home/lorkhan/repo/simple_tools/aos/proto4-6/README.md)、三支執行器及三份對應測試
- proto4-7：[README.md](/home/lorkhan/repo/simple_tools/aos/proto4-7/README.md)、`aos_agent_cli.py`、`aos_user_cli.py`、`mailbox.py`、`state_machine.py`、兩份測試

### 測試

- proto4-3：237 → **243**
- proto4-6：77 → **79**
- proto4-7：29 → **31**
- proto4-5：**64**
- proto4-4：**42／48／12**
- 根目錄 build 成功，ctest **8/8 全綠**
- `git diff --check`、Python 語法檢查全過

沒有未完成項目。既有 751 行的 `test_kernel.py` 只替換一條過時斷言、沒有增加行數；其餘本次新增或擴張檔案皆不超過 300 行。