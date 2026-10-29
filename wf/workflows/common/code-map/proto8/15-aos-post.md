← [入口](../proto8.md)｜涵蓋：`proto8/impls/aos-post`（投遞，10-29）｜同層：[16-aos-lock](16-aos-lock.md)（鎖，aos-post 連它）

> 2026-10-29 新專案（[medium-plan](../../../../../proto8/thinking/2026-10-29-medium-plan.md) 實作第 2、4 步）。逐專案說明在 [aos-post](../../../../../proto8/impls/aos-post/README.md)；規範 NORMS N-16 的 10-29 改口＋補。
> 一個 lib（`lib/libaos-post.a`，公開標頭 `include/aos/post.hpp`）加一支命令列 `bin/aos-post`。

| 哪裡 | 負責什麼 |
|---|---|
| `include/aos/post.hpp` | 公開介面（aos-daemon 信箱模式要連）：`Mailbox`（`tmp`／`fresh`＝new／`cur`／`done`）、`SendOpts`、`Checked`；`init`、`open`、`sender`、`letter_id`、`send`、`claim`、`claim_all`、`check`、`reply`、`finish`、`withdraw`、`check_id`；代號 `CommandUnknown`、`MailboxMissing`、`LetterMissing`、`LetterBad`、`WithdrawFailed`、`OrderBad` |
| `src/main.cpp` | 命令列 `aos-post 子命令 [旗標...] 信箱 [信號]`：子命令表（`init`、`send`、`claim`、`claim-all`、`check`、`finish`、`withdraw`）、`parse_cli`、印結果；沒東西退 10；錯一行 `aos-post: 代號 原因`、退 1 |
| `src/common/common.hpp` | 內部標頭：`is_dir`、`names_in`（照名字排序、`.` 開頭不算）、`drop`、`move`（rename；不在／搶輸＝false） |
| `src/mailbox/mailbox.cpp` | 信箱四格的路徑、`init`（mkdir -p＋三格）、`open`（缺格＝MailboxMissing）、`check_id`；common 小工具的實作 |
| `src/send/send.cpp` | `sender`（`$AOS_WS`→`$HOME`→`/`）、信號與 `sent_at` 取自同一刻、`send`（mkdir `tmp/<信號>` 撞名換 → 寫 `letter.json` → rename 進 `new/`）；`--ordered` 那段（`send_ordered`：先在 `tmp/` 寫好 → 拿 `order.lock/` → 讀 `order.json` → 先寫 N+1 再 rename 成 `new/<N+1 零填 12 位>.<信號>` → 放鎖） |
| `src/take/take.cpp` | `claim`／`claim_all`（rename new→cur）、`check`（驗信封必填）、`reply`（照 `reply_to` 投回信、`in_reply_to`）、`finish`（cur→tmp 再刪、`keep` 進 done/、壞信一律丟）、`withdraw`（new→tmp 再刪） |
| `tests/test_cli.py` | ctest `test_cli`：命令列黑箱（unittest） |
| `CMakeLists.txt`、`vcpkg.json`、`.gitignore` | 照 aos-directive 改名；靜態庫＋`-static-pie` 執行檔；nlohmann-json；連 aos-lock、aos-util；`bin/`、`lib/`、`build/` 不進 git |

誰連它：aos-daemon 的信箱模式（實作第 5 步，10-29；[14-aos-daemon](14-aos-daemon.md) 的 `mailbox.cpp`）。`proto8/tests/aos_bins.py` 沒列（proto8/tests 還沒用到它的 `bin/`）。
