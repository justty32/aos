← [把「exec 只當純 CPU、其餘全外放成 argv」真的做出來，去打研討會的三個主張](../argv-split.md)（分檔 24/29）｜所在：下一輪的資料包 ＞ 2. repo 裡已經有答案的｜[上一份](23-2-repo-裡已經有答案的.md)｜[下一份](25-給-p3conformance.md)

#### 給 p2：`$ref`／`$env`／`$opt` 的往返、條文草稿、插延遲的工具

- 往返是協定：`docs/aos-folder.md`〈七、instruction 的格式〉最後一段——「**每份投遞都會被格式層完整往返一次**。因此『還沒解析的指示詞必須能原樣寫回 JSON』。任何新增的指示詞都得滿足這條，**否則它會在彙整那一步被無聲吃掉**。」
- 格式層的承諾：`core/inst/docs/format.md`〈綱要(schema)〉（未解析時寫回仍是同一個物件）；`core/inst/docs/resolve.md`〈為什麼另設 resolve〉（`pending_directives` 讓 `write_one`／`write_all` 原樣寫回）。
- 內建彙整器往返的 oracle：`core/inst/tests/test_handoff.cpp` 的 `TEST_CASE("handoff preserves unresolved directives through aggregation")`（第 177 行）——投遞 `{"argv":["command",{"$env":"ARG"}],"stdout":{"$ref":"values.json#/output"},"stderr":{"$opt":"merge"}}`，斷言 `pending_directives.size() == 2`、`stderr_merge` 為真並逐欄比對。外部彙整器要比對的基準就在這裡。
- 相鄰 oracle：同檔 `"handoff aggregates deliveries in filename order and flattens batches"`（第 43 行）、`"handoff isolates invalid deliveries and publishes the valid ones"`（第 79 行）、`"handoff consumes empty deliveries with and without useful work"`（第 135 行）；端到端 `core/inst/tests/test_run_handoff.cpp` 的 `"exec resolves an environment directive delivered through handoff"`（第 44 行）、`"exec isolates invalid deliveries and ignores status suffixes"`（第 57 行）。
- 無聲蒸發的條文：`docs/aos-folder.md`〈六、交接協定〉「**整批 JSON 解析失敗也算『回合正常返回』**，`.runi` 一樣刪掉」；對照組 `.bad` 隔離在同節〈彙整的規則〉。
- 「錯誤回饋不到上游、`aos exec` 仍回 0」的現場：`wf/workflows/hackathon/records/agent-loop.md`〈規格級的發現／七、錯誤回饋不到模型：投遞被隔離成 `.bad`，warning 進 stderr，`aos exec` 仍回 0，loop 靜默死亡〉。
- 「偵測留內、政策外放」條文範本見第 3 節 `freepy/agentloop/LIMITS.md`；repo 側掛在 `docs/aos-folder.md`〈六／彙整的規則〉五條與〈彙整跑在哪裡〉。
- 插延遲的替代：確定性 failpoint（第 3 節 `p1a2_model.py` 的 `Failpoints`）；或 gdb 斷點法（主張二）。
- 提案 3、4 原文：`wf/workflows/workshop/records/exec-as-pure-cpu.md`〈轉交提案／一、要改 `docs/aos-folder.md` 的〉第 3、4 條。
