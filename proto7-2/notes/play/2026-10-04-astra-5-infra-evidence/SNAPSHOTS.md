# 快照目錄已打包

為了不讓 repo 多出近兩千個小檔，四個 `snapshots/` 目錄（中斷前後的帳、入口、後端原始檔）已打包成同層的 `snapshots.tar.gz`：

- `budget-integration/snapshots.tar.gz`
- `budget-crash/snapshots.tar.gz`
- `budget-crash/extra/snapshots.tar.gz`
- `budget-crash/verified/snapshots.tar.gz`

報告或摘要裡寫到 `snapshots/<案>/…` 的路徑，在對應的 tar 裡。展開：`tar -xzf snapshots.tar.gz`（在該層目錄執行）。各層的 `snapshots.json`／`results.json` 摘要沒有打包。
