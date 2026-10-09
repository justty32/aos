# metrics 意圖卡

← [intents](README.md)｜[包 README](../../modules/metrics/README.md)

**①解決什麼**：指一個資料夾，一行回答 AI 工作「每件 token、同時幾個、花幾秒、重試幾次」；要分組就 `job … --by model|holder|day|hour`、要帳差加 `--detail`（原學徒寫的 `packs/usage` 功能已併入，10-09 RV-fix A；`job` 預設輸出一字不改）。

**②必要的副作用**：零。只讀 llmcall／budget／author／jobs／events 留下的檔，印到 stdout；不寫檔、不鎖、不起程序、不連網。

**③不做**：不修帳、不清證據、不估價、不碰別包。

**④多出來的**：零。讀不了的檔只在行尾報「N 個檔讀不了」仍退出 0——**保留**（量尺不該因一個壞檔整支失敗），已寫進 ADVANCED 退出碼段（10-09 ER-prompt-metrics）。
