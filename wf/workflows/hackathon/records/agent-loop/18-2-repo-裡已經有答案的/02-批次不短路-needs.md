← [2. repo 裡已經有答案的](../18-2-repo-裡已經有答案的.md)（分檔 2/3）｜[上一份](01-孤兒-runi.md)｜[下一份](03-aos-llms.md)

**批次不短路／`"needs"`**

- 規格沒承諾短路：`docs/aos-folder.md`〈八〉〈五〉；`core/inst/docs/exec.md`〈狀態與失敗〉。
- 新增 instruction 欄位要改的檔：`wf/workflows/common/code-map.md`〈新增一個 instruction 欄位〉（`inst.hpp`、`format.cpp` 的 `known_key`／`encode`／`decode` 三處、必要時 `inst.h`＋`capi_instruction.cpp`、`exec.cpp`／`spawn_prep.cpp`）。
- `exit` 由父行程在等待完成後寫：`core/inst/docs/exec.md` 欄位對應段、`core/inst/docs/format.md`〈綱要(schema)〉。

**`$ref` 與重複的批次模板**

- `docs/inst-directives.md`〈四、`$ref`〉（取回的值必須是字串；展開語意另設指示詞）、〈五、適用範圍〉、〈七、對現有契約的影響〉（新錯誤狀態）。
- 新指示詞的硬門檻：`docs/aos-folder.md`〈七〉最後一段與 `core/inst/docs/handoff.md`〈彙整規則〉——未解析的指示詞必須能原樣寫回 JSON。

**投遞、檔名與投遞前驗證**

- 檔名規則：`core/inst/docs/handoff.md`〈彙整規則〉（只收第一個副檔名就是結尾的 `<name>.json`），判定函式 `core/inst/src/handoff.cpp` 的 `is_delivery_name()`。
- PID 不夠用的現場：`wf/workflows/experiments/t5-agent-loop.md`〈3. 投遞：原子 rename、壞 JSON 與檔名碰撞〉。
- 兩個 producer 各投 1,000 件：`wf/workflows/hackathon/records/core-scope/rounds.md`〈第 2 輪紀錄〉（共用本地序號遺失 1,000 件，全域唯一 ID 全部為 0）。
- 投遞前驗證與給模型的錯誤：`wf/workflows/workshop/records/tool-interop.md`〈誰驗證、驗不過怎麼回〉（rename 前驗完整 payload，驗不過整批失敗；`.bad` 只隔離繞過 Deliver 的壞檔）、〈給模型看的錯誤訊息〉（`code`／`record`／`pointer`／`expected`／`actual`／`hint`）。
- `aos deliver` 的形狀：同檔〈`aos deliver` 的合成版 `--help`〉（`--key` 沒有 ledger 不能宣稱冪等）、〈寫到哪裡、檔名怎麼配〉（五步發布）、〈退出碼還沒有共同編號〉。

**tool registry／回程的型別**

- `core/tooljson/docs/format.md`〈CLI〉：只有 `list`／`check`，`run` 尚未存在；〈`exec` 配方的載入期驗證〉：`ExecBody::run()` 固定回 `Error: exec execution is not implemented in S1`。格式與驗證有了，執行沒有。
- 欄位清單：同節（`exec`／`argv` binding／`stdin.param`／`stdout.clip`／`stderr.mode`／`ok_exit`／`timeout`／`cwd`／`limits`／`source`）、〈外殼〉。
- 展開錯誤餵回模型：同檔〈模型參數展開〉（錯誤回 `Error: ...` 字串，直接當 tool message 送回；單一 argv 項目上限 131072 bytes）。
- 回程截斷：同檔〈文字收尾〉（`decode_output()`、`clip_output()`）。
- 既有詞義：`wf/workflows/workshop/background/agent-loop.md`〈tool allowlist（具名工具映射）〉〈driver 與 adapter〉。
