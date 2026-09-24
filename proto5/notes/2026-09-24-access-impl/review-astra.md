整體隔離架構與快照流程清楚，但目前還不能視為可靠的權限牆：有兩條可讓工具修改牢外執行鏈的路徑，敏感環境變數也可能落盤或換名進牢。另有 CLI 並行、拒寫與錯誤處理缺陷。以下審查的程式與 `d4a9797` 相同；全程未修改檔案。唯讀沙箱下跳過需建立臨時檔的完整測試，另跑了 **5 個純單元測試，全數通過**，並以記憶體測例確認環境變數、CLI 與 state 驗證問題；逃逸鏈未做實機攻擊驗證。

**必修**

1. **P1：信任集合漏掉牢外執行的 aos-jail 與模組。**  
   **在哪：** `proto5/lib/aos_agent_access.py:280`、`aos_agent_batch.py:68`、`proto5/cli/aos-jail:6`。  
   **重現：** agent 家與工具 JSON 放在 repo 外，工具使用 `argv: ["sh"]`，將含 `proto5/cli`、`proto5/lib` 的 repo 可寫映射進牢。重疊檢查放行，工具便能修改 `aos-jail` 或 `aos_jail.py`；下一件工具會在建立隔離之前執行被修改的程式。記憶體測例確認這個 repo 路徑不與目前 T 重疊。  
   **建議：** 把牢外 launcher、匯入模組與必要執行鏈列入信任集合，禁止可寫映射覆蓋；launcher 使用受保護的確定路徑，避免 PATH 從可寫位置選到替身。

2. **P1：只保護 realpath 目標，漏掉可被工具替換的符號連結本身。**  
   **在哪：** `proto5/lib/aos_agent_access.py:285`、`aos_agent_batch.py:104`。  
   **重現：** `info.tools` 引用 `workspace/tool.json`，它是指向 workspace 外合法工具檔的 symlink；workspace 可寫。T 只收連結目標，故允許掛載 workspace。工具可刪掉 symlink，改放同名 JSON，保留工具名稱並加入 `_jail:false`。下一批即使算出 `AccessUnsafe`，這支工具仍會跳過隔離。  
   **建議：** 同時保護引用路徑的目錄項、途中 symlink 與最終目標。這不只是「人於檢查後換連結」的既知 TOCTOU 限制，而是牢內工具可自行完成的持續性繞過。

3. **P1：敏感環境變數過濾太晚，而且換名即可通過。**  
   **在哪：** `proto5/lib/aos_agent_batch.py:66`、`:72`；`aos_jail.py:117`。  
   **重現：**
   - `_meta.envs.OPENAI_API_KEY = {"$env":"OPENAI_API_KEY"}`：值先變成 `--setenv OPENAI_API_KEY=…` 寫入 inst，之後才被 jail 丟掉。若合法掛載 `self` 唯讀，工具仍可讀 `self/work/*.inst.json` 取得值。
   - `_meta.envs.FOO = {"$env":"OPENAI_API_KEY"}`：同一值以 `FOO` 進入牢內。`AOS_KERNEL_HOME`、`AOS_LLM_CONFIG` 也可如此換名。兩條均以假金鑰在記憶體測例確認。  
   **建議：** 在解析 jailed 工具的 `$env` 時就限制敏感來源，並在序列化 inst **之前**過濾輸出鍵；jail 端保留第二層過濾。只檢查最終變數名稱不足以履行不傳金鑰的承諾。

4. **P2：access 與 tools 並未可靠共用同一把鎖。**  
   **在哪：** `proto5/lib/aos_agent_access_cli.py:112`；`aos_agent_tools_edit.py:28`。  
   **重現：** tools 寫入持鎖並 rename `info.json`；一個 access 寫入者已在舊 inode 排隊，另一個在 rename 後鎖到新 inode。前者沒有 inode 重驗，兩者可同時修改 access；固定 `.tmp` 名也可能互相覆蓋或讓其中一方 rename 失敗。tools 在 rename 後尚有安裝收尾工作，inode 重驗也無法完整保護這段。  
   **建議：** tools/access 統一鎖住不會被 rename 的專用 lock 檔，涵蓋整個讀、驗、寫交易。

5. **P2：access set 漏掉 access 自己 `$ref` 的檔，違反拒寫規則。**  
   **在哪：** `proto5/lib/aos_agent_access_cli.py:101`、`:137`。  
   **重現：** access 的某格引用 `/shared/path.json`，執行 `access set ref /shared --rw`。解析取得的 refs 被丟掉，重疊檢查只額外加入 access 主檔，因此寫入成功；隨後顯示表格才發現 `AccessUnsafe`，命令仍退 0。新 mount 未指定模式時也不會依約自動 ro。  
   **建議：** 保留解析得到的 refs，使用與送件相同的信任集合；寫入前驗證候選設定。執行端會拒跑，所以這條主要是 CLI 錯誤與成功訊息失真。

6. **P2：cwd 使用指示詞時，access rm 會把合法設定寫壞。**  
   **在哪：** `proto5/lib/aos_agent_access_cli.py:156`、`:163`。  
   **重現：** `cwd: {"$env":"START"}` 且 `START=ws`，執行 `access rm ws`。程式比較原始物件與 `"ws"`，沒有比較解好的 cwd，於是刪除目前起點並寫檔；之後印出壞檔訊息卻仍退 0。記憶體測例已確認。  
   **建議：** 比較 `table["cwd"]`，並在落盤前重新驗證候選文件，失敗不寫。

7. **P2：明確指定但不存在的 access，ls 誤報為不關牢。**  
   **在哪：** `proto5/lib/aos_agent_access_cli.py:48`；`aos_agent_tools_edit.py:142`。  
   **重現：** `info.json` 設 `access: "missing.json"`。送件正確回 `AccessInvalid`，但 `access ls` 提早返回，印「工具不關牢」且退 0；`tools ls` 也顯示無 access 的狀態。  
   **建議：** 查詢端同樣區分「預設檔不存在」與「明確指定的檔不存在」，後者顯示錯誤，`access ls` 退 1。

8. **P2：手編錯 batch.access.cwd 會產生未處理 TypeError。**  
   **在哪：** `proto5/lib/aos_agent_info.py:102`。  
   **重現：** 把 `batch.access.cwd` 寫成 `[]` 或 `{}`，`cwd in mounts` 直接拋出 unhashable `TypeError`，沒有轉成帶位置的 `FieldTypeMismatch`。記憶體測例已確認。  
   **建議：** 先驗證為 `null` 或字串，再檢查名稱存在；快照 mount 名稱也應與 access 的名稱規則共用驗證。

**建議**

- **明示 `/opt/tool` 的整個目錄都是讀取授權。**  
  **在哪：** `proto5/lib/aos_jail.py:105`。  
  **重現：** 程式放在 agent 家根目錄，整個家便會掛到 `/opt/tool`；即使 mounts 沒有 self，工具也能讀旁邊的 info、state、work。  
  **建議：** `check` 列出實際暴露的程式目錄，對涵蓋 agent 家或敏感設定的目錄警告；規範「agent 家、金鑰檔一律看不到」須補上這個例外。

- **`_meta` 遞迴 `$ref` 的既知限制需要具體安全說明。**  
  **在哪：** `proto5/lib/aos_agent_access.py:327`；`proto5/spec/agent/access.md`〈限制〉。  
  **重現：** `_meta` 引用可信檔，該檔再引用可寫 workspace 的設定；後者不在 T。若它控制 `stderr`，工具可修改它，讓下一次 aos-exec 在牢外開啟不應寫入的檔案。  
  **建議：** 長期應由實際 inst 解析器回傳完整依賴；在此之前，文件應明說這個限制可能破壞信任資料保護，而不只是漏收路徑。

- **補安全回歸與可控的並行測試。**  
  **在哪：** `proto5/lib/test/test_agent_access.py`、`test_agent_tools_manage.py:294`、`test_jail.py:105`。  
  **重現／缺口：** 現有測試未覆蓋上述替換 launcher、替換可信 symlink、換名 `$env`、inst 落盤洩漏及跨 tools/access 的 rename 鎖競態；也沒有受控串流經 `/proc/*/fd` 的實際探測。  
  **建議：** 並行案例用 barrier 固定交錯次序；安全案例經真正 aos-exec → aos-jail → 工具執行鏈驗證。

- **bwrap 測試的可用條件不一致。**  
  **在哪：** `proto5/lib/test/test_agent_access.py:463`。  
  **重現：** 已安裝 bwrap、但禁止 user namespace 的環境，這條只檢查 executable 存在，卻要求 probe 成功，因此會失敗。  
  **建議：** 純報告測試 mock probe；整合測試使用與 `test_jail.py` 相同的實際可用性判定。

**不用改**

- `$opt` 使用物件形式符合 `spec/directives/opt.md`；`as`／`only` 的型別及錯誤代號由宿主規範定義，沒有機制層衝突。
- `only` 先挑、`as` 再改名；aos-agent 與 aos-llm 共用 `load_llm_view`，名稱一致。
- `_source`、`_jail` 等頂層私有欄位會在送模型前移除。
- `batch.access` 在建 act 批時保存；同批及崩潰重送使用舊快照，舊 state 缺鍵視為 null，符合定案。
- 沒 bwrap 時不偷偷降級；`_jail:false` 的明確例外符合本次實作定案。
- bwrap 參數使用獨立 namespace、新 `/proc`、空 `/tmp`、最小 `/dev` 與指定 `/etc` 項目；靜態檢查未見一般 `..` 或絕對路徑直接突破此配置。
- JSON 縮排、中文保留、一般格式錯拒寫與工具刪除只改引用，整體符合 CLI 定案。