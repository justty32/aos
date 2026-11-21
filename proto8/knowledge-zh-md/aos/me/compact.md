# `knowledge/aos/me/compact.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/me/compact.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# compact：agent-fsm 對話歷史被摺起來之後，留住你繼續下去需要的東西

這是給 agent-fsm 身體用的。當你看到一則以 `[aos] compact:` 開頭、要求摘要的 user 訊息，就只回覆那份摘要，別的什麼都不要。那一次回覆你沒有工具可用。不要只因為被要求摘要，就把工作做完或放棄。

就在那個要求之前，身體會清掉舊的工具輸出，讓要求變小：它們的內容變成一行 `[aos] tool output cleared (N chars from TOOL); the original is in history_removed.jsonl`，要求裡會說清掉了幾個。你自己的訊息、你的工具呼叫連同參數、最後三個工具輸出、你最後一組工具呼叫的結果，以及短於 300 字元的輸出，都保持原樣。根據你對每個輸出說過和做過的事寫摘要；如果某個被清掉的輸出裡的確切值很重要，就說明它從哪裡來（檔案、路徑、工具），讓你可以再查一次。

把你繼續下去需要的一切都寫進去：誰要了什麼、信的名字和要回到哪裡、做完了什麼、你正做到一半的是什麼、下一步、所有還沒結的事、重要的檔案和路徑、你必須繼續遵守的規則和決定，以及你的 todo 和 goal。確切的識別名稱和路徑要保留原樣。你還沒回覆的信會保持不變，但你其餘的工作脈絡全靠你的摘要。

那次回覆之後，身體會把先前的對話換成一則以 `[aos] summary:` 開頭的 user 訊息，接著一則只回覆那些 /compact 信的 assistant `compact done: ...`，再接著它保留下來的 user 訊息，包括還沒回覆、維持原樣的信。如果壓縮打斷了進行中的工作，身體還會加上一則 user 訊息 `[aos] compact: done. Go on with the work in progress described in the summary above; letters you have not answered yet are above.` 這是繼續的指示：接著做工作，不是又一次要求摘要。

原文在 `<stack>/history_removed.jsonl`。你的摘要也會附加到 `<stack>/handoff.md`，每次壓縮一節。你的 todo 和 goal 不會改。規則與控制：`aos/me/compact.json#/rules`。

---

**`#/rules`**

# compact：規則與控制

- `/compact` 是送到你自己的 `<stack>/queue` 的身體指令，不是送到你的信箱。人或 hook 可以送它。如果你有選配的 events 工具包，可以用 `clock_register` `{"op":"add","name":"compact_once","after":1,"text":"/compact"}` 要求它（沒給 box 就是你自己的 queue）。內建的 agent-fsm 工具不含 events。沒有這種工具時，不要假裝你能送。`/compact` 後面空白之後可以接額外指示。
- 一輪中途，等所有工具結果都到了，身體就可以接受 /compact。它不會在一輪中途把一般的新信交給你。正在要求摘要時，idle 不收新信。/compact 會繞過 before_queue 和 after_queue hook。
- 可摺的訊息少於四則（必須保留的 user 訊息不算）就不呼叫腦，也不摺任何東西：身體用一則 assistant 訊息 `compact not needed: only N messages to fold (it takes at least 4); nothing was folded` 回覆那些 /compact 信（aos.compact 和 aos.skipped 為 true），ask/listen 拿到的就是這個回覆。這種回覆不算可摺的，所以壓縮完馬上再送 /compact，會得到同樣的回覆。對 /compact 來說，被丟掉的 `failed` 信現在只代表摘要失敗；ask/listen 看到的是 LetterDropped。
- 清掉舊工具輸出，發生在每次要求摘要的 /compact，在要求加進去之前；回覆 `compact not needed` 的 /compact 什麼都不清。每個被清掉的原文以 `{removed_at, op: "clear_tools", line, message}` 進 history_removed.jsonl，compact.json 記下 `cleared` 和 `cleared_chars`。已經清過的輸出不會再清。如果對話歷史一直在變或讀不了，身體會跳過清除、出一行警告，照舊要求摘要。
- hook before_compact 和 after_compact（你的內建定義在它們上面什麼都沒掛；掛在那裡的程式可以改變你被壓縮的方式）。before_compact 在某次 /compact 有足夠東西可摺時、清掉舊工具輸出之前跑：它可以擋下它（那些 /compact 信得到一則回覆 `compact blocked by hook H: ...; nothing was folded`，帶 aos.skipped 和 aos.blocked；在一輪中途時，那些信會等到這一輪結束，它會再跑一次）、改變你拿到的額外指示、保留舊工具輸出，或自己給出摘要（那就不會問你，你接下來看到的就是摺好的對話歷史）。after_compact 在摘要好了、對話歷史改寫之前跑：它可以改摘要，或給一段要加回去的文字，你會在摘要之後看到它，是一則 user 訊息 `[aos] restored after compact: ...`；它不是信，不用回覆。任一個上面的 hook 失敗，都只是一行警告，壓縮照樣繼續。compact.json 記下 `by`（brain，或給出摘要的那個 hook），被擋下之後還記 `phase: blocked` 和那個 hook 的名字。要掛一個：用 self_hook add，event 用 before_compact 或 after_compact（aos/me.json#/self_hook）。
- 空的摘要，或帶工具呼叫的摘要，都不能用。身體會移除那個要求，把那些 /compact 信當失敗丟掉，保留先前的對話。腦失敗照一般的冷卻/停止規則。沒有摘要和 compact done 那兩列，就不要宣稱壓縮成功了。
- 還開著的 do_task 開始標記可能被摺掉。之後的 do_task end 就會以 MarkerMissing 結束那個工作，什麼都不摺；這是預期的，不是重試 end 的理由。身體不改 tasks.json。
- 用 --history task 時，摘要要求還是拿到完整的對話歷史。摺完之後，當中間的 assistant 列只有 compact done 列（aos.compact 為 true）時，會納入適用的摘要。一輪中途的繼續會直接接著做，不帶 idle 的 goal 提醒。idle 時的壓縮保留一般的 goal 提醒。
- 新的 agent-fsm 定義會啟用 context_wrap，on_clock 每 5000 ms，config {"percent":35,"wrap":false}。到達上限時它直接送 /compact：摘要就是交接，沒有另外的收尾回覆。
- fsm 的讀數是最後一次有效的 think usage.prompt_tokens，除以 kernel 公布的端點包 context。如果沒有 prompt_tokens，就用 input_tokens 加 cache_read_input_tokens 加 cache_creation_input_tokens。不算 completion tokens。壓縮那次的觀測不算 think 讀數。config.window 會蓋過工具包的 context；window 和有效的 usage 都沒有時，這個 hook 什麼都不做。
- 要改門檻，就改 context_wrap hook 項目裡的 config.percent（1 到 100），或用 self_hook add 再加一次，replace 設 true，並給完整的 config，wrap 保持 false：{"op":"add","event":"on_clock","every_ms":5000,"name":"context_wrap","path_json":{"$env":"AOS_HOME","$path":"/lib/tools/agent/context_wrap"},"config":{"percent":50,"wrap":false},"timeout_ms":20000,"replace":true}（aos/me/self_hook.json#/answer）。有授權的管理者可以用 JSON 工具寫這個 hook 項目。要關掉自動的 hook，有的話用 self_hook {"op":"rm","name":"context_wrap"}，或請管理者把你 stack 的 hookeds.json#/context_wrap 設成 null。這不會停用手動的 /compact。
- context_wrap --reading <stack> 印出讀數，或為什麼沒有讀數。hook 維持在已壓縮狀態時，壓縮不會重複；之後一次一般的 think 讀數必須低於門檻，才會重新上膛。跑很久的工具只在那一步結束後才檢查；單一個過大的工具結果，這個 hook 救不了。摘要品質看模型：需要時去查保留下來的原始信、history_removed.jsonl 或 handoff.md。
