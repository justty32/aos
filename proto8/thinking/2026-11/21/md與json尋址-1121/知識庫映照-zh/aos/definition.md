# `knowledge/aos/definition.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/definition.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 定義夾裡有什麼

定義是一個資料夾，說明一個 agent 是什麼（它的原始碼）。它的 `interfaces.json` 指出其他檔案在哪裡，所以別的定義可以把它們取不同的名字。下面是兩個內建範本 `agent-fsm` 和 `eca-claude` 裡的名字（用 `agent_def` 複製一份）。

- 兩個範本都有的檔案：`aos/definition.json#/files`。
- 只有其中一個有的檔案：`aos/definition.json#/only`。
- 哪些檔案你在自己的 stack 裡有自己的一份：`aos/definition.json#/overlay`。
- 兩種身體差在哪裡：`aos/body.json`。

---

**`#/files`**

# 兩個範本都有的檔案

- `interfaces.json`：其他檔案在哪裡（鍵 `tools`、`llm`、`llm_keys`、`history`、`system`，以及 `aos-agent` 底下的 `entry` 或 `screen`；最上層的 `hookeds` 和 `hooks`）。aos-agent 只讀這個來找它們。
- `_entry`：直接執行這個資料夾時跑的東西。
- `loop.json`：loop：每一拍跑什麼、拍與拍之間的停頓（`interval_ms`），以及 `on_start`／`on_stop`（它們觸發 `after_start`／`after_stop` hook）。
- `tools.json`：工具：列在 `"$override"` 裡的工具包，加上幾個 cell（`aos/packs.json`）。
- `llm.json`：腦的設定，像 `{"model": "sonnet"}`；interfaces.json 裡的 `llm_keys` 說哪些鍵算數。
- `system.txt`：系統文字。在 eca-claude 和 eca-pi 裡是兩小段（aos 是什麼、知識庫在哪裡），加在 CLI 自己的系統提示之後。
- `hookeds.json`：掛了哪些 hook（由 `interfaces.json` 最上層的清單 `"hookeds"` 指名；那裡的 `"hooks"` 指名 hook 點宣告，只供閱讀）。兩個都有 `timer`（on_clock 每 5 分鐘，什麼都不做）、`mail_notify`（on_clock 每分鐘：有新信來時發一則訊息；`aos/mailbox.json#/check`）、`brain_notify`（brain_failed：把 BLOCKED 信送到 `AOS_NOTIFY_BOX`）和 `context_wrap`（on_clock：context 夠滿時 /compact；`aos/me/compact.json`）；eca 還有 `screen_linger_start`／`screen_linger_stop`（`aos/cli/eca.json#/screen_linger`）。
- `_metainfo.json`（摘要、花費）和 `README.md`：給人看和給檢查用。
- `.env`（選用；範本裡沒有）：agent 啟動時從定義夾讀。它不會蓋掉已經設定的名字（PATH、AOS_*），除非是用 `aos-agent ctl add --dotenv-override` 加的；例如 `PATH=${HOME}/repo/aos/wf/tools:${PATH}`。

---

**`#/only`**

# 只有一個範本有的檔案

只有 agent-fsm：

- `body.json`：身體，`aos-loop loop.json`。
- `fsm.json`：四個 cell：`idle`（從佇列拿信）、`think`（問腦）、`wait`（等它的回覆）、`act`（執行工具呼叫）。
- `idle.py`、`brain.py`、`wait.py`、`act.py`、`llm_settings.py`：那些 cell 的程式；`atomic_file.py`：idle 和 wait 共用的原子寫檔；`cell_common.py`：brain 和 act 共用的開頭幾步（讀對話歷史、選工具登記表）；`compact.py`：`/compact` 信怎麼處理，含 `before_compact`／`after_compact` hook 的規則（`aos/me/compact.json`）。
- `subagents.json`：`max_subagents`，你同時最多能有幾個子 agent（工具 `subagent`）。
- 定義可以一個程式都不帶：當它的 `fsm.json` 把它們寫成 `{"$env": "AOS_HOME", "$path": "/templates/agent-fsm/idle.py"}`（start-api 起手包的 `ann` 是這樣，agent.py 裡的 `fsm=std.fsm()` 也是），cell 就跑 `$AOS_HOME` 底下 agent-fsm 範本的那幾份，而它 `interfaces.json` 的 `hooks` 指向 agent-fsm 範本的 `hooks.json` 宣告，不自己帶一份。

只有 eca-claude（以及 eca-pi，一樣但少最後兩項）：

- `cli.json`：由哪個外部 CLI 跑你的回合（`kind` claude、codex 或 pi）、它的旗標，以及 `timeout_ms`（0 = 不限時）。aos 自己會加一些旗標；把其中一個寫進 `flags` 或 `print_flags` 是 `CfgBad`（codex：`--skip-git-repo-check`、`--json`、`-o`、`--output-last-message`；claude：`-p`、`--print`、`--output-format`、`--session-id`、`--resume`、`-r`、`--continue`、`-c`、`--settings`；pi：`aos/cli/eca.json#/pi`）。
- `screen/`：人用 `aos-agent open` 打開的終端機畫面。
- `compact_hook`：Claude Code 自己包在壓縮前後的 hook，觸發 aos 的 `before_compact`／`after_compact`。
- `tools_sub.json`：claude CLI 用它的 Agent 工具啟動的幫手所拿到的 aos 工具（唯讀：peek_clock、peek_now_time、math、唯讀的 json 工具、index_view）。

---

**`#/overlay`**

# 你自己的一份（overlay）

有些檔案在你的 stack 裡有一份同名的。有的話，它會疊在定義的那份上面使用。定義本身永遠不變。

| 檔案 | 你那份放的是 | 用什麼改 |
|---|---|---|
| `tools.json` | 只放差異（拿掉的工具 = null） | `self_tools` |
| `llm.json` | 只放你改過的鍵 | `self_llm` |
| `system.txt` | 整篇文字；取代定義的那份 | `self_system` |
| `hookeds.json` | 依名字列的 hook（null = 關掉） | `self_hook` |
| `subagents.json` | 只放改過的鍵 | 人 |

`reset` 會刪掉你那份，讓定義的那份重新算數。`history.jsonl` 只存在你的 stack 裡。其他檔案（`interfaces.json`、`loop.json`、`fsm.json`、`cli.json` ...）沒有你的一份：要改它們，用 `agent_def` 做一個新的定義。
