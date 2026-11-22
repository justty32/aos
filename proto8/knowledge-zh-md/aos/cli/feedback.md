# `knowledge/aos/cli/feedback.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/cli/feedback.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/cli/feedback.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/aos-feedback: say what was hard`**

# aos-feedback：說出哪裡難用

記下一個指令或工具哪裡難用，並替它對 AI 來說有多順手打分數。回饋絕不會改變被評的對象。存放處是 `$AOS_FEEDBACK`（預設：repo 的 `wf/advices/feedback/`，從指令往上找到 `proto8` 資料夾，在它旁邊）。

```sh
aos-feedback add "aos-agent ctl add" "usage unclear" "show an example" --kind help --score 0.4 --by opus --model claude-opus
# aos-feedback: recorded .../aos-agent.jsonl
aos-feedback ls                    # aos-agent  2  2026-11-11T03:18:53.119Z
aos-feedback show aos-agent
aos-feedback score aos-agent --observed ledger.jsonl
```

鍵是第一個字的 basename（`aos-agent ctl add` -> `aos-agent`）。`--kind` 是 usage、help、errors、args 或 other（預設 `other`）；`--score` 是 0 到 1（1 = 順手）。`--by` 預設是 `$AOS_CD` 的資料夾名，沒有就是 `unknown`；`--model` 預設是 `unknown`；`--family` 和 `--tier` 會蓋過評分者規則。旗標可以放在參數前面或後面。`score` 印出 JSON：有分數的各類平均（usage、help、errors、args；`other` 不算）再取平均，當 `--observed` 帳本裡有它的呼叫時，再乘上 calls/(calls+errors+retries)；沒有這類呼叫就不乘；有呼叫但沒有分數，就只是 calls/(calls+errors+retries)；兩者都沒有就是 `null`。帳本不存在 = `FileMissing`；存放檔壞掉 = `FileBad`；`$AOS_FEEDBACK` 是空的 = `ArgumentsBad`；找不到 proto8 資料夾 = `PathMissing`；不認得的子指令 = `CommandUnknown`。在 aos 裡面，這個工具是 `lib/tools/aos/feedback`（不在預設的工具包裡）。更多旗標：執行 `aos-feedback --help`。
