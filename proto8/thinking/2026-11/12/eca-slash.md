# eca 的 slash 指令（11-12 公司 WSL）：實測 claude／codex 的 /clear、/compact、/status、/usage、/exit，修成 aos 跟上 CLI（畫面 hook 跟 id、/clear 連 history 清；say／chat 也認；codex 有畫面）

← [11-12 日索引](README.md)｜試驗場搭法 [playground](playground.md)

## 使用者原話（逐字）

- 「你自己幫我試。我這邊說一下claude code cli一些我常用的slash指令：/compact, /exit, /clear, /usage, /status。然後codex cli也一樣。」
- 「弄好後能修就修」
- 「連 aos 那邊的歷史也要一起清，eca就是要同步，eca就是會變成以他為主，aos體系要盡量跟上。codex要做畫面。然後aos-say/listen我希望也能支援這些」
- 「chat也要」

## 結論

- **修前**：畫面裡 `/status`、`/usage`、`/compact`、`/exit` 都沒事；**`/clear` 會接錯對話**——claude 換新 session id，hook 只在 `session.txt` 空著時寫，aos 照記舊 id；畫面開著時經 aos 問的是清之後那段（答 NONE），畫面一關再問就接回清之前那段（答出暗號 PLUM-7），清之後講的那幾輪接不上。say 送 slash 指令：claude 的 `/clear` 沒效（id 不記）、`/status`／`/exit` 回「isn't available」，codex 全部被當成一般題目丟給模型。codex 身在試驗場被拿掉畫面。
- **修後**（三個 commit，見文末）：畫面 hook 看到 id 換了就改記，claude `/clear` 連 aos history 一起清；`aos-agent say`／`listen`／`chat` 送這五個指令都有對應效果；codex 身有畫面（範本本來就有，只是試驗場腳本刪了它；再加一條：codex 取標題的旁支 thread 不記）。
- 臨時樹 `/tmp/slash-1112/pg`（照 playground 搭法、工作區新路徑，claude 跳信任提示，在 aos 開的畫面裡選 Yes 一次）；eca_bob（haiku、範本預設花費上限）、eca_cody（gpt-6-luna、workspace-write）。沒加任何全繞過權限旗標。

## 每個指令（實測，claude 2.1.322、codex 0.167.1／0.167.2）

| 指令 | claude 畫面 | codex 畫面 | 非互動（`claude -p`／`codex exec`） | 修後經 aos say／chat |
|---|---|---|---|---|
| `/status` | 顯示設定面板（版本、session id、cwd、登入方式、組織、帳號、模型、MCP）；不觸發 hook、檔都不變 | 顯示模型、目錄、權限、帳號、session、context、週額度 | claude：「isn't available」；codex：當題目答 | aos 自己答：kind、model、對話 id、畫面開關、history 幾則、transcript 路徑 |
| `/usage` | 顯示本 session 花費與額度百分比；不觸發 hook | 選單（看用量、重置） | claude 認得、印額度（不花錢）；codex 當題目 | claude 另起一次 `claude -p --no-session-persistence` 原樣回；codex 回一句沒有 |
| `/compact` | 同一個 session id、同一個檔多一行 compact_boundary；沒有 UserPromptSubmit／Stop；之後經 aos 問暗號照答（摘要保住） | 同一個 thread、沒有 notify | claude 認得（同 id、result 空）；codex 當題目 | claude 照一般 `--resume` 交給它；codex 刪 session.txt、下一句開新 thread 帶 aos 紀錄 |
| `/clear` | 新 session id（新檔）；**修前 aos 不知道**（見結論）；修後 SessionStart(source clear) 改記新 id、history 清空（原文搬 `history_removed.jsonl`），畫面開著、關掉後再問都答 NONE | 新 thread（下一輪才建檔）；修後下一輪 notify 帶新 id、改記；history 不清 | claude 回新 session id（舊的照樣能 resume），aos 原本不記；codex 當題目（答「我清不了」） | history 搬走、刪 session.txt、下一句開新對話；畫面開著不代打、回一句 |
| `/exit` | CLI 結束、tmux 跟著沒了（socket 檔留著、`alive()` 照判沒開）；`ctl ls` 照 running；下一句走非互動、接同一段 | 同左 | claude：「isn't available」；codex 當題目 | 畫面開著（沒人接著）就關；沒開回一句 |

旁證：hook 只在一般一輪送出（UserPromptSubmit）與講完（Stop）時叫，slash 指令兩個都不觸發；claude 另有 SessionStart（source startup／resume／clear／compact）。codex 的 notify 每輪一次，**但畫面替對話取標題時另開一條旁支 thread 也叫 notify**（`input-messages` 是「Generate a concise, single-line task title…」、`last-assistant-message` 是 `{"title": …}`，沒有 rollout 檔），有時比真的那則先到——不濾掉的話第一輪會記錯 thread id、turns.jsonl 多一行標題 JSON。

## 改了什麼

1. **畫面 hook 跟上**（`lib/agent/cli_session.py`）：多註冊 SessionStart；`follow_session`＝id 跟 session.txt 不同就 `mark_session` 改記（原本只在空著時寫）；SessionStart source startup 照舊不記（新對話第一輪才記，保住 ask 的 reseed）；source clear＝`clear_history`：history 原文照 `aos-agent history rm` 的規矩每則一行 `{"removed_at", "op": "clear", "line", "message"|"raw"}` 接到 `history_removed.jsonl`、history 換成空檔、刪 `.history_sum`（不然下一輪當成 history 被改過、又丟掉新對話）；工具形（stack＝小格）不動 history。codex notify 的 thread 沒 rollout 檔＝旁支、整則不記。
2. **say／listen／chat**（`cmd/aos-eca/bin/aos-eca-turn` ⑭）：一批只有一封、內容去頭尾空白剛好是五個之一＝aos 這層做，照一般一輪記 history（user 那封＋一則 `[aos] slash: …`；`py/aos_flags.py` 的 NOTE_KINDS 加 `slash`）、收信、after_queue 照跑；listen、chat 不用改（同一條路）。
3. **codex 畫面**：程式不用改（`start()` 本來就有 codex 那條、範本有 `screen/`）；試驗場刷新腳本拿掉刪 screen 的兩行（[playground](playground.md)），範本說明補一段。

測試：`lib/agent/tests/test_cli_hook_follow.py` 6 支、`cmd/aos-eca/tests/test_slash.py` 9 支（假 CLI）；實跑見上表。

## 代定（我選的，可翻）

- S1 只有「一封信剛好是指令」才當指令；多封一批或後面帶字＝一般題目（`/clear\n\nhello` 照原樣交給 CLI）。
- S2 `/clear` 之後 history 留這一問一答（listen 要拿得到回答），下一句的新對話開場會帶這兩則（`--- record: 2 messages ---`）。
- S3 畫面開著時 say 送 `/clear`、`/compact` 不代打、回一句請人在畫面上打或先關畫面（對話在畫面裡；代打要貼進畫面但等不到 hook，且跟 hook 清 history 會搶）。
- S4 `/compact` 不動 aos history（CLI 壓的是它自己的 context；aos history 是完整紀錄）。codex 的 `/compact`（非互動）＝丟掉 thread、下一句帶 aos 紀錄開新的（上限 `reseed_bytes`），等於拿 aos 的紀錄當壓縮版。
- S5 `/exit` 經 say＝關畫面（CLI 結束的意思）；不停掉這隻（停用 `ctl stop`）。有人接在畫面上＝不關。
- S6 `/usage` 經 say 另起一次 `claude -p`，不碰這隻的對話；codex 沒有非互動的對應，回一句。
- S7 clear 的原文檔沿用 `history_removed.jsonl`（同 history rm），op 叫 `clear`。

## 待使用者裁

- Q1 **codex 畫面的 `/clear` 要不要也清 aos history**：codex 沒有清的事件，只能在下一輪 notify 看到 id 換了；換 id 也可能是 `/resume` 到別段。可行的最小做法：新 id 的 rollout 只有這一輪＝當成開新對話、清掉這輪之前的 history（但這輪 user 那則要留，得改成「清到倒數第一則 user 之前」）——這是一條新規則，所以先沒做。
- Q2 S3 要不要改成「畫面開著也代打」（貼進畫面、不等回答、回一句已送出）。
- Q3 `/compact` 要不要在 aos history 留一筆標記或換成 CLI 給的摘要（claude 的摘要在 transcript 的 isCompactSummary 那則）。
- Q4 fsm 身要不要一致（不在這次範圍，沒做）。

## 沒試到

- 人真的 `aos-agent open` 接進畫面（要終端機）：改用 `--detach`＋`tmux send-keys`，同一個 tmux。
- claude 畫面的 `/resume` 換到別段：程式照 follow_session 會跟，沒實跑。
- 使用者直接在工作區自己開 `codex`／`claude`（不經 aos）：那是另一個 thread／session，aos 不知道、也不受影響（aos 只認 session.txt 那段）；沒另外實跑。

## commit

- `a030ee253` 畫面 hook 跟上（①）
- `57afcd827` say／listen／chat 支援（②）
- 本篇與 codex 畫面說明（③）見 SESSION-LOG 那行
