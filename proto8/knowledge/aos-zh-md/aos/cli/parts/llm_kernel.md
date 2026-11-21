# `knowledge/aos/cli/parts/llm_kernel.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/cli/parts/llm_kernel.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**

# kernel_llm：llm kernel 的一輪

跑一次 = 一輪，然後結束：它是工具夾 `$AOS_HOME/lib/tools/aos/kernel_llm`，由 `aos-exec` 執行（`aos-exec $AOS_HOME/lib/tools/aos/kernel_llm [--enable-counters] kernel.json`）；你不用手動跑它。一個 loop 會一次又一次跑它：`{"exec": {"argv": ["aos-exec", <kernel_llm>, <kernel.json>]}, "interval_ms": 300}`，所以從一輪結束到下一輪開始至少隔 300 ms。這個 loop 要嘛是某個 daemon 自己的 `exec` 身體（範本 `templates/kernel/llm-kernel` 的 daemon.json），要嘛是掛在你已經有的 daemon 上的一個會循環的 proc（一個有同樣兩個鍵的 loop.json；例如某棵樹的 `kernels/llm-gpt` 就是以 proc 跑在 ws daemon 上）。每一輪都是新的程序，都會重讀 kernel.json，所以改了 kernel.json 從下一輪起生效，不用重啟。它自己的錯誤以 `kernel_llm:` 開頭。把 kernel 當成獨立專案啟動：

```sh
cp -r $AOS_HOME/templates/kernel/llm-kernel llms/def
cd llms && aos-exec --stack stacks/llm def      # then point agents at it: AOS_LLM_KERNEL=/abs/llms/stacks/llm
aos-daemon-ctl -d stacks/llm shutdown           # stop it
```

每一輪它會回覆已經完成的腦呼叫，並從 `$AOS_STACK/requests/` 替 `kernel.json` 裡的端點包挑出最該處理的等待中的信（slots、優先順序、預算）。壞掉的信會得到錯誤回覆；那不是 kernel 的錯誤。沒有 `AOS_STACK` 卻手動跑 = `StackMissing`。kernel 停著時，agent 只會等（不會失敗）。

腦呼叫在哪裡跑：有設 `$AOS_KERNEL` 時，每個呼叫都是送給它的一封 add 信，否則送到 `$AOS_DAEMON` 的 ctl 信箱（kernel 沒有 `next`）。所以啟動 llm daemon 的那個 shell 要 `unset AOS_KERNEL`，除非你是故意的。hook（`before_verdict`、`after_verdict`、`before_reply`）放在 `kernel.json` 旁邊的 `kernel_hookeds.json`（由它的 `interfaces.json` 裡的 `"hookeds"` 指名），寫法跟 kernel station 一樣（aos/kernel.json）：exit 10 擋下，失敗的 hook 會以 `HookFailed` 停掉這一輪；`kernel.json` 沒有 `hooks`。範本的 `interfaces.json` 也指名了 hook 點宣告（`"hooks": "kernel_hooks.json"`，只供閱讀），並有 `"kernel": {}`。範本的 daemon.json 用了 `$AOS_HOME`，所以啟動時必須設好 `AOS_HOME`。
