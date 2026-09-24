本次未改任何檔。沙盒連 `/tmp` 都禁止寫入，因此未能重跑落盤、SIGKILL 或 bwrap 測試；以下以程式追查與純記憶體測試為依據。快照只讀了 `SNAPSHOT.json`。

## 必修

- **M1｜`proto5/tools/files/_trust.py:98`：信任集合沒有照實際設定完整解析，合法設定即可漏擋。**  
  `system`／`history` 的字面路徑只加入集合，沒有加入 `$ref` 追蹤佇列；`system: {"$ref":"paths.json#/system"}` 則只保護 `paths.json`，不保護解析出的路徑。純記憶體測試已確認兩種漏擋；`tools`、自訂 `access` 的指示詞也有相同問題，深度超限則直接略過。這不符合 catalog T-json 與驗收⑤。**建議**共用完整解析器及信任集合演算法，追蹤引用來源與解析後目標；解析失敗、超限時拒絕寫入，補上述案例。

- **M2｜`proto5/tools/files/json_edit:43`、`md_section:66`、`proto5/lib/aos_json_cli.py:94`：`expect_sha` 不能防止同時讀改寫造成的覆蓋。**  
  SHA 比對的是先前讀出的 `data`，檢查到 rename 之間沒有互斥。兩個寫者可以讀到同一 SHA、全部通過，最後一個覆蓋另一個，違反共同規則⑤。**建議**所有相關寫者共用不會被 rename 的鎖，鎖內重新讀檔、驗 SHA、修改及寫入；補兩個寫者同步通過讀取階段的測試。

- **M3｜`proto5/tools/wf/_wf.py:170`、`:210`：復原直接信任專案提供的 `commit.json`，可越過工作根目錄寫檔。**  
  `files`、`dirs`、`backup` 未驗型別、絕對路徑、`..` 或途中符號連結，且 `recover()` 不經 `_check_no_links()`。例如偽造 `.wf-staging-x/commit.json` 的 `files=["../payload"]`，來源可放在 staging 內，目的地卻落在專案外。關牢只能限制最外層權限，不能修正這個工具自身的越界。**建議**把 journal 當不可信輸入，嚴格驗證相對路徑與交易結構，復原也逐項驗證來源、目的地及備份位置；以 directory fd 防止換路徑。

- **M4｜`proto5/tools/wf/_wf.py:213`、`:234`：同時執行兩次 `wf_init` 會清除或搬動彼此仍在使用的 staging。**  
  沒有專案交易鎖；第二個呼叫會把第一個尚無 `commit.json` 的 staging 刪掉，或同時 roll-forward 同一筆交易。工具批次允許平行執行，這不是只有惡意輸入才會觸發。**建議**從 recovery 開始到 commit、清理完成都持同一把專案鎖，拿不到立即回 `Busy`；補雙行程交錯測試。

- **M5｜`proto5/tools/files/md_section:90`：清單格式驗證弱於 catalog T-md 與驗收⑥。**  
  只有「已有項目且全部符合工作流格式」才要求新項目符合；空節或混合清單可接受 `- arbitrary`，`remove_item` 也沒有驗證指定格式。**建議**依契約一律驗證 `- [工作流] 狀態 → 下一步`；空清單、混合清單與刪除操作都補負例。若要支援一般清單，須明確調整契約。

- **M6｜`proto5/lib/aos_directives_edit.py:435`、`proto5/lib/aos_json_cli.py:104`：常見檔案錯誤仍會漏出 Traceback。**  
  人格指令的鎖檔開啟、版本目錄建立／清理、`export` 直接寫檔，以及 `aos-json` 的父目錄建立，都可能拋出未被 CLI 捕捉的 `OSError`。例如不存在的 `--target` 或 export 目的地父目錄不存在。**建議**在操作邊界轉成具體 `ReadFailed`／`WriteFailed`，CLI 保證一行錯誤、退 1；補不存在目錄及權限失敗測試。

- **M7｜`proto5/lib/aos_directives_edit.py:264`：還原在鎖外選版、讀版，可能還原成空人格或寫入另一個目標。**  
  `system_path()`、`versions()`、`read_persona(chosen)` 都先於 `_edit()` 的管理鎖。另一個編輯若剛好淘汰所選版本，`read_persona()` 將不存在的版本當成空人格；取得鎖後便可能把空字串寫回。**建議**在同一把鎖內決定人格路徑、選版、讀版、備份及還原；版本不存在必須報錯，不能套用「新人格尚未建立」的語意。

- **M8｜`proto5/tools/wf/wf_lint:28`、`proto5/tools/wf/_wf.py:120`：檢查器執行故障被當作普通檢查不通過，工具仍退 0。**  
  子程序異常退出、缺少 `TOTAL` 或內部錯誤，都只變成 `FAIL (exit N)` 的成功文字；Python 介面也只有 `ok=False`，無法符合驗收員要求的「通過／不通過／檢查失敗」三態。**建議**區分有效檢查結果與執行故障；後者最後一行輸出 JSON、退 1，Python 介面提供明確狀態或例外。

## 建議

- **S1｜`proto5/tools/files/_trust.py:155`、`_files.py:49`：信任檢查仍有環境與換路徑前提。**  
  真正由 aos-jail 啟動時交給權限牆合理，但單憑 `AOS_TOOL_ROOT` 存在不能證明已關牢。另在 guard 與寫入間，把父目錄換成指向根目錄內信任資料的連結，現有根目錄檢查仍可能通過；硬連結檢查也只比對集合列出的 inode，未涵蓋受保護資料夾所有子檔。**建議**明確記錄限制，補環境誤設、父目錄替換與資料夾子檔硬連結測試；寫入使用穩定 directory fd。

- **S2｜`proto5/tools/wf/_wf.py:243`：目前是空 staging 產生檔案後逐檔提交，與 catalog 的複製專案、整棵替換不同。**  
  放在專案內可避開掛載點無法 rename 的問題，但提交期間讀者會看到新舊混合狀態，既有專案內容也沒有提供給初始化腳本。**建議**同步 catalog，明訂一致性保證及復原期間的使用限制；補最後一檔搬完、備份搬完與清理中的 KILL 窗口。

- **S3｜`proto5/lib/test/test_tools_wf.py:221`、`proto5/tools/wf/_wf.py:104`、`:345`：固定檢查器及關牢相容性尚缺足夠驗證。**  
  現有測試確認不跑專案的同名 shell，未涵蓋專案 `.py`、`fmt-vars.local.json` 的間接執行，也沒有真正的 `/opt/tool` 唯讀、target 掛載點測試。本次受沙盒限制，不能宣稱這些面向通過。**建議**補惡意設定與 Python 模組替身的黑箱測試，以及真 bwrap 整合；檢查器啟動時隔離 Python 搜尋路徑並清理環境。

其餘靜態檢查：JSON Pointer 五種操作、序列化拒絕非法結果、`wf_doc` 快照路徑限制、一般同名標題拒絕，以及人格字面 `content` 限制均有對應實作；人格使用指示詞時明確拒絕編輯，與新增規格一致。

必修 8 條、建議 3 條