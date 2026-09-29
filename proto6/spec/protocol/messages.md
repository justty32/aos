# 檔案訊息與成員摘要

← [共用約定](README.md)｜[投件正本](../base/transport.md)｜[tick 的 Q1／Q2](../tick.md)｜[第九批裁定](../../notes/2026-09-29-verdicts.md)

本篇只定 node 之間的檔案格式；工作與 LLM 的業務參數由分工表指定篇章定義。agent 預設接件、正式回覆及人手入口見 [agent 任務](agent-tasks.md)；本篇不新增程式、argv 或環境變數；發布與接收由 node 已登記的普通任務執行，全部用該 node 的 `user`。

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

追蹤區的檔案仍放所屬訊息／工作狀態旁；只要求能以「請求或回應＋ID」找回已提交原件及原請求目標，不另建通用 outbox、確認表或永久墓碑。追蹤位置見 [node P-206](node.md)。

## P-302．完整封包〔建議預設，未拍板〕

請求、成功與錯誤的形狀直接沿 [P-002～005](README.md)，由 [msg-file-rpc.schema.json](schemas/msg-file-rpc.schema.json) 引用共用型別，不另包 envelope。請求帶 `jsonrpc`、`id`、`method`、`params`、`reply_to`；回應帶 `jsonrpc`、`id` 及二選一的 `result`／`error`。不加 `version`、sender、notification 或 batch。解析層限制依 P-002／004。

`reply_to` **是回件 node 的絕對路徑，不是 `requests/`／`responses/` 或任意檔名**。例如請求投 `/srv/aos/b/requests/m1.json`，`reply_to` 為 `/srv/aos/a`，回件便投 `/srv/aos/a/responses/m1.json`。回應的 ID 沿用原請求；不另加 reply ID 或 `reply_to`。JSON 成功只表示該 method 定義的成功，不一律表示產品工作完成。

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

重投也受 [Q2](../tick.md) 與 [C-03](../contracts.md) 約束：有可信在途／已接件證據，可等候或以原 ID 取回已保存回應；能證明從未送出才可正常送出。無法判定曾否執行時留 unknown，**不靠定時重送重做工具或 LLM**。去重只在 [B-404](../base/storage.md) 的證據保留期內承諾；證據已清不能宣稱仍可安全重投。

## P-305．送出、消費與門鈴順序〔使用者方向 2026-09-29〕

順序固定：**提交原請求 → 發布目標收件檔 → 可用的通知／叫醒**。成功發布才算收件；接收任務按 Q1 複製原件、與狀態一起 commit，成功才刪 收件區原件。收件、消費、完成各看其證據，不能把叫醒成功或刪檔當成工作完成。

投件權限不等於 daemon IPC 叫醒權限。所屬 kernel 依 [S-201／202](../scheduling/admission.md) 觀察收件及摘要、核對資源後決定叫醒；跨隊投件者無權直接 wake 對方時，已發布的檔案照樣有效，靠對方所屬 kernel 的通知或低頻補查接手。不為叫醒而轉送原請求，不讓 daemon 讀正文或替 kernel 決定排程。

## P-306．通用傳訊與成員找上層〔建議預設，未拍板〕

以下通用 method 用 [msg-methods.schema.json](schemas/msg-methods.schema.json)。`agent.send` 的 `params.text` 必填非空文字，`attachments` 可省，是普通絕對檔案路徑陣列；收件 node 須能讀，附件不因此取得執行權。大內容放附件，不加 MIME、角色或任意 metadata。`kernel.recheck` 的 `params` 固定空物件，不需要文字解讀或 LLM。

| method | 送去哪裡／成功意思 |
|---|---|
| `agent.send` | 投給提供收訊任務的 node；文字與附件引用已按 Q1 提交，回 `{"accepted":true}`，不表示 agent 已完成文字要求。後續正式 progress／final 依 [agent 任務 P-708](agent-tasks.md) 保存並以新 ID 的 agent.reply 投回，不覆寫本 RPC 回應。 |
| `agent.reply` | params 是 [agent-reply](schemas/agent-reply.schema.json) 完整物件，id 必須等於 params.id，input_id 對原 agent.send。接件者核對原請求與可信來源、提交後回 accepted；只保存回覆，不當新的使用者輸入，也不啟 LLM。 |
| `kernel.recheck` | 成員請可信登記的上層 kernel 核對自己的收件區／已提交摘要，重新判斷排程（依 S-201／202）；消費與本地排程判斷提交後回 `{"accepted":true}`。資源不足仍可等待，不保證這次一定叫醒，也不直接改額度。 |

| method | params／回應與授權 |
|---|---|
| `resources.set` | `params` 為 [res-quota](schemas/res-quota.schema.json) 整份配額；投給 quota.node_id 的可信父 kernel，只允許具有該父配置權的 owner／祖先來源。核對 seq 與父額度、提交配額後回 `{"accepted":true}`；不代表 OS 已套用。普通成員不得自行擴額。 |
| `resources.measure` | `params:{}`，投給要量測的 node，由其 owner／可信直接父要求；資源任務重測並提交後，回 `result` 為 [res-usage](schemas/res-usage.schema.json) 完整摘要（含資料版本 1）。不啟用缺席的 module。 |
| `work.submit` | 請求／結果與授權見 [work P-400～404](work.md)；只有最終結果或拒收 error，不先回 accepted。 |
| `llm.complete` | 請求／結果與授權見 [work P-405～408](work.md)，由 agent 設定 llm.target_node 選目的 node；可能轉交、也可能在當地代發，wire 格式不變，同樣只回最終結果或拒收。 |

摘要**讀取不是 method**：依 P-307 直接讀已提交摘要，不為查詢啟 tick；重測才使用 resources.measure。set／measure 沒有對應任務回 -32601；越權回 member_not_authorized，seq 衝突回 resource_conflict，量測失敗回 resource_observation_failed，均不授權自動重做。

`kernel.recheck` 的 `reply_to` 選出要核對及收回應的直接成員；按 P-303 將已核對投件 UID 對上可信登記裡該成員的 user／授權。同 UID 時這是同帳號授權，不證明是哪個 node 發件；不符就拒絕。不能把檔案系統父目錄當上層。工作／LLM 參數只在 work 篇定義；全部檔案 method 見上表。上層沒有處理本 method 的任務就回 -32601；不是直接成員或來源不足就回 `member_not_authorized`。要 helper 做固定特權步驟仍由獲授權者走 daemon IPC。

〔主編補；接 H-025／026／036〕只傳話的 kernel 也要收回件：kernel 範本的 `aos-kernel-schedule` 同時接本 node 已送出 agent.send／agent.reply 的 accepted/error，按原請求及可信來源保存到 `state/messages/responses/<id>.json`；接 agent.reply 按上列規則保存原件並備 accepted，不啟模型。新保存材料隨所在 group 提交；**只補投／清理格首已提交的回件及相符原件**，本格新備 accepted 等下一格送。agent 範本由 P-704 四階段做同樣交接。這是現有收件任務的分流，不新增 RPC 或常駐程序。

**驗收：**kernel 用 H-025 傳話後，H-026 能讀已提交 accepted，正式 reply 也得到接件確認；看回話不會開 kernel 的 LLM。

agent.send、agent.reply、kernel.recheck、resources.set 成功用 [msg-accepted](schemas/msg-accepted.schema.json)；resources.measure 用 [msg-resource-result](schemas/msg-resource-result.schema.json)。錯誤沿共用 Error：-32600 封包、-32601 method、-32602 參數；業務錯誤均 -32000，`data.code` 用 `id_conflict`、`member_not_authorized`、`reply_unavailable` 或 `attachment_unavailable`，帶 `retryable`。前兩者固定 false；後兩者只在可證明未接納時可標 true，仍不授權重做 unknown。無合法 ID／安全回件地址的壞檔只留本地診斷及事項；共用 schema 雖允許 null 解析錯誤，檔案載體仍需 ID 才能定址。

## P-307．上層直接讀成員摘要〔建議預設，未拍板〕

成員的追蹤檔 `summary.json` 用 [msg-summary](schemas/msg-summary.schema.json)：必填 version:1、node_id、observed_at_ms、ready、due_ms、status；due_ms 沒到期事件用 null，ready 可同時成立。status 為 idle、queued、waiting_resources、waiting_result、running、paused、canceling、unknown、needs_attention；reason 可省。可選 `usage` 引用 [res-usage](schemas/res-usage.schema.json)，必須與摘要在同一 commit、同一 node，缺量測不補零。不放成員清單、history 或 key。

有 repo 讀權的上層，先固定一個 commit 再讀摘要，核對 node_id 等於可信直接成員；不讀未提交工作檔。**只開摘要權限時**，成員在後組任務把已提交 summary.json 的原 bytes 發布成 ignored 的 `public/summary.json`，父目錄只授 traverse、檔案只授 read；此固定副本以暫存→fsync→原子替換→fsync 目錄更新，是 P-003 不覆蓋規則的明示例外，不是請求。讀者一次 open 取完整版本，usage 與摘要不拆檔，避免混版；副本失敗留舊值並報錯，過時／缺失不等於 idle。

摘要是觀測，不能蓋掉新的收件區 事件；上層不為查詢啟成員 tick，也不因要讀摘要就取得其 repo 或下層內容權限。

## P-308．schema 與最小範例〔建議預設，未拍板〕

[範例](examples/messages/)各一正一反：file-request 缺 reply_to、file-error 同時 result/error、agent-send 空文字、kernel-recheck 自報 sender、accepted 冒稱 completed、summary 用布林 due，均拒絕。resources-set 反例為負配額；resources-measure 反例夾帶未定參數；resources-measured 反例用負用量。[agent.reply 正例](examples/messages/agent-reply.minimal.valid.json) 可配回輸入；[反例](examples/messages/agent-reply.missing-input.invalid.json) 漏 input_id，拒絕。重送／同 ID 異 bytes 是執行語意，沿 P-304，不另複製範例。

## P-309．待決與跨篇

見 [README P-008](README.md#p-008)。
