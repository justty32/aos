# `knowledge/aos/me/self_llm.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/me/self_llm.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**

# 改你自己的腦設定

工具 `self_llm` 就是對準你的 `aos-agent llm`。它只改你自己的腦設定；你的定義和其他 agent 保持原樣。改動從你下一次腦呼叫起生效。

`model` 選你的腦（llm kernel 的一個腦工具包名稱）。其他鍵只調整它怎麼回答，不會改變你是哪個腦：`temperature`、`top_p`、`max_tokens`、`seed`、`presence_penalty`、`frequency_penalty`、`stop`。`reasoning_effort`（agent-fsm）設定腦想得多用力（`low`、`medium`、`high`、`xhigh`、`max`；只能用你的工具包接受的名稱，見 `aos-llm ls --json`）。你的身體讀哪些鍵，看你是哪一種 agent：eca agent 讀 `model` 和 `reasoning_effort`。eca 的話，effort 交給它的 CLI（claude：`low`、`medium`、`high`、`xhigh`、`max`；pi 另外還有 `off`、`minimal`）；CLI 不收的等級會讓你停下（`CfgBad`），直到它被改掉或移除。

每次呼叫一個 op（JSON 就是工具的參數）：

- 看：`{"op": "ls"}`（每行一個 KEY=VALUE：定義的設定，上面疊著你的改動）；`{"op": "ls", "long": true}` 另外會說哪些鍵是你改的（`agent`）、哪些來自你的定義
- 改：`{"op": "set", "settings": {"model": "smart-high", "temperature": "0.2"}}`（值是字串；你的身體不讀的鍵照樣留著，附一行警告；鍵 `system` 會以 ArgumentsBad 拒絕，什麼都不存：你的系統文字要用 `self_system` 改）
- 復原部分改動：`{"op": "rm", "keys": ["temperature"]}`（回到你定義的值；你沒改過的鍵是 `KeyMissing`）
- 復原你所有的改動：`{"op": "reset"}`

規則：

- 先用 `ls`，一次只改一樣。
- 沒有東西擋你選一個不能用的腦。如果你這樣做，你會停止回覆，直到有人跑 `aos-agent llm --target <you> reset`。只換到別人告訴你確實存在的模型。
- 腦工具包可能固定某些調整用的鍵（例如它的 `temperature`）；那就不要設那個鍵：agent-fsm 身體每次腦請求都會送出你的值，llm kernel 會以 `RequestBad ... is fixed by endpoint <pack>` 拒絕請求；用 `rm` 把那個鍵移除。
- 不認得的參數名稱，或這個 op 不收的參數，是 `ArgumentsBad`。`LlmBad`：你的腦設定檔（你的或你定義的）壞了；必須由人來修。
- `DaemonMissing`、`DaemonFailed`、`InstanceMissing`：跟 `self_tools` 一樣（這個功能暫時不能用；照實說）。
