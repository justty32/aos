# `knowledge/aos/cli/parts/llm.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/cli/parts/llm.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/cli/parts/llm.md#/…` 對的就是它。改請改正本，再照 [README](../../../README.md) 的做法跟上這份。

---

**`#/aos-llm: ask the llm kernel`**

# aos-llm：問 llm kernel

send、ask 和 regret 需要 `AOS_LLM_KERNEL`＝llm kernel 的 stack（沒設＝`LlmKernelMissing`）。ls 先選 `--kernel NAME|PATH`，再來是 `AOS_LLM_KERNEL`，再來是 `$AOS_DAEMON` 表上唯一的那一列 llm kernel。旗標值含有 `/` 就是 stack 路徑（相對於目前所在的資料夾）；不然就是表上某一列的名字。一個都沒對到或對到好幾個＝`LlmKernelMissing`，並附上 `--kernel` 的提示；對到好幾個時會列出它們的名字。agent 透過它們的腦來問；這個是讓你手動試端點包用的。

```sh
aos-llm ls --kernel llm-local     # a named row on AOS_DAEMON's table
aos-llm ls --kernel ./stacks/brain # an explicit kernel stack
aos-llm ls      # fake<TAB>fast<TAB>free<TAB>-<TAB>-<TAB>-<TAB>fake brain: ...
echo '{"request": {"messages": [{"role": "user", "content": "hi"}]}}' | aos-llm ask
# {"role": "assistant", "content": "FAKE ANSWER to: hi"}
echo '{"request": {"messages": [{"role": "user", "content": "two"}]}, "endpoint": "fake", "priority": "high"}' | aos-llm send --reply-to BOX
aos-llm recv BOX LETTER          # exit 10 = no reply yet; --full adds usage, model and letter
aos-llm regret LETTER            # withdraw a request still waiting
```

自動偵測只看那一列的 stack：裡面必須同時有 `endpoints.json` 檔和 `requests/` 資料夾。表的各部分和相對於 daemon stack 的 stack 路徑都支援。

ls 的欄位（TAB）：name、speed、cost、context、slots、backend、summary。沒有 `endpoint` 的請求內容（body）用 kernel 的預設端點包（pack）；不認得的＝`EndpointUnknown`。`send` 和 `ask` 接受 `--priority P`（蓋過 body 裡的）；`ask --full` 印的跟 `recv --full` 一樣。body 也可以帶 `reasoning_effort`（aos/brain.md）。`recv --quiet` 不印為什麼還沒有回覆的警告（給輪詢用）。`ls --json` 把窗口（window）印成 JSON；`EndpointsMissing`：kernel 還沒跑過。對 kernel 已經拿走的信做 `regret`＝`RegretFailed`。端點包（pack）和優先順序：`aos/brain.md`。

更多旗標：跑 `aos-llm --help`。
