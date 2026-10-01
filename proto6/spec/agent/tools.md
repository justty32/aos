# 工具選擇與結果解讀

← [Agent](README.md)｜[兩條通則](../README.md)

> **〔2026-10-01 殘留註記〕本篇是 2026-10-01 之前的設計，下列內容現在不是現行的**；原文照留，以這裡指的正本為準（各批裁定見 [verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md)）：
> - 標準任務表範本（[B-629](../settled/deferred/template.md)）、`aos-mq get`／`post`（[B-623、B-624](../settled/deferred/mq.md)）、`aos-clean`（[B-404](../base/storage.md) 的系統級任務部分、P-605）：第十八批暫緩，現行沒有系統級任務；kernel／agent 範本裡掛的這些項也跟著不成立。現行收發信是 daemon 訊息模組 `aos-mq send`／`take`／`peek`（[B-645](../settled/daemon/mq.md)）。
> - node：tick 層改稱「工作資料夾」，daemon 只認設定檔 `insts` 的一項；node 模組不做（[名詞](../settled/terms.md)、[node 模組方向](../../notes/verdicts/11-tick-as-unit.md#node-模組方向2026-10-01記錄用未排程)）。本篇講的 node、上下層、kernel／agent 角色都是舊設計。
> - 舊 daemon 的通道與憑證（`AOS_TICK_TOKEN`）、登記、runner、`state.json`：整套在暫緩區（[舊 daemon](../settled/deferred/daemon/README.md)）；現行 daemon 只定期叫 `aos-exec` 加各模組（[B-640](../settled/daemon/core.md)）。

## A-401 工具清單與參數

〔建議預設，未拍板〕工具清單是設定檔，描述工具名稱、用途、參數 schema、要跑的程式與參數，以及回傳文字或 JSON 的解讀方式。名稱在清單內唯一；宣告 JSON 回傳時提供結果 schema。實作只接納它能驗證的 schema，不默默忽略不支援的規則。增刪工具沿[設定更新](configuration.md) 的做法。

模型呼叫帶呼叫 ID、工具名稱與參數。同一回覆中的呼叫 ID 不重複；未知工具、參數不合 schema 或回覆格式錯誤時不派工，留下具體錯誤供下一次思考。清單的程式設定負責把合法參數轉成普通工作材料，JSON 與 adapter 格式見 [P-702](../protocol/agent-tasks.md)，不另訂工具專用權限。

格式修補必須有限：預設連續兩次模型回覆格式無效就停止自動修補，不再派修補請求，並寫[待處理事項](../scheduling/operations.md)；合法回覆把計數歸零。計數只是 node 的普通狀態檔。

〔使用者方向 2026-09-29；第十九批改經通道〕`tools.target_node` 決定路線：填 node id 時，把 `kernel.work.submit` 請求交該 kernel，由它管額度、排程及 once；填 `null` 時，agent **自己經 daemon 通道掛 once**：下一格用本格憑證送 `node.mount`（[B-613](../settled/deferred/daemon/channel.md)、[P-118](../settled/deferred/protocol/daemon/channel.md)），掛的目標是 `.aos/jobs/<attempt_id>/` 裡那份 inst；上層由憑證認出，就是 agent 自己，不帶 `identity_grant`；掛行程立即開跑，不需要另外 wake。工具跑的帳號落在 agent 的身分額度內（B-613；inst 頂層沒有 `user`，2026-10-01）。once 屬標準配備（[B-629](../settled/deferred/template.md)），通道只有 daemon 開的格才有，人手或 cron 跑的格沒有通道，掛不了。agent 記用量供上層用量收集 module 讀。兩條路線共用工作結果格式，once 用量都歸發起 agent。提交及收結果依[通用 tick](../settled/tick.md)。

〔使用者方向 2026-09-30，第十八批，維持第十七批〕`tools.target_node=null` 時 agent 自己開的 once 做完，**aos 不叫醒 agent**；結果由 agent 自己想辦法收，例如把摘要的 `due_ms` 設成下次查看的時間，讓上層到時叫醒它，醒來再去看 `result.json`／`.err`。查看間隔放在哪（例如 agent 設定的一欄）延後（[P-008](../protocol/README.md#p-008)）。〔第十九批〕自開 once 的取消與收尾：agent 用 `node.kill` 砍掉（[B-613](../settled/deferred/daemon/channel.md)）；核權看掛它的那個 tick 的路徑，不看當時的憑證，所以隔了幾格也砍得掉。

〔第十八批，P-707 從協議篇搬上〕**模型決定與兩種工具路線的行為**：

- 只解讀已收結果。最後一次 LLM 成功、`finish_reason=stop`、沒有 tool_calls、content 非空，而且沒有未結或 unknown 的工作，才準備成功的 final。
- 有 tool_calls 時先驗整批：名稱、唯一呼叫 ID、arguments 是 object、對派出時保存的工具 schema。有一項無效就整批不派，每個 call 留未派原因，保持呼叫與結果成對；`invalid_count` 加一，第一次可問一次修補，連續第二次 needs_attention。重號等無法配對時，原文留 response，以 developer 事件記錯。合法決定歸零；length、空回覆、未知 finish_reason 也最多修補一次。
- 合法的工具照 calls 順序建材料，走上面兩條路線之一：`target_node` 是 node id 用 `kernel.work.submit`（params.argv 對應 `aos kernel work submit`，業務 JSON 經 stdin，投到該 kernel）；`target_node=null` 則先提交工作材料，下一格經通道掛 once（上面）。兩路都沿 [P-402](../protocol/work.md)，結果下格收，不讓工具自選資源歸屬。
- 模型文字可作 progress，沒有文字就寫正在用哪些工具。工具全回後按 calls 順序寫結果、預覽及引用，再問 LLM；確定失敗可交模型判斷，unknown 停新副作用並記事項，不因改設定重跑（[S-401](../scheduling/operations.md)）。卡在 unknown 的輸入之後怎麼收，延後（P-008）。

〔第十八批，P-710 從協議篇搬上〕**agent 自記用量**：每筆用量帶 `kind:llm|tool`。LLM 請求建立時記 pending，結果改 completed、rejected 或 unknown；每次 HTTP attempt 保留 provider usage，null 不補零。自跑工具由標準配備在 leaf 收尾前保存可信量測到 `.aos/jobs/<attempt_id>/usage.json`（cgroup 讀數；備援下只有已 wait 的子程序的粗略量測，[B-631](../settled/tick/cg.md)），agent 下格收；量不到記 null，不信工具自報。工具的 `target_node` 填 agent 自己。轉交路線也可留核對資料，但彙總只選轉交或自記一份，不重加。kernel 讀 agent 已提交的用量，以 node／request／attempt 去重、逐筆替換觀測，不把累積數每格再加一次；部署要明授用量讀權，摘要可讀不等於能讀用量。工具自用 LLM 仍走同一地址與協議，不信 stdout 自報。

驗收：schema 要求整數而模型傳字串時，不開工具程序，可查到參數路徑與格式錯誤。

## A-402 委託執行邊界

（09-29 重寫：已刪；併入[兩條通則](../README.md)與[共通身分規則](../base/identity-resources.md)，LLM key 規則見 [LLM 池](../scheduling/llm.md)。）

## A-403 結果配對與解讀

〔建議預設，未拍板〕agent 讀收件區的結果檔，以原請求、工作／嘗試 ID 配回模型呼叫 ID。工具結果是原呼叫的證據，不當成新的使用者訊息；晚到結果依 [C-03](../contracts.md)。找不到配對或結果互相矛盾時，留下證據供[處理](../scheduling/operations.md)，不任取最後一份。

〔第十八批，從 P-705 搬上〕收到結果先核對 RPC id、可信來源及原請求，再保存並套入 history 或下一步決定；同 bytes 的結果不重吃。工作結果裝在指令 stdout 裡，外層指令成功不等於工具／LLM 成功，要照結果本身判斷。套用後才記 `response_consumed`、移除待收的請求；同一批工具全部回來才一起處理。對方的 RPC 收件確認只更新發件紀錄，不觸發另一則回話；回話本身仍是普通 `agent.say`（[A-201](input.md)）。欄位與檔案落點見 [P-705](../protocol/agent-tasks.md)、[P-703](../protocol/agent-tasks.md)。

〔第十八批，P-709 從協議篇搬上〕**投件故障與恢復**：投件與清原件都由標準配備做（[B-623](../settled/deferred/mq.md)、[B-624](../settled/deferred/mq.md)）。可以補投同 ID、同 bytes 的待送訊息，這只補交付，不授權重跑工具或 LLM。已提交證據保留時，同 ID 不重消費；撞名但內容不同留事項、不覆蓋。自跑 once 的掛行程照 [B-613](../settled/deferred/daemon/channel.md)；`launch-started` marker、從未啟動證據與何時記 unknown 照 [S-401](../scheduling/operations.md)（格式見 [kernel P-807](../protocol/kernel-tasks.md)），不因登記消失、逾時或換 boot 自動另開嘗試。

結果的保存與去重沿[投件規則](../base/transport.md)，消費沿 [B-623](../settled/deferred/mq.md)（Q1）。供模型看的內容只需呼叫識別、執行結果、原始引用，以及 [A-303](memory.md) 的預覽與截斷標記，不再包另一份權威結果。

`exit 0` 只表示程序正常結束。文字模式檢查能否解讀成 UTF-8；JSON 模式只有原始 stdout 完整保存時才解析並驗 schema。格式不合就記 `tool_result_invalid`，不改寫原本的程序結果。stderr 是診斷；缺失的輸出不能當成空字串，非零退出、逾時、取消及截斷也要如實呈現。

語意格式錯誤不自動重跑工具；若 agent 決定再呼叫，就建立新工作並引用前次證據。未知結果依[共通操作](../scheduling/operations.md)。

驗收：工具 exit 0 但 JSON 不合 schema，保留原始結果與語意錯誤，不自動重跑；同一結果重送也只消費一次。

## A-404 LLM 與未知結果

（09-29 重寫：已刪；LLM 行為併入 [LLM 池](../scheduling/llm.md)，unknown 併入[共通操作](../scheduling/operations.md)，重啟處理見 [daemon](../settled/daemon/README.md)。）
