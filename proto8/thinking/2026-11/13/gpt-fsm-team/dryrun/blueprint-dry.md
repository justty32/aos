# 乾跑圖紙（假工單）

← [gpt-fsm-team 入口](../../gpt-fsm-team.md)

gpt 隊（astra 指揮、sol 施工）在 aos 裡第一次乾跑用的圖紙。只要求一件極小、可機械驗收的事。

## 1. 要做的事

在 `proto8/thinking/2026-11/13/gpt-fsm-team/dryrun/target.txt` 的**最後**加一行，內容逐字是：

```
T01 done by sol
```

- 只動這一個檔；其他任何檔都不動。
- 原有的那一行不改。
- 加完後檔案共兩行，結尾有換行。

## 2. 驗收

```
tail -n 1 proto8/thinking/2026-11/13/gpt-fsm-team/dryrun/target.txt
```

預期輸出逐字是 `T01 done by sol`；`wc -l` 是 2。

## 3. 拆單

一張工單就夠（T01）。
