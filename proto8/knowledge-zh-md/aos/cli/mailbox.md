# `knowledge/aos/cli/mailbox.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/cli/mailbox.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/cli/mailbox.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Mailbox for humans`**

# 給人用的信箱

用 aos-mailbox 從 shell 讀信和寄信。你自己的 stack 是 `-s STACK`，預設 `~/.aos/stack`（`$AOS_LINUX_USER_STACK` 可以改它；把它設成使用者區 `~/.aos/user`，見 `aos/user_zone.md`，那裡等著的信要用 `aos-user` 讀，不要用 `aos-mailbox read`）。

```sh
aos-mailbox where                         # your mailbox folder
aos-mailbox peek                          # letters waiting
aos-mailbox read [--all] [--keep | --drop] [--keep-to FILE]   # --keep-to: append one JSON line per letter to FILE
aos-mailbox send --to bob [-d DAEMON] --status REQUEST --title "one line" "what to do"
aos-mailbox send --box PATH --status DONE --title "one line" "the answer"   # WHAT `-` reads stdin
aos-mailbox send ... --keep-to FILE ...  # also append one JSON line for the sent letter to FILE
```

STATUS 的字和回覆規則跟 agent 用的一樣：`aos/mailbox.md#/Mailbox rules`。

沒有信時 read 以 10 結束。使用者區的信就算沒加 `--keep` 也會被歸檔；`--drop` 則是刪掉它（`--keep` 和 `--drop` 互斥）。send 還接受 `--outputs TEXT`、`--not-done TEXT`、`--decide TEXT`、`--in-reply-to LETTER` 和 `--from NAME`（預設 `$USER`）。`peek` 和 `read` 接受 `-j`。代號：`StatusBad`、`MailboxMissing`/`MailboxBad`（`--box` 不是信箱）、`InstanceMissing`（`--to` 沒有 stack）、`StackMissing`、`LaunchFailed`、`CommandFailed`、`WriteFailed`、`CommandUnknown`（見 aos/errors.md）。更多旗標：跑 `aos-mailbox --help`。
