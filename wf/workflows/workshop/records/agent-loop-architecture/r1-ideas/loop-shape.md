# agent loop 的形狀

> 〈成形的方向〉底下的三節：agent loop 在磁碟上長什麼樣、一個完整循環怎麼走，
> 以及它為什麼不需要前一場四題先拍板。

## agent loop 是磁碟上的耐久狀態機，不是新的 `exec` 模式

**四位獨立地都把 agent 定義成「world＋driver／adapter＋已提交歷史」**。`aos exec` 仍只執行
普通 instruction，不知道眼前這個世界是不是 agent；driver 看目前狀態，決定要不要投遞下一批。
有投遞就還有下一回合，**沒有投遞就是停止**，不需要常駐 loop process。

四份版面名稱不同，但職責可以對齊：

| 區域 | 放什麼 | 讀寫規則 |
|---|---|---|
| `.aos/` | 既有 kernel、`inst.json`、交接暫存與 `.runi` | 照既有回合協定走；agent 不另造一套 executor |
| `agent/` | `system.md`、config、driver cursor | cursor **只指向已提交紀錄**，不能先指到尚未發布的 response |
| `events/`／`history/`／`turns/` | prompt、模型 response、plan、commit 等回合紀錄 | 已提交後不可變；driver 下一次從 commits fold 出狀態，不讀半成品 |
| `effects/`／`calls/` | request、key、status、stdout／response、exit | 至少能表示 pending／done／unknown；done 可回放，unknown 不可無聲重跑 |
| `tools/` | tool request 與 result | tool 結果提交後，再投遞模型／driver 的下一回合 |

資深工程師用 `turns/N/{request,attempt,response,commit}.json`；資深架構師用不可變
`events/N.d` 與 `calls/N.d`；研究人員分成 history、turns、tools、effects；要接工具的開發者則把
events、effects、tools 都放在 `agent/` 下。**已成形的是提交邊界，不是資料夾名稱**：下一回合只
相信 commit／done，看不到 commit 就不把前一步當完成。

## 一個完整循環怎麼走

四位的步驟可以疊成同一條回合鏈：

1. driver 從已提交的 events／turns 與 cursor 組出 prompt。
2. 以 effect 原語先發布 call request／key，再呼叫 LLM CLI。
3. 成功時原子發布 response／event 與 done；中斷時留下 unknown。
4. adapter 解析 response，透過 `deliver` 投遞工具 instructions。
5. 工具執行並提交 results，再由 driver 投遞下一次模型回合。
6. response 是 final、或 driver 沒有投遞任何 next instruction 時，loop 自然停止。

這條鏈不要求模型、工具與 driver 同一回合跑完，也不要求 core 理解 prompt、tool call 或 final。
core 只保證「已發布的是完整資料」「同一 key 不會悄悄變成另一份內容」「外呼結果不明時有狀態
可診斷」。

## 前一場四個選擇可以繼續懸著

四位沒有把[前一場](../../four-open-choices-tradeoffs.md)的傾向偷寫成前提。共同的 agent 契約只要求
「有一個可推一步的 world」：

- World 尚未決定是否成為同 OS 行程 multiplex 的 handle；driver 可先呼叫普通 `aos exec <folder>`。
- kernel 可先視為該 world 執行時可取得；完整本地或分層來源不影響 events／effects 的提交語意。
- A 可把 queue／effects 放子世界，B 可放 root lane；工程師、架構師、研究人員明列兩種，開發者
  採子世界版本，但都沒有把其中一種寫成使用者已拍板。
- agent 的外部 handle 可用路徑、父域名稱＋generation 或日後其他身分；effect key／turn key 只需在
  當前契約下穩定，不必先假定 UUID。

所以「agent 是誰」也沒有被寫成一種新核心行程：工程師說它是 folder＋cursor＋turn log＋driver；
架構師說 world＋events＋queue；研究人員說 world＋kernel＋adapter；開發者說 world＋driver 狀態機。
**四位獨立地都把決定續跑／停止的權力放在 driver，不放在 `exec`。**

