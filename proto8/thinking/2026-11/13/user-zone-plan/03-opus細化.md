# 使用者專區 opus 細化：fable 設計對到實際檔案與指令，改了六處（收件格叫 `mailbox/`、專區本身就是人的 stack、回信帶齊標準欄、沒有 shell 的 agent 怎麼寄、手機走 tailscale serve 仍只綁本機、程式源頭在 repo）

← [使用者專區規劃](../user-zone-plan.md)｜上一份 [02 fable 設計](02-fable設計.md)｜下一份 [04 施工與驗收](04-施工與驗收.md)

> 線人 11-13 晚。fable 的設計原樣留在 02，這份只寫「照實際程式要改的地方」與「每一格對到哪個檔、哪個指令」。沒施工、沒起 aos 行程、沒寫 `~/.aos`、`~/aos-home`。

## 一、對 fable 設計改的六處

| # | fable 原案 | 改成 | 為什麼（出處） |
|---|---|---|---|
| 1 | 收件格叫 `inbox/`，舊的 `~/.aos/stack/mailbox` 做捷徑指過去 | 收件格叫 **`mailbox/`**，讓 `~/.aos/user/` **本身就是使用者的 stack** | `aos-mailbox` 認「STACK/mailbox」（`proto8/cmd/aos-mailbox/aos_mailbox/__init__.py:127`），stack 可用 `$AOS_LINUX_USER_STACK` 換。專區當 stack，`aos-mailbox peek`、`aos-user` 都不用改路徑規則；捷徑對 aos-post 的 rename 與 `reply_to` 相對路徑（存「相對收件信箱根」，`impls/aos-post/docs/01-用法與元素.md`）都沒驗過，能不用就不用。舊路徑 `~/.aos/stack/mailbox` 留成捷徑只為了照舊指令寄的信不丟（待裁 U2） |
| 2 | 回信 body 只有 `from/status/answers/text…` | 回信 body **先帶齊 aos-mailbox 的八個標準欄**（`from to status title what outputs not_done decide`），再加 `zone`、`answers`、`via`、`letter_hash`、`auth` | 對方 agent 用 `mailbox_read`／`aos-mailbox read` 讀，`flat` 先印標準欄、不認得的照印（`__init__.py:232`）；少了 `title`／`what`，對方看到的是一封怪信。`what` 寫一句人話版答案（例如「q1 選 a（照推薦）；q2 選 c（跟推薦不同）：備註…」） |
| 3 | agent 一律用 `aos-user send` 寄 | 分兩種身：**有 shell 的**（claude／codex 身）打 `aos-user send`；**只有 aos 工具的**（agent-fsm、gpt 隊）第一段先照舊用 `mailbox_send {box: ~/.aos/user/mailbox, status: NEEDS-USER, …}`，專區當「舊格式」照收；第二段再加一支 aos 工具 `user_send`（`proto8/lib/agent/user_send/`，跟 `mailbox_send` 同層） | `mailbox_send` 不收多的 key（`proto8/lib/agent/mailbox_send/_entry:6`「別的鍵＝ArgumentsBad」）；agent-fsm 沒有 shell（gpt-fsm-team 設計就是這樣）。新加一支工具不算改底層 |
| 4 | 網頁「只綁 127.0.0.1」，手機推薦 tailscale | 兩者不衝突：網頁**仍只綁 127.0.0.1**，手機用 **`tailscale serve`** 把本機埠代理到私人網路；Host 檢查多收一個 tailscale 主機名 | 現有看板就是只綁本機＋Host 檢查（`wf/tools/progress_board/dash.py:141`、`answers.py:97`），照抄這個做法；`tailscale serve` 由 tailscale 自己做 https 與「只限自己的裝置」 |
| 5 | `aos-user` 放 `~/aos-home/ws/tools/` | **源頭在 repo `proto8/cmd/aos-user/`**（跟 `aos-mailbox` 同層、有測試），裝成 `~/.local/bin/aos-user`，`~/aos-home/ws/tools/aos-user` 放一條連結 | `ws/tools` 不在 git 裡，兩台各一份會走樣；使用者說「放在~/aos-home/ws/tools，大家一起用」是指 agent 找得到的地方，連結就滿足。跟原話有出入，列待裁 U12 |
| 6 | 名片放 `~/aos-home/ws/public/user.json` | 照放；另加**知識庫一節** `aos/user_zone.json`（`_description.json` 加一列、`mailbox.json` 的 NEEDS-USER 那條指過去） | 樹裡的 agent 第一個會讀的是知識庫（`~/aos-home/agents/eca_main/system.txt` 只叫它讀知識庫）；`ws/public` 還不存在、別的樹不一定有 |

## 二、專區目錄（細化版）

```
~/.aos/user/                 使用者的 stack＝專區（$AOS_LINUX_USER_STACK 指這裡）
├── mailbox/                 ★ 標準 aos-post 信箱，agent 只准寄這裡
│   ├── tmp/  new/  cur/      new＝沒看過；cur＝看過、還沒回（＝待辦）
├── done/2026-11/<信名>/     回完的：letter.json（原信）＋reply.json（我的回信副本）
├── rejected/<信名>/          不合公告的信＋reason.txt
├── drafts/<信名>.json        答到一半
├── door.json                 門上公告（公開）
├── schema/letter.json        信的 JSON schema
├── config.json               通知、安靜時段、出門模式、網頁埠
├── web/token                 網頁 POST 用的記號（0600）
├── keys/                     第 5 段才有：簽名金鑰（密語鎖）
└── log.jsonl                 流水帳：收、看、回、退、搬，各一行
```

- 舊路徑：`~/.aos/stack/mailbox` → 捷徑到 `~/.aos/user/mailbox`（待裁 U2；捷徑行不行先在暫存夾驗，見 04 段 1 第 2 步）。
- `~/.aos/log.md`、`~/.aos/say/` 不動（不知道誰在用，06 第 9 條）。

## 三、每個動作對到的指令

| 誰 | 做什麼 | 指令（第一段） | 底下其實做的 |
|---|---|---|---|
| agent（有 shell） | 問使用者一題 | `aos-user send --kind decide --title … --json q.json` | 照 schema 驗 → `aos-post send --reply-to $AOS_STACK/mailbox ~/.aos/user/mailbox < body` |
| agent（沒 shell） | 同上 | `mailbox_send {box:"~/.aos/user/mailbox", status:"NEEDS-USER", title, what, decide}` | 舊格式，`aos-user ls` 標「舊」 |
| 使用者 | 看清單 | `aos-user ls` | `peek`＋掃 `cur/`，讀 body 額外 key 排序 |
| 使用者 | 看一封 | `aos-user show 3` | 自己 `os.rename` 那一封 `new/<信名>`→`cur/<信名>`（`aos-post take` 只認領「最舊的一封」、不能指定，`impls/aos-post/docs/01-用法與元素.md:13`），記 log |
| 使用者 | 裁 | `aos-user answer 3 q1:a q2:c* --note …` | 組回信（八標準欄＋answers）→ `aos-post send --in-reply-to <信名> <原信 reply_to>` → 成功才把信從 `cur/` 搬 `done/` |
| 使用者 | 純告知收下 | `aos-user ok 5` | 不回信，直接搬 `done/` |
| 收信 agent | 讀回信 | 照舊 `mailbox_read` | `mail_notify` 一分鐘內會叫醒它（`proto8/lib/agent/mail_notify/_entry`） |
| 收信 agent | 驗是不是使用者回的（段 2） | `aos-user verify <信資料夾>` | 比對 `~/.aos/user/done/*/reply.json` 的 `letter_hash`、log 有沒有同一筆 |

**禁止**：使用者別對專區打 `aos-mailbox read`（不帶 `--keep` 會直接刪信，繞過 `done/`）。`aos-user` 啟動時對照 log，`cur/` 少了沒進 `done/` 的信就印警告。

## 四、網頁（段 3、段 4）

- `aos-user serve [--port 8766]`：Python 標準庫 `http.server`，只綁 `127.0.0.1`；跟 `aos-user` 共用同一個函式庫（`aos_user/zone.py`），不寫第二份邏輯。
- 四頁：待辦、單封、已回、公告。POST 要帶 `web/token`（第一次開頁從本機檔讀進 cookie）＋ Host 檢查。
- 手機版面：照 `wf/workflows/common/user.md:17` 的手機遠端頁風格——一張卡＝一句話問題＋兩句 ELI5＋選項鈕（推薦標星）＋意見欄＋「都不要，我寫」；why／details／出處收進 `<details>`；不放圖；頂上「全部照推薦」要二次確認、`risk=irreversible` 的不算。
- 跟桌面看板：**並存**，看板 8765 繼續管進度；看板的「待你裁」加一條連到 8766 的連結。合併要等線遷把 `wf/tools/progress_board` 搬進 aos 再說。
- 跟 claude.ai 手機看板：過渡期 `remote_sync.py export` 多推一份 `snap/zone`（各台 `aos-user ls --json`），讓出門時也看得到題；那裡答的經頂層拉回，回信標 `via: phone-relay`，授權最高只到 L1。

## 五、授權（細化）

- **同一個 uid 是事實**：家機 agent 行程全是 `lorkhan`（11-13 晚 `ps` 實查）。L1 擋得住「轉述」與「往別人信箱丟假回信」，擋不住會開 shell、刻意連 `done/` 與 log 一起造假的 agent。
- 守門 hook 只蓋得到 aos 工具（eca 的 `before_tool` 只看得到 aos 工具，知識庫 `body.json`）；claude 身的 shell 寫檔擋不到。所以 L1 寫成「紀律＋留底可查」，不吹成「擋住」。
- L2 具體做法：`ssh-keygen -Y sign -n aos-user`，私鑰 `~/.aos/user/keys/id_ed25519` 用密語鎖、**不加進 ssh-agent**；公鑰放 repo（`proto8/…` 或知識庫）當 `allowed_signers`，被偷換會留 git 紀錄。手機經 Claude 中轉那條路簽不了，所以手機答的永遠 ≤L1。
- 鐵律 2 要不要加一句，列待裁 U5、U6。

## 六、跨機（細化）

- 兩台各一份 `~/.aos/user/`，不同步（照 fable）。每封信 `host` 由 `aos-user send` 自動填 `hostname`，寄件 agent 不用管。
- 公司 WSL 的特別處：`notify-send` 在 WSL 多半沒有桌面可跳（待驗，06 第 15 條）；tailscale 公司准不准不知道（待裁 U3）。公司機第一段只做指令列＋網頁，手機先留 artifact 中轉。
