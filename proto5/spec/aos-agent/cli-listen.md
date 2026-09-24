← [aos-agent](README.md)｜[spec 總導航](../README.md)

## 1.5 `listen`：看回話（09-24 fix-r4 補，取代 `last`；09-24 listen 微調改）

```
aos-agent listen [--target DIR] (--last [N] | --wait [秒] | --follow) [--show-calls | --show-calls-full] [--json]
```

三種看法互斥（給兩個以上＝用法錯 2）。（09-24 listen 微調改）**都不給＝用法錯 2**：stderr `aos-agent: Usage: listen 要選一種看法：--last [N]（最後 N 則）、--wait [秒]（等下一則）、--follow（一直印）；例：aos-agent listen --last`，stdout 空。
理由：以前不給＝`--last`，使用者要它不再是預設；改成默默換別的看法（例如 `--follow` 卡住不退）比報錯更難懂，報錯順便把三種看法列給他挑。只給 `--show-calls` 也不算選了看法。
不要 `AOS_KERNEL_HOME`。「回話」＝記憶裡 `role: assistant`、**有字**（`content` 非空）或**沒叫工具**的一則；只叫工具（`content` 是 null 或空、有 `tool_calls`）的那則不算回話——例外：它是記憶裡最後一則 assistant（這一輪還沒走完）時算一則。
一則回話的印法：`content` 原樣；只有 `tool_calls` 時印 `(tool_calls: 名1, 名2)`；`--json` 改印整則一行 JSON（不加標頭）。

- **`--last [N]`**（就是舊的 `last`）：N 省略＝1；給了要是正整數（只收 `0-9` 組成、≥1），不是＝用法錯 2（`--last 後面要是正整數…`）。讀驗 info 後找記憶裡**最後 N 則回話**、照時間順序印出來、退 0。
  一則都沒有＝`NotFound`、退 1；info 讀驗錯照 §12 退 1。記憶裡不到 N 則＝有幾則印幾則、退 0，stderr 多一行 `aos-agent: note: 記憶裡只有 K 則回話，全印`。
  （09-24 listen 微調）**N＝1 且沒開 `--show-calls*`**：stdout 跟以前一樣只有回話本身（方便 `$(…)`）。**N＞1 或開了 `--show-calls*`**：每一輪第一個印出的東西前面多一行標頭（見下），多則之間靠標頭分隔。
  （09-24 試玩 r2 補）info 讀驗錯時改讀 `<dir>/prompts/history.json`，stderr 一行 `aos-agent: warn: info.json 讀不了（<代號>），改讀 prompts/history.json`；那份也讀不了才退 1。
  下面三種警告與時間都只看**最後印的那則**：門關著（`waits` 有沒到的）時照印，stderr 多一行 `aos-agent: warn: 門關著…這則回話可能是舊的；看 aos-agent status`（連敗暫停就說用 `aos-agent continue` 解除）；手動暫停時同樣多一行 `已手動暫停…`。
  （09-24 fix-r5 補）**還沒講完**：沒有上面那兩種警告、但這一輪還沒走完——那則帶 `tool_calls`、它後面還有別的訊息、`state` 不是 `idle`、有 `batch`／`intake`、或 `input` 有還沒收的檔——stderr 多一行
  `aos-agent: warn: 還在處理中（tool_calls: 名1, 名2）：最後的回話還沒出來；要等就 aos-agent listen --wait --target <dir>`（不是 tool_calls 那種，括號寫 `新輸入還沒回`，並說「這則是上一輪的回話」）。
  **回話附時間**：stderr 一行 `aos-agent: time: <MM-DD HH:MM:SS>`——記憶檔的修改時間；那則不是最後一則時後面加 `（記憶最後更新，這則更早）`。
- **`--wait [秒]`**：開始時記下記憶長度 H0，阻塞等**下一則新回話**：用 §1.2 那套等法（同一個函式）——這一輪走完（`idle`、沒 batch、沒 intake）且最後一則是第 H0 則以後的 assistant，就印那一則、退 0。
  秒數省略＝300。逾時＝stderr `aos-agent: Timeout: 等了 N 秒沒有新回話…`、stdout 印 `status`、退 101；沒登記／手動暫停／連敗暫停（09-24 fix-r5 再加 kernel 家有問題、`bad`）＝跟 `say --wait` 一樣開始前就看、立刻退 101（listen 沒投話，不印「已投入」那行）。
  中途要看的是「一整輪的結果」，所以模型先叫工具的那則（只有 `tool_calls`）不算，等到輪完才印最後那則。
- **`--follow`**：從現在的記憶長度起，每 200 ms 看一次，**每多一則 assistant 就印一則**（含只有 `tool_calls` 的中間那則，印成 `(tool_calls: …)`），印完 flush，一直到 Ctrl-C（退 0）。
  沒登記、暫停都不退出（它只是看著）；記憶被人改短就從新的長度重新算。info 讀驗錯＝退 1。`--follow` 不印標頭（即時看，時間就是現在）。

### 輪次標頭（09-24 listen 微調）

一行 `── 第 R 輪 · 收話 MM-DD HH:MM:SS ──`。R＝這格以前（含）有幾段「連續的 user」——每段 user 開一輪；記憶開頭還沒有 user 的那幾格標 `── 記憶開頭（還沒有你的話）──`。
**時間**：記憶本身沒有時間戳，這裡是「收下那輪輸入的時刻」，取自輸入封存檔名 `<原檔名>.<ns>-<pid>.done`（[agent §4.1](../agent/state.md)）裡的 ns：`input` 每個路徑是資料夾就看 `<它>/done/`、是檔就看同層 `done/` 裡 `<檔名>.*.done`；同一個消費 id＝同一次收件。
每輪第一句 user 的 `content` 跟收件（照時間排）裡第一句 user 比對，往後找、不回頭；對不上（封存被清掉、手改記憶、`state.json` 讀不了）就只印 `── 第 R 輪 ──`。

### `--show-calls` 與 `--show-calls-full`（09-24 listen 微調）

兩個互斥（都給＝用法錯 2），對三種看法都有效。開了之後印的是**一段記憶**而不只是回話：user 不印，叫工具的 assistant 印它的字（有的話）再印呼叫行，`role: tool` 印結果行（工具名用前面 `tool_calls` 的 `id` 對回來，對不到寫 `?`）。

- 哪一段：`--last N` 是「倒數第 N＋1 則回話之後」到記憶尾（所以第一則回話那輪叫的工具也看得到）；`--wait` 是 H0 以後這一輪；`--follow` 是每多出來的一格即時印（叫工具那一刻就印呼叫行，不等結果）。
- **`--show-calls`**（簡化）：呼叫一行 `[呼叫 名 k=v k=v]`——參數解成 JSON 物件就逐個 `k=v`（字串原樣、換行寫成 `\n`、別的型別印 JSON），每個值超過 40 字截成 40 字加 `…`，整段參數超過 120 字再截；沒參數＝`[呼叫 名]`；參數不是 JSON＝`[呼叫 名 參數不是 JSON：<前 40 字>]`。
  結果一行 `[結果 名：<第一個非空行，超過 60 字截>]`，多於一行時寫 `[結果 名 K 行：…]`，空的寫 `[結果 名：（空）]`。工具失敗、逾時的文字（§6.2）照樣出現在那一行，不另判成敗。
- **`--show-calls-full`**（完整）：呼叫印 `[呼叫 名 id=<id>]`，下面兩格縮排印參數（能解成 JSON 就縮排 2 的 JSON，不能就原字串）；結果印 `[結果 名 id=<id> K 行 L 字]`，下面兩格縮排印原文。
  參數、結果各超過 4000 字只印前 4000 字，再一行 `  …（截斷：共 L 字，只印前 4000 字；全文在記憶檔）`。
- `--json` 同時給：不印標頭與呼叫行，這一段裡 user 以外的每格（含 `role: tool`）各印一行原樣 JSON；簡化與完整沒有差別。
