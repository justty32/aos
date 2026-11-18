comm/1 協議的四份 JSON Schema（2020-12）與樣本：布告欄、信件的 comm 物件、頻道設定、頻道成員；`aos-comm check` 拿它們驗檔。

# schema/comm/1 — comm/1 的格式

圖紙：[board-1114](../../../../thinking/2026-11/14/board-1114/)（02 稿 §7.5、§八；05 採納表 A5、A12、A16；衝突時 05 優先）。布告欄那份與 [06 給 ok-view 的 board/1](../../../../thinking/2026-11/14/board-1114/06-給ok-view的board1.md) §7.5 逐欄一致。

| 檔 | `$id` | 描述什麼 | 誰讀寫 |
|---|---|---|---|
| [board.json](board.json) | `comm/1/board` | `<stack>/board.json`（使用者：`~/.aos/user/board.json`），`format` 是 `board/1` | `aos-comm board …`、`board_*` 工具、全景頁 |
| [letter-comm.json](letter-comm.json) | `comm/1/letter-comm` | 只有信的 `body.comm`（分級、why、頻道欄）；信的其他部分不在這 | 之後的批（comm_send／comm_read）；本批只有 `check` 驗 |
| [channel.json](channel.json) | `comm/1/channel` | `<頻道 stack>/channel.json`，`format` 是 `channel/1` | 之後的批（頻道） |
| [channel-members.json](channel-members.json) | `comm/1/channel-members` | `<頻道 stack>/members.json`，`format` 是 `channel-members/1`；鍵＝成員 stack 絕對路徑 | 之後的批（頻道） |

共通：`additionalProperties: true`——**不認得的鍵，讀的人忽略、寫的人保留**；時間一律 `#/$defs/time`（ISO 8601 帶時區，寫的人用 UTC 到毫秒，同信封 `sent_at`）。schema 只管形狀；「怎麼算現在算數的狀態」（讀失敗重試、時鐘校正、過期、phase 併入）是讀的規則，寫在 06 §7.3 與 `py/aos/comm/board.py`，不在 schema 裡。

## 驗

```
aos-comm check FILE                          # 照檔的 format 認 schema；信（夾或 letter.json）驗 body.comm
aos-comm check FILE --schema letter-comm     # 指定哪份（board、letter-comm、channel、channel-members）
aos-comm check FILE --builtin                # 不用 Python jsonschema，用內建小驗證器
```

有裝 Python `jsonschema` 就用它（另給 date-time 的 format 檢查，因為它預設不查）；沒裝或給 `--builtin` 就用 `py/aos/comm/check.py` 的小驗證器——它只認這四份用到的關鍵字（`$ref` 本檔內、`type`、`const`、`enum`、`required`、`properties`、`additionalProperties`、`items`、`maxItems`、`minLength`、`maxLength`、`minimum`、`if`／`then`、`format`），碰到別的關鍵字報 `SchemaBad`，不默默放過。改 schema 加新關鍵字時要一起改它。

## samples/

每份至少一個該過（`-ok`）、一個該不過（`-bad`）；`proto8/cmd/aos-comm/tests/` 兩種驗證器都跑一遍，名字帶 `-ok` 的要過、帶 `-bad` 的要不過。

| 樣本 | 該 | 為什麼 |
|---|---|---|
| board-ok-agent.json | 過 | 06 §7.6 第一份假資料＋`waiting_on` 帶 `level`／`notified_at`／`ref`（05 P1）＋`ext` 與未知鍵 |
| board-ok-user.json | 過 | 06 §7.6 第二份（使用者那張，`by: user`） |
| board-bad-mode.json | 不過 | 沒 `updated_at`、`mode` 不是四個之一 |
| board-bad-waiting.json | 不過 | 時間沒時區、`waiting_on` 項缺 `since_at`、`level` 不認得 |
| letter-comm-ok.json | 過 | urgent 帶 why |
| letter-comm-ok-low.json | 過 | low、帶未知鍵 |
| letter-comm-bad-urgent.json | 不過 | urgent 沒 why（`if`／`then`） |
| letter-comm-bad-v.json | 不過 | `v` 不是 1、level 不認得、`via` 超過 3 |
| channel-ok.json | 過 | 一般頻道設定 |
| channel-bad.json | 不過 | 缺 `name`、時間不是時間、`join` 不認得、`keep_days` 小於 1 |
| channel-members-ok.json | 過 | 一個成員、`gone_at`／`missed_from_seq` 是 null |
| channel-members-bad.json | 不過 | 成員缺 `box`、`role` 不認得 |

讀的人遇到「不過」的檔怎麼辦不在這裡定：布告欄照 06 §7.3 當沒貼；信的 `comm` 不合＝當普通信（02 §3）。
