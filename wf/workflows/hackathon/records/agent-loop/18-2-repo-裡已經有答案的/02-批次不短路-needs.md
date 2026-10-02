← [2. repo 裡已經有答案的](../18-2-repo-裡已經有答案的.md)（分檔 2/3）｜[上一份](01-孤兒-runi.md)｜[下一份](03-aos-llms.md)

**批次不短路 ／ `"needs"`（p2）**

- **這不是實作與規格對不上，規格從沒承諾短路**：`docs/aos-folder.md`〈八、退出碼〉與〈五、回合語意〉；`core/inst/docs/exec.md`〈狀態與失敗〉寫得最白——「非零的子行程狀態、訊號終止、PATH 找不到、設定階段狀態，或逾時，都是一次已完成的執行……**它不會中止後續的記錄**」。
- **真要把 `"needs"` 加進 format，動到哪幾個檔已經列好了**：`wf/workflows/common/code-map.md`〈新增一個 instruction 欄位〉——① `inst.hpp` 的 `inst_t` 加欄位；② `format.cpp` 的 `known_key`／`encode`／`decode` **三處都要加**；③ 需要的話 `inst.h` 加 C ABI 存取子＋`capi_instruction.cpp`；④ `exec.cpp`／`spawn_prep.cpp` 視語意決定。
- **`exit` 欄位是誰在什麼時候寫的**：`core/inst/docs/exec.md` 欄位對應那段——「非空的 `exit` 會由**父行程在等待完成後**建立／截斷，並寫入回報的十進位狀態」；`core/inst/docs/format.md`〈綱要(schema)〉的欄位表是同一件事的格式層說法。

**`$ref` 與重複的批次模板（p2、p4）**

- **規格的原話與那扇留著的門**：`docs/inst-directives.md`〈四、`$ref`〉——「**已定：取回來的值必須是字串。** 指到陣列或物件就是錯誤」，以及括號那段：「考慮過讓 `argv` 的元素可以展開成多個……但那會讓 `$ref` 從『產生一個值』變成『可能改變結構』……**真的需要時，另設一個明確表達「展開」語意的指示詞會更誠實**」。同檔〈五、適用範圍〉是可放指示詞的位置表。
- **新指示詞的硬門檻**：`docs/aos-folder.md`〈七、instruction 的格式〉最後一段——彙整會把每份投遞經格式層完整往返一次，所以「**還沒解析的指示詞必須能原樣寫回 JSON**」，否則會在彙整那一步被無聲吃掉。`core/inst/docs/handoff.md`〈彙整規則〉重述了同一條。
- **要新增哪些錯誤狀態**：`docs/inst-directives.md`〈七、對現有契約的影響〉已列（不認得的 `$xxx`、多於一個鍵、值不是字串、`$ref` 目標不存在或逃出 root……）。

**投遞、檔名與投遞前驗證（p4，以及四位都重寫過的 counter）**

- **檔名規則規格層寫得很精確**：`core/inst/docs/handoff.md`〈彙整規則〉——「只接受**第一個副檔名就是結尾**的 `<name>.json`；`123.json.temp`、`123.json.bad`、`name.part.json` 都會跳過」。這解釋了 Carmack 的 `185452-0.json` 為什麼被正常收走。判定函式是 `core/inst/src/handoff.cpp` 的 `is_delivery_name()`。
- **PID 不夠用，上一次就有現場**：`wf/workflows/experiments/t5-agent-loop.md`〈3. 投遞：原子 rename、壞 JSON 與檔名碰撞〉——同一 shell 連做兩次 temp+rename，`first_exists=no`，第一份靜默遺失；同節還有「直接寫 ready、不經 `.temp`」讓半份 JSON 被 rename 成 `.bad` 的現場。
- **兩個 producer 各投 1,000 件的壓力數據已經有人跑過**：`wf/workflows/hackathon/records/core-scope/rounds.md`〈第 2 輪紀錄〉——共用本地序號時**遺失 1,000 件**，改用全域唯一 ID 時「遺失、重複、覆蓋、明確失敗皆為 0」。
- **投遞前驗證是四位獨立的共識，錯誤該長什麼樣也定了**：`wf/workflows/workshop/records/tool-interop.md`〈誰驗證、驗不過怎麼回〉——「四位獨立地都要求 Deliver 在 rename 前驗證完整 payload；驗不過就整批失敗，不發布任何可見檔案」，並劃清 `.bad` 的邊界（**它只隔離繞過 Deliver 直接塞檔的壞檔**）。〈給模型看的錯誤訊息〉給了共同的 JSON 欄位：`code`／`record`／`pointer`（JSON Pointer）／`expected`／`actual`／`hint`。
- **`aos deliver` 的形狀、發布五步與退出碼分歧**：同檔〈`aos deliver` 的合成版 `--help`〉、〈寫到哪裡、檔名怎麼配〉（四位獨立地都給出同一個五步發布順序，**四位都沒有只靠 PID 保唯一**）、〈退出碼還沒有共同編號〉（四份不同編號的對照表）。
- **`--key` 目前不能宣稱冪等**：同檔〈`aos deliver` 的合成版 `--help`〉末段——aggregate 會刪除投遞檔，沒有 ledger 就不能承諾跨回合 Already／Conflict。

**tool registry ／ 回程的型別（p2 的第 3 次轉換、p3 的不對稱）**

- **`aos tooljson` 到底解決了多少，有明確答案**：`core/tooljson/docs/format.md`〈CLI〉——S1 只有 `aos tooljson list <spec.json>` 與 `check <spec.json>`，「`run` 尚未存在」。〈`exec` 配方的載入期驗證〉開頭寫著 `ExecBody::run()` **固定回 `Error: exec execution is not implemented in S1`，不會 fork 或 exec**。也就是：**格式與驗證有了，執行沒有。**
- **「對的那一種 registry」的欄位清單**：同檔〈`exec` 配方的載入期驗證〉列出 `exec`／`argv`（binding 只接受 `position`／`flag`／`separate`／`repeat`）／`stdin.param`／`stdout.clip`／`stderr.mode`／`ok_exit`／`timeout`／`cwd`／`limits`／`source`；〈外殼〉列出 schema 形狀的載入期檢查與「同一檔內 `function.name` 不得重複、多檔比照 `PATH` 先出現者獲勝」。
- **展開錯誤就是要餵回模型的那句話**：同檔〈模型參數展開〉——「模型給錯參數時回 `Error: ...` 字串，**呼叫端應把它直接當 tool message 送回模型**，而不是丟例外」，並列出八條展開規則（含「任何單一 argv 項目超過 131072 bytes 都拒絕」）。
- **回程的截斷語意**：同檔〈文字收尾〉——`decode_output()` 遇 NUL 只回 `(binary output, N bytes, not shown)`，`clip_output()` 超過限制保留 head 或 tail 並標明省略的字元數。這是 Armstrong 手寫 `sed -n '1,60p'` 的規格版。
- **具名工具映射的既有詞義**：`wf/workflows/workshop/background/agent-loop.md`〈tool allowlist（具名工具映射）〉與〈driver 與 adapter〉。
