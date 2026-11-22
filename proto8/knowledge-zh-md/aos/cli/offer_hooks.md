# `knowledge/aos/cli/offer_hooks.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/cli/offer_hooks.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/cli/offer_hooks.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/aos-hook: offer hook points from your own program`**

# aos-hook：從你自己的程式提供 hook 點

當你寫的程式（C++、shell、任何能啟動行程的東西）要讓別人 hook 進來，就像 agent 的 hookeds.json hook 進 agent 那樣，用 aos-hook。要 hook 進一個現有的 agent，則是用 `aos-agent hook`（aos/cli/hook.md）。

一個 hook 點就是在那個時刻的一次 `aos-hook fire`。aos-hook 只照名字順序跑掛在那個事件上的處理程式（handler），交回每一個的結束碼和 stdout；它們代表什麼（擋下、改一個欄位、失敗）由你的程式決定。要 hook 進來的人寫一份 hookeds 清單：

```json
{"description": "What is hooked on before_save.",
 "a_deny": {"event": "before_save", "handler": "a_deny", "timeout_ms": 5000},
 "b_rename": {"event": "before_save", "handler": "b_rename"}}
```

```sh
echo '{"file": "notes.txt"}' | aos-hook fire --list hookeds.json --stack "$STATE" before_save
# {"event": "before_save", "hooks": [{"hook": "a_deny", "code": 0, "stdout": "", "error": null}, {"hook": "b_rename", "code": 0, "stdout": "{\"file\": \"notes.txt.bak\"}\n", "error": null}]}   exit 0
echo '{"file": "secret.txt"}' | aos-hook fire -q --stop-on-nonzero --list hookeds.json --stack "$STATE" before_save
# exit 10: a_deny said no (10 prints no error line); another non-zero code: that code and "aos-hook: error: HookFailed ..."
```

- hook 在哪：`--list FILE`（可重複；後面的檔案依名字蓋過前面的，null 關掉一個 hook，不存在的檔案就是沒有 hook）或 `--def DIR`（DIR/interfaces.json 的 `hookeds`，每個相對路徑的那份上面再疊 stack 裡同名的複本）。
- 一筆項目：`event`、`handler`（相對於清單所在資料夾的路徑，或一個指示詞（directive））、`timeout_ms`（預設 60000，0 = 不限；到時限時停掉處理程式的整個行程群組）。其他鍵留給你的程式；aos-hook 不讀。
- 事件資料只有 stdin 上的 JSON 物件（給 JSON 或 /dev/null：除非 stdin 是終端機，aos-hook 會把它讀到底）。每個處理程式拿到同樣的資料，加上 `event`、`hook` 和 `stack`，以 `STACK/hookeds/NAME/event.json` 放在它的 stdin；它自己的 `$AOS_STACK` 就是那個資料夾。`--stack DIR` 預設為 `$AOS_STACK`。
- stdout：一行 JSON `{"event", "hooks": [{"hook", "code", "stdout", "error"}]}`（處理程式逾時或無法啟動時，`code` 為 null，`error` 是原因）；`-q` 什麼都不印。不管處理程式做了什麼都 exit 0；`--stop-on-nonzero` 在第一個非零碼停下並以它結束（逾時 / 無法啟動 = 1）。錯誤（`aos-hook: error: CODE reason`，exit 1）：`ArgumentsBad`、`HooksBad`、`InterfaceBad`、`StackMissing`、`HookFailed`。
- 宣告告訴別人你提供哪些點（只供閱讀；aos-hook 和引擎都不讀它）：一個 JSON 物件 `hooks.json`，鍵是點的 id，每個都有必填的 `input`（處理程式拿到什麼的 JSON Schema），以及任何你想加的其他鍵（`description`、`output`、`block`、`phase`、`condition`...）；最上層的 `description` 是一句話，不是一個點。定義在 `interfaces.json` 裡列出它的宣告（`"hooks": "hooks.json"`，或檔名與指令的陣列）。

```json
{"description": "Hook points of my-saver.",
 "before_save": {"description": "before a file is saved",
                 "input": {"type": "object", "properties": {"event": {"const": "before_save"}, "hook": {"type": "string"},
                           "stack": {"type": "string"}, "file": {"type": "string", "description": "the file name"}}},
                 "output": {"type": "object", "properties": {"file": {"type": "string", "minLength": 1}}},
                 "phase": "before", "block": true, "if_blocked": "the file is not saved"}}
```

- aos-loop 的點（after_start、after_stop、before_run、after_run）宣告在 `$AOS_HOME/lib/aos/apps/hook/loop_hooks.json`；loop.json 用 `aos-hook fire -q --stop-on-nonzero --def $AOS_CD EVENT` 觸發它們，所以處理程式的結束碼原樣傳到 aos-loop。它們的處理程式從環境讀 `AOS_LOOP_*`（fsm agent 的狀態從 `STACK/stage.txt` 讀）。
- 每次 fire 會啟動一個 Python 行程（幾十毫秒）再加上處理程式。Python 程式不用那個行程就能跑處理程式：`aos.hook_run.fire(event, data, aos.hook_lists.load(paths), stack)`。更多：`aos-hook --help`、`aos-hook fire --help`；給人看的整個 hook 系統總覽（中文）：`$AOS_HOME/lib/aos/apps/hook/docs/README.md`。
