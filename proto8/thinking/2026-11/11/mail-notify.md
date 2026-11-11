# mail-notify：信箱有新信時用 on_clock hook 提醒自己（11-11，線 I）

← [2026-11-11](README.md)｜[thinking](../../README.md)｜hook 的 on_clock 本身見 [clock-hook](clock-hook/README.md)

## 使用者原話與裁定（11-11）

- 「對了，hook這塊，我記得有"當新信來"這個時機對吧。agent之間傳訊這塊，可以用這個。就是說，agent之間傳訊，有父子之間的直接aos-say/listen，這是比較底層的直接操作history，而mailbox這塊就是把信頭過去，對方agent自己決定啥時候要呼叫工具看信箱。我們可以透過hook，當有新信來的時候執行一次aos-say "[aos] new_mail: you got a new mail from xxx"這樣。當然，具體這是可調整的，agent自身也可以調整hook，類似免打擾」
- （頂層更正：現在沒有「信箱有新信」這個時機。）選項框：
  - 怎麼做（使用者自己寫）：「用on_clock。不過我記得on_clock好像也可以設置多個間隔。就是說你知道板子上有除頻器...好吧，不太對，但反正就是有所謂的基礎間隔，然後我們可以在基礎間隔之上，去設置其他。或是乾脆多個間隔。」（頂層回覆：現在就是這樣——daemon 時鐘是基礎間隔，每個 on_clock hook 各自除頻，一隻 agent 可掛多個。）
  - 範本預設：「預設開」。
  - 多封新信：「合成一句」。
- 間隔頂層代定 10 秒（`every_ms: 10000`）；原有 `timer` 不動。

## 驗證「多個間隔」是真的

成立，不用修。`hooks.clock_tick` 對每個 `on_clock` hook 各讀各的狀態檔 `<stack>/hooks/<名>/on_clock.json`、各算各的格數。新測試 `test_clock_hook.py::test_two_intervals_on_one_agent`：同一隻掛 `every_cycles` 2、`every_cycles` 5、`every_ms` 3000 三個，時鐘從 100 走到 120——各跑在 100,102,…,120／100,105,…,120／100,103,…,118，三個狀態檔各記自己的最後一格。實跑時範本的 `timer`（5 分鐘）與 `mail_notify`（10 秒）也同時掛著、互不影響。

## 施工

- **handler** `lib/agent/mail_notify/_entry`（照 hook_noop／hook_fire 的寫法，純標準庫、不 import py）：讀事件的 `stack`（agent 自己的 stack）→ 沒有 `<stack>/mailbox/`＝安靜退 0 → `aos-mailbox --stack <stack> peek -j` 列 `new/` 的信 → 跟 `$AOS_STACK/notified.json`（hook 自己的小格）比，沒通知過的＝新信 → 有就 `aos-post send --ordered <stack>/queue` 寄一則 `{"role": "user", "content": "[aos] new_mail: 3 new letters from bob, amy. Look with mailbox_peek, read with mailbox_read."}`（queue 沒有就先 `aos-post init`；這就是 `aos-agent say` 做的事，使用者口語的 aos-say 取同效果）→ 寄成了才記 notified。只帶封數與寄件人（最多列 5 個，其餘 `and N more`），不帶標題與內文。
- `[aos]` 種類 `new_mail` 登記進 `py/aos_flags.NOTE_KINDS`（lib 不 import py，handler 自己拼同一個格式）。
- **範本**：agent-fsm、eca-claude 的 `hooks.json` 多一格 `mail_notify`（`on_clock`、`every_ms` 10000、handler `{"$env": "AOS_HOME", "$path": "/lib/agent/mail_notify"}`、`on_error: continue`、`timeout_ms` 10000），description 加一句怎麼關、怎麼改。只有這兩份範本有 hooks.json（reviewer、judge-llm、tool-python、daemon-root 沒有）。
- **知識庫**：`aos/mailbox.json` 的 `#/check` 改寫成「出廠 mail_notify 怎麼提醒、怎麼免打擾（`self_hook rm`）、怎麼改間隔（`self_hook add` 同名 `replace`）、其他做法」，`#/check_hook` 從「自己寫一支查信 hook 的程式」改成「mail_notify 細節」——線 C 的手寫配方拿掉，只留一套說法；`_description`、`_index` 跟著改。`aos/clock.json#/choose`、`#/quiet_timer`、`aos/me/self_hook.json#/clock`、`#/handler`、`aos/definition.json`、`aos/world.json`、knowledge README 提到範本 hook 的地方補 mail_notify。`mailbox_peek` 的 tooldef 原寫「nothing tells you they arrived」改成「預設有 hook 提醒，也可以隨時 peek」。
- 文件：範本兩份 README、templates/docs/01、02、aos-agent docs/06（加「同一隻可掛多個 on_clock、各自除頻」與 hook rm／add --replace）、lib/docs/03 加一列、NORMS 附錄 4 加 `hooks/mail_notify/notified.json`（暫時、不進 image）。

## 邊緣（代定與確認）

| 情況 | 怎麼樣 |
|---|---|
| 剛起來、睡醒、重起的第一次（事件 `first`） | 代定「通知一次」：不看 notified，信箱裡還沒讀的全算新的、提醒一則 |
| agent 正在忙 | 確認：提醒只是 queue 裡的一則信，fsm 下一次輪到收信那格、eca 下一輪才看到，不打斷（daemon 實跑：提醒、腦答、下一則提醒依序進 history） |
| 自己寄給自己 | 代定照算（可能是寫給未來自己的備忘） |
| 信箱不存在 | 安靜，也不替人建信箱、不碰 queue（單元測試） |
| handler 壞掉 | 範本 `on_error: continue`：agent 的 log 一行 warning、不停 agent |
| 讀掉信之後 | 信離開 `new/`，下次跑時從 notified 拿掉，檔不會越來越大 |
| 沒讀、也沒新的 | 不重複提醒（下一個間隔安靜） |
| 只看 `new/` | 跟 `mailbox_peek` 一樣；`cur/`（讀到一半當掉的那封）不算新信 |

## 測試

- 單元 `lib/agent/tests/test_mail_notify.py` 4 支：沒信箱、沒新信安靜（連 queue 都不碰）；一封一則、再跑不重複、三封合成一句、不帶內文、`first` 再提醒一次、讀掉的掉出 notified；7 個寄件人截成 5 個＋`and 2 more`；壞事件 ArgumentsBad、`--help`。
- 實跑 `templates/tests/agent-fsm/test_mail_notify_daemon.py`（真 root daemon、1 秒一格的時鐘、假腦、範本原樣的 hooks.json）：起來第一次空信箱安靜 → 寄一封，16 秒內收到一則 `1 new letter from amy` → 連寄三封只多一則 `3 new letters from cody`，再等一個間隔不重複 → `self_hook` 同名 `replace` 改 `every_ms` 2000，寄一封 6 秒內到 → `self_hook rm`（stack 那份寫 null）後再寄，等 13 秒沒有提醒。history 裡只有三則提醒＋假腦三則回答，沒有信的內文。約 53 秒。
- 多個間隔：上面「驗證」那段。

## 真腦

（見下一段，codex gpt-6-luna。）
