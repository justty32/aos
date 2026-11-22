# aos-user：使用者專區的指令與網頁（agent 寄「要你裁／驗／試／做／知道」的信進 `~/.aos/user/mailbox`，你列、看、回，回了才消）

規劃與裁定：`proto8/thinking/2026-11/13/user-zone-plan.md`。**新家在 `proto8/frontend/aos-user/`，跟著 git 走**：11-13 晚使用者裁 U12 原本放在 `~/aos-home/ws/tools`、不進 git，本體 11-18 隨舊樹刪掉；11-22 從 11-14 的抄本搬進 repo（規劃 `proto8/thinking/2026-11/22/aos-user新家-1122/`，使用者選第 1 題 a）。`proto8/frontend/bin/aos-user` 是連到同夾 `aos-user` 的符號連結，`source $AOS_HOME/env.sh` 就在 PATH 上，換台 `git pull` 就有、不用跑 `install.py`。專區的資料每台一份，留在 `~/.aos/user/`，不進 git（第 3 題 a）。給 agent 的說明在知識庫 `aos/user_zone.md`。

## 你最常用的

```sh
aos-user ls                          # 在等你的，急件在上（! 急、* 沒看過）
aos-user show 1                      # 看第 1 封（信從 new/ 移到 cur/）
aos-user answer 1 q1:a 'q2:c*' --note "…"   # 裁；* ＝不照推薦（同 decide-page；zsh 裡帶 * 的要加引號）
aos-user answer 1 --all-recommend    # 沒寫的題都照推薦（不可逆的信不吃這招）
aos-user reply 2 "一段話"             # 驗／試／做、舊格式的信
aos-user ok 3                        # 純告知：收起來，不回信
aos-user serve                       # 網頁 http://127.0.0.1:8766/（只綁本機）
aos-user notify on                   # 桌面通知開（off 關；test 跳一則試試）
aos-user ls --rejected               # 不合規矩、被退回寄件人的信
```

## 段 2：收件檢查、退信、通知（11-13 晚）

`aos-user tick` 每分鐘由 systemd --user 計時器跑一次，做四件事（11-22 起**先不裝**，使用者第 2 題選 a；沒裝時題目照樣寄得進、照樣上全景頁，少的是每小時上限、到期提醒、退信）：

1. **收件檢查**：`mailbox/new/` 裡沒檢查過的信，照 `schema/letter.json` 驗（舊格式＝`mailbox_send` 寄的照收）；同一寄件人（信封 `sender`）一小時超過 `max_per_hour` 封（預設 10）的也算不合。
2. **退信**：不合的搬 `rejected/<信名>/`（原信＋`reason.txt`），寄一封 `status=FAILED`、`title="Returned: …"`、`in_reply_to=原信` 的信回寄件人的 `reply_to`（回信地址在專區裡就不退，免得繞圈）。
3. **通知**：`new/` 裡還沒通知過的信合成一則 `notify-send`（只帶標題與寄件人）；出門模式（`door --mode away`）或 `quiet_hours`（例 `"23:00-08:00"`）只報急件，其他的留到能報時再報；看過的（已在 `cur/`）不報。
4. **到期提醒**：有 `deadline` 的信，到期前 `remind_hours`（預設 24）小時、過期各提醒一次。

狀態全記在 `log.jsonl`（`checked`／`rejected`／`notified`／`reminded`），不另開檔。`config.json` 的 `notify` 是 false 時什麼都不跳（檢查與退信照做）。

裝計時器（一次，要裝時由使用者自己下；會蓋掉 `~/.config/systemd/user/` 裡同名的舊單元）：

```sh
mkdir -p ~/.config/systemd/user
cp $AOS_HOME/frontend/aos-user/systemd/aos-user-tick.{service,timer} ~/.config/systemd/user/   # 先改單元裡的 AOS_HOME
systemctl --user daemon-reload && systemctl --user enable --now aos-user-tick.timer
journalctl --user -u aos-user-tick -n 20     # 看它做了什麼（沒事時不印）
```

給 agent 的另兩件在 repo：沒 shell 的身用 aos 工具 `user_send`（原始碼 `proto8/py/tools/agent/user_send/`，包 `aos-user send`，範本預設不掛）；eca 身可掛 before_tool hook `user_zone_guard`（`proto8/py/tools/agent/user_zone_guard/`，aos 工具寫專區 `mailbox/` 以外＝擋；只是紀律，擋不到 CLI 自己的 Bash／Write）。

<details><summary>全部子命令</summary>

| 子命令 | 做什麼 |
|---|---|
| `init` | 建專區（已有的檔不蓋）：`mailbox/{tmp,new,cur}`、`done/`、`rejected/`、`drafts/`、`door.json`、`schema/letter.json`、`config.json`、`log.jsonl`、`web/token`（0600） |
| `where` | 印專區路徑（`--zone` ＞ `$AOS_USER_ZONE` ＞ `~/.aos/user`） |
| `send --kind K [--title] [--from] [--reply-to] [--urgent] [--deadline] [FILE\|-]` | agent 寄信；先照 schema 驗，不合 `SchemaBad`、不寄 |
| `ls [--json] [--done]` | 待辦／已回；`--json` 每列 `n letter where format kind from title questions deadline urgent risk host sent_at same bad`；沒待辦退 10 |
| `show N` | 看一封；同 `dedupe_key` 的一起移進 `cur/` |
| `answer N id:key… [--note] [--all-recommend]` | 裁；每題都要答，少了＝`AnswerMissing`、存草稿 |
| `reply N TEXT` | 自由回話 |
| `ok N` | fyi（或舊格式信）收起來，不回 |
| `door [--mode normal\|away]` | 看門上公告／切出門模式 |
| `ls --rejected [--json]` | 被退的信與理由 |
| `notify [on\|off\|test]` | 桌面通知開關（寫 `config.json`）、跳一則試試 |
| `tick [--json] [--quiet]` | 收件檢查＋退信＋通知＋到期提醒（計時器每分鐘跑；`--quiet` 沒事不印） |
| `verify 回信資料夾` | 收信方驗回信：寄件人是專區、跟 `done/` 的 `reply.json` 逐欄一樣、log 有同一筆 |
| `serve [--port]` | 網頁 |

錯誤：`aos-user: error: 代號 原因`，退 1。代號：`ZoneMissing SchemaBad ArgumentsBad LetterMissing AnswerMissing ReplyToMissing MailboxMissing VerifyBad MoveFailed ToolMissing NotifyFailed CommandUnknown`（aos-post 的代號照轉）。
</details>

<details><summary>回信長什麼樣、怎麼回到原寄件人</summary>

回信用 `aos-post send --in-reply-to <原信名> <原信 reply_to>` 寄出，寄件人身分＝專區（`AOS_STACK` 設成專區、拿掉 `AOS_WS`／`AOS_CF`／`AOS_CLOCK`）。body：八個標準欄（`from=user to status=DONE title="Re: …" what outputs not_done decide`）＋ `zone answers answer_line note text via answered_at host letter_hash reply_id auth`。寄成功才把原信從 `cur/` 搬到 `done/<年-月>/<信名>/`，並寫 `reply.json`（回信副本＋`sent_as`、`sent_to`）。寄不出去（對方信箱沒了）：信留在 `cur/`、答案存 `drafts/`。
</details>

<details><summary>網頁的安全</summary>

只綁 `127.0.0.1`；Host 只收 `127.0.0.1:埠`、`localhost:埠`；POST 要表單 token 與 cookie token 都等於 `web/token`；有 Origin 就要是本機。同一個 Linux 帳號的 agent 一樣連得到，所以網頁回的不比指令列回的更可信。
</details>

<details><summary>測試</summary>

`python3 -m unittest discover -s $AOS_HOME/frontend/aos-user/tests -v`（先清掉 `AOS_*` 環境，PATH 上要有 `aos-post`；全部在暫存夾，不碰 `~/.aos/user`）。`test_zone.py`＝段 1；`test_tick.py`＝段 2（通知用假的，不真的跳）。
</details>
