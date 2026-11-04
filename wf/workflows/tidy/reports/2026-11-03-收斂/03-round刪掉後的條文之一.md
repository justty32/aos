← [回入口 2026-11-03-收斂.md](../2026-11-03-收斂.md)｜段落：round 刪掉後沒實作撐的條文（11-04，給使用者裁）｜上一份：[02-條文摺疊紀錄與補對讀](02-條文摺疊紀錄與補對讀.md)｜下一份：[04-round刪掉後的條文之二與明天怎麼接](04-round刪掉後的條文之二與明天怎麼接.md)

## round 刪掉後沒實作撐的條文（11-04，給使用者裁）

round 那套 agent（`lib/agent/round/`、parts、queue／history／act／compact 格、`lib/endpoint/`、`hook/*`）11-03 已刪，概念在 `proto8/archive/agent-round-concepts/`。下面 13 條（小條）是 SESSION-LOG 列的、講到 round 的條文；文字一字沒動（鐵律 5），「還有實作嗎」是 11-04 grep 現有程式的結果。建議分三種：**留**（規則本身還有程式在做，只是例子出自 round，例子旁加一句已無實作）、**加註**（整條已無實作，但有一半還有用或有同類做法，留著加註）、**刪**（整條只講 round，沒有程式撐）。NORMS 05（N-14～17）與 C-54 不在這份裡。

| # | 條 | 白話：它在講什麼 | 還有實作嗎 | 建議 |
|---|---|---|---|---|
| 1 | NORMS/01 N-43 10-30「10 是對直接收到它的那層說的」 | 退 10＝「叫我的那層別再跑了」；中間的 fsm 表上接住了 10，fsm 自己退 0，外面的 loop 看不到 10 | 有：aos-fsm 的物件 `next` 照舊（impls/aos-fsm 測試 G 段「10 接住→fsm 退 0」）；例子出自 aos-round | 留，例子加註 |
| 2 | NORMS/01 N-43 10-28「錯誤分類靠 stderr 代號，結束碼仍一律 1」 | 要讓人分種類的錯，寫在 stderr 那行的代號裡，不另用結束碼 | 有：demo 各隻 `brain.py` 退 `BrainFailed` 等代號，全 repo 的錯都這樣報；只有末句「round 把 stderr 交給 `hook/on_error`」那個例子沒了 | 留，例子加註 |
| 3 | NORMS/07 N-36 10-30「`next` 兩種寫法、照結束碼分岔」 | fsm 每格的 `next` 可以寫成「結束碼 → 下一格」的表 | 有：aos-fsm C++ 實作與測試都在；目前沒有現役的表用物件 `next`；末句「範本 `lib/agent/round/` 的表只接 0 與 10」範本已刪 | 留，末句加註 |
| 4 | NORMS/07 N-39 10-30「trace 加 `next`」 | fsm 的 trace 每行多記這次換到哪一格 | 無：fsm 11-03 起不寫 trace | 刪 |
| 5 | NORMS/08【agent】「agent 的一輪（round）與各格」 | 待定清單裡記著 round 那套的細節「等 round 做完再落條文」 | 無：整套已刪 | 刪 |
| 6 | NORMS/10 N-53 10-28「一格一次用 aos-loop、一輪用 round，看 `_entry`」 | 同一套格，`_entry` 寫 aos-loop＝一次一格；寫 round＝一次跑完一整輪 | 「一輪」那半無；「一次一格」N-53 本文本來就有 | 刪（使用者 10-28 兩句原話留在 thinking 10-28 agent-ops/01） |
| 7 | CONVENTION/06 P-33 10-28「round 與每一格拿 agent 資料夾絕對路徑當第一個參數」 | 格放在共用庫、cwd 在庫那邊找不到 agent，所以 loop.json 用 `{"$env": "AOS_CD"}` 把 agent 資料夾當參數明給 | round 那套無；同一手法 aos-eca-turn 在用（demo/eca-claude 的 loop.json 把 `AOS_CD` 當參數給它），但 eca 不在這條的字面裡 | 加註已無 round 實作（要留「agent 資料夾用參數明給」這個做法，改寫成一般說法由使用者定） |
| 8 | CONVENTION/06 P-35 10-30「接住的 10 到不了 loop」 | 同 1，從「格叫工具」這邊講：物件 `next` 的表上任一格的 10 都能被接住 | 有：同 1；例子「think 退 10＝該交卷、act 退 10＝插話」出自 aos-round | 留，例子加註 |
| 9 | CONVENTION/02 P-20 10-30「表上沒接住時才是預設停」 | 「任一格失敗＝停下等人」是表沒接那個碼時的預設，表上接了就照表走 | 前半有（fsm 物件 `next`）；後半「endpoint 的 retry／switch 問 `hook/on_error`、數 `AOS_ROUND_MAX_RETRIES`」無 | 加註後半已無實作 |
| 10 | CONVENTION/02 P-20 10-28「起改成『預設』停」 | endpoint 失敗先問 `hook/on_error`，它說 retry／switch／stop | 無：`hook/`、endpoint 格都刪了 | 刪 |
| 11 | CONVENTION/02 P-23 10-28「起 endpoint 是 aos 函數」 | 腦＝一個 `endpoint/<名>` 資料夾，stdin 請求、stdout 一則回覆；`endpoint.txt` 選哪個、`usage.jsonl` 記用量 | 無：`lib/endpoint/`、`endpoint.txt`、`usage.jsonl` 都沒人用；現有 demo 照條末「舊的寫法」用 `brain.py` | 刪（使用者原話「各種單位都要跟aos函數對上…包括endpoint」留在 thinking 10-28 agent-ops；這個方向要不要留一句由使用者定） |
| 12 | CONVENTION/02 P-25 10-28「格也走註冊檔」 | 腦能叫的工具走 `tools.json`；agent 自己的格走另一份 `parts.json`，沒寫的找固定名字 | `tools.json`（bin/aos-tools）有；`parts.json` 無（只剩 test_eca 驗「沒有 parts.json」） | 加註 `parts.json` 那半已無實作 |
| 13 | CONVENTION/02 P-41 10-28「起腦拆成格、history 只有 compact 可以改寫」 | think 拆成 endpoint／history／act 格；history 只附加，只有 `history compact` 能壓短、舊的收進 `history_archive/` | 無：這些格都刪了；demo/agent-hal 自己的 compact 是另一套（輪替到 `compact/<run>/orig.jsonl`），不是這條講的 | 刪 |

小計：留 4 條（1、2、3、8，只在例子旁加註）、加註 3 條（7、9、12）、刪 6 條（4、5、6、10、11、13）。

**11-04 使用者照建議、已落**（使用者 11-04「照建議」）：留 4、加註 3、刪 6，照上表建議欄做完；NORMS 05（N-14～17）與 C-54 沒碰。

- 留與加註的 7 條：條文原字不動，各在出自 round 的那句旁加一段 **11-04 加註**（例子／哪一半出自已刪的 round、規則本身由誰撐著或哪一半已無實作），連回本段。1、2 在 NORMS/01 N-43，3 在 NORMS/07 N-36，7、8 在 CONVENTION/06 P-33、P-35，9、12 在 CONVENTION/02 P-20、P-25。第 7 條只加註，不改寫成一般說法。
- `<!-- round：待使用者看 -->` 標記（P1-1 留的，NORMS/01 兩個、07 兩個、10 一個）裁完拿掉。
- 改了的引用：NORMS/07 N-39 本文刪「下面的『10-30 加註：trace 加 `next`』照這條讀」半句；NORMS.md 主題表組合子那列刪「N-39 trace 加 `next`」；CONVENTION.md 腦的工具呼叫那段改成只列還在的 P-25、P-33，註明 P-23、P-41、P-20 三條 10-28 加註已刪；CONCEPTS/03 C-25 的 10-28 補引「N-53 的 10-28 加註」旁註明已刪；C-25 這個子項本身也只講 round，使用者 11-04「一起刪」，已刪（原話在 thinking 10-28 agent-ops/01）；第 2 條末句引的「CONVENTION P-20 的 10-28 加註」在 11-04 加註裡註明已刪。
