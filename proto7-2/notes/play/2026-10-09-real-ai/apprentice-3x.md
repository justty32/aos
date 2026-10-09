# 2026-10-09 學徒三連題：自我改進的真證據（S3 隊）

← [真 AI 第一圈](README.md)｜上一輪：[A5 學徒](apprentice-aos.md)｜意圖卡：[apprentice-3x](../../intents/apprentice-3x.md)｜證據：[evidence/apprentice3/](evidence/apprentice3/)

A5 那輪看不出「學徒越做越好」：只做了兩題，而且兩題不同類、失敗原因都在代理。這一輪讓學徒**連做三題同類的題目**，再和「不帶筆記」的對照組比。

## 三題（同形：讀 node 檔案 → 彙總 → 印一行 JSON）

| # | 題目夾 | 新工具 | 讀什麼 | 輸出 |
|---|---|---|---|---|
| 1 | [aos-tool-gap](../../../packs/author/examples/aos-tool-gap/request.json) | `aos7-evgap <events夾>` | events 的 obs／must 段檔＋state.json | 各通道筆數、首尾 seq、缺號區間、重號、未 ack 數、state 是否落後；壞行列 `bad` |
| 2 | [aos-tool-runs](../../../packs/author/examples/aos-tool-runs/request.json) | `aos7-runs <node> --now ISO` | `wf/routines.json`、`wf/schedule.json` | 每個 routine 的狀態（running／never／failed／overdue／ok）與下次時間、schedule 狀態、各狀態計數；壞列列 `bad` |
| 3 | [aos-tool-audit](../../../packs/author/examples/aos-tool-audit/request.json) | `aos7-mailtodo <郵局> --now ISO` | 各人 `inbox/`、`done/` 的信檔 | 沒人回終局狀態的 REQUEST（含信齡分鐘）、各信箱計數；壞信列 `bad` |

三題刻意共用同一批坑，題 1 學到的才用得上題 2、3：stdout 只能一行；路徑不是資料夾退 2；完全唯讀（**連鎖檔都不能建**，不能借用既有模組會寫檔的讀法）；bool 不算整數；「沒這個欄位」不等於「值是 null」；壞資料整筆不算、改列進 `bad`；每張表的排序寫死；時間一律 UTC，「現在」只從 `--now` 來。

**測資用真紀錄**：上一輪 usage 學徒寫的工具能過三關，卻讀不了真資料，因為測資是手捏的。這輪每題的 `fixture/` 都由 `make_fixture.py` 只用真模組的公開指令產生（events `pub`／`ack`、routines `add`／`ls --run`、mail `send`／`read`／`done`），原樣複製進來，連鎖檔、`.seen`、`.handled/` 都保留。之後只手動加少量壞資料，並在腳本裡註明：gap 有 24 筆真事件，刪掉 1 筆、加 2 行壞的；runs 有 12 列真資料、2 列壞的；audit 有 10 封真信、2 封壞信。也因為改用真資料，才發現第一版規格寫錯了兩處：辦結的信其實在 `inbox/done/`；routines 的 `last_time` 沒帶時區。檢查器還會把測資複製成唯讀的一份再跑，學徒的工具只要寫任何檔（包括鎖檔）就會失敗。

每題都有隱藏的答案檢查器（`check_answer.py`，學徒看不到）和固定測資（`fixture/`），另附一份參考答案（`valid.json`）證明題目做得出來。測試 [test_author_aos_3x.py](../../../packs/author/tests/test_author_aos_3x.py)：三份參考答案都通過離線三關；每題 4 種故意改壞（多印空行、`v` 給 true、排序反過來、建鎖檔）共 12 份都被擋下。

## 怎麼比

- **A 組（帶筆記）**：題 1 → 題 2 → 題 3。每題做完（過或沒過）跑一次 `aos7-author learn`，學徒把這題踩到的坑寫進 A 組自己的筆記；題 2、3 把筆記帶進提示。題 1 不帶筆記，條件和 B 組題 1 一樣。
- **B 組（對照）**：同樣三題、同樣順序，不帶筆記、不寫筆記。
- 固定：學徒 `chatgpt-gpt-6-sol-high`、審查 `chatgpt-gpt-6-astra-high`，全部走 llmcall 記帳；每題最多 3 輪（2 次重問）；A、B 各跑 2 次（rep 1、2），每次 A 的筆記從空白模板重來。題目順序對兩組一樣，題目本身的難易差異由 B 組抵掉。
- 名字：每組每題的 rid＝`<題><組><rep>`（例 `gapA1`），`aos7-metrics` 用它分單，A、B 不會混在一起。
- 量什麼：每題重問次數、學徒 token、審查 token、秒數、三關各關擋下的原因。token 以 `aos7-metrics job <學徒node> --json --overhead 1644` 為準。
- 選項（呼叫數有剩才跑）：A 組加 `--compact`，每題後把筆記壓到 2 KiB 內（本機摘要，不打 AI），看壓過的筆記還有沒有用；再由 astra-high 當學徒跑一次 A 組，只當參考。
- 呼叫數上限：所有組加起來 ≤200 次。每次呼叫前先記帳（出題＋審查記 2、learn 記 1，沒走到審查就退回 1），帳本加鎖，幾組同時跑也不會超過上限。最壞情況一組 A 是 3 題 ×（3 次出題＋3 次審查）＋3 次 learn＝21 次，B 是 18 次；兩次 rep 共 78 次。

腳本：[drive3.py](evidence/apprentice3/drive3.py)（跑一組）、[compare3.py](evidence/apprentice3/compare3.py)（印表與判準）。`drive3.py --offline` 用參考答案代替 AI 跑完整管線，已實跑：三題都一次通過。

## 成功判準（先寫死，跑完照算）

| 代號 | 判準 | 門檻 |
|---|---|---|
| G0 有效 | A、B 的 rep 成對，模型與 compact 設定相同，每組三題都跑完、沒有中途停下，每題 token 都有 metrics 數字；疑似代理問題 0 次（疑似＝沒交回候選，或①json 擋下且回覆 <500 字元） | 必須成立；不成立時結論寫「量不到」並列出原因，代理問題就停下回報 |
| G1 重問 | A 組（題 1 重問 − 題 3 重問）合計 − B 組同值合計 | ≥ 1 |
| G2 token | A 組（題 1 − 題 3）/ 題 1 的平均 − B 組同值的平均；只在 A、B 每次的題 1、題 3 都過時才算（沒過的答案變短不算省） | ≥ 0.20 |
| G3 不輸 | 題 2＋3 的學徒 token，A ≤ B | 輔助，不單獨決定結論 |

沒過的題，重問記 3 次（用完 2 次重問仍沒過，算比最差的過關多 1 次），token 照實際用量算。「過」＝三關都過，而且發布到 `apprentice/` 分支成功。

**結論規則**：G0 成立，而且 G1 或 G2 成立，才寫「有自我改進的證據」。G0 不成立寫「量不到」並附上原因，其他情況寫「沒看到」。連續兩輪疑似代理問題（可跨題），`drive3.py` 會自己停下（退出碼 5）。

## 結果

（實跑後填：2×2×3 題的表、擋下原因表、G0～G3、一句結論）
