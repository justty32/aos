# `knowledge/aos/tools/peek_clock.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/peek_clock.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 工具 peek_clock

看 daemon 的時鐘：目前的週期數，以及一個週期多長。沒有參數。什麼都不改。

用它知道時鐘走到哪裡，例如在你給另一個工具 `timeout_cycles` 或 `every` 之前。要知道一天中的時間，用 `peek_now_time`。

```json
{}
```
-> `{"cycle": 42, "interval_ms": 1000}`

- `cycle`：時鐘檔 `$AOS_CLOCK` 裡的數字。root daemon 每跳一下加 1。空的時鐘檔算 0。時鐘暫停或樹睡著時它不動。
- `interval_ms`：一個週期大約幾毫秒（`$AOS_CLOCK_INTERVAL`，預設 1000）。
- 週期數只在同一棵樹裡能比較。更多關於時間：`aos/world.json`（Time 一節）。

錯誤：`aos/tools/peek_clock.json#/errors`。

---

**`#/errors`**

# peek_clock：錯誤

- `ClockMissing`：你沒有時鐘。沒設 `AOS_CLOCK`（你不在一棵有時鐘的 daemon 樹底下），或它的檔還不存在（時鐘關著或還沒跳過）。不要猜週期：要一天中的時間用 `peek_now_time`，或照實說。
- `ClockBad`：時鐘檔裡放的不是數字，或 `AOS_CLOCK_INTERVAL` 不是正整數。必須由人來修；回報。
- `ArgumentsBad`：給 `{}`（不要有鍵）。見 `aos/errors/common.json#/input`。
