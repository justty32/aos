# 2026-11-04 晚 思考是一個 aos 函數：問腦＝寄信給 llm kernel、收回信（fable 規劃，沒改程式）

← [thinking README](../../../README.md)｜日 [2026-11-04](../README.md)｜前情：[aos-agent 06/03](../aos-agent/06-衝突與方向題/03-新題-tools-llm.md)（`AOS_BRAIN_URL`「我不喜歡」「我再想想」；`llm` 子介面）、[loop-fsm-agent](../loop-fsm-agent/README.md)（`demo/agent-fsm` 的 think 格直接打端點）、[10-24 llm-kernel](../../../2026-10/24/llm-kernel/README.md)（閘門＋信箱）、[11-03 aos-post](../../03/aos-post/README.md)、[11-01 playground-bob 02](../../01/playground-bob/02-環境變數要使用者裁的問題.md)（腦「未來會被統一管理」）、[four-elements](../four-elements/README.md)（N-63 四種性質表）｜程式（只翻、沒改）：[aos-llm-kernel](../../../../impls/aos-llm-kernel/README.md)、[aos-llm-send](../../../../impls/aos-llm/README.md)、[aos-post](../../../../impls/aos-post/README.md)、[aos-daemon](../../../../impls/aos-daemon/README.md)、`demo/agent-fsm`、`bin/aos-llm`、`bin/aos-tools`｜條文：[C-19、C-20、C-42、C-46](../../../../docs/CONCEPTS/05-agent.md)、[C-47](../../../../docs/CONCEPTS/04-kernel.md)、[C-52、C-56、C-68～C-70](../../../../docs/CONCEPTS/01-設計理念.md)、[N-16](../../../../docs/NORMS/05-基礎設施-窗.md)、[N-42](../../../../docs/NORMS/09-kernel.md)、[N-63、N-64](../../../../docs/NORMS/10-基礎設施-定義與工作區.md)、[P-15、P-17、P-20、P-23](../../../../docs/CONVENTION/02-題目stack停錯腦.md)

狀態：**11-04 晚已實作**（使用者在外，隊長照 [05](05-衝突與方向題.md) 推薦先做；四題 11-04 晚使用者都選推薦，已定案；commit、手跑、實作時代定與改設計在 [07](07-實作結論.md)；條文已改）。原規劃時的狀態：規劃、沒改程式、沒改條文（當時另一個 opus 在 tidy 條文）。本檔只記使用者原文（逐字）、決定、fable 照原則定的結論（可翻案）、未決（[user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。

## 使用者原文（11-04 晚，逐字；給的方向）

> brain url那塊我不喜歡，我希望llm呼叫，或者說思考，這本身也是用aos函數

> 並且可以的話，考慮非同步呼叫，也就是正在跑的loop不停。

> 然後aos llm,tool這兩個，我希望他們的定位是跟aos post一樣，作為基礎工具

> llm呼叫這塊，我希望是把請求丟到llm kernel(一個loop)，處理好後收回信

> 也可以是一個daemon，實際endpoint呼叫就是aos exec

> 包起來的

之前的：11-04 下班後「AOS_BRAIN_URL，我不喜歡這個環境變數」「我再想想」（[06/03](../aos-agent/06-衝突與方向題/03-新題-tools-llm.md#使用者原文11-04-下班後逐字aos_brain_url)）；11-01「腦這東西未來會被統一管理，大多agent都是向某個kernel遞送請求，由那個kernel統一向endpoint發起。那塊就到時候再說。倒是可以有個AOS_BRAIN，用於指向那個kernel或之類的。」（[playground-bob 02](../../01/playground-bob/02-環境變數要使用者裁的問題.md)）；10-24「LLM kernel，也就是把brain這塊弄成一個請求，而不是直接打API，請求會被丟到某個地方，由kernel排隊跑」（N-42）。

## 決定（使用者，11-04 晚；原文見上）

- 問腦＝**把請求寄進 llm kernel、處理好後收回信**；kernel 是一個 loop，也可以是一個 daemon（掛在 daemon 上的 proc）；實際打端點那一下是 **aos-exec 包起來的**。
- **非同步**：寄完的那個 loop 照跑、不卡著等；之後再收回信。
- **`aos-llm`、`aos-tools` 是基礎工具**，定位同 aos-post（IPC 的語法糖、基底工具，跟 aos proc 關聯不深，proc 自己拿它們組），不是 aos-agent 的附屬。
- `AOS_BRAIN_*` 環境變數不要；端點、模型、金鑰歸 kernel 的定義。

> 我是希望走2

> 除此之外，各種llm設定也可以包裝，這樣寄信的時候只要寫簡單的代號就可以

- **llm 設定包成代號**：kernel 定義裡預先登記幾組設定（端點、模型、金鑰、溫度…），每組一個代號；寄信只寫代號（例 `"haiku"`、`"local-qwen"`），kernel 照代號取用（[02 § 3](02-設計-信與kernel.md)）。
- 「包起來的」＝**讀法 ②**（使用者 11-04 晚裁）：那個 daemon 被包在 llm kernel 的信箱介面後面，呼叫端只看到「寄請求、收回信」；裡面是 daemon＋loop＋aos-exec 打端點，全是封裝細節。（讀法 ①「端點呼叫包成 aos 函數由 aos-exec 跑」只是裡面的做法，見 [02 § 3](02-設計-信與kernel.md)、[02/01 § 4](02-設計-信與kernel/01-endpoint函數-aos-llm-kernel形態.md)，不是對外介面。）

## 一句話

**agent 的 think 格不再自己打端點**：它把 OpenAI 形狀的請求（messages、tools、選填 model）寫成一封信寄進 `$AOS_KERNEL` 信箱（`aos-llm send --reply-to 自己的回信信箱`），馬上退 0；loop 照常每隔 `interval_ms` 跑下一格 `wait`（`aos-llm recv`：回信沒到退 10 停在 wait、到了接進 history 退 0）。kernel 這邊是**現成的 aos-llm-kernel 改一件事**：信裡不再帶「單子＋整份環境」，而是帶請求；kernel 用 **aos-exec 跑自己定義裡的 endpoint 函數**（`kernel.json` 的 `exec`，stdin＝`{"endpoint": {url, model, key}, "request": …}`、stdout＝`{"message", "usage", "model"}`），把 stdout 當回信照 `reply_to` 寄回。端點、模型、金鑰只在 **kernel 的 `kernel.json`**；呼叫端只要知道 `AOS_KERNEL`（N-63 ② 現成的 hub）。kernel 本身＝一個資料夾程式 `demo/llm-kernel/`（`_entry`＝aos-loop、`loop.json` 每 300 ms 拍一次 `aos-llm-kernel kernel.json`），可以 `aos-daemon-ctl add` 掛成 daemon 的 proc。`aos-llm`＝寄單／收回信那支基礎工具（由 aos-llm-send 改名、長出 `send`／`recv`／`ask`／`regret`）；`aos-tools` 現狀就是基礎工具、不動；aos-agent 的 `llm`／`tools` 子命令縮成語法糖。

## 分檔目錄

| 分檔 | 涵蓋 |
|---|---|
| [01-現況](01-現況.md) | `AOS_BRAIN_*` 在哪、現在三條問腦的路、kernel／閘門／信箱做到哪、條文裡「函數」「工具」「腦」怎麼定 |
| [02-設計-信與kernel](02-設計-信與kernel.md) | 請求信與回信的形狀、`kernel.json`（`endpoints` 代號表、`exec`）；[02/01](02-設計-信與kernel/01-endpoint函數-aos-llm-kernel形態.md)＝endpoint 函數、`aos-llm` 基礎工具的子命令、kernel 當 loop／daemon、「包起來的」、跟現有 C++ kernel 的關係 |
| [03-呼叫端](03-呼叫端.md) | agent-fsm 的 idle／think／wait／act、eca、工具自己要腦（json_edit、pyfix）、aos-agent `llm`／`tools` 子命令怎麼縮、沙箱 |
| [04-邊緣狀況](04-邊緣狀況.md) | 失敗、逾時、取消、同時好幾封、kernel 不在、重啟、串流、成本、遞迴、金鑰、舊信 |
| [05-衝突與方向題](05-衝突與方向題.md) | **要使用者看的**：衝突 2、方向題 2（白話、推薦放第一）；fable 代定的清單 |
| [06-實作步驟](06-實作步驟.md) | 步 0～3（endpoint 函數、kernel、aos-llm、demo kernel）；[06/01](06-實作步驟/01-步4～8.md)＝步 4～8（agent-fsm、aos-agent／eca、驗收、條文、試驗場）；給隊長、不實作；驗證＝build 得過＋手跑 |
| [07-實作結論](07-實作結論.md) | 11-04 晚實作：commit、手跑、實作時代定與改設計（可翻案）；第 13 條兩題 11-04 晚使用者已裁定 |
| [08-邊緣狀況實測](08-邊緣狀況實測.md) | 11-04 夜 A 線實測 28 種邊緣狀況（假 OpenAI 伺服器、kill -9、鎖、done/ 累積…）：修了 4 個小 bug、**留 4 題給使用者**（AOS_KERNEL 打錯默默寄、搶不到鎖 loop 停、done/ 平方成長、recv 分不出永遠不會回） |
