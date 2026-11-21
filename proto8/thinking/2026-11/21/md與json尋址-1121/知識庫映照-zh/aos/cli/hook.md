# `knowledge/aos/cli/hook.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/cli/hook.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**

# 一個 agent 上的 hook

用 aos-agent hook，在某個 agent 發生某件事時跑一個程式。它只寫那個 agent 自己的那份 `<stack>/hookeds.json`；定義的 `hookeds.json` 保持原樣。定義的 `interfaces.json` 必須在最上層指名這份清單，`"hookeds": "hookeds.json"`，否則是 `HooksMissing`（它的 `"hooks"` 鍵指名 hook 點的宣告，只供讀取）。

```sh
aos-agent hook -t bob                       # = ls: NAME TAB EVENT TAB HANDLER
aos-agent hook -t bob ls -l                 # also CONDITION TIMEOUT_MS FROM, and hooks set to null
aos-agent hook -t bob ls --json
aos-agent hook -t bob get guard
aos-agent hook -t bob add --event before_tool --condition agents_ctl --timeout-ms 5000 hooks/guard   # exit 10 blocks the call
aos-agent hook -t bob add --event brain_failed -n ping --path-json '{"$env": "AOS_HOME", "$path": "/lib/x"}'
aos-agent hook -t bob add --event on_clock --every-ms 600000 -n check hooks/check   # every 10 minutes of clock cycles; --every-cycles N, --clock PROC_OR_PATH, --config JSON
aos-agent hook -t bob rm guard              # a definition hook is set to null; an own hook is deleted
aos-agent hook -t bob reset -y              # delete the agent's own list, back to the definition's
```

- add 的旗標：`--event`（必填；不會對照任何宣告檢查）、`-n/--name`、`--condition`（只針對這些工具名稱 / 錯誤代號；可重複）、`--timeout-ms N`（預設 60000；0 = 不限）、`--replace`、`--path-json`，以及 on_clock 用的 `--every-cycles` / `--every-ms`、`--clock`、`--config`。
- 失敗的 hook（結束碼不是 0 / 10、太慢、啟動不了、stdout 不對）：在 before_queue 和 before_tool 上，這個事件就停下（agent 以 HookFailed 停止）；在其他事件上，只是一行警告；在 loop 事件（after_start、after_stop、before_run、after_run）上，loop 停止。
- 名字預設是檔案或資料夾的名字；用 `--path-json` 時 `--name` 必填。`NameBad`：空的、含 `/`、以 `.` 開頭，或是 `description`。
- 相對路徑從目前的資料夾算；不存在 = `PathMissing`。
- `HookExists`：加上 `--replace`。`HookMissing`：沒有那個名字的 hook。`HooksBad`：清單壞了。
- 事件包括 after_start / after_stop（loop 開始 / 快要結束）、before_run / after_run（包住 loop 主體的每一次執行；before_run hook 結束碼 10 會跳過那一次執行；只有在定義的 loop.json 有接上它們時才有，否則 add 會印一行警告：重新編譯並重新啟動）、before_compact / after_compact（包住 agent-fsm 的 /compact，以及帶 claude 的 eca 透過它的 compact_hook；在那裡失敗的 hook 只是警告；aos/me/compact.json）和 on_clock（需要 --every-cycles 或 --every-ms；不會有東西進對話歷史）；on_clock 在 add、start 或 wake 之後馬上跑一次，之後每 N 跑一次，事件裡有 `first`。
- Eca 畫面的生命週期：內建的 screen_linger_start / screen_linger_stop hook 會取消 / 排定延後關閉畫面（cli.json screen_close_after_s，預設 600 秒，0 是立刻）。兩個都設成 null 就停用。見 aos/cli/eca.json#/screen_linger。
- 寫處理程式（stdin、`$AOS_STACK` = hook 自己的資料夾 `<stack>/hookeds/NAME/`、用 JSON 項目代替 chmod）：`aos/me/self_hook.json#/handler`；檢查信箱的範例：`aos/mailbox.json#/check_hook`。
- 事件和回覆協定跟 agent 自己的工具一樣：`aos/me.json#/self_hook`。
