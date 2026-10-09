# EF2：LLM 之後的等待（效率 #2）

← [R1 消耗報告](README.md)｜基線：[metrics-baseline](metrics-baseline.md) 排序 #2｜改動：[author spec 第二層](../../../packs/author/spec.md)

2026-10-09 EF2 隊。目標「結算→step 結束」4.1 秒 → ≤1.5 秒，只准用核心既有 wake／early_tock、不改核心與 step。

## 改了什麼

- author 編出的 step 表 `options.wake` 由 `false` 改 `true`（`aos7_author.py` `compile_steps` 一行）。step 每派一個子工作就寫 daemon 的 wake；固定 interval 時這會**提前結束當回合**，子工作下一回合馬上起。
- `modules/up/aos7_up.py` **沒改**：up 不寫 `timeline.json`，用核心預設 interval 1000 ms、`early_tock: false`；沒有 interval 常數可調。心跳 1 秒是設計下限，`early_tock` 預設關是使用者先前的裁定（「有些人就是想要固定的 interval」），本隊不翻。
- 新測試 `packs/author/tests/test_author_wake.py`：編出的表 `wake` 為真且過 step 檢查器；真 daemon 跑完 csv 範例，log 裡有 ≥2 筆該工作送的 wake。改回 `false` 兩案都紅。

## 量測

兩種口徑。**step 真結束**＝旁邊每 20 ms 看 `frame.json` 第一次 `phase: ended`；**E1 口徑**＝`frame.json` 最後的 `at`，實際是 run.sh 的 `step close` 時刻，含 run.sh 每 1 秒輪詢一次 status、`answer` 與 close——基線 4.131 用的就是這個，所以它有一大塊是量測腳本自己的等待。

| | 改前 | 改後 | 差 |
|---|---|---|---|
| 真 AI，step 真結束（改前 6 圈 main、改後 12 圈） | 3.340（3.242～3.402） | **2.714**（2.595～2.794） | −0.63 |
| 真 AI，E1 口徑（同上） | 4.503（4.363～4.560）；R1 存檔復算 4.131 | **3.768**（3.647～3.848） | −0.74 |
| 離線（不叫 LLM，propose 後→step 真結束，各 8 圈） | 3.646 | 2.739 | −0.91 |

真 AI 共 19 次呼叫（改後 12＋單測 1、改前 6），12／12、6／6 都過三關、step ok、答案對、close。

**目標 ≤1.5 秒沒達到。** 原因（離線拆解）：剩下約 2.7 秒＝發布＋起 daemon 約 0.3 秒＋兩個子工作各卡一整個 1 秒回合＋最後一圈。wake 只能縮「派工→子工作開始」；子工作 0.05 秒跑完後，沒有人能 wake（結果是 step 包寫的，不在本隊領地；核心也不在），step 要等到這回合滿 1 秒的 tock 才看到結果。

## 其他組合（離線、只供裁定，未採用）

| 設定（都已 wake=true） | 平均秒 | 代價 |
|---|---|---|
| 預設：1000 ms、固定 | 2.739 | — |
| 1000 ms＋`early_tock: true` | 2.104 | 推翻「預設固定 interval」；step 常駐任務起的那回合仍卡滿 1 秒；step 的 wake 若早於 tock 收尾會被忽略，偶爾多等一回合 |
| 500 ms、固定 | 1.799 | 心跳快一倍（低於 1 秒下限） |
| 500 ms＋`early_tock` | **1.429** | 兩者都要 |

不改核心／step 要到 ≤1.5，只有最後一列。另一條路（要動別人的領地）：step 結果檔寫完就 wake（step 包），或 publish 後 wake（`aos7_author_pub.py`，daemon 已在跑時省平均 0.5 秒的等 tick）。

## 邊緣

- 審查（astra）P2：**舊版程式編到一半中斷**（steps.json 已寫、verdict 未存），升級後重送同一候選，新編出 `wake: true` 與磁碟上的 `false` 不同 → `conflict`。已發布、有 verdict 的舊工作不受影響（recompute 用磁碟原檔）。代定：不修，遇到時刪掉那個未發布的 `jobs/<job>/` 再 propose。
- wake 作用整個 node：同 node 的 brain 等常駐任務、以回合計的 patience 會跟著多一個回合（brain 空信箱不叫 LLM）。
- 量測腳本（不入庫）：離線 bench＝暫存 root、`propose --candidate valid.json`、publish、起 daemon、輪詢 frame；真 AI＝原樣跑 `examples/llm-request/run.sh`，旁邊輪詢 frame。
