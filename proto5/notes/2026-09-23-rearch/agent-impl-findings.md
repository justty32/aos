# agent 線實作（T9）：實作發現

← [rearch README](README.md)｜規範：[agent.md](../../spec/agent.md)、[aos-agent.md](../../spec/aos-agent.md)、[aos-llm-call.md](../../spec/aos-llm-call.md)

2026-09-24。照三份定稿規範重寫 agent 線時碰到的歧義與實作層級的選擇；本次未修改 `spec/*.md`。方向性的列在最後「要使用者拍的」。

1. **頂層是指示詞物件的代號。** agent.md §2 要 info.json 頂層是字面物件，沒指定頂層整份是 `$ref` 時用哪個代號。
   選 `FieldTypeMismatch`（跟 kernel info 的同類情況一致）；頂層不是物件仍是 `NotAnObject`。llm.json 同樣處理。
2. **記憶頂層不是陣列用 `NotAnArray`。** agent.md §3.2 說「不合＝MessageInvalid」，§5 另列 `NotAnArray`。選：頂層型別錯 `NotAnArray`、陣列裡的壞訊息 `MessageInvalid`。
3. **message 缺 `content` 鍵不當 null。** §3.2 要 content 是字串或 null；§5 正規化只處理「null」。模型若整個省略 content（只給 tool_calls）會被判 `EngineFailed`。
   照字面實作；若真跑遇到省略 content 的端點再議（可能要把「缺」併進正規化第 ② 步）。
4. **六格與 llm.json 的 `$opt` 在實際求值的位置才報 `UnknownOption`。** 被指示詞優先序忽略的鍵不求值、不誤報。
5. **共用讀驗層另立 `aos_agent_home.py`。** 為了讓第 1 段不動舊 `aos_agent_info.py`（舊 llm／tool cpu 還在 import 它），message 驗證、工具檔、人格／記憶讀與六格 loader 放新模組；
   新版 `aos_agent_info.py`（完整 info＋state）建在它上面。
6. **舊 llm／tool cpu 的程式刪除提前到第 2 段。** 新版 `aos_agent_info.py` 換掉舊 API 後，`aos_llm_ask`／`aos_llm_cpu`／`aos_tool_cpu`／`aos_cpu` 與其測試、cli 無法再跑，
   所以跟 aos-agent 重寫同一個 commit 刪；第 3 段只剩規範檔、文件與連結。
7. **ack 檔名自己放，不改 aos_client。** aos-agent.md §6 要 `ack-<ns>-<pid>-<i>.json`、EEXIST 換 ns；`aos_client.ack` 的名字沒有序號。
   選：aos-agent 直接用 `aos_home.post_request` 放，新架構五支一行沒動。
8. **`info.tick` 可以是指示詞。** agent.md §2 只要求頂層與 `llm` 是字面物件；`tick` 整格用 `$ref` 取也收，只解驗 `pool`／`interval_ms`。
9. **`waits` 的一條不能整條是 `$ref`。** agent.md §4.2 說 `$val` 可再是指示詞，沒說條目本身；選：條目限字串或 `$opt` 物件，整條 `$ref`＝`FieldTypeMismatch`、只有 `$val` 沒 `$opt`＝`UnknownDirective`。
10. **逾時訊息裡的 T 用當下設定。** `batch` 沒存每筆的 `timeout_ms`（agent.md §4.3 沒這格），§6.1／§6.2「逾時（T ms）」只好用收回當下 info／工具檔的值；人在途中改了會跟實際 add 的不同。只影響訊息文字。
11. **K 帳本形狀另驗。** §5.2 第 4 步只說「讀得到但壞掉＝退 1」；實作把 `procs` 不是物件、`replies` 不是陣列或元素缺 `name` 也當壞掉（送件退 1；清檔則跳過那筆）。
12. **門劃掉了但輸入空時退 101。** §12 說「做了事」退 0；門有劃掉（已寫 state）而之後 idle 沒輸入，實作退 101（照 §8 第 1 步）。對 kernel 都不算失敗，無害。
