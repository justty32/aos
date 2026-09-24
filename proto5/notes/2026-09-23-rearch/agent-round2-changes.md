# agent 線規範第 2 輪：改了什麼

← [README](README.md)｜審查：[review-agent1-report.md](review-agent1-report.md)｜改後：[agent.md](../../spec/agent.md)（A）、[aos-agent.md](../../spec/aos-agent.md)（G）、[aos-llm-call.md](../../spec/aos-llm-call.md)（L）

2026-09-24。依「定稿前必改」12 條，以及使用者當天拍板的三件事修改。三份仍是草稿，程式還沒跟上。

## 12 條逐條

1. **C-1／C-4／K-4**：新增 `state.batch`，在途工作的身分只記在這裡。`waits` 只留給外人的門。本地就結束的 call 直接寫進 `done`。A §4.3；G §5.1、§5.2。
2. **C-2／K-5／K-6**：先讀驗、寫 `done`，再 ack，再寫 `acked`，最後把記憶重寫成「前 base_len 則＋這批」，一次寫 state 結清。對不上＝`HistoryChanged`。刪掉「看尾巴自癒」。G §6、§7。
3. **C-3／X-5**：先記一批、標 `sent:false`，再送件。崩掉後用四步查「放過沒」：K/requests → 帳本的 procs／replies → K/responses。刪掉「boot 會清孤兒」這句。G §5.2。
4. **X-2／C-5**：分清 Stopping、Removed、Interrupted、`stopped:true` 四種情況，think／act 各自怎麼處理都列成表。工作檔要等帳本 procs 裡沒有這個名字才刪。G §6.1、§6.2、§10。
5. **C-6／C-8**：consume 時，劃掉門和記進 `consuming` 在同一次寫完成，之後才 rename。idle 先記 `intake`（連訊息內容），再寫記憶。A §4.4；G §3、§8。
6. **C-7**：`done` 帶 `count`。連敗次數在結清那一次寫裡加一。壞輸出記為 MessageInvalid，算一次連敗。G §6.1、§7、§9。
7. **X-1／X-7**：三種名字寫死。工作名用 `aw-` 前綴。request 和 ack 用 tmp＋link，自家檔用 tmp＋rename。不用 `call()`。A §1；G §0、§5.2、§6。
8. **X-3／X-4**：`_meta` 重新編成字面 inst，附選項對照表。路徑照 inst-posix §3.1 解。A §3.3；G §5.3。
9. **X-4／K-9**：分內外兩圈逾時。外圈是 `info.llm.timeout_ms`（預設 125000），內圈是 llm.json 的 HTTP 逾時，兩者分工列成表。改成執行時才讀 agent 家；兩邊都讀的欄位不要用 `$env`。A §2；L §3、§6。
10. **X-6／K-8／R-3／R-4**：kind=aos 回固定文字。輸出一律用 UTF-8 讀，壞位元組換掉。waits 可以寫單條或陣列，寫回一律用陣列，`$opt` 必寫。llm.json 各欄位的型別寫死。驗 message 規則：role 必須是 assistant、tool_calls 逐項驗、id 不能重複。A §3.2、§4.2；G §6.2；L §2、§5。
11. **C-9／X-8**：等回音沒有上限，timeout 只限執行時間。補上 stopping 期間各種情況的處理。補 start 的正確範例和 llm 池的前置條件。G §11、§13。
12. **K-2／R-1／R-6**：每份開頭加「調度者裁決」，結尾加「已拍板的前提」，寫明同步工具的取捨。重寫一句話摘要。人格和記憶拆成兩小節。刪掉所有「跟第 1 版一樣」這類句子。

## 調度者裁決彙整

- A（7 條）：身分只記在 batch；拿掉 info.kernel 和 llm.config；新增 info.tick；工作區併成 work/；waits 只剩 consume 一個選項；程式寫的格必須是字面值；message 驗證共用同一套。
- G（8 條）：先記批再送，用四步對帳；先 done 再 ack，記憶用前綴重寫；清檔看帳本 procs；子命令分成 tick／start／stop，tick.json 帶 AOS_K；工作名加 `aw-` 前綴；定清楚哪些算連敗；暫停沿用 continue.json，加門前先清掉舊訊號；kind=aos 回固定文字。
- L（6 條）：`_metainfo` 必填；新代號 ConfigInvalid；執行時讀；印出前先驗 message；做兩件正規化；api_key 為空字串時不帶。

## 要使用者拍的

1. **明確的 `fail` 狀態**（backlog agent-fail-state）：這輪沿用 continue.json，只補了 bad_after 的關係。
2. **將來 pause 的語意**：現在門關著時連回音都不收；你構想的 pause 是照收不反應，到時要定門擋不擋收回。
3. **agent 屬於哪個 kernel 記在哪**：這輪只記在 tick.json 的 AOS_K 和 `batch.kernel`，info 不記。

## 這輪解掉的 backlog（檔沒刪）

- request-identity：**解掉**。身分用 `calls[].name`，恢復靠 G §5.2 的四步，消費紀錄用 `consuming`／`intake`。
- agent-fail-state：**沒解**（見上面第 1 條）。

## C-1～C-10 時序自走

我自己走一次，另派 subagent 獨立走一次，當時結論是 10 條都通；第 2 輪審查推翻了 C-6／C-8（下表已改）。

| 窗口 | 下次怎麼認 | 結果 |
|---|---|---|
| C-1 開門丟身分 | 身分在 batch，跟門無關 | 通 |
| C-2 記憶／ack／state 之間崩 | 補 ack；記憶長度只可能是「還沒接」或「接過且尾巴相同」 | 通 |
| C-3 放單後崩 | sent:false，重做時四步查，K 固定用 batch.kernel | 通 |
| C-4 本地失敗沒紀錄 | 寫在 done；全部都是本地失敗就直接結清 | 通 |
| C-5 Removed 就清檔 | 看帳本 procs，還在跑就留著 | 通 |
| C-6 consume 半途崩 | 下次靠 `consuming` 補 rename | **沒通**（同名訊號再投會被吞，第 2 輪審查 B-2；第 3 輪改成唯一封存名，見 [round3](agent-round3-changes.md)） |
| C-7 連敗計數 | 跟 batch:null 在同一次寫 | 通 |
| C-8 idle 收輸入 | 靠 intake 重做 | **沒通**（同名輸入再投會被吞，B-2；第 3 輪修，見 [round3](agent-round3-changes.md)） |
| C-9 stop／boot | 回 Stopping 就重問；boot 保留帳本；等回音不設上限 | 通 |
| C-10 同一個家兩個驅動者 | 列為保證外；stop 後等 ls 看不到才改 | 通（只是約定） |

走的過程抓到 7 處，已改回：重送時固定用 batch.kernel；記憶長度檢查改嚴；stop 後要等 ls 看不到才改；tick.json 改用 tmp＋rename；ack 名稱加序號；節號 §4.4 改成 §4.3；補上被標 bad 之後怎麼救。還沒改：K/requests/ 裡殘留的 `.tmp` 沒人清。
