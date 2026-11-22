# `knowledge/aos/cli/clock.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/cli/clock.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/cli/clock.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/The clock and its letters`**

# 時鐘與它的信

root daemon 的 `_clock` 那一列每秒推進一個時鐘檔；旁邊有一份登記表，每 N 個週期、只一次、或在牆上時間（wall-clock）的某些時刻寄信。agent 改用工具 `peek_clock` 和 `clock_register`（`aos/clock.md`）。

**`#/aos-clock: one cycle forward`**

# aos-clock：往前走一個週期

```sh
aos-clock clock && cat clock    # 1   (a missing or empty FILE counts as 0)
aos-clock clock && cat clock    # 2
```

它什麼都不印。你很少親手跑它：root daemon 把 `aos-clock $AOS_DAEMON/clock` 當成它的 `_clock` 列來跑。每走完一個週期，它就寄出 `FILE_register.json` 裡的信（見 `register`）。寄不出去的信是一行警告（`aos-clock: warning: clock register entry w2: cannot send to .../nobox: MailboxMissing ...`）；時鐘照樣推進，以 0 結束。FILE 不是數字或讀不了＝`ClockBad`，FILE 不動。其他代號：`WriteFailed`、`FlagUnknown`、`LaunchFailed`（啟動不了 aos-clock-register）。沒給 FILE＝`ArgumentsBad`。`aos-clock register ARGS...` 就是 `aos-clock-register ARGS...`（時鐘檔真的叫 register 的話：寫 `./register`）。

**`#/aos-clock-register: letters on a schedule`**

# aos-clock-register：照排程寄信

```sh
Q=stacks/root/procs/ann/queue
aos-clock-register -d stacks/root add --every 10 --box $Q ann-wake "Check data/ for new files."  # cycles 10, 20, 30 ...
aos-clock-register -d stacks/root add --after 5 --box $Q ann-once "Look again."  # once, 5 cycles from now
aos-clock-register -d stacks/root add --at +15m --box $Q ann-standup "Post the status letter."  # once, wall clock
aos-clock-register -d stacks/root add --cron "0 9 * * 1" --box $Q ann-monday "Weekly review."  # Mondays 09:00
aos-clock-register -d stacks/root ls        # ann-wake  10  procs/ann/queue  Check data/ for new files.
aos-clock-register -d stacks/root rm ann-wake
```

時鐘：`-c FILE` > `-d D`（D/clock）> `$AOS_CLOCK`；都沒有＝`ClockMissing`，兩個都給＝`ArgumentsBad`；長名稱 `--clock`、`--daemon`。登記表是它旁邊的 `CLOCK_register.json`（`ls -j` 印出 `{file, check_every, letters}`）。add 剛好要一種排程（不然＝`ArgumentsBad`）：`--every N` 在新的週期數能被 N 整除時觸發，而且留著；`--after N` 只觸發一次，從現在起 N 個週期後；`--at WHEN` 在某個本地時間觸發一次（`HH:MM`、`YYYY-MM-DD HH:MM` 或 `+10m`；過去的時間＝`ArgumentsBad`）；`--cron EXPR` 照 5 欄的 cron 式子用本地時間重複。只觸發一次的項目會自己移除。牆上時間的項目在時鐘推進時檢查，所以最多晚一個週期；樹睡著時錯過的，醒來後補寄一次。ls 的排程欄是 `10`、`cycle N`、`at TIME` 或 `cron EXPR next TIME`。信以使用者訊息的樣子送到：`[aos] clock: cycle N. TEXT`（牆上時間的：`cycle N, due TIME. TEXT`）。同名＝`EntryExists`（`--replace`）；rm 給了不認得的名字＝`EntryMissing`。信箱（box）還不是信箱時是一個警告，照樣加進去。每 `check_every` 個週期（預設 100），信箱資料夾已經不見的項目會被移除。其他代號：`RegisterBad`（登記表檔壞了）、`WriteFailed`、`CommandUnknown`、`ClockBad`。更多旗標：跑 `aos-clock-register --help`。
