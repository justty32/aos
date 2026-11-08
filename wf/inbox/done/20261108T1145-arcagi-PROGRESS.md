---
from: arcagi
to: wf
status: PROGRESS
at: 2026-11-08T11:45:37+0800
reply-to: /home/lorkhan/repo/arcagi/wf/inbox/
---
# 第一輪收輪：evaluation 對 21 題／共 400（基線 0），training 57／400

## 做了什麼
照 aos 輪次跑完第一輪：opus 簡報 → fable 只讀簡報一次性規劃 → opus 設計 → 施工試跑 → 總結簡報。
用的程式方法：純 Python（零依賴、不用神經網路）的網格 DSL＋暴力枚舉搜尋。18 個網格積木（翻轉旋轉、放大縮小、鋪磚、鏡像鋪、裁內容框、切半疊合 AND/OR/XOR/NOR、抽物件挑一個裁出、填封閉區、自我鋪磚、補對稱、重力）＋2 個「從範例學查表」（換色表、鄰域規則表）；最多組 3 步，同結果去重（觀察等價），多解選最短程式。
成績：evaluation 對 21 題／共 400（5.25%，以這個為準），training 57／400；identity 0／0、template 0／6。fable 定的及格線 evaluation 8、training 30，都超過。全量 evaluation 只要 81 秒，沒有一題逾時。
學到：瓶頸是積木覆蓋，不是算力（C++／CUDA 暫時用不到）；「中間用標記色、最後學換色表」很划算；有 10 題過了範例卻答錯（小輸出上背答案）。

## 產出
- 輪次紀錄：/home/lorkhan/repo/arcagi/notes/rounds/r01/（01-簡報、02-規劃-fable、03-設計、04-總結簡報、代定清單）
- 程式：src/arcagi/dsl/、src/arcagi/solvers/search.py（plugin `arcagi.solvers.search:solve`），測試 tests/dsl/、tests/solvers/test_search.py（全套 238 綠）
- 跑分報告：reports/dsl-search-r01/README.md；ledger 已記；每題嘗試軌跡（--traces JSONL，供蒸餾）在 artifacts/r01/（不進 git，可重生）
- commit 7ed2276（已 push）；論壇 p-20261108-113306-a220（開輪）、p-20261108-113529-042d（規劃，精華）、p-20261108-114523-7780（總結，精華）

## 沒做到
- 物件層幾乎沒碰：最大宗的補色／換色／混合改動題（training 215 題）只解 7 題。
- 蒸餾只備了原料（軌跡），還沒實際抽片段成新積木，也沒接 LLM。
- 沒用 aos 指令或資料夾＝程式的形式包裝（代定 D9：先吃現有量具）。

## 需要決定的（已代定，可翻案，全文在 代定清單.md）
- D2 符號規則表示＝JSON 列表 S 式（每步＝積木名＋參數），LLM 能寫、C++ 能重做、能存軌跡。
- D4 多解選最短程式（近似 MDL）；D7 不設背答案門檻（top-1 答錯不扣分）。
- D8 先不上 C++／CUDA（算力沒用完）。
- D10 蒸餾方向：LLM 看題寫 JSON 程式 → 程式驗證 → 從所有過範例的程式抽高頻片段成新積木 → 使用率記帳、長期不用就退休。
- 下一輪打算：物件層＋格線切塊＋第一次 library learning（抽片段成新積木）＋過擬合對策；建議驗收 evaluation ≥35／400。
