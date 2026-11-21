# `knowledge/aos/cli/mailbox.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/cli/mailbox.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**

# 給人用的信箱

用 aos-mailbox 從 shell 讀信和寄信。你自己的 stack 是 `-s STACK`，預設 `~/.aos/stack`（`$AOS_LINUX_USER_STACK` 可以改它；把它設成使用者區 `~/.aos/user`，見 `aos/user_zone.json`，那裡等著的信要用 `aos-user` 讀，不要用 `aos-mailbox read`）。

```sh
aos-mailbox where                         # your mailbox folder
aos-mailbox peek                          # letters waiting
aos-mailbox read [--all] [--keep | --drop] [--keep-to FILE]   # --keep-to: append one JSON line per letter to FILE
aos-mailbox send --to bob [-d DAEMON] --status REQUEST --title "one line" "what to do"
aos-mailbox send --box PATH --status DONE --title "one line" "the answer"   # WHAT `-` reads stdin
aos-mailbox send ... --keep-to FILE ...  # also append one JSON line for the sent letter to FILE
```

STATUS 的字和回覆規則跟 agent 用的一樣：`aos/mailbox.json#/rules`。

沒有信時 read 以 10 結束。使用者區的信就算沒加 `--keep` 也會被歸檔；`--drop` 則是刪掉它（`--keep` 和 `--drop` 互斥）。send 還接受 `--outputs TEXT`、`--not-done TEXT`、`--decide TEXT`、`--in-reply-to LETTER` 和 `--from NAME`（預設 `$USER`）。`peek` 和 `read` 接受 `-j`。代號：`StatusBad`、`MailboxMissing`/`MailboxBad`（`--box` 不是信箱）、`InstanceMissing`（`--to` 沒有 stack）、`StackMissing`、`LaunchFailed`、`CommandFailed`、`WriteFailed`、`CommandUnknown`（見 aos/errors.json）。更多旗標：跑 `aos-mailbox --help`。
