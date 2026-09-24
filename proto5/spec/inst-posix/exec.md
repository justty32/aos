← [inst-posix](README.md)｜[spec 總導航](../README.md)

# 6. 執行語意（執行者要做到的）

這一節講「照這份 inst 跑一次」是什麼意思，執行者（現在是 aos-exec）必須照做：

1. **驗完才跑**：任何一個讀／驗錯誤＝那次根本沒跑，退 125、不寫 `exit`。
2. **前置檢查也算「沒跑」**：`exit` 的父目錄不存在（且沒用 `mkdir` 選項）、`cwd` 不是資料夾
   （且沒用 `mkdir` 選項）、重導向的檔開不起來，都是執行者自己失敗（125）。
   - **`mkdir`**：`cwd` 是先解出路徑、`makedirs` 把目錄建好，再拿它當中心解其他相對路徑；
     `stdout`／`stderr`／`exit` 的 `mkdir` 是在**開檔前**先把父目錄建好。`makedirs` 失敗
     （例如路上卡了一個同名的檔案）＝執行者自己失敗（125）。
   - **`append`**：`stdout`／`stderr` 是照 `>>` 開檔（存在就接在後面、不存在就建）；`exit`
     是把「十進位＋換行」的結束碼接在檔尾，一樣寫完 fsync 檔與父目錄。
   - **`inherit`**：那條串流直接沿用執行者（aos-exec）自己的標準輸入／輸出／錯誤（傳給
     `Popen` 的參數是 `None`），不開檔、不重導向。aos-exec 命令列的 `--stderr -`／
     `--stderr PATH` 仍然蓋過 inst.json 的 `stderr` 設定，包括 `merge`／`inherit`／
     `append`。
   - **`merge`**：`stderr` 跟 `stdout` 走同一條（`2>&1`），照 `stdout` 當時的設定走——
     `stdout` 是 `append` 就跟著 append、是 `inherit` 就跟著 inherit。
3. 環境：`envs` 用 `clear` 選項時從空的開始，否則從執行者自己的環境複製一份；再把 `envs`
   疊上去（只加不減）。
4. 用 `argv[0]` 在**疊加後**的 PATH 找程式；找不到＝127、沒執行權＝126——**這兩種算
   「跑完了一次」**，有 `exit` 就照樣寫進去。
5. 子程式開在**新的 process group**（`setsid`），逾時砍的是整個 group：先 SIGTERM、等 2 秒、
   還在就 SIGKILL。被 SIGTERM 砍死＝143、SIGKILL＝137。
6. 結束碼：正常結束＝它的 exit code；被訊號 N 砍＝128+N。有 `exit` 就寫進去（十進位＋換行，
   `append` 就接在檔尾，否則覆蓋；都要 fsync 檔與父目錄）。
7. 執行者的**自己的**失敗碼固定 125、用法錯 2，跟子程式的碼分開，看的人才分得出
   「跑了但失敗」跟「根本沒跑」。
