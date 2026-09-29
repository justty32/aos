# 檔案訊息與成員摘要

← [共用約定](README.md)｜[投件正本](../base/transport.md)｜[tick 的 Q1／Q2](../tick.md)｜[第九批裁定](../../notes/2026-09-29-verdicts.md)

本篇只定 node 之間的檔案格式；工作與 LLM 的業務參數由分工表指定篇章定義。agent 預設接件、正式回覆及人手入口見 [agent 任務](agent-tasks.md)；檔案命令由收件 node 的普通任務處理，投件與收件清理由 tick 做，全部沿 node 的身分授權。

## P-300．兩條路各做什麼〔使用者方向 2026-09-29〕

兩條請求路線依 [P-001](README.md)；跨隊有投件權就直投，不經上層轉送。權限配置見 [node P-208](node.md)。

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

待送封套放追蹤的 `.aos/outbox/{requests,responses}/<id>.json`；消費原件逐 byte 複製到 `state/messages/{requests,responses}/<id>.json`。封套與 tick 交接見 [node P-206](node.md)。

## P-302．完整封包〔建議預設，未拍板〕

請求、成功與錯誤的形狀直接沿 [P-002～005](README.md)，由 [msg-file-rpc.schema.json](schemas/msg-file-rpc.schema.json) 引用共用型別，不另包 envelope。請求帶 `jsonrpc`、`id`、`method`、`params`、`reply_to`；回應帶 `jsonrpc`、`id` 及二選一的 `result`／`error`。不加 `version`、sender、notification 或 batch。解析層限制依 P-002／004。

`reply_to` **是回件 node 的絕對路徑，不是 `requests/`／`responses/` 或任意檔名**。例如請求投 `/srv/aos/b/requests/m1.json`，`reply_to` 為 `/srv/aos/a`，回件便投 `/srv/aos/a/responses/m1.json`。回應的 ID 沿用原請求；不另加 reply ID 或 `reply_to`。`result` 一律是 [work P-403](work.md) 的指令執行結果；業務 JSON 是該指令的 stdout，不另塞進 RPC result。程序成功不代表產品工作完成。

## P-303．回應路由與來源〔建議預設，未拍板〕

接件前核對 `reply_to` 是可使用的 node 回件位置，且目前執行身分能投進其 `responses/`。無法回件便不接納會產生副作用的請求，保留原件及本地錯誤供修正；不能先執行再假裝已回覆。接納後固定原請求的 `reply_to`，先將回應隨狀態 commit，再依 P-003 發布；中途失敗留已提交回應，後續只補送該回應，不重做請求。

`reply_to` 只是地址，**不是來源或授權證明**。依 [B-501](../base/transport.md) 核對 OS 權限與可信投遞資料；需要辨識成員時，將經核對的檔案擁有 UID 等來源證據對上可信登記及授權設定，不信正文自稱的 node。回件也須核對原請求目標及可信來源，不能只因 ID 相同就當作成功證據。可讀附件路徑同樣不證明來源，開檔只用收件 node 的身分。

同 UID 的多個 node 無法只靠檔案 owner 分辨；這是共用帳號的信任界線。同帳號 node 本就共用 OS 權限，可以為同帳號直接成員提出 P-306 的核對請求，但不能宣稱已認證到某個唯一發件 node。只有部署要求更細的 node 隔離時，才須另配可信證據，沒有就拒絕那種額外授權；不要求無 helper 部署一律拒收。可信來源的必要核對結果隨既有接件／工作狀態保存，不新增全域身分帳本。

## P-304．同 ID、衝突與重送〔建議預設，未拍板〕

「同內容」以已發布 JSON 的 **UTF-8 bytes 完全一致**為準，連空白與 key 順序也算；發件者重送已提交原檔，不重新序列化。同 ID 範圍由 P-301 定義；收件區 或追蹤區的已提交原件都是去重依據。

- 請求同 ID 同 bytes：不重新接納或執行。已有已提交回應就補投原回應；仍在處理就繼續等，不另送第二種「處理中」回應。commit 後遺留的收件區原件依 Q1 補清，不重吃。
- 回應同 ID 同 bytes：只消費一次，commit 後的遺留原件只補清；不再回覆這份回應，避免來回無限投件。
- 同 ID 異 bytes：不覆蓋、不執行新內容，留下 `id_conflict` 待處理事項；包括改 method、params 或 reply_to。無覆蓋發布的 EEXIST 只證明撞名；投件者有讀權並比對原件才可判同／異 bytes。只有寫入及穿越權、無法比對時，保留本地原請求並報投遞未確認，不猜已收同內容、不覆蓋；接收端再用自己可讀的原件及已提交證據判斷。只有新投件者有經核對、且不同於原請求的回件 node 時，才能向新地址送衝突錯誤；同一回件地址只留本地診斷及事項，避免錯誤搶佔原請求尚未發布的回應。任何情況都不取代原請求的成功／失敗回應。
- 同 ID 回應異內容也算衝突，不採最後寫入者；同文字但新 ID 則是新請求，不能用換 ID 繞過 unknown。

「查詢或重送沿用 ID」指**重投完全相同原請求以取得已保存回應**，不是用同 ID 改成另一個查詢 method。一般查詢直接讀有權限的已提交檔案或摘要（P-307），不叫醒 node。

重投也受 [Q2](../tick.md) 與 [C-03](../contracts.md) 約束：有可信在途／已接件證據，可等候或以原 ID 取回已保存回應；能證明從未送出才可正常送出。補投原 bytes 只交付同一請求，不是開新嘗試；收件端仍須查已提交去重證據。無法判定曾否執行且無可信去重依據時留 unknown，**不靠定時重送重做工具或 LLM**。去重只在 [B-404](../base/storage.md) 的證據保留期內承諾；證據已清不能宣稱仍可安全重投。

## P-305．送出、消費與門鈴順序〔使用者方向 2026-09-29〕

順序固定：**任務備好待送封套／消費副本 → tick 提交該組 → tick 投件及刪相符收件原件 → 可用的通知／叫醒**。成功發布才算收件；未提交的待送檔不投，未提交的消費紀錄不刪。收件、消費、完成各看其證據，不能把叫醒成功或刪檔當成工作完成。

投件權限不等於 daemon IPC 叫醒權限。所屬 kernel 依 [S-201／202](../scheduling/admission.md) 觀察收件及摘要、核對資源後決定叫醒；跨隊投件者無權直接 wake 對方時，已發布的檔案照樣有效，靠對方所屬 kernel 的通知或低頻補查接手。不為叫醒而轉送原請求，不讓 daemon 讀正文或替 kernel 決定排程。

## P-306．method 就是指令〔使用者方向 2026-09-29〕

檔案 method 是指令去掉 `aos`、以 `.` 連接；`params` 是完整 [inst](../base/inst.md)，表示「在你那裡跑這條指令」。指示詞及身分授權沿 inst，base 為收件 node。展開後 argv 必須保留 `aos`、命令段必須和 method 一致，而且是收件 node 開放的命令；否則 -32601。envs、指示詞與 stdin 路徑照 inst，借權讀檔或換程式的風險由使用者承擔。接件執行該命令的本地動作，不再投同一份 RPC。

有業務資料的命令從 stdin 讀一份 JSON；inst.stdin 是收件者可讀的絕對檔案路徑，不是 JSON 內容。發件者將資料隨請求固定並保留至消費完成；收件者用自己的權限開檔。無資料的命令省略 stdin。需要結果的串流用 `{"$opt":"inherit"}`，由接件執行器捕獲；其餘串流規則沿 inst。輸入形狀與 argv 的一致性須在展開及讀檔後另驗，schema 不代替開放命令檢查。

| method／完整命令 | stdin JSON／本地動作與 stdout |
|---|---|
| `agent.say`／`aos agent say` | `{text,attachments?,in_reply_to?}`；text 非空、attachments 為絕對檔案路徑陣列。一律收進 history，stdout `{"accepted":true}`；回話也是新 ID 的 agent.say，以 in_reply_to 指原句 id。 |
| `kernel.schedule.recheck`／`aos kernel schedule recheck` | 無；核對 reply_to 指向的可信直接成員收件與摘要，重新判斷排程，stdout `{"accepted":true}`。不保證叫醒，也不改額度。 |
| `kernel.quota.set`／`aos kernel quota set` | [res-quota](schemas/res-quota.schema.json)；投 quota.node_id 的可信父 kernel，只准父配置權 owner／祖先，核對 seq 與父額度、提交後 stdout `{"accepted":true}`。不代表 OS 已套用。 |
| `kernel.usage.measure`／`aos kernel usage measure` | 無；由 owner／可信直接父要求重測，stdout 為 [res-usage](schemas/res-usage.schema.json)，不啟用缺席 module。 |
| `kernel.work.submit`／`aos kernel work submit` | [work P-401](work.md) 工作材料；完成後 stdout 為內層工作的本地 work-result。 |
| `llm.chat`／`aos llm chat` | [llm-work P-406](llm-work.md) LLM 材料；完成後 stdout 為本地 llm-result。 |

全部回應用 [work-result](schemas/work-result.schema.json)；最後兩條由 module 跨格接續，業務結果回來才完成命令；tick 不等待工具或 HTTP，也不先用 ACK 占住 RPC id。摘要查詢直接讀 P-307，不開 tick。kernel 範本也保存自己送出命令的回應及收到的正式回覆，由 tick 投確認、清原件，不必裝 LLM。

授權核對沿 P-303；同 UID 是同帳號授權，不證明是哪個唯一 node 發件。錯誤沿 P-005：不開放／命令不符 -32601，輸入不合 -32602；業務拒收 -32000，`data.code` 用 `id_conflict`、`member_not_authorized`、`reply_unavailable`、`attachment_unavailable`、`resource_conflict` 或 `resource_observation_failed`。只有能證明未接納的暫時讀取／回件問題可 retryable:true；不能重做 unknown。無合法 ID／安全回件地址只留本地診斷。

**驗收：**argv 少了 aos、和 method 不符或未開放都回 -32601；listen 只讀 history，不開模型；RPC 收件確認不再引發回話。

## P-307．上層直接讀成員摘要〔建議預設，未拍板〕

成員的追蹤檔 `.aos/summary/summary.json` 用 [msg-summary](schemas/msg-summary.schema.json)：必填 version:1、node_id、observed_at_ms、ready、due_ms、status；due_ms 沒到期事件用 null，ready 可同時成立。status 為 idle、queued、waiting_resources、waiting_result、running、paused、canceling、unknown、needs_attention；reason 可省。可選 `usage` 引用 [res-usage](schemas/res-usage.schema.json)，必須與摘要在同一 commit、同一 node，缺量測不補零。不放成員清單、history 或 key。

有 repo 讀權的上層固定一個 commit 讀摘要，核對 node_id 等於可信直接成員。只開摘要讀權時，tick 在提交後把同一版原 bytes 原子發布到 ignored 的 `.aos/summary/published.json`；父目錄只授 traverse、檔案只授 read。這是 P-003 不覆蓋規則的明示例外。讀者一次 open 取完整版本，usage 不拆檔；發布失敗留舊值並報錯，過時／缺失不等於 idle。

摘要是觀測，不能蓋掉新的收件區 事件；上層不為查詢啟成員 tick，也不因要讀摘要就取得其 repo 或下層內容權限。

## P-308．schema 與最小範例〔建議預設，未拍板〕

[範例](examples/messages/)涵蓋完整 inst、命令結果、各命令的輸入與摘要。缺回址、雙 result/error、命令不符、空文字、無效 in_reply_to、負配額／用量及布林 due 都拒絕；重送與同 ID 異 bytes 另依 P-304 驗行為。

## P-309．待決與跨篇

見 [README P-008](README.md#p-008)。
