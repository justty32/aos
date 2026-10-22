← [入口](../gotchas.md)｜涵蓋：core/loop 的投遞與回合

## core/loop 的投遞與回合

- **`aos deliver <file.json>` 撞名直接覆蓋，不查重**（2026-09-01 實測）：這條路的 id 取
  **檔名 stem**（`core/loop/src/deliver_cli.cpp:49`），而 `deliver()` 只是 `write_atomic`
  到 `inbox/<id>.json`（`core/loop/src/deliver.cpp:16`），不檢查檔案在不在。同一個檔名連
  投兩次、或兩個目錄下同名的 `job.json`，**前一份還沒被跑掉就沒了**——`aos deliver` 回
  exit 0，沒有任何警告。`aos deliver -- <argv...>` 那條不受影響，它的 id 是
  `make_delivery_id()` 產的 `d-<epoch_ms>-<pid>-<seq>`。要保證不掉件就自己給獨一無二的
  檔名，或改用 `--` 那條。

- **`core/loop` 全程沒有 `fsync`**：唯一的寫檔入口 `fs::write_atomic()`
  （`core/loop/src/fs.cpp:42`）是 `ofstream` → `close` → `std::rename`——`rename` 只保證
  目錄項原子替換，不保證內容落地。斷電後可能留下已改名、內容零長度的 `state.json` 或
  `turn`。正確順序是 寫檔 → `fsync(fd)` → `rename` → `fsync(dir_fd)`。`core/tick` 同一
  個毛病。
