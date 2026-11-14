# 清淨時段小工具（11-14）：repo-aos 自己的「暫時免打擾」，擋 new_mail、kernel_hold 兩種通知，時段結束合併寄回

← [11-14 日索引](README.md)｜來源：頂層轉的使用者原話（下）、[mail_notify](../11/mail-notify.md)

## 使用者原話（11-14，頂層轉，逐字）

「太多的aos信件通知，你可以自己寫個腳本或小工具，讓自己有個暫時的清淨時段，專心處理事情」「派claude subagent去做也可以」

## 結論

- 三支程式，都在 `wf/tools/`：`quiet.py`（指令＋共用函式）、`quiet_hook.py`（before_queue）、`quiet_tick.py`（on_clock，每 60 秒）。測試 `wf/tools/tests/test_quiet.py`（7 題，過）。
- 用法：開 `python3 ~/repo/aos/wf/tools/quiet.py 30m`（也收 `90s`、`1h`、`1h30m`）；關 `python3 ~/repo/aos/wf/tools/quiet.py off`；看 `quiet.py status`。stack 預設取 `$AOS_STACK`（在 repo-aos 自己的 Bash 裡就是它），可用 `--stack` 指定。
- 狀態都在 `<stack>/quiet/`：`until.json`（到幾點，epoch 秒）、`deferred.jsonl`（被擋的通知：時間＋原文）。
- 清淨期間擋：開頭 `[aos] new_mail`、`[aos] kernel_hold`。放行：new_mail 的寄件人欄含 `xiaosi`（不分大小寫、子字串）；其他所有訊息（人打的、不是 `[aos]` 開頭、cross-session、`[aos] goal`、`[aos] quiet_over` 本身）。沒開或過期一律放行；hook 讀不懂事件、寫不進檔也放行（寧可吵、不吞）。
- 時段結束後 tick 把暫存的合成一則：`[aos] quiet_over: N notices held during the quiet time: new_mail xA (M new letters; senders: …); kernel_hold xB (letters: …). Nothing was lost: …`，寄成了才清空；寄失敗併回 deferred、下一分鐘再試。`quiet.py off` 後也走同一條路（一分鐘內合併寄回）。
- 訊息用英文：頂層給的格式是中文，但使用者規矩「程式輸出一律英文」，照規矩；格式其餘照給的（暫存則數、new_mail ×a 與寄件人、kernel_hold ×b 與 letter 名單）。
- 被擋的只是「通知」：信還在信箱、kernel_hold 請求還在 gate。驗過：測試 `test_a_held_kernel_request_stays_at_the_gate` 用真的 kernel_gate 站，通知被丟掉後 `kernel_gate ls` 仍列著、`requests/cur/<letter>` 還在、合併訊息列出 letter 名、之後 `pass` 照常。kernel_gate 通知過就記進它的 notified.json，不會重發，所以靠 quiet_over 這則補回來。

## 暫存樹實測（`~/code/quiet-1114`）

- 起一台暫存 daemon（只有 `_clock`）＋一隻 agent-fsm（範本複本，`brain.py` 換成永遠退 10 的假腦），掛 `quiet_hook`、`quiet_tick`（on_clock 改每 1 秒，其餘同活樹）。經 `aos-post` 往它的 queue 寄訊息，看 history.jsonl：
  - 沒開清淨：new_mail 進 history。
  - 開 15 秒：new_mail（bob, amy）、kernel_hold 被丟（`mailbox_warning.txt` 記「dropped by hook quiet_hook」）、deferred 兩行；xiaosi、`xiaosi-digest`、人打的、`[aos] goal`、`[xsession]` 全進 history。
  - 到期後 tick 合併寄出一則、deferred 清空；`status` 顯示 off、0 held。
  - 過期後 new_mail 照進。`off`、壞的時長（`5x` 報 ArgumentsBad、退 1）也驗過。
- 踩到：暫存 daemon 的 agent 要 `AOS_CLOCK`（`env.sh` 要 export 成 `<daemon stack>/clock`），否則 on_clock hook 只警告「not checked」；補上後重起 daemon 才動。
- 收行程：`aos-daemon-ctl -d ~/code/quiet-1114/root/.stack shutdown`（下之前核對 pid 的 cwd 在暫存夾）；活樹 daemon 一台沒動。

## 活樹

- `~/aos-home/ws/.stack/procs/repo-aos/hooks.json` 加兩筆（`aos-agent hook -t repo-aos add`）：`quiet_hook`（before_queue，timeout 5000、on_error continue）、`quiet_tick`（on_clock，every_ms 60000、timeout 10000、on_error continue）。handler 直接指 repo 的 `wf/tools/` 絕對路徑，所以改 repo 裡那三檔＝改活樹，改時先寫暫存檔再改名。
- 備份：`~/.aos/saves/tree-swap/quiet-1114-083239/hooks.json`（掛之前的原樣）。diff 只多那兩筆；`kernel_gate`、`mail_notify`、`timer` 沒動。
- 掛上後**沒開清淨**；由頂層自己 `quiet.py 30m` 開。
- 拿掉：`aos-agent hook -t repo-aos rm quiet_hook`、`rm quiet_tick`（或把備份抄回去）。

## 已知限制

- 時長到了只靠 tick（每 60 秒一次，且 eca 等 CLI 回答時不檢查），所以合併訊息最多晚一分鐘多；不影響「到期就不擋」（hook 自己比時間）。
- 擋下 kernel_hold 期間，gate 請求若帶 `queue_wait_ms`，寄件方到期照樣被站拒絕，清淨時段不延長它。
- 寄件人欄超過五個時 mail_notify 寫「and N more」，xiaosi 若排在被省略的那幾個裡不會被認出（照擋；信還在信箱）。

## 自動回信與分享版（11-14 晚）

使用者原話（頂層轉，逐字）：「好，你也可以弄個自動回信工具...www。」「你做的這個工具也可以分享給大家。」

- 新增 `wf/tools/autoreply_tick.py`（on_clock，每 60 秒）：只看 `<stack>/mailbox/new`、不收信。清淨中、而且信是這段清淨期間來的 → 回 PROGRESS「[auto] <自己> is in quiet time (until HH:MM): letter received, will be handled later」，附「要緊的改寄 <to>，status 標 NEEDS-USER 或 BLOCKED」。寄件人符合 `redirect.senders`（repo-aos 設 `ok-*`）→ 回「reports should go to xiaosi」，同寄件人一小時一次；兩條同時成立合成一封（算提醒過）。不回：自己、urgent_senders、no_reply_senders、title 開頭 `[auto] ` 的信（兩邊不會互相回）。回信地址取原信 reply_to，`--in-reply-to` 帶原信名。
- 狀態 `<stack>/autoreply/`：`replied.json`（信被讀掉就移除）、`reminded.json`、`count.json`（`quiet.py status` 多印「quiet auto-replies sent this quiet time: N」，新一段清淨歸零）。
- 分享化：誰算要緊、不回誰、ok-* 改寄誰，不再寫死，放 `<stack>/quiet/config.json`（`self`、`urgent_senders`、`no_reply_senders`、`redirect{senders,to}`、`autoreply`）；沒設定＝沒有人特別、全部照擋照回。`quiet_hook.py` 原本寫死的 xiaosi 改讀 config。repo-aos 的 config 照原值（urgent／no_reply＝xiaosi、redirect ok-*→xiaosi）。
- `quiet.py install [--no-autoreply]`／`uninstall`：走 `aos-agent hook -t <stack 資料夾名>` 加減三個 hook，並寫預設 config.json；stack 取 `$AOS_STACK` 或 `--stack`。agent 看的英文說明：`wf/tools/quiet-README.md`。
- 測試：`wf/tools/tests/test_autoreply.py`（10 題）＋ test_quiet.py 補 config；全部 52 題過。暫存 daemon `~/code/autoreply-1114`：install 後 hook 都在、清淨中 bob／ok-kf 各回、xiaosi／自動回信不回、同一封不回二次、status 計數 3、uninstall（連跑兩次）乾淨；daemon 已 shutdown。
- 活樹：先把 repo-aos 的 `quiet/config.json` 寫好（因為 quiet_hook 改讀它，否則 xiaosi 不再放行），再加 `autoreply_tick` 一個 hook（every_ms 60000、timeout 15000、on_error continue）。備份 `~/.aos/saves/tree-swap/autoreply-083754/`（hooks.json 原樣＋quiet 資料夾）。其他 hook 沒動。拿掉：`aos-agent hook -t repo-aos rm autoreply_tick`（或 `quiet.py uninstall` 會連 quiet 兩個也拿掉）。
- 限制：autoreply 只回「這段清淨期間來的」信；清淨前就在信箱的不回。on_clock 在 agent 等 CLI 回答時不檢查，所以回信最多晚一分鐘多。
