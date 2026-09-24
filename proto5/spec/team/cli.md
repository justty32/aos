← [team](README.md)

# `aos-team`：子命令一覽

```
aos-team <子命令> [參數…] [--target 團隊資料夾]
```

- 團隊資料夾：`--target`（放在任何位置都行）；沒給看環境變數 `AOS_TEAM_HOME`；再沒有＝目前資料夾。
- 成功退 0；做不到退 1，stderr 一行 `aos-team: <代號>: <白話>`；用法錯退 2。
- 分派表在 [`lib/aos_team_cli.py`](../../lib/aos_team_cli.py) 的 `COMMANDS`：子命令 → (模組, 函式)。函式簽名 `fn(團隊資料夾, 參數陣列) → 退出碼`，自己用 argparse 解。模組或函式還不在＝印「還沒做（第 N 隊）」退 1。
- 別隊只新增自己的模組；要加子命令就在 `COMMANDS` 加一行。

| 子命令 | 一句話 | 隊 |
|---|---|---|
| `init [--config FILE]` | 照 team.json 建團隊資料夾、每個成員的家（模板）；重跑只補新成員與沒生完的 | 1 |
| `start`／`stop` | 全部成員向 kernel 登記／撤銷（要 `AOS_KERNEL_HOME`）；有郵差、心跳模組就一起 | 1 |
| `ls [--json]` | 一行一個成員：模板、health、手上的單、最後一封信 | 1 |
| `rm NAME` | 拿掉一個成員：要先 stop；先記 `members/.removing-<名>.json`，再把家搬進 `members/.removed/`、名冊刪那列（不刪檔）；崩了重跑 rm 接著做，init 看到這個檔會拒跑。加 `--purge` 才真的刪掉家（先搬再刪，刪不回來） | 1 |
| `ask "一句話"` | 交給門房（route.md）：命中就直接做、沒命中投給領隊 | 1 |
| `route test [--file F]`／`route save F` | 跑門房規則的例句；save 全過才存 | 1 |
| `task ls [--all] [--json]`／`task show ID`／`task cancel ID [--reason …]`／`task reassign ID NAME` | 看任務表；取消、改派（寄申請給郵差） | 1 |
| `wait ls [--json]`／`answer Q "…"` | 看等人回答的問題；回答一題（寄申請給郵差） | 1 |
| `mail [--follow]`、`post` | 一封信一行；郵差走一次（kernel 反覆叫） | 2 |
| `verify ID`、`routine ls/add/rm`、`beat` | 驗收；心跳排程；心跳走一次 | 2 |
| `score` | 六軸自動彙整 | 5 |

## start 的掛勾

`start`／`stop` 先處理成員，再看有沒有這些模組（有才叫，沒有略過）：`aos_team_post.start(團隊資料夾)`／`stop(…)`、`aos_team_beat.start(…)`／`stop(…)`。
回傳退出碼；它們自己印自己的行。
