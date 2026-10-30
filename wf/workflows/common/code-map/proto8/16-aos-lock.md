← [入口](../proto8.md)｜涵蓋：`proto8/impls/aos-lock`（鎖，10-29）｜同層：[15-aos-post](15-aos-post.md)（投遞，連它）

> 2026-10-29 新專案（[medium-plan](../../../../../proto8/thinking/2026-10-29-medium-plan.md) 實作第 3 步）。逐專案說明在 [aos-lock](../../../../../proto8/impls/aos-lock/README.md)；規範 NORMS N-15 的 10-29 補。
> 一個 lib（`lib/libaos-lock.a`，公開標頭 `include/aos/lock.hpp`）加一支命令列 `bin/aos-lock`。

| 哪裡 | 負責什麼 |
|---|---|
| `include/aos/lock.hpp` | 公開介面（aos-post 的 `--ordered` 連它）：`Holder`（名牌各欄）、`Seen`（鎖在不在、名牌原文、解出的物件、鎖資料夾多久沒動、inode）、`STALE_MS`＝10000；`lock_dir_of`、`identity`、`holder_of`、`to_json`、`look`、`reapable`、`try_acquire`、`acquire`、`release`；代號 `LockMissing`、`HolderBad`（`CommandUnknown` 10-30 收進 aos-util） |
| `src/main.cpp` | 命令列 `aos-lock acquire|release|show [旗標...] 目標`：持有者預設 getppid（`--pid` 換別的行程）、`--lease-ms`、`--note`、`--wait-ms`；拿不到／沒有鎖退 10；錯一行 `aos-lock: 代號 原因`、退 1 |
| `src/common/common.hpp` | 內部標頭：`now_ms`、`parse_at`（ISO 8601 UTC 到毫秒 → epoch 毫秒）；放鎖改名用的獨一無二名字 10-30 起是 aos-util 的 `aos::unique_id` |
| `src/holder/holder.cpp` | 名牌：`identity`（`$AOS_WS`→`$HOME`→`/`）、`holder_of`（`/proc` 的 ticks、`boot_id`、`utc_now_ms`）、`to_json`、`look`（stat 鎖資料夾、讀 `holder.json`）、`reapable`（`boot_id` 不同、pid＋ticks 對不上、殭屍、租約過、名牌壞且 10 秒沒動）；common 小工具的實作 |
| `src/lock/lock.cpp` | 鎖：`lock_dir_of`（結尾 `/` 或資料夾＝`/.lock`，否則＝`.lock`）、`write_holder`（`.holder.json.tmp` 再改名、不建資料夾）、`move_away`（改名成 `<鎖>.releasing.<信號>`）、`reap`（先 mkdir 收屍牌 `.reaping`〔10 秒沒動算死〕→ 再讀名牌、不同或 inode 換了就拔牌不收 → 改名再刪）、`try_acquire`（mkdir → 名牌｜收屍再試，最多三輪）、`acquire`（每 20 毫秒、steady_clock）、`release` |
| `tests/test_cli.py` | ctest `test_cli`：命令列黑箱（unittest） |
| `CMakeLists.txt`、`vcpkg.json`、`.gitignore` | 照 aos-post 改名；靜態庫＋`-static-pie` 執行檔；nlohmann-json；只連 aos-util；`bin/`、`lib/`、`build/` 不進 git |

誰連它：aos-post（`send --ordered` 的 `<信箱>/order.lock/`）。`proto8/tests/aos_bins.py` 沒列。
