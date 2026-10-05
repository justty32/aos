目前完成了 budget、subd 的狀態機與持久化邊界讀碼，找到一條 subd「合法 stop 後重開可能誤殺保留任務」的候選反例，但尚未完成窮舉檢查器或真程式驗證，因此不能宣稱任何不變條件已通過或已被實測推翻。

## 1. 執行範圍與交付狀態

依照提前收尾指示，停止新增執行與派工，本報告只採用已讀取的程式、收到的分析，以及已知證據路徑。

- 沒有修改 `/home/guanyu/projs/aos` 下的檔案，沒有 commit、push 或呼叫 LLM 端點。
- 已開五條平行工作線：budget 模型、subd 模型、兩包真程式驗證、獨立審查。
- 收尾前尚未收到可確認完成的檢查器、窮舉統計或重現結果。
- 已啟動兩包既有測試，輸出導向 `evidence/baseline/original-suites.log`；**尚未取得完成狀態，不能報成通過或失敗**。

以下路徑均相對於工作副本：

```text
/tmp/claude-1000/-home-guanyu-projs-aos/8aa61430-d017-4079-b09f-02620d555dd9/scratchpad/burn/ws/model-check/
```

## 2. 已確認的發現：程式結構與保護邊界

### 2.1 budget 的餘額與業務去重紀錄，在同一次帳本寫入提交

reserve 在持有 `ledger.json` 鎖時讀帳、查同一業務鍵的紀錄，接著一起修改餘額、log 與 `ops`，最後寫回整份帳本。settle 同樣先檢查是否已結算，再將結算狀態與餘額一起寫入。

這表示檢查器應把「帳本整份提交」作為一個提交邊界，不能虛構出「餘額已扣但 ops 尚未寫入」這種程式沒有的獨立寫入窗口。

**證據：**

- `proto7-2/packs/budget/aos7_budget.py:208`：餘額與轉移紀錄更新。
- `proto7-2/packs/budget/aos7_budget.py:243`：取得帳本鎖。
- `proto7-2/packs/budget/aos7_budget.py:257`：同鍵、同內容重播直接回傳既有紀錄。
- `proto7-2/packs/budget/aos7_budget.py:272`：建立預留、修改帳本並於第 276 行提交。
- `proto7-2/packs/budget/aos7_budget.py:282`：已結算請求直接回傳。
- `proto7-2/packs/budget/aos7_budget.py:291`：結算狀態、餘額與紀錄於第 294 行共同提交。

**限制：**這是程式結構確認，不是對所有並行與中斷組合的證明。

### 2.2 budget 的回條與請求刪除，是帳本提交之外的中斷點

處理 inbox 時，程式先完成帳本處理，再寫回條，最後刪除請求。因此檢查器必須涵蓋「帳本已提交但尚未回條」及「回條已寫但請求仍在」兩種恢復路徑。

**證據：**

- `proto7-2/packs/budget/aos7_budget.py:319`：呼叫帳本處理。
- `proto7-2/packs/budget/aos7_budget.py:325`：寫回條。
- `proto7-2/packs/budget/aos7_budget.py:326`：刪除請求。
- `proto7-2/packs/budget/aos7_budget.py:247`：時鐘水位另有一次帳本寫入，不能漏列。

### 2.3 subd 的合法停止判定，跨越三類持久化證據

subd 不只看生命週期檔，而是以 daemon 的 `status.json`、成功 stop 回條及生命週期的 `since` 判斷。判定成功後，先寫 `stopped.json`，再把生命週期改成 `stopped`。

啟動端能補完這段提交，確實覆蓋「合法 stop 已完成，但包裝程式尚未寫完停止標記」的窗口；不過，這不等於後續重新啟動的所有窗口也受到保護。

**證據：**

- `proto7-2/modules/subd/aos7-subd:141`：`allowed_stop()`。
- `proto7-2/modules/subd/aos7-subd:173`：成功回條時間必須不早於 `since`。
- `proto7-2/modules/subd/aos7-subd:179`：先寫停止標記，再寫生命週期。
- `proto7-2/modules/subd/aos7-subd:189`：啟動端補完停止提交。
- `proto7-2/modules/subd/aos7-subd:264`：生命週期為 `stopped` 才跳過前代回收。

## 3. 從程式抽出的狀態機草圖

這些是已讀碼的文字模型，**尚未完成可執行的狀態空間檢查器**。

### budget

```text
未開帳
  └─ init：提交 ledger.json
       ↓
無此 K
  └─ reserve：資格／餘額檢查
       └─ 原子提交〔available -= amount、inflight += amount、ops、log〕
            ↓
已預留
  ├─ 同 K 同內容 reserve → 回既有結果
  ├─ 同 K 不同內容 reserve → conflict
  ├─ run → gateway intent → backend 效果＋去重提交 → gateway 終局
  └─ cancel → 依入口／後端事實產生終局
            ↓
入口已有終局
  └─ settle：原子提交〔inflight -= amount、used += 支用量、
                       available += 未支用量、ops、log〕
            ↓
已結算
  └─ 同 K 重播 → 回既有結果

帳本處理完成 → 寫回條 → 刪請求
每個持久化邊界前後均應可中斷，重開後由持久事實恢復。
```

預定檢查：守恆、各餘額非負、同 K 不重扣，以及後端效果不因重播重複。最後一項不能只從帳本守恆推導。

### subd

```text
啟動
  → 查 stopped.json
  → 取得 subd.lock、daemon.lock
  → 讀生命週期
       ├─ running 且合法 stop 證據成立
       │    → 補 stopped.json → life=stopped → 不起、不回收
       ├─ stopped
       │    → 跳過回收
       └─ 其他
            → life=recovering → 回收前代 → 確認已空
  → life=running（新 since）
  → 寫 stop-guard.json
  → 釋放 daemon.lock
  → 起 argv
  → 寫 owner.json
  → 等 argv 結束
       ├─ 合法 stop → stopped.json → life=stopped
       └─ 否則保留 running，留待下次判斷／回收
```

**證據：**`proto7-2/modules/subd/aos7-subd:227`、`:242`、`:250`、`:264`、`:275`、`:292`、`:295`、`:303`。

## 4. MC-01：重新接回前覆寫停止證據，可能誤殺應保留任務

**狀態：讀碼候選反例；未經檢查器產生，未經真程式重現。**

主線與獨立審查線皆指出以下路徑：

1. 子 daemon 完成合法、不帶 kill 的 stop，任務仍存活。
2. 包裝程式完成停止提交，生命週期為 `stopped`。
3. 使用者依文件允許的操作刪除 `stopped.json`，準備重新接回。
4. 新包裝程式看到生命週期 `stopped`，跳過前代回收。
5. 包裝程式先提交新的 `running` 與較晚的 `since`。
6. 在起 argv 前中斷。
7. 再次啟動時，生命週期已是 `running`；先前 stop 回條早於新 `since`，不再符合 `allowed_stop()`。
8. 程式進入前代回收，可能殺掉原本應保留、而且尚未被新 daemon 接回的任務。

```text
合法停止、任務保留
  → 刪停止標記
  → 跳過回收
  → 寫新 running
  → 中斷，尚未起 argv
  → 重開時舊 stop 回條不符新 since
  → 回收保留任務
```

**證據：**

- `proto7-2/modules/subd/README.md`：「被允許的 stop 不回收」與刪除停止標記後接回任務的規則。
- `proto7-2/modules/subd/aos7-subd:264`：`stopped` 跳過回收。
- `proto7-2/modules/subd/aos7-subd:275`：產生新 `since`。
- `proto7-2/modules/subd/aos7-subd:276`：覆寫為 `running`。
- `proto7-2/modules/subd/aos7-subd:277`：現成中斷點 `subd-before-argv`。
- `proto7-2/modules/subd/aos7-subd:173`：依新 `since` 排除舊回條。
- `proto7-2/modules/subd/aos7-subd:266`：轉入 `recovering`，第 268 行執行回收。

**尚缺驗證：**建立真實保留任務，確認合法 stop 已完成，以 `subd-before-argv` 中斷重開，再觀察下一次重開是否殺掉同一 PID／starttime 的任務；並保留正常重開的對照案例。此次沒有可交付的重現腳本或結果。

## 5. 窮舉規模與實測證據

| 項目 | 收尾時可確認狀態 |
|---|---|
| budget 檢查器 | 已分工、已盤點主要提交點；未取得完成品 |
| subd 檢查器 | 已分工、已抽出主要生命週期；未取得完成品 |
| 已探索狀態數／邊數 | 無可確認統計 |
| 中斷點 × 重開順序 × 並行請求覆蓋率 | 尚未建立 |
| 檢查器產生且真程式驗證的反例 | 0 件已確認 |
| 讀碼候選反例 | MC-01 |
| 既有測試 | 已啟動，完成結果未確認 |

既有測試啟動指令：

```sh
python3 proto7-2/tests/run_all.py -v \
  packs/budget/tests modules/subd/tests \
  > evidence/baseline/original-suites.log 2>&1
```

**證據路徑：**`evidence/baseline/original-suites.log`。本次收尾沒有重新讀取該檔，不能據此填入測試數或成功率。

## 6. 做到一半與尚未完成的工作

做到一半：

- 兩包的模型建置與持久化點盤點。
- 真程式中斷注入與並行驗證腳本設計。
- MC-01 的模型化與重現安排。
- 兩包既有測試的執行與結果收集。

尚未完成：

- 交付兩支可重跑的 Python 窮舉檢查器。
- 宣告有限域、探索界限、狀態合併規則與完整性限制。
- 產生狀態數、轉移數、最短反例及機器可讀結果。
- 用真程式重播模型選出的路徑。
- 對時間敏感的失敗單獨重跑。
- 驗證 subd 同代不雙開，以及 budget 守恆、同 request 不重扣。
- 確認 MC-01 是否構成契約內的實際缺陷。

因此，本次交付屬於**有來源定位的初步分析與一條待驗證反例**，不是已完成的狀態空間窮舉報告。