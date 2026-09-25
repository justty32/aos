← [把「exec 只當純 CPU、其餘全外放成 argv」真的做出來，去打研討會的三個主張](../argv-split.md)（分檔 24/29）｜所在：下一輪的資料包 ＞ 2. repo 裡已經有答案的｜[上一份](23-2-repo-裡已經有答案的.md)｜[下一份](25-給-p3conformance.md)

#### 給 p2：`$ref`／`$env`／`$opt` 的往返、條文草稿、插延遲的工具

- **往返這條約束是規格明文，而且明寫是協定而非實作細節**：`docs/aos-folder.md`〈七、instruction 的格式〉最後一段——「彙整是把每份投遞 `read_all` 成結構、再 `write_all` 回去，所以**每份投遞都會被格式層完整往返一次**。因此『還沒解析的指示詞必須能原樣寫回 JSON』。任何新增的指示詞都得滿足這條，**否則它會在彙整那一步被無聲吃掉**。」
- **格式層那一側的承諾**：`core/inst/docs/format.md`〈綱要(schema)〉——「format 只保存未解析指示詞……**未解析時寫回仍是同一個物件**，解析後才輸出實際字串」；`core/inst/docs/resolve.md`〈為什麼另設 resolve〉——「額外的 `pending_directives` 逐項記住指示詞種類、所在欄位、`argv` 索引或 `env` key……因此字面值永遠不需要跳脫，`write_one`／`write_all` 也能把尚未解析的物件原樣寫回」。
- **內建彙整器的往返已經有一個現成的 oracle 測試**：`core/inst/tests/test_handoff.cpp` 的 `TEST_CASE("handoff preserves unresolved directives through aggregation")`（第 177 行）——投遞是 `{"argv":["command",{"$env":"ARG"}],"stdout":{"$ref":"values.json#/output"},"stderr":{"$opt":"merge"}}`，斷言彙整後 `pending_directives.size() == 2`、`stderr_merge` 為真，並逐欄比對 `kind`／`field`／`argv_index`／`argument`。**外部彙整器要比對的那份基準行為就在這裡。**
- **相鄰的三個 oracle**：同檔 `TEST_CASE("handoff aggregates deliveries in filename order and flattens batches")`（第 43 行，字典序＋攤平）、`TEST_CASE("handoff isolates invalid deliveries and publishes the valid ones")`（第 79 行，`.bad` 隔離）、`TEST_CASE("handoff consumes empty deliveries with and without useful work")`（第 135 行）。端到端那一側在 `core/inst/tests/test_run_handoff.cpp`：`"exec resolves an environment directive delivered through handoff"`（第 44 行）、`"exec isolates invalid deliveries and ignores status suffixes"`（第 57 行）。
- **「無聲蒸發」那條規格條文的原文**：`docs/aos-folder.md`〈六、交接協定〉——「**整批 JSON 解析失敗也算『回合正常返回』**，`.runi` 一樣刪掉。那批壞內容就此消失，只在 stderr 留下一行診斷——這是刻意的取捨」；對照組（`.bad` 隔離）的規則在同節〈彙整的規則〉的「無效的投遞：噴 warning、把那一份隔離、繼續處理其餘的」。
- **同一個「錯誤回饋不到上游、`aos exec` 仍回 0」的完整現場**：`wf/workflows/hackathon/records/agent-loop.md`〈規格級的發現／七、錯誤回饋不到模型：投遞被隔離成 `.bad`，warning 進 stderr，`aos exec` 仍回 0，loop 靜默死亡〉。
- **「偵測留內、政策外放」的條文寫法，兄弟專案有成品**（見第 3 節 `freepy/agentloop/LIMITS.md`）。repo 這一側可以掛的位置：`docs/aos-folder.md`〈六、交接協定／彙整的規則〉那五條，以及〈彙整跑在哪裡〉那兩段。
- **「插延遲把窗口拉開」的替代路線——確定性 failpoint**，兄弟專案有可運行的實作（見第 3 節 `p1a2_model.py` 的 `Failpoints`）。p3 這一輪用的 gdb 斷點法（K1／K2／K3）是同一個目的的另一種做法，寫在本檔〈4. 三個主張各收到什麼／主張二〉。
- **提案 3、4 的原文出處**：`wf/workflows/workshop/records/exec-as-pure-cpu.md`〈轉交提案／一、要改 `docs/aos-folder.md` 的〉第 3 條（退出碼只帶類別）與第 4 條（`--loop` 停止條件寫成「回合開頭自己 `stat` 一次 `.runi`」）。
