← [agent](README.md)｜[spec 總導航](../README.md)

# 記憶壓縮（機械版）

（09-24 工具大開發時代第一波第 4 隊，T-compact）[info.md §3.2](info.md) 原本寫「記憶太長怎麼辦之後再說」——這份就是那個「之後」。
**不叫模型**：舊的輪只留使用者原話與那輪最後的回話，中間的工具呼叫與結果換成一行說明；原文整份存進 archive，要看再翻。
實作 [`lib/aos_agent_compact.py`](../../lib/aos_agent_compact.py)；命令列在 [cli-memory.md](../aos-agent/cli-memory.md)。

## 1. 什麼時候可以縮

**持 `.tick.lock`、`state` 是 `idle`、`batch` 與 `intake` 都是 `null`** 才縮。三個入口：

| 入口 | 鎖 | 條件不合 |
|---|---|---|
| 人 `aos-agent compact` | 自己拿（非阻塞） | 被佔＝退 101、不動檔；不是 idle／有 batch／intake 做到一半＝`NotIdle` 退 1、不動檔（拿鎖會把 pid 寫進 `.tick.lock`，跟 tick 一樣） |
| tick 自動（§4） | tick 本來就持著，**不再拿第二次**（同一行程對同一檔再開一個 fd 拿 flock 會被自己擋住） | 只在 idle 那一步、`intake` 是 `null`、而且沒有輸入等著收時才看 |
| 模型的申請（§5） | 郵差不拿成員的鎖，只投一個申請檔；真的縮是成員下一次 idle 時 tick 做 | — |

`--dry-run` 不建鎖檔：鎖檔在就試一下（被佔一樣退 101），不在就不拿；其他照算、印結果、**什麼都不寫**。

## 2. 輪與怎麼縮

- **輪**：一段連續的 `user` 開一輪，到下一段 `user` 之前（第一則 `user` 之前的算第 0 輪）。
- 最後 `keep_rounds` 輪（預設 3）**原樣**。
- **沒做完的任務不縮**：agent 家在 `<團隊>/members/<名>/`、團隊資料夾有 `team.json` 時，一輪裡 `user` 訊息（信頭）提到的單號 `t-0001`、`t-0001.r1`，只要 `team/tasks/<單號>.json` 的 `status` 不是 `done`／`cancelled`（包括讀不到），那一輪原樣留、也不封存。不在團隊裡就沒有這條。
- 其他較早的輪：留開頭那段 `user` 原話、那輪最後一則回話（沒有 `tool_calls` 的 `assistant`；沒有就不留），中間全部換成一則 `user`：
  `[aos 已壓縮 4 則：read×2、bash×1；原文 prompts/archive/<sha>.json 第 2～5 則]`（則數從 1 數，指 archive 裡的位置）。
  說明行用 `user` 不用 `assistant`：放在回話裡模型會學著自己寫這種行。
  **換掉的比說明行還短就不換**（只叫一次 `date` 的輪縮了反而變長，09-24 真跑看到的）。
- `tool_calls` 與它的 `tool` 結果**永遠一起留或一起換掉**（整輪處理，拆開模型端會退 400）。縮完再驗一次：每則有 `tool_calls` 的 assistant 後面緊接著每個 id 的結果、沒有落單的結果，不過＝`HistoryInvalid`、不寫。
- **還有上限**（`max_tokens`，token 照 [cli-memory.md](../aos-agent/cli-memory.md) 的粗估，只算記憶）：縮完還超過，就從最舊的一輪起整輪換成 `[aos 已封存較早的 3 輪（18 則）；原文 … 第 1～18 則]`（相連的併成一行），每封一輪就重算一次，直到不超過。
  **封存也不能讓記憶變長**：要開一行新封存行時，那輪本身比封存行（照最長位數估）還小就不封；接在上一段封存後面的併進同一行。「值不值得換」一律照最長位數估說明行，跟位置數字無關，所以重跑判斷一樣（astra M2、M3）。
  最近 `keep_rounds` 輪、沒做完的任務、已經是封存行的不封；都封完還超過就停，印一行「還超過」，**不算失敗**（退 0）。
- 同樣的記憶、同樣的選項、同樣的任務狀態，算出來一定一樣；縮過的再縮一次是空轉（「nothing to compact」）。

## 3. 怎麼寫（每步可重跑）

1. 讀記憶檔的原始 bytes，`sha`＝sha256 的前 16 個十六進位字。算新記憶（§2）。沒變＝結束。
2. 寫 `<記憶檔所在資料夾>/archive/<sha>.json`＝**舊記憶原樣的 bytes**（暫存檔＋fsync＋rename；已在而且內容對得上就略過）。
3. 記一行事件 `compact`（[events.md](events.md)，`id` 是 `sha`）。
4. 用暫存檔＋rename **換掉**記憶檔。

永遠不是「先搬走舊的」：崩在 2 之前、2 與 4 之間，記憶檔都是完整的舊版，重跑算出同一份新版、archive 已在就略過；崩在 4 之後記憶檔是完整的新版，重跑是空轉。
所以 `history.json` 從來不缺、不會是半截。archive 預設全留；`compact --prune-archive 天數` 刪超過天數、而且現在的記憶沒提到檔名的（**也持 tick 鎖**，不會刪到「archive 寫了、記憶還沒換」那一份）。任務狀態在算之前一次讀成快照。

## 4. 自動壓縮（tick 的 idle 一步）

`info.json` 加一格（字面物件，不解指示詞；沒寫＝不自動）：

```json
"compact": {"max_tokens": 30000, "keep_rounds": 3, "auto": true}
```

| 鍵 | 沒寫時 | 意思 |
|---|---|---|
| `max_tokens` | 不自動 | 記憶粗估超過它就縮，也是縮的上限（100～10⁸） |
| `keep_rounds` | 3 | 最後幾輪原樣（0～1000） |
| `auto` | 有 `max_tokens` 就是 `true` | `false`＝只留給人與申請用 |

tick 在 idle、`intake` 是 `null` 時，**收輸入之前**：沒有輸入等著收、而且（有申請，或 `auto` 開著且記憶超過 `max_tokens`）→ 在同一把鎖裡叫同一個函式縮。縮了（或收了申請）這格就退 0，下一格才收輸入。
有輸入等著就先不縮（那句先進記憶；縮會讓 `say --wait`／`talk` 追的長度變短，見 §6）。
縮不動（還是超過、或 `HistoryInvalid`）就把「記憶 sha＋選項＋記憶提到的單號的狀態」寫進 `log/compact-skip`（任務做完了就會重新看），同一份記憶不再每格重算；記憶一變就又會看。錯誤進 `log/agent.err`（`aos-agent: compact: …`）與事件 `compact_fail`，不擋收輸入。`info.compact` 寫壞了不自動縮，也不每格噴錯（`check` 另查）。

## 5. 申請（模型只能寄申請）

走 [spec/team/mail.md〈申請〉](../team/mail.md)：`kind: "compact"`，登記在 `aos_team_requests.KINDS`（`aos_agent_compact:on_request`）。寄件人模板的 `may` 要有 `compact`。

| 欄位 | 意思 |
|---|---|
| `member`? | 縮誰的記憶；沒寫＝寄件人自己。只有 `human` 能替別人申請（`NotAllowed`）；名冊外＝`BadRecipient` |
| `keep_rounds`?、`max_tokens`? | 這次用的選項（範圍同 §4）；沒寫＝照那個成員的 `info.compact` |
| `reason`? | 500 字內，記進事件 |

處理函式把申請投成那個成員家的 `compact-req/<申請 id>.json`（暫存檔＋link，不覆蓋＝同 id 已在就是投過了），回空的後續動作清單。
tick 看到 `compact-req/*.json` 裡 `compact-req/done/` 還沒有同名收據的就縮（多份一起算一次，選項以檔名排序最後一份有寫的為準），然後在 `done/` 寫同名收據（原申請的副本）；**原檔不搬**：郵差靠「原檔在不在」去重，沒有先查再投的窗口（astra M4）。**先縮再放收據**，崩在中間重跑是空轉＋放收據。
`compact-req/` 由郵差建檔、tick 搬走，跟 `input/` 一樣「一邊投、一邊收」；成員的工具碰不到（在家裡，信任資料）。

## 6. 保證外

- 人在 `say --wait`／`talk` 等回話時剛好被縮（很窄：記下長度之後、那句被收之前）：記憶變短，它們會說「記憶被改短了」而不是印回話；回話照樣在記憶裡，`listen --last` 看得到。
- **封存的輪模型就看不到了**：09-24 真跑，封存後問「剛才 long.txt 幾行」，模型沒說不知道、答了錯的數字（原本 40 答 21）。要回頭找原文是二波 T-recall（模型）或人 `history --archive --grep`。
- 手改記憶與縮同時：縮拿了 tick 鎖，但手改的人不一定拿（[tick.md §2.1](../aos-agent/tick.md) 末那句同樣適用）；讀到的 bytes 與讀驗時不同就 `HistoryChanged`、不寫。
- token 是粗估，比端點的真數字少 15～30%；上限要留餘裕。
