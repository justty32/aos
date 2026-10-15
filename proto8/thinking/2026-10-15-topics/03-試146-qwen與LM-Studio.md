← [回入口](../2026-10-15-topics.md)｜上一份：[02-agent工具與試146](02-agent工具與試146.md)｜下一份：[04-agent當函數](04-agent當函數.md)

## 8. 試 146 ollama：qwen2.5:14b

**原文**：「試試看 qwen2.5:14b」（主對話親口；ops-notes 同時監控）。

**做了什麼**（10-15 02:57:45～02:58:22Z）：用改好的 fsm（連錯 3 次停住）在 scratchpad 複製 demo/fsm，腦換成 `brain/qwen146.json`（`qwen2.5:14b-instruct-q4_K_M`，num_ctx 4096、keep_alive 30s），一拍一拍敲。共 10 次請求：`/api/tags` 1、`/api/ps` 5、`/api/chat` 3（腦）＋1（keep_alive 0 卸載）。第一次載入後 `/api/ps`：size＝size_vram≈9.7 GB，全在 GPU；最後卸載、`/api/ps` 空。

**結果**

| 問 | 腦叫幾次 | 延遲（ask 那拍） | 工具 | 最後回覆 |
|---|---|---|---|---|
| 現在幾點？ | 2 | 15.2 秒（含載入）、3.5 秒 | `clock`，`tool_calls` 形狀正確（ollama 沒給 id，腦編 `call_x5xq7f2d`；arguments `"{}"`） | 「현재 시간은 10시 58분 3초입니다.」（韓文） |
| 用一句話介紹你自己。 | 1 | 2.9 秒 | 沒叫（有帶 tools，模型自己沒用） | 「我是由阿里雲開發的語音助手Qwen，能夠回答問題、創作文字和完成各種任務。」 |

- 整圈 idle → thinking → tool → thinking → idle 第一次對真模型跑通；fsm 沒出錯、沒觸發停住。
- history 摘錄：assistant 第一則 content 是泰文（「…โปรดรอสักครู่…」）＋ tool_calls；tool 回 `{"code": 0, "result": {"time": "10:58:03"}}`；第二則韓文。

**挖到的邊緣狀況（攤給使用者）**
- 帶 tools 時回覆語言亂跳（泰文、韓文），沒帶工具結果的那題正常中文。history 沒有 system 訊息；要不要讓 agent 設定能放 system prompt（例「用繁體中文回答」），由使用者定。
- CPU：qwen 雖 100% GPU，整機 CPU idle 曾掉到 1.9%（ollama 容器約 19.5 核）；ops-notes 要求暫停，見 [dev-env](../../../wf/workflows/dev-env.md)。
- 第一次叫腦含載入 15 秒：`think/ask.json` 的 `timeout_ms` 200 秒夠；loop 拍的話 `loop.json` 的 20 秒不夠（這次是手動一拍一拍敲）。

## 9. 試 LM Studio：Qwen3-1.7B

**原文**：使用者允許在公司這台用 LM Studio 試 agent（「可以」）；同時定「那就都用本地的就好，別碰146」——146 不再使用，一律用本地（[dev-env](../../../wf/workflows/dev-env/01-跨機與外部工具.md#跨機--離線差異)）。

**做了什麼**（10-15）：試前 `lms ps` 沒載模型、server 沒開。`lms server start -p 1234`（沒加 `--bind`，只聽本機）；WSL 是 mirrored 網路，`localhost:1234/v1` 直接通。`/v1/models` 拿到 id `qwen/qwen3-1.7b`；`lms load qwen/qwen3-1.7b -c 4096 --ttl 600 -y`（4.7 秒載好、1.56 GiB）。腦用現成的 `aos_brain_openai.py --base-url http://localhost:1234/v1`（demo 加 `brain/lmstudio.json`），沒設 `max_tokens`。在 scratchpad 複製 demo/fsm 一拍一拍敲。共 4 次 chat 請求（fsm 3 次＋直接 curl 1 次看原始回應）。收尾 `lms unload --all`、`lms server stop`，`lms ps` 空、server 沒開、1234 連不上。

**結果**

| 問 | 腦叫幾次 | 延遲（ask 那拍） | 工具 | 最後回覆 |
|---|---|---|---|---|
| 現在幾點？ | 2 | 3.9 秒、4.5 秒 | `clock`，`tool_calls` 形狀正確（LM Studio 給 32 字的亂數 id、arguments `"{}"`、content `""`） | 「現在時間是11:05:34。」（中文，對） |
| 用一句話介紹你自己。 | 1 | 8.2 秒 | 沒叫（有帶 tools，對） | 「我是一個AI助手，可以幫助你解答問題、分享知識並提供支持。我是友好的、可靠的夥伴，隨時準備為你服務！」（兩句，不算一句） |

- `<think>` 沒漏進 content：LM Studio 把想的字放在另一個欄位 `reasoning_content`（直接 curl 看到：簡體中文的推理約 86 token），腦只取 `content`，所以 history 乾淨；想的字也就丟了。
- 跟 146 的 qwen2.5:14b 比：語言沒亂跳（都中文），延遲多花在「想」。

**挖到的邊緣狀況（攤給使用者）**
- `reasoning_content` 被丟掉：要不要留（例存進 work 或 history 旁），由使用者定。
- 「想」佔 token 也佔時間：沒設 `max_tokens` 時一題 4～8 秒；要設上限得 1500 以上，不然想完就沒字可回。
- LM Studio server 開著、模型 `--ttl 600` 閒 10 分鐘會自己卸，但 server 不會自己關——試完一定手動關。

## 10. 丟掉想的內容、加系統提示

**原文**：使用者（10-15）看完 §9 的邊緣狀況後說「（模型想的內容）丟掉。加上系統提示。」

**決定**
- `reasoning_content` 等想的字**一律丟**，腦只留 `content`／`tool_calls`（agent.md 已寫明），不另存。
- agent 設定加選填 `system`＝系統提示檔路徑（沿用 [07 §12.1](../2026-10-14-json-entry/07-fsm樹與一拍.md) 的 `"system":"system.md"` 想法）。think 每次叫腦在 messages 最前面插 system 訊息，**不進 history**（改檔下一拍生效）；沒寫＝不帶；檔讀不了＝`SystemUnreadable`（N-29）。
- demo 加 `demo/fsm/system.md` 並接進 `agent.json`、`think/fsm.json`；假腦照舊不理 system。測試 `AgentSystemTest` 3 個。沒碰任何 endpoint。
