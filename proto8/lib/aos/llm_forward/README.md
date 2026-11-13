llm_forward 是端點轉交函數：包寫下一層 kernel 與代號，成功串帳，失敗原樣轉交。

← [lib](../../README.md)｜[隊 kernel 範本](../../../kernel/llm-team/)｜[kernel 契約](../../../impls/aos-llm-kernel/docs/01-用法.md)

平常由 llm kernel 經 `aos-exec` 呼叫。stdin 是 `{"endpoint":{"to":"fake","kernel":"/下層/stack"},"request":{"messages":[...]},"priority"?:...}`。`to` 與 `kernel` 必填非空字串；request 原樣、priority 有就原樣帶給 `aos-llm ask --full`。只對子行程設 AOS_LLM_KERNEL、拿掉 AOS_STACK（那是這封請求自己的小格），其他環境繼承；下一層的寄件人＝這台上層 kernel（aos-llm 沒有 `$AOS_STACK` 時照 `identity()`＝`$AOS_WS`），整台算一個寄件人、不冒用原 agent（11-13 線修：aos-llm 改 `$AOS_STACK` 優先後，不拿掉會每封一個寄件人）。

成功把下層回覆的 letter 換成 `child:{"kernel":包的原字串,"letter":信名}`，其餘鍵保留，印一行 JSON、退 0。上層 kernel 只把 child 收進自己的 ledger，不放回信。下層失敗時 stdout、stderr 原位元組轉交，退同一個碼，不增加自己的錯誤行。

自己的錯只在 stderr 印 `llm_forward: error: CODE reason`、退 1：stdin／包不合是 CfgBad，啟動 aos-llm 失敗是 LaunchFailed，成功輸出不是一行帶 letter 字串的物件是 ReplyBad。缺 kernel 的精確錯誤是 `llm_forward: error: CfgBad endpoint pack has no "kernel"`。`--help` 列英文契約與旗標；PATH 必須有 aos-llm。metadata 只估自己的開銷（700 ms、一次呼叫、零 token），下層花費在下層帳。
