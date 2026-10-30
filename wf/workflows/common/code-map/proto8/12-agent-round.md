← [入口](../proto8.md)｜涵蓋：agent-round 的格（`proto8/lib/agent/` 的 round、queue、history、compact、act，`proto8/lib/endpoint/`）與它們的測試、範本 `demo/agent-nia`，10-28 晚｜下一份：[12-agent-round-2](12-agent-round-2.md)（範本 agent-nia、round 當外部接口、測試）｜工具庫其他部分見 [09-lib](09-lib.md)

### agent 自己的格（不是給腦叫的工具）

一輪（round）照順序叫的那幾格：每格一個資料夾程式，叫法 `aos-exec <格> <agent 資料夾絕對路徑> [子命令]`，stdin／stdout 是資料、錯 stderr 一行 `名: 代號 原因` 退 1；格與格之間經 `aos-parts --file <agent>/parts.json which --json 槽` 互相找。沒有 `_tooldef.json`／`_metainfo`（不是工具）。設計與代定：[thinking 2026-10-28 agent-round](../../../../../proto8/thinking/2026-10-28-agent-round.md)（§ 2～§ 5、文末「實作時代定」）；說明在 [lib/README「agent 自己的格」](../../../../../proto8/lib/README.md)。

| 哪裡 | 負責什麼 |
|---|---|
| `lib/agent/round/_entry` | 一輪的骨架：照「從哪接著做」（10-30 起看 queue 的 `$AOS_STACK/queue/cur/`、`new/` 與 `current.txt`，[agent-lifecycle](../../../../../proto8/thinking/2026-10-30-agent-lifecycle.md) 第 2 步；`cur/` 有沒列進 `current.txt` 的信＝補認領、不叫 pre_round）認領 → 問腦 → 跑工具 → 交卷（`queue finish`，答案就是 history 最新那則 assistant），叫 `hook/pre_round`、`pre_think`、`post_think`、`on_error`、`pause`、`post_round`；endpoint 照 `$AOS_STACK/endpoint.txt` 選、on_error 的 retry／switch（上限 `MAX_RETRIES`，預設 3）；act 退 10（插話）就 `queue claim --more`；queue 空照 `ROUND_ON_EMPTY`（`stop` 退 10、`idle` 退 0 不做事）；每叫一格 `$AOS_STACK/trace.jsonl` 一行；`--step`＝只做下一格（給 aos-loop 一格一格跑） |
| `lib/agent/queue/_entry` | queue 格（10-30 改，[agent-lifecycle](../../../../../proto8/thinking/2026-10-30-agent-lifecycle.md) 第 1 步）：`$AOS_STACK/queue/`（N-16 有順序的信箱）的 push（沒有就 `aos-post init`＋`send --ordered`，stdin 一則 message）／pop（信不在 `new/`、`cur/` 就印 history 最新沒有 tool_calls 的 assistant）／claim [--more]／peek／current／done／emit／finish [--keep]（`cur/` 全部 `aos-post finish`）／withdraw（`aos-post withdraw`）；claim 先 `aos-post claim` 搬 `cur/`、再把 body 經 history 格接上、最後寫 `current.txt`（`cur/` 有沒列進 `current.txt` 的＝補完）；壞信（非有序、check 不過、body 不是 message）`aos-post finish` 丟掉 |
| `lib/agent/history/_entry` | 對話紀錄格：`$AOS_STACK/history.jsonl` 的 append／read／compact（compact 收 stdin 的短版，舊的整份收進 `history_archive/<UTC 毫秒>.jsonl` 再換上，`--expect-bytes`） |
| `lib/agent/compact/_entry` | 掛在 `hook/pre_think`：history 超過 `MAX_BYTES` 才壓（三步土法：工具呼叫各一句 → 逐段總結＋保留行 → 修飾），壓好的交給 history compact 換上；半成品與報告在 `$AOS_STACK/compact/`；來源 demo/agent-hal/compact |
| `lib/agent/compact/ask.py` | compact 格問腦（經 endpoint 格）與讀回覆（容許 ``` 包起來的 JSON、讀不懂走退路） |
| `lib/agent/compact/prompts/` | 三步的提示詞：`note.txt`、`segment.txt`、`final.txt` |
| `lib/agent/act/_entry` | 跑工具格：吃一則 assistant，每個 tool_call 經 `hook/pre_tool`（10＝不跑）→ `aos-tools call` → `hook/post_tool`，吐一行一則 tool 訊息、照原順序；`MAX_PARALLEL` 一批一批跑；批與批之間 queue 的 `$AOS_STACK/queue/new/` 有信就問 `hook/on_interrupt`（10-30 起，原本看 `$AOS_WS/new/`），interrupt＝剩下的接「被打斷」、退 10；全有或全無 |
| `lib/endpoint/fake/_entry` | 假腦：最後一則 user＋tools 有 clock＝叫 clock，否則 `FAKE ANSWER to: …`（接過 tool 附 clock said）；不連網、不寫 usage |
| `lib/endpoint/openai/_entry` | OpenAI 相容腦：stdin 請求體 → `{AOS_BRAIN_URL}/chat/completions` → 一行 assistant（只留 role／content／tool_calls）；usage 追加 `$AOS_STACK/usage.jsonl`；錯 `BrainFailed`／`KeyBad`／`ModelUnknown`／`RequestBad`／`ReplyBad`／`UrlMissing`／`TimeoutBad` |
