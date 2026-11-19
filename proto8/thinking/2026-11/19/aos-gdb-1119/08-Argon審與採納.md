# Argon 審調查稿（11-19，第一版乙案施工前）：十條審查、三條提案逐點採納與否；沒有一條推翻「先乙」或使用者的定義

← [README](README.md)｜原文：[08-Argon原文](08-Argon原文.md)｜施工紀錄：[aos-gdb-lib-第一版](../aos-gdb-lib-第一版.md)

線 `aosgdb-lib-1119`。使用者：「argon額度雖然不多，但是只有正規調查流程會用到。不用省　去派吧」。Argon 拿到的是本夾 13 份全文加 `py/aos/agentlib/hooks.py`、`py/aos/hook_run.py`（附行號），要它分 (A) 審查、(B) 提案，並明說有沒有哪條會推翻方向。

## 先講結論

1. **方向不動。** Argon 自己的 A10：「沒有任何一條問題會推翻『先乙』的方向或使用者的斷點定義」，全部問題都能在不改 hook 機制、不改 daemon／aos-agent 的前提下由庫與 handler 解掉。對過事實，同意。
2. **真會出事、已照改的五件**：hook 一律 `on_error: continue`、`intercept: false`（A1，否則條件或 handler 壞了會連環重起）；字條與「停住」要分開等，`wait_paused()` 看 `state.json` 的 `paused`（A4）；shell 續了又停時字條會變舊，字條記 ctl seq、`why()` 比對（A5）；「連續 N 次」不能交給 hook 的 condition 篩、否則變成累計（A6）；Python 條件在下斷點那一刻就驗（A7）。
3. **多做的一件**：`before_tool` 加 `block=True`（停的那一次工具不跑）。調查稿第 07 份就寫了「pause 停在這一格做完」，Argon 的 A4 與 B1 建議用既有的退 10 補「事前攔住」，零成本，收。
4. **沒收的**：只記不停（`action="log"`，A9 建議砍，照砍）、每個觸發器一支自己的 `run.py`、once 自己改寫 `hooks.json`、active／history 兩份字條、從內容猜錯誤行（理由見下表）。

## 逐點

| # | Argon 說 | 對過的事實 | 採納 | 理由／怎麼做 |
|---|---|---|---|---|
| A1 | `intercept` 預設開、`on_error` 預設 stop：handler stdout 不是 JSON 或腳本壞掉＝HookFailed＝連環重起 | 對（`hook_run.py` 的 `_changes`、`fire`；07 的 T2 實測過連環重起） | 採納 | 掛的時候一律 `--on-error continue`、`--no-intercept`（只有 block 的開 intercept，handler 不印 stdout）、逾時 15 秒（sh／py 40 秒）；handler 叫 pause 時 stdout 丟掉；py 條件跑時 `sys.stdout` 換成 stderr；sh 條件 stdout 丟掉 |
| A2 | condition 只有四個事件收；清單載入時的 HooksBad 不受 on_error 保護；寫 `hooks.json` 要原子 | 對（`validate_entry`、`_read`）。寫檔走 `aos-agent hook add`，它本來就先驗再暫存改名 | 採納 | `tool=` 只准用在收 condition 的事件（before_tool、after_tool、brain_failed、tool_added），其餘當場拒；`hooks.json` 只經 `aos-agent hook add／rm` 寫，不自己改；`attach()` 先跑 `hook ls`，沒宣告 hooks 當場 `HooksMissing` |
| A3 | hook 裡的 `$AOS_STACK` 是小格，不是 agent 的 stack | 對（`hook_run.run`；context_wrap 的檔頭也這麼寫） | 採納（本來就這樣設計） | agent 的 stack 取事件 JSON 的 `stack`；daemon 與名字在下斷點時寫進 `trigger.json`，不靠環境變數猜 |
| A4 | 字條與 paused 的先後、同一格多個觸發器互蓋、`wait_paused` 不能看字條；建議先寫字條再發停；`block=True` | 前半對：`wait_paused` 改看 `state.json`；字條只往後加、不覆蓋。先後順序那半在 aos 不會出事：hook 是同步跑在格裡的，pause 要等這一格做完 loop 才套用，所以字條一定比「表上變 paused」早寫好 | 部分採納 | `wait_paused()` 輪詢 `state.json` 的 `paused`；字條一律 append（`gdb/log.jsonl`），同一次停的多張都列；順序改成**先發停、再留字條**，好把 pause 實際用的 ctl seq 寫進字條（A5 要用）；發停失敗另記 `pause_failed`；`block=True` 收（只給 before_tool） |
| A5 | 在 shell `ctl resume` 再 `ctl pause`，`why()` 會把舊字條當這次的原因；建議綁 ctl seq | 對（`ctl.json` 每道指令遞增 seq） | 採納（做小一點） | 字條記 handler 發停後 `ctl.json` 的 seq；`why()` 看最後一張的 seq 跟現在 `ctl.json` 的一不一樣，不一樣就說「之後有人下過 ctl、字條可能是舊的」。不做 Argon 的 active／history 兩份檔與自動歸檔：一份只往後加的檔加「resume 那筆之後才算」就夠，丙之後也只要往同一份加 |
| A6 | 有工具名 condition 時，別的工具的事件進不來，「連續」變「累計」；停了要歸零 | 對（`hook_run.matches` 在起 handler 前就篩掉） | 採納 | `times > 1` 時不交 condition，工具名寫進 `trigger.json` 的 `tools` 由 handler 篩，別的工具＝不成立、歸零；`times == 1` 才交 condition 省行程；停了 streak 歸零 |
| A7 | REPL 的 lambda 拿不到原始碼、pickle 不行；建議 marshal、帶預設值、當場驗 | 對（標準 REPL 的 `inspect.getsource` 丟 OSError） | 採納 | 函式用 marshal 帶 code、預設值要是 JSON；用到外層變數、REPL 裡別的名字（看 `LOAD_GLOBAL`）、預設值不是 JSON、參數不對都在下斷點那一刻拒；另收運算式字串（`py="ev.get('code') == 2"`）；記 Python 版本，不同就當條件壞了 |
| A8 | 字條帶來源欄、檢閱方法做在同一個物件上，丙才接得上 | 對 | 採納 | 字條的 `by` 欄（hook／repl，丙用 watch）；檢閱方法在 `aos.gdb.look.Look`，丙可以拿同一個物件當條件函式的參數 |
| A9-1 | 砍掉 add_tool 一類包裝，留萬用 `agent(*args)` | — | 採納 | 只有 `a.agent(...)`，例 `a.agent("tools", "add", ...)` |
| A9-2 | 砍掉只記不停（log）與 debug 大禮包 | — | 採納 | 第一版只有「停」；只記不停是丁的事，等用過再說 |
| A9-3 | 不改事件、一律 intercept false | — | 採納 | 同 A1；block 例外 |
| A9-4 | 現成條件和自訂條件收成同一個 runner | — | 採納（本來就這樣） | 只有一支 handler `lib/tools/agent/gdb_trigger`，現成條件是 `kind` 的幾個值 |
| A10 | 沒有一條推翻先乙或使用者的定義 | 同意 | — | 所以沒有停下來回報選項 |
| B1 | API 形狀；「工具回錯」用內容裡的 `xxx: error:` 行判 | 形狀大致照收。判錯誤：agent-fsm 交給 after_tool 的事件本來就有 `code`、`timed_out` | 部分採納 | 用 `code` 不是 0 或逾時判，不猜內容（工具照 N-43 有錯誤行就不退 0，code 更準）；名字照 aos 慣例 `aos.gdb`（對外指令 `aos-gdb`），不是 `aos_gdb` |
| B2 | 每個觸發器在 stack 放一支 `run.py`；once 觸發後自己從 `hooks.json` 刪掉；active／history 兩份字條 | — | 不採納 | 一支共用的 handler（裝在 lib）比每隻 agent 抄一份程式好改、好查；once 改成 handler 記「已停過」、之後什麼都不做，不讓第二個寫的人碰 `hooks.json`（`triggers()` 也看得到它停過）；字條見 A5 |
| B3 | 八個測試情境 | — | 大部分採納 | 實跑測了：停→看→續、block＋once、工具連錯兩次、條件壞了不停不掛、shell 續了又停字條變舊、同一個事件兩個觸發器都成立（兩張字條都在）；不起 daemon 的單元測試補了錯→錯→對→錯…的歸零、別的工具打斷連續、stdout 雜訊、壞條件、閉包與未知名字拒收。沒測「停著時加一個新工具、續了被不指名的觸發器攔到」（要另寫劇本腦；照 hook 的篩法推想會成立） |

## 叫 Argon 時撞到的小事

- 提示約 16 萬位元組，Windows 命令列放不下；`--input-format stream-json` 的訊息格式跟 claude 不同（要 `event` 鍵），沒試出來。改成提示寫成檔放 `--add-dir` 的空夾、`-p` 只寫「只准用 view_file 讀這一個檔」，一次就過。記進 [wf/public/model-notes](../../../../../wf/public/model-notes.md) 的 Argon 坑。
