完成，未 commit／push，也未碰範圍外檔案。

- `src/step.janet` 193 行（+31/−8）；`test/step.janet` 101 行（+3/−1）；`test/cpu.janet` 131 行（+84）。
- `README.md` 153 行（+11/−3）；`proto4-3/docs/kernel.md` 120 行（+7/−5）；`test/fx/` 無須修改。
- `test/aos.janet`：`34 條通過 ✓`
- `test/cpu.janet`：`12 條通過 ✓`
- `test/step.janet`：`28 條通過 ✓`
- proto4-3：188 條，末行原文 `OK`
- kernel 整合：`1.989 秒，log.txt 3 行，done: 1`
- 根目錄 build＋ctest：`100% tests passed out of 8`；文件相對連結全數存在。
- 自行將 `--done-exit` 限為 0–255；處理了 daemon 啟動競速與失敗收尾。沒有未完成項。