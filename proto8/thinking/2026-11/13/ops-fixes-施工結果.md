# 線巳施工結果（11-13）：ops-agent 六點建議裡使用者裁要做的幾件——信的留底進工作區（A1）、範本 README 指到 CLI 自己的 hook（A2）、畫面的環境變數（B1）、flags 裡的 `--settings`（B2）、定義自帶 CLI 設定（B3）

← [11-13 日索引](README.md)｜出處：[ops-agent-six-suggestions](ops-agent-six-suggestions.md)（三題的裁定記在那份的三題下面）

## 使用者原話與裁定

- 11-13 對 ops-agent-six-suggestions 三題的回覆（逐字）：「都按照建議」——第 1 題乙（定義可以自帶 CLI 設定）、第 2 題乙（索引檢查工具先讓 ops-agent 自己寫，我們不做）、第 3 題甲（收信、寄信都能在工作區留一行）。
- 11-13 在 ops-agent 畫面上直接對它說的（經 ops-agent 來信轉述，逐字）：「我覺得沒差，eca的bash工具，就是讓eca自己的機制擋。頂多加個hook，在eca跳yes/no的時候幫忙接住，寄信給特定目標處理。這個之後再做，這有點麻煩。我覺得現在就是勇敢一點，就全面開放。後面再來做這塊。」

## A1 信的留底進工作區（第 3 題甲）

結論（現況）：

- 給腦的工具：`mailbox_read` 的 `keep` 除了 `true` 也收一個檔名；`mailbox_send` 多一個選填的 `keep`（檔名）。檔名從工作區算（比照 `self_history` 的 `"keep": "FILE"`）。每封信在那個檔追加一行 JSON（jsonl）。沒給、給 `true` 的行為跟以前逐字相同。
- 人用的指令：`aos-mailbox read --keep-to 檔`、`aos-mailbox send --keep-to 檔`（可跟 `--keep` 併用）。
- 一行長這樣：收信 `{"kept": "received", "letter", "sent_at", "in_reply_to", "from", "to", "status", "title", "what", "outputs", "not_done", "decide"}`；寄信同一組鍵、`"kept": "sent"`。
- 寫不了＝`WriteFailed`：收信那邊信留在信箱、下次照樣讀得到；寄信那邊檔開不了就不寄。

代定（可翻案）：

1. **留底那行不放這台機器上的絕對路徑**：沒有 `sender`、`reply_to`；`to` 是路徑（寄到 `box`）時也不放。依據：出處 03 檔「建議留底那行不放 `sender`／`reply_to` 的絕對路徑，只留 `from`／`to` 名字與信名」；`to` 是路徑時取最小＝整個鍵不寫（不另外發明改寫規則）。後果：留底檔可以直接進 git，但看不出要回信到哪——回信要在讀信當下做（印給腦看的那份照舊有 `reply_to`）。
2. `mailbox_read` 的 `keep` 給檔名時**只進檔、不另外留在 `mailbox/archive/`**（一份就好；兩邊都要的人用指令 `--keep --keep-to`）。
3. 每行最前面多一個 `kept`（`received`／`sent`），因為收、寄接在同一個檔。
4. 寄信那行的 `sent_at` 讀自剛寄進對方信箱 `new/` 的那封；對方在這一瞬間已經拿走＝`null`。
5. 上層資料夾不在不替人建（＝`WriteFailed`）。
6. 寄信是「先開檔、寄、再寫那行」：寄出後才寫不了（例如磁碟滿）＝`WriteFailed`，原因句開頭 `letter 信名 was sent, but:`。
7. 格式 jsonl 照出處檔的代定。

動的檔：`cmd/aos-mailbox/aos_mailbox/__init__.py`、`lib/agent/mailbox_read/`、`lib/agent/mailbox_send/`（`_entry`、`_tooldef.json`、`_metainfo.json`）、兩支測試、`cmd/aos-mailbox/README.md`、`lib/docs/03`、P-48 一句、知識庫 `aos/mailbox.json#/tools`（線辰早上補的「寄出的信沒有留底」「`read --all --keep -j >> FILE`」兩條改成現況）、`aos/cli/mailbox.json`、`aos/errors/common.json#/mail`。

測試：新增 `test_mailbox.py` 的 `test_keep_to_appends_one_json_line_per_letter`、`test_keep_to_unwritable_takes_and_sends_nothing`，`test_mailbox_tools.py` 的 `test_keep_file_in_workspace`（外加 `test_refusals` 兩列）。拿 HEAD 的程式跑新測試：`FAILED (failures=2)`、`FAILED (failures=1)`；改後 `Ran 7 tests … OK`、`Ran 4 tests … OK`。

## A2 範本 README 指到 CLI 自己的 hook

`templates/eca-claude/README.md` 加一段「權限與擋 CLI 自己的工具」：範本是全面開放、aos 的 hook 看不到 CLI 自己的工具、要擋用 CLI 自己的 hook（指到知識庫 `aos/cli/eca.json#/cli_hooks`），附出處 02 檔那支最小範例（`host_gate.py`）。範本本身不帶任何這種 hook。

## 生效表

| 改了什麼 | 什麼時候生效 |
|---|---|
| `cmd/aos-mailbox`（`--keep-to`） | 存檔即生效（`~/.local/bin/aos-mailbox` 連到 repo）；只多旗標，沒給時行為不變 |
| `lib/agent/mailbox_read`、`mailbox_send`（`keep` 收檔名） | 等 `~/aos-home/lib` 重抄；之後 agent 的 aos-mcp 要重起才看到新的工具說明（下一輪 `claude -p` 或重開畫面） |
| 知識庫、範本 README | 等 `~/aos-home/knowledge`、`templates` 重抄 |
