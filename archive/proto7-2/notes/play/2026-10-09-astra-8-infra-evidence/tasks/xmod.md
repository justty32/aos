# 子線 xmod：跨模組契約與統一錯誤路徑

線名 `xmod`。範圍是「模組之間」，不深挖單一模組內部：
- 統一錯誤路徑：`proto7-2/notes/blueprint-errors.md`、`blueprint-errors-items.json`、`proto7-2/tests/error_path.json`、`proto7-2/tests/core/test_error_path.py`。逐一列出 proto7-2 下所有可執行入口（`find proto7-2 -path '*/bin/*' -o -name 'aos7-*' -type f`），檢查哪些沒列進 error_path.json、哪些 exempt 理由已過時、測試是否真的驗到它聲稱的（例如「暫存夾不能有任何變動」是否涵蓋 $HOME、cwd 外）。人話行前綴、退出碼 0／1／2／3／4／5 各包意思是否衝突（同一個碼在不同包意思相反？）。
- 跨包契約：`proto7-2/notes/component-contracts.md`、`proto7-2/notes/layer-interfaces/`、各包 README 的「契約卡」——今天新增的包（events、llmcall、kernel、up、mail、compact、skills、routines、wfnode、author、prompt）彼此呼叫處（例如 up→compact、up→llmcall、brain→mail、mail→events、author→events、compact→llmcall、kernel→ctl、skills→llmcall、metrics/diag→llmcall/budget 檔）的參數、檔案格式、退出碼解讀是否對上：呼叫方是否正確處理被呼叫方的 3（unknown）與 4。
- 共用工具是否被重複實作（原子寫、flock、tmp 清理、JSON 讀錯處理、hist_name 類編碼）而行為不同（C 類或 B 類）。
- 環境變數（`AOS7_*`）命名與傳遞：K1 白名單後，模組依賴的變數是否傳得到任務裡。
- 文件導航：`proto7-2/README.md`、`INDEX.md`、`modules/README.md`、`tests/README.md` 的清單與實際檔案是否一致（測試數、包列表、archive 狀態）。
