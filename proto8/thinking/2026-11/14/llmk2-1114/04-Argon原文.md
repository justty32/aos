# 04 Argon 原文：審 03 計劃第一版（agy Gemini 4 Argon High，原文照錄）

← [llmk2-1114](../llmk2-1114.md)｜提示＝01＋03（第一版）全文，不給工具；採納與否見 [05 採納表](05-採納表.md)

### 總結論

opus 這份 `03-計劃` 骨架收斂得很準：**記帳樹不改路由、放行判準放站內、站外 `aos-llm-quota` 驗表與出報表、Claude 先從本機紀錄唯讀量測**，大方向完全可以拍板。

但在進入施工前，有 **3 個「高」嚴重度的算式與驗收破口**必須先補：
1. **§3.1 放行公式在三層以上的樹會破功**：同分支底下沒保底的兄弟，既能「偷吃」旁系保底，其消耗又會「抵銷」父節點往上申報的保底；而且公式算子孫可用量時**漏扣了父節點的 `self_reserve`**，子孫依然能把主管保底吃光。
2. **§7 驗收劇本沒測到上述破口**：劇本 3 的三層樹沒有旁系無保底兄弟，且整套劇本漏了 `self_reserve` 測試，照現有劇本跑會「假綠燈」。
3. **§6 Claude 電表與 §2.4 記帳細節有實作陷阱**：Claude 兩個帳號（`.claude` 與 `.claude-alt`）在設定與報表被混成同一個池、JSONL 串流多行去重若搭「記位移」會算錯、站內每 300ms 無狀態退路會狂印 warning。

以下分 **(A) 審查**、**(B) 提案** 與 **§9 方向題檢討** 逐條說明。

---

## (A) 審查：錯誤、漏洞、矛盾與修法

### 1. 【§3.1｜嚴重度：高】放行公式漏扣 `self_reserve(A)`，且沒區分「主管本人」與「子孫」
- **問題**：
  §3.1 寫 `self_reserve(A)` 只給 A 本人用、子孫碰不到；但算「A 給 X 這支的可用量」公式是：
  `cap(A) − used(A) − in_flight(A) − Σ_{兄弟 d≠往 X 那支} max(0, eff_g(d) − used(d) − in_flight(d))`
  這裡只扣了「其他兄弟分支 `d`」的未用保底，**完全沒扣 A 本人還沒用的 `self_reserve(A)`**！
  舉例：`repo-aos`（`cap: 100, self_reserve: 10`）底下只有 `ok-release`（無保底）。`ok-release` 連打 100 次，公式裡沒有其他兄弟可扣，`100 - used > 0` 全部放行，直接把主管的 10 次吃光，主管收到 BLOCKED 照樣卡死。
  反過來，當寄信者就是主管本人（`X == A`）時，公式裡的「往 X 那支」不存在，必須扣掉**所有子節點 `c ∈ children(A)`** 的未用保底，卻不扣 `self_reserve(A)`。
- **具體修法**：
  區分節點 A 的「本人消耗 `self_used_all(A) = self_used(A) + self_in_flight(A)`」與「子樹總消耗 `sub_used_all(A) = rollup_used(A) + rollup_in_flight(A)`」。
  定義 A 本人未用保留額：`rem_self(A) = max(0, self_reserve(A) - self_used_all(A))`。
  - 當信來自 A 的子孫（走分支 $c_X$）時，在 A 必須多扣掉 `rem_self(A)`。
  - 當信來自 A 本人（`X == A`）時，在 A 不扣 `rem_self(A)`，但要扣所有子節點 $c \in \text{children}(A)$ 的未用保底。

---

### 2. 【§3.1｜嚴重度：高】多層樹下，無保底兄弟會「抵銷」或「偷吃」跨層保底
- **問題**：
  在三層以上的樹，§3.1 的公式有兩個致命破口。
  設：`Root (cap=10)` → `D1 (無 cap, 無 guarantee)` → 子節點 `T1 (guarantee=4)` 與 `T2 (guarantee=0)`；`Root` 另有子節點 `D2 (guarantee=0)`。此時 `eff_g(D1) = 4`。
  - **破口一（無保底兄弟的消耗抵銷了保底）**：
    1. 沒保底的 `T2` 先打 4 次（在 `D1` 扣 `T1` 保底 4 後還有餘裕，在 `Root` 沒人有保底，全過）。此時 `used(D1) = 4`，但**有保底的 `T1` 其實 1 次都沒用**。
    2. 接著 `D2` 來打 6 次。`Root` 檢查為 `D1` 保留的未用保底：`max(0, eff_g(D1) - used(D1)) = max(0, 4 - 4) = 0`！
    3. `Root` 誤以為 `D1` 的 4 次保底已經兌現了，放行 `D2` 打光剩下的 6 次。最後 `T1` 來打第 1 次信時，全站已滿 10 次，`T1` 直接被 `BudgetMissing` 擋死！
  - **破口二（父層把分支當黑盒，無保底兄弟偷吃同支保底）**：
    1. 反過來，`D2` 先打 6 次（`Root` 留 4 次給 `D1`，放行）。此時 `used(Root) = 6, used(D1) = 0`。
    2. 接著 `D1` 底下沒保底的 `T2` 來打 4 次：
       - 在 `D1` 看：`D1` 沒寫 `cap`（就算繼承 `Root` 靜態 `cap=10`，`10 - used(D1)(0) - eff_g(T1)(4) = 6 > 0`），放行！
       - 在 `Root` 看：`T2` 屬於 `D1` 這支，`Root` 只扣 `D2` 的保底（0），**不扣 `D1` 內部的 `T1` 保底**，`10 - 6 - 0 = 4 > 0`，也放行！
    3. `T2` 把剩下的 4 次全打光，`T1` 的保底又被 `D2 + T2` 聯手吃光！
- **具體修法**：
  1. **未用保底 `rem_g(A)` 必須由下往上遞迴算，不能拿 `sub_used_all(A)` 混扣子節點保底**：
     $$\text{rem\_g}(A) = \text{rem\_self}(A) + \max\Big(\max(0, \text{guarantee}(A) - \text{sub\_used\_all}(A)), \sum_{c \in \text{children}(A)} \text{rem\_g}(c)\Big)$$
     （更佳做法見 (B) 提案 1：規定中間節點不手填 `guarantee`，則 $\text{rem\_g}(A) = \text{rem\_self}(A) + \sum_{c} \text{rem\_g}(c)$，葉節點 $\text{rem\_g}(L) = \max(0, \text{guarantee}(L) - \text{self\_used\_all}(L))$，完全不會被無保底兄弟抵銷。）
  2. **沿祖先鏈 $X = P_0 \to P_1 \to \dots \to P_k$ 檢查時，要累計整條路徑旁系的未用保底 `other_rem_g`**：
     - 起點 $P_0 = X$：若 $X$ 有子節點（主管本人寄信），$\text{other\_rem\_g}(X, X) = \sum_{c \in \text{children}(X)} \text{rem\_g}(c)$；若為葉節點則為 $0$。
     - 往上每一步 $P_j \to P_{j+1}$：
       $$\text{other\_rem\_g}(P_{j+1}, X) = \text{rem\_self}(P_{j+1}) + \sum_{d \in \text{children}(P_{j+1}), d \neq P_j} \text{rem\_g}(d) + \text{other\_rem\_g}(P_j, X)$$
     - 對每個有設 `cap` 的祖先 $A = P_i$，放行條件為：
       $$\text{cap}(A) - \text{sub\_used\_all}(A) - \text{other\_rem\_g}(A, X) > 0$$
     這樣在破口二中，`T2` 在 `Root` 檢查時會帶著 `other_rem_g(Root, T2) = rem_g(T1) = 4`，`10 - 6 - 4 = 0`，當場擋下 `T2`！

---

### 3. 【§2.4 vs §5.1 vs §8.8｜嚴重度：中】`used.json` 的 `groups` 記帳方式前後矛盾
- **問題**：
  1. §2.4 寫 `used.json` 的 `groups[<id>]` 只有 `{"calls", "tokens", "in_flight", "refused", "clamped"}`，**沒分 `self` 與 `rollup`**，也**沒有 `waiting` 與 `elapsed_ms`**；但 §5.1 的 `report.json` 卻需要 `self`、`rollup`、`waiting`、`elapsed_ms`。
  2. §8.8 寫「當窗用量跟 sender 走（一搬就可能超）」，但若站每拍是把用量死記在 `used.json` 的 `groups[<id>]` 裡，改表搬移 sender 時舊部門的 `groups` 數字根本不會跟著搬（那叫「跟 group 走」）。
- **具體修法**：
  站內原本就有 `used.json` 的 `senders[<sender>]`（記每個 sender 當窗已用 calls/tokens/elapsed_ms）與當拍活著的 `llm_*` proc / `requests/` 隊列。
  站每拍應**由 `senders` + 在飛 proc + 排隊信，透過當拍 `plan.json` 的 `match` 即時歸戶加總出每格的 `self` 與 `rollup`**（只有 `refused`、`clamped` 按發生當下的 group 累計或跟 sender 記），並把匯總快照寫入 `used.json` 的 `groups`（含 `self`、`rollup`、`waiting`）。這樣自然達成「改組時當窗用量跟 sender 走」，`report` 也能直接讀。

---

### 4. 【§2.4、§3.2｜嚴重度：中】驗表公式漏項、`default` 歸屬未定、`match` 深度定義混淆
- **問題**：
  1. **驗表公式與 §3.1 不一致**：§3.2 寫「每格 `Σ eff_g(children) + self_reserve ≤ cap`」，萬一該格自己寫了 `guarantee(A) > cap(A)` 卻沒小孩，這條式子竟然不驗！應改為對每一格 $A$ 檢查 **`eff_g(A) ≤ effective_cap(A)`**（`effective_cap` 為 $A$ 到根路徑上最近的 `cap`），且 `calls` 與 `tokens` 分別驗；單一子節點的 `cap` 若大於父的 `effective_cap` 也應拒。
  2. **`default` 格在 `tree` 外**：§2.4 的 `"default": {"cap": {"calls": 50}}` 在 `tree`（`company`）外面。請問 `default` 的用量算不算進根節點 `company` 的 `cap: 1500`？沒定義的話，unmatched 流量會繞過全公司總上限。
  3. **混淆「樹深度」與「字串前綴長度」**：§2.4 寫「多格都中取最深的」，§3.2 寫「不讓同一 sender 落在兩格同深度」。如果同層兩個兄弟部門一個叫 `ok-release`（預設 `procs/ok-release-*`）、一個叫 `ok-release-hotfix`（預設 `procs/ok-release-hotfix-*`），它們在**樹上是同深度**，但前綴一短一長！
  4. **sender 路徑格式未對齊 01 備料**：01 備料 §2.2 寫活樹 `llm-gpt` 的 senders 是 `gpt-lead2`、`sol-T03`（不帶 `procs/`），但 §2.4 預設 `match` 卻寫 `procs/<id>`。
- **具體修法**：
  1. `default` 應視為掛在根節點 `tree` 底下的隱含葉節點（共用根的 `cap`，且算進根的 `eff_g` 檢查）。
  2. `match` 改為**最長前綴優先（longest-prefix match，精確匹配優先於 `*`）**；驗表禁止「兩格擁有完全相同的 match pattern」。
  3. 明確規定比對前先把 sender 正規化（或同時支援 `<id>` 與 `procs/<id>`），務必與活樹 `used.json` 裡的 `senders` 鍵名格式一致。

---

### 5. 【§3.2｜嚴重度：中】300ms 無狀態行程的 `plan.applied.json` 寫檔與狂印 warning 問題
- **問題**：
  01 備料 §1 指出 `llm-gpt` 是 300ms 一拍、每拍一個新行程。
  若每拍讀 `plan.json` 驗過都重寫 `plan.applied.json`，一天會寫檔 28 萬次；若 `plan.json` 改壞了，因為每拍是新行程（無記憶體狀態），不知道上一拍已經印過 warning，會**每 300ms 印一行 warning 灌爆 log**。
- **具體修法**：
  比對 `plan.json` 與 `plan.applied.json` 的 `(mtime, size)` 或 `rev`：沒變就直接讀 `plan.applied.json` 略過驗表與寫檔；若 `plan.json` 壞掉，把壞檔的 hash 記在 `plan.bad.hash`，同一個壞檔只印一次 warning。

---

### 6. 【§2.3、§2.4、§7.4｜嚴重度：中】部門 `priority` 蓋寫規則與 `brain.py` 現況矛盾
- **問題**：
  01 備料 §2.1 明確指出：**現有 `brain.py` 根本不填 `priority`，信進來預設全是 `normal`**。
  但 §2.4 寫：「信自填的只能更低，不能更高：高了夾下來」。如果 `ok-release` 部門設為 `priority: "high"`，而它底下的 agent 寄信沒填 `priority`（被當成 `normal`），照「只能更低」的規則，這封信就會停在 `normal`，永遠升不上部門的 `high`！
- **具體修法**：
  把規則寫死：**信沒帶 `priority`（或為 null）時，直接填上部門的 `priority`；信有顯式帶 `priority` 時，若高於部門則夾為部門級並記 `priority_clamped`，若低於部門級則保留**。

---

### 7. 【§2.4、§5.1、§6｜嚴重度：中】Claude 電表：雙帳號混池、串流去重與共用工作區盲區
- **問題**：
  1. **雙帳號被混成單一池**：01 備料 §3 寫額度緊時會切 `.claude-alt`（兩個 200 美元帳號各有獨立週上限）。§6 雖寫「兩個帳號＝兩個池」，但 §2.4 的 `plan.json` 把兩個目錄塞進同一個 `"claude"` 字典，§5.1 的 `report.json` 也只有一個 `pools.claude.calibrated_pct`！兩個帳號混加會讓百分比校正完全失真。
  2. **JSONL 多行去重＋記位移會漏算**：Claude Code 一個回覆 turn（同一 `message.id`）在 JSONL 常隨 tool call 寫入多行，最後一行才有最終 `usage`。若「按 `message.id` 先見先贏去重＋記檔案 byte offset 增量掃」，會拿到第一行的殘缺 token 或跨次掃描重複算。
  3. **共用 `cwd` 盲區**：多數 agent 若都在主倉庫 `~/repo/aos` 啟動，`cwd` 相同，單靠 `ws_match` 分不出是哪條 `ok-*` 線。
- **具體修法**：
  1. `observed` 與 `report.json` 的 `pools` 將帳號分列（如 `claude` 與 `claude-alt`，或 `claude.accounts.<名>`），各自獨立校正百分比；部門 `nodes.<id>.claude` 則可合計 token。
  2. 同一個 `message.id` 必須取 **`output_tokens` 最大（或最後出現）** 的那筆；增量狀態檔要存當週已見 `message.id -> usage` 才能扣差額，且掃描時忽略最後未換行的半截行。
  3. `ws_match` 採最長路徑前綴匹配；共用 `~/repo/aos` 的紀錄歸入 `repo-aos` 並在報表註明。

---

### 8. 【§7｜嚴重度：高】驗收劇本漏測三層旁系與 `self_reserve`，無法證明聲稱性質
- **問題**：
  1. **劇本 3（三層保底）太單純**：`根 → D1（無保底）→ T1（guarantee 3）`，`D1` 底下沒有另一個無保底兄弟 `T2`，完全測不出審查第 2 條的兩個跨層破口。
  2. **完全沒有 `self_reserve` 劇本**：§1 把 `self_reserve` 列為核心設計，§7 卻連一條測試都沒寫（所以沒抓到審查第 1 條的漏扣）。
  3. **劇本 2（在飛）只測父 cap**：沒測「兄弟保底的在飛（`in_flight`）抵扣」。
- **具體修法**：
  - **擴充劇本 3**：設 `Root(cap 10)` → `D1` → `T1(guarantee 3)`、`T2(無保底)`，及 `Root` → `D2(無保底)`。必測兩輪：(3a) `T2` 先打 3 次後，`D2` 只能再打 4 次、第 5 次必擋，留 3 次給 `T1`；(3b) `D2` 先打 7 次後，`T2` 打第 1 次必擋，留 3 次給 `T1`。
  - **新增劇本 3.5（`self_reserve`）**：父 `cap 5, self_reserve 2`，子無保底；子打 3 次過、第 4 次必擋；此時父本人連打 2 次都過。
  - **擴充劇本 2**：在劇本 1 中讓 A 的 4 次保底處於「在飛（睡 5 秒）」狀態，驗證 B 的可用量不會因為 A 還沒完成而多扣或少扣。

---

## (B) 提案：還該加或該砍的

1. **【該砍】砍掉中間節點（有 `children` 者）手填的 `guarantee`，只留葉節點 `guarantee` 與主管 `self_reserve`**
   - **理由**：中間節點若能填一個跟子節點保底總和不同的 `guarantee`，會製造「多出來的部門保底算誰的」這筆糊塗帳，也是 §3.1 與 §3.2 算式變複雜的根源。規定**保底只設在葉節點（`guarantee`）與主管本人（`self_reserve`），父部門的保底純由子孫自動加總**，心智模型最直覺，公式與驗表瞬間乾淨一半。
2. **【該砍】v1 把 `tokens` 從站內放行（`admit`）拿掉，只做報表軟警告**
   - **理由**：§0.5 與 §1 明寫「只有次數是硬上限；token 只記與軟警告」，但 §3.4 又寫「已完成 token 超過時擋下一封」，自相矛盾。v1 應貫徹「站內只按 `calls` 擋 `BudgetMissing`；`tokens` 上限只在 `report` 亮 `soft` 燈」，避免單次長文本直接把部門鎖死。
3. **【該加】加一個 `aos-llm-quota match <sender>` 診斷子指令**
   - **理由**：十幾行程式就能印出「某 sender 命中哪一格、祖先鏈、有效 priority 與剩餘可用額」，在 v1.5 換上活樹對齊舊 sender 名時能省下大量除錯時間。

---

## 方向題（§9）檢討：有無漏題或選項寫偏

1. **第 2 題選項 (b) 寫成了稻草人**：
   原文 `(b) 不改站，站外每 N 秒產生 budget.senders（做不到……Argon 已證）` 既然已證明做不到，列出來只是陪榜。若要給真正的複雜度取捨，(b) 應改為：**「站內只做一層扁平部門格（不做多層動態保底扣減）」**，讓使用者在「多層樹 (a)」與「單層部門 (b)」之間做真選擇。
2. **第 4 題（Claude 盲區）漏了「多帳號怎麼呈現」**：
   使用者有 `.claude` 與 `.claude-alt` 兩個帳號輪替，題目應補問：**「報表與電力卡要把兩個 Claude 帳號分兩條池顯示，還是合在一起？」**（建議：卡片分列兩帳號餘額，部門帳合算 token）。
3. **漏了第 8 題：「當窗改表或改組時，已燒掉的額度怎麼算？」**：
   當某 agent 今天已經燒了 200 次，下午被移出該部門（或從 `default` 認領回某部門）時：
   - **(a) 跟 sender 走**（即時按新表重算，認領回來時該部門當日已用立刻 +200，可能馬上觸頂）；
   - **(b) 跟發生當下的部門走**（既往不咎，改表只影響改表後的呼叫）。
   這題直接決定站內 `used.json` 的記帳結構（對應審查第 3 條），應列為第 8 題請使用者拍板（預設建議 a，但支援 `set` 時順手拉高當日 `cap`）。
