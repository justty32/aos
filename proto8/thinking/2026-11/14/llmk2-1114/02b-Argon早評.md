# 02b Argon 早評：對 02 fable 稿與 02a astra 稿的審查＋提案（agy Gemini 4 Argon High，原文照錄）

← [llmk2-1114](../llmk2-1114.md)｜提示＝01＋02＋02a 全文，不給工具（第一次它想跑指令被 headless 擋、沒產出，第二次在提示開頭加「不要呼叫任何工具」）

## 先講結論

1. **大方向選 fable 的「記帳樹」，淘汰 astra 的「路由樹（每部門一站）」**：全景（ok-view）已定調「組織歸屬 ≠ 請求路由」。如果照 astra 讓每個部門、小隊都開一個 `llm_forward` 站，每次問腦就要多串幾層 300ms 的 looping proc 與子 proc，不僅吃光系統 `procs` 限額、放大延遲，還會讓底層硬體 `slots` 與部門排程脫節。
2. **但 fable 的「站外分配器每 N 秒寫檔」與「第一版靜態編譯」有嚴重漏洞，應改為「站外管政策與跨站報表、站內即時查樹扣帳」**：`ledger.jsonl` 是請求**收尾**才寫入（在飛請求不在裡面），且現有站的 `budget.senders` 不支援萬用字元、對未列名 sender 是「無限額度」。不微調 `kernel_llm` 站內邏輯，fable 第一版連「部門共享上限」與「擋未知 sender」都做不到。
3. **配額模型採「父格圈子孫＋保底（guarantee）＋允許上限（cap）超賣」**：吸收 fable 的 cgroup 思維，淘汰 astra 僵化的「嚴格切塊＋人工撥候補池」。但必須修補 fable 在三層樹以上的保底遞迴數學漏洞。
4. **面對最大的盲區（Claude 不經 kernel）**：融合 astra 的誠實標記（`enforced / observed / unknown`）與 fable 的「本機 log 外部電表＋派工閘」。先讓董事長看得到哪個部門燒了多少 Claude，並在開新 Claude 子 agent（派工／hire）那道門設卡，而不是去改動 eca 身體。

---

## (A) 審查：兩稿錯誤、漏洞與分歧裁決

### 一、02 fable 稿的毛病與漏洞

1. **[嚴重度：高] 第一版用 `compile` 靜態編成 `budget.senders`，根本做不到「部門共享額度」與「限制未知 sender」（出處：第 0 節結論 5、第 8 節）**
   - **與備料事實矛盾**：備料第 2.2 節明載「沒列名的 sender 沒有預設額度（只受站總量與 pack 限）」，且現有 `kernel.json` 的 `budget.senders` 只認完整 sender 字串，不認 fable 第 3.1 節寫的 `match: ["procs/ok-release-*"]` 萬用字元。
   - **漏洞後果**：第一版若不改 kernel 程式、只靜態產出 `budget.senders`：(a) 執行期新長出來的 subagent（不在靜態名單上）打進來會**完全無上限**，直接打穿 `default` 規則；(b) 若部門 A（cap 100）底下有 3 隻已知 agent，靜態編譯「取自己到根的最小 cap」會給每隻 agent 各 100 的額度，結果部門 A 總共能打 300 次，根本擋不住部門總量。
2. **[嚴重度：高] 放行公式在「三層以上樹」會算丟孫部門保底，且站外讀 `ledger.jsonl` 漏算在飛（in-flight）請求（出處：第 2.2 節、第 3.2 節）**
   - **公式漏洞**：3.2 節公式寫祖先 A 的可用量為 `cap(A) − used(A) − Σ 其他孩子 d 的 max(0, guarantee(d) − used(d))`。在三層樹（Company → 部門 D1 → 小組 T1）中，若 D1 沒設 `guarantee`、但孫子 T1 設了 `guarantee: 100`，當旁系部門 D2 來用額度時，根節點 Company 只檢查直接孩子 D1 的 `guarantee(D1)`（為 0），就會把留給孫子 T1 的保底全部吃光！3.2 節只規定「子 guarantee 加總 ≤ 父 cap」，漏掉了「父的有效保底必須 ≥ 子保底加總」的遞迴約束。
   - **時差與在飛漏洞**：備料第 1 節明載 `ledger.jsonl` 是「每封**收尾**一行」。分配器每 N 秒讀一次 `ledger.jsonl` 產出 `gate.json`，完全看不到「正在飛（佔住 slots）」的請求，在短時間併發或長耗時呼叫下必然超發、吃掉別人的保底。
3. **[嚴重度：中] 報表宣稱有 `waiting`（排隊中）與 `refused`（被拒次數），但只讀 `ledger.jsonl` 根本生不出來（出處：第 2.2、3.3、5.1、8 節）**
   - 排隊中的信在站的 `requests/` 裡，還沒打完不會進 `ledger.jsonl`；被 `BudgetMissing` 擋掉的信若沒進 ledger，站外分配器也算不出 `refused`。fable 在 3.3 與 5.1 把 `refused`、`waiting` 當核心指標，卻在第 8 節括號自招「refused 先留空欄」，前後矛盾。
4. **[嚴重度：中] 發明「點（points）」跨模型換算，卻與 `plan.json` 的 `calls` 配額脫鉤（出處：第 3.1 節、第 6 節）**
   - 第 6 節定義 `點 ＝ total_tokens ÷ 1000 × rates[pack]` 說要放在同一條額度比，但 3.1 節的配額表全用 `calls` 定 cap 與 guarantee。Token 是事後才知、每次浮動極大，且備料第 3 節只有「astra 約 sol 3 倍」的粗略說法，把「點」放進配額與靜態編譯只會製造混亂。
5. **[嚴重度：低] `power` 單自創字串語法＋LLM 兜底解讀，與 5.3 節結構化 UI 自相矛盾（出處：第 5.2 節 vs 第 5.3 節）**
   - 5.2 節設計了 `[池] cap|保底 數字 calls|tokens|點 [/day|/week]` 的字串解析，還說看不懂轉給 agent 解讀；5.3 節卻又要求全景把 `quota` 拆成結構化欄位。既然全景正在改，直接傳結構化欄位即可，讓固定程序去解析自然語言字串純屬找麻煩。

---

### 二、02a astra 對照稿的毛病與漏洞

1. **[嚴重度：高] 把「每部門一個 `llm_forward` 站」當主幹，引發 proc 數量與延遲爆炸，且違背全景設計（出處：第二、四、七節）**
   - **與備料事實衝突**：備料第 1 節指出「一站＝一個 300ms looping proc，每封放行的信另掛成 `llm_<信名>` proc」。照 astra 設計（`agent → team station → department station → provider station`），每問一次腦要穿過 3 個輪詢站、生出 3 個子 proc！這不僅平白增加近 1 秒延遲，還會快速撞上備料第 5 節 daemon 的 `procs` / `procs_total` 限制。
   - **排程與硬體 slots 脫鉤**：真正有硬體限制（3 個 slots）的是最底層 provider station。如果上游部門站不限 slots，信件瞬間轉給下游，部門站的 priority 與 aging 根本沒發生（因為沒在部門站排隊）；如果部門站限了 slots，又會發生「底層 provider 有空位、部門站卻自己卡住」的阻塞。況且備料第 6 節明講「組織歸屬 ≠ 請求路由」，綁死路由樹會讓每次組織改組都得重啟站、改環境變數。
2. **[嚴重度：高] 宣稱第一版「不重寫底下的 scheduler、只靠既有 forwarding 站」，卻要求站做出現有程式碼沒有的功能（出處：第二、三、七節）**
   - **自相矛盾**：astra 第二節說 `llm-budget-office` 不在每次問腦的熱路徑上，只產出設定給既有站；但第三節與第七節卻要求做到：(a)「未知 sender 在政策檢查處拒絕，不能沿用沒列名就沒有個別上限的漏洞」、(b)「部門設定 `priority_default` 與 `priority_max`，站在排程前填入或限制信的優先級」。
   - **事實查核**：備料第 2.1、2.2 節寫得一清二楚——現有站**沒有**預設 sender 拒絕機制（沒列名就不限），也**沒有**替 sender 填入或限制 priority 的功能！不改站的程式碼（或加 hook），既有 forwarding 站根本做不到這兩件事。
3. **[嚴重度：中] 嚴格切塊（不准超賣）＋人工候補池＋停機轉移，會造成嚴重的額度閒置與官僚死鎖（出處：第三、四節）**
   - astra 規定 `本人 + 直接子部門 + 候補 ≤ 本部門額度`，不自動借貸，跨部門轉移還要「等換窗，或先停止新放行、結清在飛請求，再減舊額、增新額」。
   - 在 agent 公司中，各部門是波峰波谷運作（今天衝 release、明天衝 view）。嚴格切塊每往下一層就鎖死一塊候補與本人額度，分到第三層時每隻 agent 剩不到幾十次；忙碌的線動輒撞 `BudgetMissing` 等主管人工批候補，閒置部門的額度卻鎖死不能用。
4. **[嚴重度：中] 降級（fallback）前提假設了現有站不存在的「部門內按 pack 切子額度」（出處：第三節「不夠時的順序」）**
   - astra 說「若碰到的是昂貴 pack 的子額度，而總額仍有餘裕，才可能改走核准的替代包」。但現有站的帳是 `站總量 / pack / sender` 三份平行的帳，並沒有 `sender × pack` 的交叉配額，除非強制每個部門獨佔一個 forwarding 站。
5. **[嚴重度：低] 額度窗口綁死「日（day）」，與 Claude 的「週（week）」上限格格不入（出處：第三節 vs 第五節）**
   - 第三節規定第一版以「日」為共同窗口，但備料第 3 節指出全公司唯一真正緊的資源是 Claude 的**週上限**。

---

### 三、兩稿分歧處：Argon 的裁決與理由

| 分歧點 | fable 主張 | astra 主張 | Argon 站哪邊與理由 |
| :--- | :--- | :--- | :--- |
| **1. 部門樹是記帳樹還是路由樹** | **記帳樹**：信直寄供應站，按表查部門歸屬 | **路由樹**：每部門一顆 `llm_forward` 站串起來 | **站 fable**。記帳樹零轉發成本、改組免改 `AOS_LLM_KERNEL`，且讓所有請求在同一個供應站排隊，全域 priority 與 slots 才準確。`llm_forward` 只留給跨機或硬隔離。 |
| **2. 超賣 vs 嚴格切塊** | **允許上限（cap）超賣**：父格圈子孫，只鎖死保底（guarantee） | **嚴格切塊＋候補池**：子額度加總 ≤ 父額度，追加靠人工撥候補 | **站 fable**。同 cgroup 原理：保底留住就不怕餓死，沒用完的額度天然由先到的兄弟借用，利用率最高，省去主管天天人工搬候補池。 |
| **3. 超出天花板：夾值 vs 拒絕** | **夾值（clamp）**：子 priority 超出父就夾到父級，記 `clamped` | **拒絕（refuse）**：申請超出天花板直接回絕，不靜默夾小 | **分期處理（融合）**：<br>• **設定期（改配額表／申請單）站 astra（拒絕）**：保底超額或越權申請必須明確拒絕（`PlanBad`），不能偷夾小讓主管誤判。<br>• **執行期（問腦信 priority）站 fable（夾值）**：信件自填過高 priority 直接夾到部門上限並記 `priority_clamped`，不因填錯 priority 而中斷工作。 |
| **4. 未知（沒列名）sender** | 落入 `default` 給小額度，報表列 `unmatched` | 在政策檢查處直接拒絕 | **站 fable**。活樹常動態生出新 subagent，直接拒絕會讓新線一開就卡死；落入全站共用的小 `default` 池並亮 `unmatched` 告警最穩健。 |
| **5. Claude（eca）怎麼面對** | 外部電表抄本機對話紀錄（b）＋派工閘與回合閘（c） | 節點標三態 `enforced / observed / unknown`，先接人工回報總量 | **融合兩者**：採 astra 的**三態標記**（誠實區分硬控與觀測、不假造分攤），但實作採 fable 的**本機 log 外部電表＋派工閘**（不靠人工填，也不改 eca 身體）。 |

---

## (B) 提案：設計修正與「最小可用第一版」

### 一、Argon 認為該加入或改掉的設計點

1. **架構微調：把「扣帳與放行檢查」放進站內（或站內 hook），拿掉站外分配器的 N 秒時差**
   - 為什麼 fable 會有在飛漏算、拿不到 `waiting` / `refused`、以及 N 秒延遲的問題？因為它把「算帳跟判放行」放在站外定期跑的腳本，再寫 `gate.json` 給站讀。
   - 事實上，現有 `kernel_llm` 本來就是每 300ms 跑一輪的 Python 程序，手握即時的 `requests/` 隊列、在飛清單與 `used.json`！
   - **正確分工**：
     - **站內（小改 `kernel_llm` 預算模組約 50 行，或透過擴充後的 `before_verdict` hook）**：站直接按 mtime 熱載入 `plan.json`。每封信進來時，站當場做三件事：① 用 `sender` 匹配部門（含萬用字元，沒中落 `default`）；② 填入部門預設 `priority` 並夾在部門最高級內；③ 把「站內已用 `used` ＋ 站內在飛 `in_flight`」代入部門樹公式，算祖先鏈是否放行。被擋的信直接計入站內 `refused` 統計。**零時差、不漏在飛、不需第二套 daemon 跑熱迴圈。**
     - **站外工具（`aos-llm-quota`）**：只負責兩件事——① **改表與驗表**（處理董事長 `power` 單、主管重分配、檢查保底不超標）；② **跨站與外部報表**（合併各站帳本＋Claude 外部電表，產出 `report.json` 與 `daily/` 結算）。
2. **修補三層樹以上的「有效保底（Effective Guarantee）」驗表規則**
   - 為防止孫部門的保底被上層旁系吃掉，在 `aos-llm-quota check` 驗表時加入一條硬規則：任何節點 $A$ 的有效保底為 $\text{eff\_g}(A) = \max\big(\text{guarantee}(A), \sum_{c \in \text{children}(A)} \text{eff\_g}(c)\big)$，且所有直接子節點的 $\sum \text{eff\_g}(c)$ 必須 $\le \text{cap}(A)$。放行公式統一扣減兄弟節點的 $\text{eff\_g}(d)$，三層以上的樹就絕對嚴密。
3. **加入「主管 본인（`self`）救援保底」，防死鎖**
   - 採納 fable 10.5 點出的風險：若子 agent 把部門 `cap` 燒光並寄出 `BLOCKED` 通知給主管（`AOS_NOTIFY_BOX`），主管本人若共用同一個滿載的池，會連起來處理危機、發申請單的 1 次問腦額度都沒有。因此規定：有子節點的部門主管，可設定 `self_reserve: {"calls": 5}`（專門留給節點本人 sender、子孫不能借用的小保底）。
4. **砍掉不切實際的複雜度（減法清單）**
   - **砍掉「點數（points）」換算**：第一版配額只管硬 `calls`（以及選填的昂貴 pack 如 `astra-high` 呼叫上限）；報表照實列出 `calls`、`tokens (in/out/cached)`、`elapsed_ms`。
   - **砍掉 `power` 單的自然語言解析**：`power` 單只收結構化欄位（或明確固定格式），不合法直接退單，不叫 LLM 猜。
   - **第一版不開自動降級（`fallback`）**：換模型涉及 context 長度與能力落差，第一版只留欄位契約，不自動偷換端點。
5. **Claude 盲區採「本機 JSONL 電表 ＋ 派工閘」**
   - Claude Code（eca）每次對話都會在本機 `~/.claude/projects/` 下寫入含 usage 與 cwd/session 的紀錄。寫一支唯讀 parser 對齊工作目錄與 agent 名稱，就能算出各部門的 `observed` 用量；加上 `calibrations.jsonl`（人工輸入看到的 `/usage` 週百分比）即可校準。
   - 要管住 Claude 時，不攔每次問腦，而是攔 **`kernel_gate` / 派工（開新 Claude proc 或 `hire` 單）**——當該部門的 Claude 週配額亮紅燈時，禁止再派生新的 Claude 子 agent。

---

### 二、「最小可用第一版（MVP）」切法

在 repo 外獨立暫存樹實施，用 fake 端點與複製出來的活樹 `ledger.jsonl` 驗收，分四個小零件：

1. **`plan.json` 與驗表工具（`aos-llm-quota check`）**
   - 支援無限層 `tree`、`match`（前綴／萬用字元）、`priority`（low/normal/high）、`guarantee`、`cap`、`self_reserve`、`default`（未知 sender 共用小額度）、`control_mode`（`enforced / observed / unknown`）。
   - 驗表：檢查無循環、子 priority 不高於父、遞迴有效保底 $\sum \text{eff\_g} \le \text{cap}$，違反回 `PlanBad`。
2. **站內樹狀配額與優先級執行（在暫存樹擴充 `kernel_llm`）**
   - 站熱讀 `plan.json`。
   - 信件進入時：匹配 sender 部門（未命中歸 `default`）→ 自動補上或夾值 `priority`（記 `priority_clamped`）→ 用「站內當窗 `used` + 在飛 `in_flight`」沿祖先鏈檢查可用量。
   - 超額回 `BudgetMissing`（觸發既有 AK17 冷卻與 `brain_notify`），並在站狀態記下該部門 `refused` 次數。
3. **正式報表指令（`aos-llm-quota report --json`）**
   - 讀取站的 `used.json`、`ledger.jsonl`（按 `(station, id)` 去重、統計壞行）與當前隊列，輸出全景所需的正式 JSON：各池總覽、各部門 `self` 與 `rollup`（calls / tokens / elapsed_ms / waiting / refused / state）、`control_mode`（Claude 池在 MVP 標為 `unknown`、顯示 `not recorded`）與 `unmatched` 清單。
4. **MVP 驗收四劇本**
   - **劇本 1（保底與超賣）**：父 cap 10，子 A（guarantee 4, cap 8）、子 B（guarantee 0, cap 8）。B 連打 6 次放行，第 7 次因「保護 A 的保底 4」被拒（`BudgetMissing`）；隨後 A 打 4 次皆放行。
   - **劇本 2（在飛不漏算）**：父 cap 2，同時送入 3 封慢請求（在飛尚未寫入 ledger），第 3 封當場被擋，證明不會因 ledger 未收尾而超發。
   - **劇本 3（未知 sender 與 priority 夾值）**：未列名 sender 打超過 `default` 小額度被擋並列入 `unmatched`；low 部門自填 high 被夾為 low。
   - **劇本 4（活樹歷史帳試算）**：把活樹 `llm-gpt` 的 `ledger.jsonl` 複本餵給 `report`，跑出真實的部門 `self / rollup` 用量表。

*(註：接全景 `power` 單自動改表、以及 Claude 本機 log 外部電表，緊接著放在第二版做。)*

---

## 請使用者拍板的方向題（6 題）

1. **架構路線（記帳樹 vs 路由樹）**：是否確定採用「單一供應站＋配額記帳樹」（部門只是一張查表規則，不為每個部門開一個 `llm_forward` 站 proc）？
2. **站內即時扣帳 vs 站外定期寫檔**：是否同意直接在 `kernel_llm` 站內加幾十行樹狀查表邏輯（直接讀 `plan.json` 並結合在飛請求即時判放行），而不是在站外另跑一支每 N 秒同步一次檔案的 daemon？
3. **超賣＋保底 vs 嚴格切塊＋候補池**：子部門的「上限（cap）」加總可否超過父部門（沒人用的額度先到先用，但別人未用的「保底 guarantee」鎖死不准碰），還是要嚴格切塊、多出來的放候補池由人手動撥？
4. **Claude（eca）盲區的處理深度**：
   - **(a)** 完全不管，報表永遠寫 `not recorded`；
   - **(b)** 只觀測：寫外部電表讀本機 Claude 紀錄＋人工校準週百分比，算進部門報表；
   - **(c)** 觀測＋派工閘：在 (b) 之上，當部門 Claude 額度超標時，攔截新開 Claude 子 agent 的派工／`hire` 單。
5. **自動降級（換便宜模型）與「點數換算」**：第一版是否同意**不做**自動換便宜模型（避免偷換模型影響品質）、也**不發明**虛擬「點數」，單純以 `calls`（外加可限制特定貴 pack 的次數）來管配額？
6. **調整權限下放**：除了董事長（全景 `power` 單）能改全表之外，各部門主管（如 `ok-release` 主管）能否在「自己部門的 cap 與 priority 範圍內」自行調整底下子節點的配額？
