# 檔案訊息與成員摘要

← [共用約定](README.md)｜[投件正本](../base/transport.md)｜[Q1／Q2](../settled/tick.md)｜[第九批裁定](../../notes/2026-09-29-verdicts.md)

> **〔2026-10-01 殘留註記〕本篇是 2026-10-01 之前的設計，下列內容現在不是現行的**；原文照留，以這裡指的正本為準（各批裁定見 [verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md)）：
> - `aos-git`（開格、存檔點、收尾）與有 git 版範本：第十七批暫緩（[B-630](../settled/deferred/git.md)）；要提交、還原改用 hook 加普通 git 指令（範例在 [B-635](../settled/tick/hooks.md)）。
> - 標準任務表範本（[B-629](../settled/deferred/template.md)）、`aos-mq get`／`post`（[B-623、B-624](../settled/deferred/mq.md)）、`aos-clean`（[B-404](../base/storage.md) 的系統級任務部分、P-605）：第十八批暫緩，現行沒有系統級任務；kernel／agent 範本裡掛的這些項也跟著不成立。現行收發信是 daemon 訊息模組 `aos-mq send`／`take`／`peek`（[B-645](../settled/daemon/mq.md)）。
> - `aos-tick-check-task`（原 `aos-needs`）：第十六批暫緩（[暫緩區 B-621](../settled/deferred/tick.md#暫緩b-621-前面的項沒跑好就停格aos-tick-check-task)）。
> - node：tick 層改稱「工作資料夾」，daemon 只認設定檔 `insts` 的一項；node 模組不做（[名詞](../settled/terms.md)、[node 模組方向](../../notes/verdicts/11-tick-as-unit.md#node-模組方向2026-10-01記錄用未排程)）。本篇講的 node、上下層、kernel／agent 角色都是舊設計。
> - 舊 daemon 的通道與憑證（`AOS_TICK_TOKEN`）、登記、runner、`state.json`：整套在暫緩區（[舊 daemon](../settled/deferred/daemon/README.md)）；現行 daemon 只定期叫 `aos-exec` 加各模組（[B-640](../settled/daemon/core.md)）。

本篇只定 node 之間的檔案格式，行為以主規格為正本（[P-009](README.md)）；工作與 LLM 的業務參數由分工表指定篇章定義。agent 預設接件、正式回覆及人手入口見 [agent 任務](agent-tasks.md)；檔案命令由收件 node 的普通任務處理，〔第二十批，astra 審整理區定案〕系統級任務只剩系統訊息佇列 `aos-mq`（[B-629](../settled/deferred/template.md)）；檔案投件與收件清理改由普通程式做、aos 不管，本篇下一輪跟上。

## P-300．兩條路各做什麼〔使用者方向 2026-09-29〕

兩條請求路線依 [P-001](README.md)；跨隊有投件權就直投，不經上層轉送。〔第十九批〕同一 daemon 底下的 tick 之間，待送封套也可以標 `channel` 改經通道送，訊息格式不變（[B-624](../settled/deferred/mq.md)、[node P-206](../settled/protocol/tick.md)）。權限配置見 [node P-208](../settled/protocol/tick.md)。

## P-301．收件區分請求與回應〔使用者方向 2026-09-29，收件分兩格〕

每個 node 根目錄建兩格，`requests/`、`responses/` 都 ignored；回應投回發問者家，不留在回答者家等人來拿：

```text
requests/.tmp/       # 請求暫存
requests/<id>.json   # FileRpcRequest
responses/.tmp/      # 回應暫存
responses/<id>.json  # RpcResponse
```

**不依來源再分資料夾**：node 路徑不能直接當檔名，來源目錄也不證明身分；分請求／回應已能避免雙向同 ID 互撞。同一收件 node 的請求 ID 共用一個命名空間；發件 node 也須讓自己發出的 ID 在所有目標間唯一，才能把回件對回唯一原請求。建議產生隨機 ID，不拿 mtime 或檔名排序。

只讀兩個目錄的直接普通檔案，不跟隨 symlink、不遞迴，不處理點開頭名稱。檔名去掉 `.json` 必須等於正文 `id`。發布依 P-003，在正式目錄下依共用流程操作；發布後不再修改正式檔。收件端只處理發布完成的檔案。

待送封套放追蹤的 `.aos/outbox/{requests,responses}/<id>.json`；消費原件逐 byte 複製到 `state/messages/{requests,responses}/<id>.json`。封套格式見 [node P-206](../settled/protocol/tick.md)。

## P-302．完整封包〔建議預設，未拍板〕

請求、成功與錯誤的形狀直接沿 [P-002～005](README.md)，由 [msg-file-rpc.schema.json](schemas/msg-file-rpc.schema.json) 引用共用型別，不另包 envelope。請求帶 `jsonrpc`、`id`、`method`、`params`、`reply_to`；回應帶 `jsonrpc`、`id` 及二選一的 `result`／`error`。不加 `version`、sender、notification 或 batch。解析層限制依 P-002／004。

`reply_to` **是回件 node 的絕對路徑，不是 `requests/`／`responses/` 或任意檔名**。例如請求投 `/srv/aos/b/requests/m1.json`，`reply_to` 為 `/srv/aos/a`，回件便投 `/srv/aos/a/responses/m1.json`。回應的 ID 沿用原請求；不另加 reply ID 或 `reply_to`。`result` 一律是 [work P-403](work.md) 的指令執行結果；業務 JSON 是該指令的 stdout，不另塞進 RPC result。程序成功不代表產品工作完成。

## P-303．回應路由與來源〔建議預設，未拍板〕

〔第十九批依方案 A 搬上〕本條不另定格式（`reply_to` 的格式見 P-302），行為都在主規格：接件前核對回址、固定回址與回應投遞見 [B-623](../settled/deferred/mq.md)；`reply_to` 不是來源或授權證明、可信來源與同 UID 的信任界線見 [B-501](../base/transport.md)；投回應時回址不是 node 或沒有寫入權限照 [B-624](../settled/deferred/mq.md)；回不了錯誤回應的壞件只報一次照 B-623。

## P-304．同 ID、衝突與重送〔建議預設，未拍板〕

行為正本是 [B-503](../base/transport.md)（重送、補投原回應、衝突處理）；本條只定比對格式。

- 「同內容」以已發布 JSON 的 **UTF-8 bytes 完全一致**為準，連空白與 key 順序也算；發件者重送已提交原檔，不重新序列化。
- 同 ID 範圍由 P-301 定義：同一收件 node 的 `requests/` 一個命名空間，`responses/` 另一個。
- 衝突用 -32000 加 `data.code:"id_conflict"`；事項 `reason` 也用 `id_conflict`（[ops P-601](ops.md)）。

## P-305．送出、消費與門鈴順序〔使用者方向 2026-09-29〕

〔第十九批依方案 A 縮短；第二十批改順序〕順序（備好待送封套與消費副本 → 本格使用者任務跑完後投件 → 下一格收件任務在上一格正常收尾時刪相符原件；叫醒另計；有 git 時 `aos-git close` 排在送出之前）以 [B-623／B-624](../settled/deferred/mq.md) 為正本；誰來叫醒見 [S-201／202](../scheduling/admission.md)。

## P-306．method 就是指令〔使用者方向 2026-09-29〕

檔案 method 是指令去掉 `aos`、以 `.` 連接；`params` 是完整 [inst](../base/inst.md)，指示詞及身分授權沿 inst，base 為收件 node。展開後 argv 必須保留 `aos`、命令段必須和 method 一致。收件 node 接哪些 method、什麼時候回 -32601、什麼時候回 -32000 業務碼，以 [B-501](../base/transport.md) 與 [B-623](../settled/deferred/mq.md) 為正本；宣告格式是任務表的 `methods`（[node P-202](../settled/protocol/tick.md)）。〔使用者方向 2026-09-30，第十八批〕投件權就是執行權，而且會傳遞（[B-501](../base/transport.md)）。

有業務資料的命令從 stdin 讀一份 JSON；inst.stdin 是收件者可讀的絕對檔案路徑，不是 JSON 內容。發件者將資料隨請求固定並保留至消費完成；收件者用自己的權限開檔。無資料的命令省略 stdin。需要結果的串流用 `{"$opt":"inherit"}`，由接件執行器捕獲；其餘串流規則沿 inst。輸入形狀與 argv 的一致性須在展開及讀檔後另驗，schema 不代替開放命令檢查。

〔使用者方向 2026-09-30，第十八批〕**本地動作的 stdout 落點**：當格就做完的命令（下表除 `kernel.work.submit`、`llm.chat` 以外的各列），執行的任務把 stdout 存成追蹤的 `state/messages/requests/<id>.stdout`，跟消費副本放一起、同一組提交（組見 [B-621](../settled/deferred/tick.md#暫緩b-621-前面的項沒跑好就停格aos-tick-check-task)）；回應 result 的 `stdout.path` 指這個檔的絕對路徑，不填 null，這樣結果可以被引用（[B-103](../base/work.md)）。清理跟那份請求副本一起（[B-404](../base/storage.md)）。

| method／完整命令 | stdin JSON／本地動作與 stdout |
|---|---|
| `agent.say`／`aos agent say` | `{text,attachments?,in_reply_to?}`；text 非空、attachments 為絕對檔案路徑陣列。一律收進 history，stdout `{"accepted":true}`；回話也是新 ID 的 agent.say，以 in_reply_to 指原句 id。〔使用者方向 2026-09-29，第十六批〕帶 in_reply_to 的只記錄，不觸發 LLM、不再回話（[P-705](agent-tasks.md)）。〔第十七批〕投給 kernel 的 agent.say 由 kernel 範本現有的 schedule 任務處理：寫 kernel 的 history、回確認，不裝 LLM（[kernel P-803](kernel-tasks.md)）。 |
| `kernel.schedule.recheck`／`aos kernel schedule recheck` | 無；核對 reply_to 指向的可信直接成員收件與摘要，重新判斷排程，stdout `{"accepted":true}`。不保證叫醒，也不改額度。 |
| `kernel.quota.set`／`aos kernel quota set` | [res-quota](schemas/res-quota.schema.json)；投 quota.node_id 的可信父 kernel，只准父配置權 owner／祖先，核對 seq 與父額度、提交後 stdout `{"accepted":true}`。不代表 OS 已套用。 |
| `kernel.usage.measure`／`aos kernel usage measure` | 無；由 owner／可信直接父要求重測，stdout 為 [res-usage](schemas/res-usage.schema.json)，不啟用缺席 module。 |
| `kernel.work.submit`／`aos kernel work submit` | [work P-401](work.md) 工作材料；完成後 stdout 為內層工作的本地 work-result。 |
| `llm.chat`／`aos llm chat` | [llm-work P-406](llm-work.md) LLM 材料；完成後 stdout 為本地 llm-result。 |
| `work.cancel`／`aos work cancel` | [msg-cancel-payload](schemas/msg-cancel-payload.schema.json) `{request_id}`，指要取消的原請求 RPC id；投給持有那件工作的 node。〔第十七批〕stdout `{"accepted":true}`；核權、排隊中與在跑的怎麼處理見 [B-203](../base/execution.md)，原工作的結果照舊由原請求的回應帶回（[work P-411](work.md)）。 |

全部回應用 [work-result](schemas/work-result.schema.json)。`kernel.work.submit`、`llm.chat` 跨格接續、業務結果回來才完成命令，不先用 ACK 占住 RPC id（[work P-401](work.md)、[llm-work P-406](llm-work.md)）；kernel 收一般回話見 [S-406](../scheduling/operations.md)；agent 之間的問答機制延後（[P-008](README.md#p-008)）。

授權核對沿 P-303；同 UID 是同帳號授權，不證明是哪個唯一 node 發件。錯誤沿 P-005：-32601 與 -32000 怎麼分依 [B-501](../base/transport.md)，輸入不合 -32602；業務拒收 -32000，`data.code` 用 `id_conflict`、`member_not_authorized`、`reply_unavailable`、`attachment_unavailable`、`resource_conflict`、`resource_observation_failed`，或 work.cancel 的 `cancel_not_authorized`、`work_not_found`（[work P-411](work.md)）。只有能證明未接納的暫時讀取／回件問題可 retryable:true；不能重做 unknown。無合法 ID／安全回件地址的回不了錯誤回應，照 [B-623](../settled/deferred/mq.md) 只報一次事項。

**驗收：**-32601 的驗收見 [B-501](../base/transport.md)、[B-623](../settled/deferred/mq.md)。本條另驗：本地動作的回應 `stdout.path` 指到存在的 `.stdout` 檔；listen 只讀 history，不開模型；RPC 收件確認不再引發回話。

## P-307．上層直接讀成員摘要〔建議預設，未拍板〕

成員的追蹤檔 `.aos/summary/summary.json` 用 [msg-summary](schemas/msg-summary.schema.json)：必填 version:1、node_id、observed_seq、ready、due_after_ticks、status。〔使用者方向 2026-09-30，第二十批疑點裁定 7〕`observed_seq` 取代 `observed_at_ms`：寫這份摘要時是成員自己的第幾格（[B-633](../settled/tick.md)），上層只比有沒有前進，不跟自己的格數相減。〔暫定，第二十批疑-10 照 a〕`due_after_ticks` 取代 `due_ms`：希望上層從讀到這一版摘要起再過幾格叫醒我，算上層的格；上層讀到新一版時換成自己的到期格。沒到期事件用 null，ready 可同時成立。status 為 idle、queued、waiting_resources、waiting_result、running、paused、canceling、unknown、needs_attention；reason 可省。可選 `usage` 引用 [res-usage](schemas/res-usage.schema.json)，必須與摘要是同一版（有 git 時同一 commit；沒有 git 時同一次寫出，[B-632](../settled/deferred/git.md)）、同一 node，缺量測不補零。不放成員清單、history 或 key。

**發布檔**（〔暫緩（2026-10-01）〕發布它的 `aos-publish` 隨 B-624 發摘要搬到[暫緩區](../settled/deferred/tick.md#暫緩b-624-發布摘要aos-publish)，現在沒有人寫這個檔；下面照留）：ignored 的 `.aos/summary/published.json`，內容是已提交 `summary.json` 的同一版原 bytes，usage 不拆檔；父目錄只授 traverse、檔案只授 read。它會被整份替換，是 P-003 不覆蓋規則的明示例外。

〔第十九批依方案 A 縮短〕誰何時發布、發布失敗怎麼辦、上層怎麼讀與核對、摘要跟收件事件誰優先，以 B-624 的發布摘要一節為正本（〔暫緩（2026-10-01）〕那節已搬到[暫緩區](../settled/deferred/tick.md#暫緩b-624-發布摘要aos-publish)）；〔使用者方向 2026-09-30，第十八批〕多久沒更新算失聯、失聯時做什麼由父 kernel 自己定，見 [S-202](../scheduling/admission.md)。aos 提供的訊號是 `observed_seq` 有沒有前進，與 daemon `node.show` 的 `last_tick`。

## P-308．schema 與最小範例〔建議預設，未拍板〕

[範例](examples/messages/)涵蓋完整 inst、命令結果、各命令的輸入與摘要。缺回址、雙 result/error、命令不符、空文字、無效 in_reply_to、負配額／用量及布林 due 都拒絕；〔第十七批〕work.cancel 有[正例](examples/messages/work-cancel.minimal.valid.json)、[命令不符反例](examples/messages/work-cancel.mismatch.invalid.json)、[材料正例](examples/messages/work-cancel-payload.minimal.valid.json)／[空材料反例](examples/messages/work-cancel-payload.empty.invalid.json)與[沒權限的錯誤回應](examples/messages/work-cancel-error.denied.valid.json)；重送與同 ID 異 bytes 另依 P-304 驗行為。

## P-309．待決與跨篇

見 [README P-008](README.md#p-008)。
