aos-comm 是 comm/1 協議的命令列；本批（board-1114 批 1）只有布告欄 `board set|clear|wait|show|ls` 與 `check`。

# proto8/cmd/aos-comm — aos-comm：布告欄（comm/1）

← [cmd](../README.md)｜圖紙：[board-1114](../../thinking/2026-11/14/board-1114/)（02 稿 §一、§2、§5.2、§5.3、§7；03 計劃；05 採納表 A2、A7、A13、A14、A16、P1；衝突時 05 優先）｜格式：[schema/comm/1](../../lib/schema/comm/1/README.md)

每隻 proc 在自己的 stack 貼一張布告欄 `<stack>/board.json`（`format: board/1`）：在忙什麼、能不能打擾、在等誰。讀寫與算法都在 [`lib/aos/comm`](../../lib/aos/comm/__init__.py)，這支只派發與印；給腦用的是 `board_set`、`board_clear`、`board_wait`、`board_read`、`board_ls`（[`lib/agent/board_*`](../../lib/agent/board_set/_entry)，包 [`lib/packs/comm.json`](../../lib/packs/comm.json)），都是這支的純包裝。信件分級、頻道、`comm_tick` 是之後的批。

```
aos-comm [-s STACK] board set MODE [TEXT...] [--doing S] [--back WHEN] [--back-text S] [--for WHEN]
                    [--accept LEVEL] [--allow-from N,N] [--wake] [--deputy NAME] [--clear-on-start] [--by self|auto|user] [-j]
aos-comm [-s STACK] board clear [--by B] [-j]
aos-comm [-s STACK] board wait WHO WHAT... [--ref LETTER] [--level urgent|normal|low] [--by B] [-j]
aos-comm [-s STACK] board wait --done WHO [-j]
aos-comm [-s STACK] [-d DAEMON] board show [NAME | user | me] [-j]
aos-comm [-d DAEMON] board ls [--deep] [--only dnd|away|waiting|waiting-user] [-j]
aos-comm check FILE|LETTER_DIR [--schema board|letter-comm|channel|channel-members] [--builtin] [-j]
```

例：

```sh
aos-comm board set dnd "running the full tests, no new work until they finish" --doing "ok-board batch 1" --back 1h
aos-comm board wait user "decide the six board questions" --level normal
aos-comm board show                      # 我的；show bob＝bob 的；show user＝使用者的
aos-comm -d ~/aos/.stack board ls        # bob	dnd	tests	user	-   …最後一行是計數
aos-comm board wait --done user
aos-comm board clear
aos-comm check ~/aos/procs/bob/board.json
```

- **我的 stack**：`-s/--stack`（子命令前後都收）＞ `$AOS_STACK`；`$AOS_STACK` 形如 `<root>/tools/<名>` 且 `<root>/mailbox` 在＝`<root>`（工具小格認回叫它的那隻 agent，05 A2），否則就是它本身；都沒有、或資料夾不在＝`StackMissing`。不叫 `aos-agent ctl who`。
- **別人的**：`show NAME` 用 `aos-agent [--daemon D] ctl where NAME` 拿它的 stack（`-d` 傳給 `--daemon`；沒給照 aos-agent 自己的找法：`AOS_KERNEL`、`AOS_DAEMON`、`./.stack`）；查不到＝aos-agent 的錯原樣轉（`InstanceMissing`…）。`user`＝使用者專區 `$AOS_USER_ZONE`（沒設＝`~/.aos/user`）底下的 `board.json`，跟 aos-user、user_zone_guard 同一套；`me` 或不給＝自己。
- **寫**（set、clear、wait）：鎖 `<root>/comm/board.lock`（flock，沒有 `comm/` 就建；05 A13），讀舊的、改、寫暫存檔 `board.json.tmp.<pid>` 再 rename——讀的人不必加鎖、永遠讀到完整一份。每寫一次 `seq` 加一、`updated_at` 換成現在（UTC 毫秒）、`by` 預設 `self`。寫前照 schema 自驗（`ArgumentsBad`、`BoardFull`＝等待滿 20 筆、`BoardTooBig`＝超過 16 KiB）。舊檔讀不懂＝當沒有、從空的寫起，不擋人。
  - `set` 整張換掉：沒給的欄位清空，**`waiting_on` 保留**；`dnd` 沒給 `--for` 預設 2 小時到期、`away` 12 小時；`here`／`busy` 不寫到期（讀的人照 `updated_at`＋24h 算）。WHEN＝`30m`、`8h`、`2d`（從現在起）或帶時區的 ISO 8601 時間。
  - `clear`：mode `here`、清掉文字與等待。
  - `wait WHO WHAT`：加一筆 `{who, what, since_at[, ref][, level]}`；`--done WHO` 拿掉 WHO 的每一筆，一筆都沒有＝不寫、沒輸出、退 10。
  - **未知鍵**（含 `ext`）寫的時候一律照搬。
- **讀**（show、ls）照 06 §7.3 四步（05 A14）：1. 沒檔＝沒貼（常態，不是錯）；讀不了、JSON 壞、`format` 不是 `board/1`＝重試一次，還不行就當沒貼、stderr 提醒一行。2. `updated_at` 比現在晚超過 5 分鐘＝當成現在、標 `clock_odd`。3. 過了 `expires_at`，或沒 `expires_at` 而過了 `updated_at`＋24h＝`stale`（**不分 mode**，05 A7）：文字照顯示，mode 算 `here`，`waiting_on` 不算數。4. daemon 表上 phase 是 `sleeping`／`stopped`＝`asleep`，mode 算 `away`。另外 `back_at` 已過＝`overdue`。`show` 併表上那一列的 `live: {phase, busy}`；查不到表就不併、不報錯。未知鍵讀的時候忽略。
- **ls**：`aos-agent ctl ls --json` 那張表逐隻讀，一行 `NAME TAB MODE TAB DOING TAB WAITING FOR TAB BACK`（沒有＝`-`；MODE 後註 `(stale)`、`(asleep)`、`(no board)`），最後一行計數（幾隻、幾隻 dnd、away、在等人、在等使用者）。`--deep`（02 §2.5）：哪一列的 stack 自己有 `procs_state.json`（跟 aos-agent ctl 認 daemon stack 同一條）就用 `aos-agent --daemon <那個 stack> ctl ls --json` 再列它那張，名字寫成 `上層/名`；廣度優先、記走過的 stack 防繞圈、最深 5 層、最多 500 隻，超過標 `truncated`；下層那張列不了＝stderr 提醒、照走別的。
- **check**：哪份 schema 照 `--schema`；不然是信（資料夾裡的 `letter.json`，或檔名 `letter.json`）就驗 `body.comm`（沒有 comm＝普通信，算過）；再不然照檔的 `format`。有 Python `jsonschema` 就用它（另查 date-time），沒有或 `--builtin` 用內建小驗證器（只認這四份 schema 用到的關鍵字，見 [schema README](../../lib/schema/comm/1/README.md)）。過＝印 `ok …`、退 0；不過＝一行一個 `指標: 原因`，再 `CheckFailed`。
- **輸出**：英文，預設一行一項（show 是 `key: value`），`-j/--json` 給程式（show 是一個物件 `{who, stack, board, mode, posted, stale, clock_odd, overdue, asleep, waiting_on, live}`；ls 是 `{rows, count, truncated, skipped}`）。
- **錯**：stderr 一行 `aos-comm: error: 代號 原因`、退 1；沒東西（`wait --done`）退 10（同 aos-mailbox）。代號：`ArgumentsBad`、`FlagUnknown`、`CommandUnknown`、`StackMissing`、`BoardFull`、`BoardTooBig`、`WriteFailed`、`FileMissing`、`ReadFailed`、`JsonBad`、`SchemaMissing`、`SchemaBad`、`CheckFailed`、`LaunchFailed`、`CommandFailed`；aos-agent 的錯（`InstanceMissing`、`DaemonMissing`…）原樣轉。
- 需要 PATH 上有 aos-agent（`show NAME`、`ls`、`show` 併 live 才用到）。純標準庫（`jsonschema` 選用）；import `py/aos_flags`、`lib/aos/comm`。
- 測試：`python3 proto8/cmd/aos-comm/tests/test_comm.py`（四步：缺檔、壞檔、過期含 here、時鐘怪、sleeping 併入；set 保留 waiting_on；併發寫用 flock；agent 根認 `tools/<名>`；`--deep`；check 樣本兩種驗證器都對）；五支工具：`python3 proto8/lib/agent/board_set/tests/test_board_tools.py`。測試的暫存夾不刪（使用者 11-14 不刪規則），用 `TMPDIR` 指到要放的地方。
