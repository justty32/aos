git-image 這題 sol 替使用者定下的 15 個設計決定（五欄一覽表）
← [入口](../04-設計規劃.md)｜上一份 [02-續-git-image發現4到5](02-續-git-image發現4到5.md)｜下一份 [03-mailbox-naming](03-mailbox-naming.md)

## 設計決策一覽

| 決定了什麼 | 出處檔:行 | 對照的使用者原話 | 判斷 | 要裁時的選項與推薦 |
|---|---|---|---|---|
| image 放專門的 repo | `05-其他手段與衝突.md:9`；`02-image保存與邊界.md:28` | 「只留最新一份 (Recommended)」（選項說明含專門 repo，`README.md:48`） | OK | 不用裁 |
| 每次凍住做 orphan commit＋`push --force`＋要留的打 tag | `02-image保存與邊界.md:46-49` | 同上 `README.md:48` | OK | 不用裁（做法本身要照第 2 條補 lease） |
| 食譜關掉自動 gc、也不手動清 | `02-image保存與邊界.md:34,52` | 沒找到原話 | 該翻案 | 直接修：push 後補 reflog expire＋gc --prune（推薦） |
| `push --force` 不帶 lease | `02-image保存與邊界.md:49` | 沒找到原話 | 該翻案 | 直接修：改成 `--force-with-lease`（推薦） |
| wait 缺 request 就退 11 回 think 重組 | `wait.py:112-114` | 「改成可重建、擋掉」（`README.md:49`；選項原文「wait 格找不到這個檔，就退回 think 重組」，`04185730c` 的 README） | OK | 不用裁 |
| 有 pending 先收原回信、不重寄 | `wait.py:114`；`README.md:49` | 沒找到原話，從「不重寄」推得出 | OK | 不用裁 |
| 拿掉 `RequestMissing` 錯誤 | `wait.py:12`（`cf5799221`） | 同「改成可重建、擋掉」 | OK | 不用裁 |
| 擋 `**/think/request.json` | `stack.gitignore:37` | 「改成可重建、擋掉」（`README.md:49`） | OK | 不用裁 |
| image repo 根只擋 `ws/.trash/` | `02-image保存與邊界.md:37`；`04-gitignore建議.md:44` | 「擋掉不搬 (Recommended)」（`README.md:50`） | OK | 不用裁 |
| 擋 log 類（stderr、live、turns、mcp-logs、transcripts） | `stack.gitignore:16,39-44` | 沒找到原話 | 該問使用者 | A 擋、但換機器不刪這台的紀錄（推薦）／C 全帶 |
| 擋 `**/archive/`（N-16 選擇留的歸檔） | `stack.gitignore:45`；`05-其他手段與衝突.md:28` | 沒找到原話 | 該問使用者 | B 不擋、照 N-16（推薦）／維持擋 |
| 新機器 `clean -fdX` 清被擋的檔 | `02-image保存與邊界.md:59-62` | 沒找到原話 | 該問使用者 | 改成只清 request（推薦）／維持現狀 |
| 擋 `/queue.json` | `stack.gitignore:26` | 見 A 區第 4 條 | 該翻案 | 見 A 區第 4 條：拿掉這條（推薦） |
| 擋鎖、暫存、可重寫的小檔（sender.flock、order.lock、endpoints、mcp.json、tmux.conf、busy、run_python、ctl 回信） | `stack.gitignore:20-35` | 沒找到原話，從 C-79／N-67 ④「行程狀態不跟檔走」推得出 | OK | 不用裁 |
| 方向題 2 推薦「先不改」 | `04185730c` 的 README 方向題 2 | 使用者反選「改成可重建、擋掉」 | OK | 不用裁（推薦有附理由，沒有偏頗） |
