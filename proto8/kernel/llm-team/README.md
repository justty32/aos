llm-team 是隊 kernel 範本，用包指定下一層 stack，透過 llm_forward 轉交問腦信。

與 [`llm-kernel`](../llm-kernel/) 的 stack 並排，兩者各有一份 `def/`，各在 stack 執行 `aos-exec --stack . def`。完整佈局、repo 外的 lib 路徑、額度與串帳方式見 [kernel 說明](../docs/01-llm-kernel.md#隊-kernel-範本-llm-team一封信走兩層)。

寄信方只設 AOS_LLM_KERNEL 指向隊 stack；預設 fake，另有 sol、terra、luna、local。timeout 180000 ms，大於主 kernel 的 120000 ms。daemon 的環境不改 hub；每包 kernel 用 AOS_STACK 加 ../llm-kernel 解出下一層，interfaces.json 宣告本層 ledger。
