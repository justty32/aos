# 02 fable 稿：llm kernel 上一層＝「配額帳樹＋一支分配程序」，不是再疊一排站

← [llmk2-1114](../llmk2-1114.md)｜事實依據：[01 備料](01-備料.md)（細節 01a／01b／01c）｜本稿只規劃、不施工；標「需核」的是我沒有實作依據、要 opus 深化時查的點。

## 0. 先講結論

1. **比喻改成「配給制」**（形狀像 cgroup：保底、上限、優先級、父格圈住子孫），頁面上照舊叫「電力」沒關係。電力比喻最不貼的一點：電是用多少付多少、供應幾乎無限；我們的 llm 是**吃到飽訂閱＋硬上限**（Claude 週上限），稀缺的是「這一窗還剩多少」，不是價錢。
2. **這一層不是新的 kernel 類型，也不是每個部門一個站**。它是三樣東西：一份**配額表**（`plan.json`，部門樹＋每個部門的優先級／保底／上限）、一支**不經模型的固定程序**（分配器，讀各站 ledger 算帳、產出報表與放行表）、站上一個**很笨的 hook**（照放行表蓋優先級、擋超額）。現有 llm kernel 站繼續當「供應端」：管 slots、排隊、打端點、記 ledger。
3. **部門樹是記帳的樹，不是路由的樹**。agent 的信照舊直接寄到供應站；它屬於哪個部門由配額表查。這樣才對得上全景說的「組織歸屬 ≠ 請求路由」，改組也不用重接每隻 agent 的 `AOS_LLM_KERNEL`。
4. **最該誠實講的事**：現在經過 llm kernel 的只有 gpt 系，而 gpt 方案是「不用省」的；真正緊的 Claude 完全不經過。所以這一層第一階段的實際價值是 (a) 看得到誰燒多少、(b) 三個 slot 不夠搶時誰先，(c) 把 Claude 用量**量進同一本帳**。「管住 Claude」要另外的閘（第 7 節），是方向題。
5. **第一版只做「帳」**：配額表＋報表程序＋把表編成現有 `budget.senders` 的靜態上限，在 repo 外暫存樹用 fake 端點驗。不改 kernel 程式、不碰活樹。

## 1. 比喻：四種模型比一比

| 模型 | 核心想法 | 貼合的地方 | 不貼合的地方 |
|---|---|---|---|
| 電力／公用事業 | 基礎設施、抄表、跳電、限電 | 「llm 是基礎設施」「各部門有電表」「缺電時分級限電」很直覺 | 電按量計價、供應近乎無限；電沒有「品質等級」（模型有貴有便宜、能力不同）；電不能「換便宜的電」；電沒有週上限 |
| 預算制（財務部） | 每期撥款、花完再申請 | 「額度」「申請追加」「期末歸零」都對得上 | 預算管的是存量，不管**同時幾個人在用**（slots）；也不管誰先誰後 |
| 內部市場（競標） | 各部門拿點數出價搶 | 理論上最有效率 | 出價這件事本身要問腦、會燒額度；agent 會學著喊高價；使用者想自己拍板優先序，不是讓市場決定；除錯困難 |
| 配給＋排程（作業系統／cgroup） | 保底、上限、權重、父格圈子孫；排程器決定誰先跑 | 我們的資源同時是**流量**（slots，同時幾封）與**存量**（一窗多少次／token）；限制線（01 第 5 節）已經是這個形狀 | 太工程味，董事長不會想看「cgroup」三個字 |

**選擇：機制用「配給＋排程」，帳的語言用「預算」，門面沿用「電力」。**理由：

- 稀缺的本質是**硬上限下的分配**（配給），不是價格。
- 現有零件就是這個形狀：priority＋aging＋reserved 是排程，budget 三份帳是存量，limits 的 default／by_sender／max 是「預設／按人／天花板」。照它長，新東西最少。
- 市場模型先不要：01 第 7 節的「競標」留作以後的實驗，不進主線。
- 「電力」當門面名字留著：全景已經有 `power` 單與「電力」卡，改名沒有好處。只要記得三個不貼合處：**有品質等級、有週上限、不按量計價**。

以下「電力部門」＝接 `power` 單的那個信箱；「配額層」＝這一整層。

## 2. 這一層是什麼

### 2.1 四個候選實體

| 候選 | 做法 | 判斷 |
|---|---|---|
| A 新 kernel 類型 | 另寫一種站 | 不要。現有站加 hook 就夠，多一種型別多一份維護 |
| B 每部門一站，用 `llm_forward` 串 | 部門樹＝站的樹 | **不當主幹**。每層多一個 300 ms 的 looping proc 與一次轉信；下一站只看得到「上一站」這個整體；改組要重接；有的部門根本沒有 kernel。只在**真的要隔離**時用（見第 4 節） |
| C 一隻 agent 來分 | 模型判斷誰該得多少 | 不放在熱路徑。分電這件事自己不該耗電，也不該因為模型一次誤判就停掉全公司。agent 只負責**接單與提議** |
| D 規則＋固定程序 | 一份表、一支程序、一個 hook | **選這個** |

### 2.2 零件與分工

```
董事長（全景 power 單）──信──▶ 電力部門信箱（接單：先固定程序，看不懂才轉 agent）
                                      │ 改
                                      ▼
                                 plan.json（配額表，唯一真相）
                                      │ 讀
各供應站 ledger.jsonl ──讀──▶ 分配器 aos-llm-quota（固定程序，每 N 秒一輪）
Claude 用量來源（第 7 節）──讀──▶      │ 寫
                                      ├─▶ report.json（給全景、給人看）
                                      ├─▶ gate.json（給站上 hook：每個 sender 的優先級／放行／降級）
                                      └─▶ daily/2026-11-14.json（每日結算，留存）
agent ──照舊寄信──▶ 供應站（llm-gpt…）──before_verdict hook 查 gate.json──▶ 排隊／放行／拒
```

| 誰 | 管什麼 | 不管什麼 |
|---|---|---|
| 供應站（現有 llm kernel） | slots、排隊次序、打端點、ledger、站總量與 pack 上限 | 不知道部門、不做跨站加總 |
| 分配器（新，固定程序） | 部門歸屬、樹狀加總、保底與上限的判定、報表 | 不碰請求本身、不排隊 |
| hook（新，很薄） | 查 `gate.json`：蓋優先級、該拒的拒、該降級的換 pack | 不算帳、不讀 ledger |
| 電力部門信箱 | 接 `power` 單、改 `plan.json`、回信 | 不自己決定分配（只執行與提議） |

熱路徑上只有「查一個小檔」。分配器掛了，站照舊能跑（見第 10 節 fail-open）。

### 2.3 為什麼現有的不夠（新東西各自的理由）

| 新東西 | 現有的為什麼不夠 |
|---|---|
| `plan.json` 的樹 | budget 只有「站／pack／sender」三份平的帳，沒有父子加總、沒有保底 |
| sender → 部門的對照 | sender 是 stack 路徑，活樹的 `senders` 還是舊名；沒列名的 sender 沒有預設額度 |
| 分配器自己從 ledger 算帳 | 站的 `window` 只有 hour／day／all 且 pack 與 sender 共用；Claude 要**週**窗；跨站加總站自己做不到 |
| `gate.json`＋hook 蓋優先級 | priority 現在由寄信者自填、沒人填、也沒權限檢查 |
| `report.json` | 全景只走正式介面，目前沒有任何「部門用量」的讀取介面 |

**重用清單**：站總量與 pack 上限（最後一道防線）、`budget.senders`（第一版直接用）、priority 三級＋aging＋`reserved.high`、ledger 與 `child` 串帳、`spent: refuse／wait`、BudgetMissing 冷卻（AK17）、`brain_notify`、`llm_forward`、limits 的 default／by_sender／max 形狀。

**需核**：(1) `before_verdict` hook 除了改 body（01a 有寫），能不能直接判拒與改 `endpoint`；不能的話要給站加一個小口「hook 可回 verdict」，或退回「分配器定期改寫 `budget.senders`」。(2) 站會不會熱讀 `kernel.json`。

## 3. 優先級、需求、額度

### 3.1 配額表的形狀

```json
{
  "schema": "llm-quota-plan/1",
  "rev": 12,
  "pools": {
    "gpt":    {"stations": ["kernels/llm-gpt"], "window": "day",  "metering": "metered"},
    "claude": {"stations": [],                  "window": "week", "metering": "estimated"}
  },
  "rates": {"sol-high": 1, "astra-high": 3, "terra": 0.3, "fake": 0},
  "default": {"priority": "normal", "pools": {"gpt": {"cap": {"calls": 50}}}},
  "max":     {"priority": "high"},
  "tree": {
    "id": "company",
    "pools": {"gpt": {"cap": {"calls": 1500}}},
    "children": [
      {
        "id": "ok-release",
        "match": ["procs/ok-release", "procs/ok-release-*"],
        "priority": "high",
        "pools": {"gpt": {"guarantee": {"calls": 400}, "cap": {"calls": 900},
                          "soft_pct": 80, "fallback": {"astra-high": "sol-high"}}},
        "children": [
          {"id": "ok-release-sol-1", "pools": {"gpt": {"cap": {"calls": 300}}}}
        ]
      },
      {"id": "ok-llmk2", "match": ["procs/ok-llmk2*"], "priority": "low",
       "pools": {"gpt": {"cap": {"calls": 300}}}}
    ]
  }
}
```

- **pool（供應池）**：一個訂閱／一個真實上限一個池。Claude 與 GPT 不能互換，所以額度**按池分**，不混成一個數。
- **priority**：部門的級，三級沿用 low／normal／high。意思是「這個部門的信預設用這級、最高也只能這級」。子部門不能比父部門高（超過就夾到父的級，記 `priority_clamped`，同 limits 的夾值做法）。
- **guarantee（保底）**：別人再怎麼搶，這個量留給你。
- **cap（上限）**：你與你所有後代加起來最多這麼多。
- **default／max**：沒列名的 sender 落到 `default`（小額度，不是無限）；`max` 是全表天花板。直接借 limits 的形狀。
- **match**：哪些 sender 屬於這個節點（stack 路徑的前綴／萬用字元）；沒寫就用 `id` 當前綴。多個節點都符合取最深的。

### 3.2 放行判準（一條式子）

一封信從部門 X 來，往上每一層祖先 A 都要過：

```
A 的可用量（給 X 這一支用）＝ cap(A) − used(A) − Σ 其他孩子 d 的 max(0, guarantee(d) − used(d))
```

可用量 > 0 才放行。白話：**父格圈住所有子孫；兄弟還沒用到的保底要先扣下來留著。**

- 子部門 `cap` 加總**可以**超過父（超賣，平常大家用不滿；真的滿了由父格擋）。
- 子部門 `guarantee` 加總**不可以**超過父的 cap，否則保底是空話，驗表時直接拒（`PlanBad`）。
- 「借用」不必另做：沒人用的額度本來就誰先到誰用，只有保底被保護。

### 3.3 需求怎麼表示

**需求以量到的為主、申報為輔。**

- 量到的：每個部門每窗的 `used`、`refused`（被拒幾次）、`waiting`（排隊中）、`wait_ms`（等了多久）。「用了多少＋被擋多少」就是真實需求，不用誰來填表。
- 申報的：部門主管寄一封申請信給電力部門信箱（跟董事長的 `power` 單同形狀，`from` 不同），寫要多少、為什麼。電力部門**不自動批**，整理後轉董事長，或在主管自己權限內直接生效（3.5）。

### 3.4 不夠的時候：四段，順序固定

| 段 | 觸發 | 動作 | 用的零件 |
|---|---|---|---|
| 1 排隊 | slots 滿 | 照部門級排；`reserved.high` 留格給 high 部門；low 靠 aging 慢慢升，不會餓死 | 現有 |
| 2 降級 | 部門用到 `soft_pct`（預設 80%）**且**該部門有寫 `fallback` | 之後的信改掛便宜 pack（例 astra-high → sol-high），ledger 記 `switched` | hook 改 `endpoint`（需核） |
| 3 拒絕 | 祖先鏈任何一層可用量 ≤ 0 | 回 BudgetMissing；agent 冷卻重試（AK17）；`brain_notify` 寄 BLOCKED 給主管 | 現有 |
| 4 通報 | 部門進入拒絕段 | 分配器寄**一封**通報給電力部門信箱（每部門每窗一次）；報表亮紅 | 新（很小） |

- **降級預設關**：換模型會改品質，沒寫 `fallback` 的部門不會被偷換。
- **high 部門不享「無上限」**：high 只是先排、有保留格，仍受 cap。要破例由董事長下單調 cap。
- `spent: wait`（留在隊裡不拒）只建議用在站總量；部門層一律 refuse，因為 agent 的冷卻重試比卡在隊裡看得見。

### 3.5 誰有權調

| 誰 | 能做什麼 |
|---|---|
| 董事長 | 任何節點的任何欄位（`power` 單或直接改檔） |
| 部門主管 | **只在自己的 cap 之內**重新分給自己的子部門（改自己子樹的 guarantee／cap／priority，priority 不能高過自己） |
| 電力部門（程序與 agent） | 執行上面兩者的單；只**提議**調整（例如「A 連三天用不到三成，B 天天被擋」），不自己動 |
| 一般 agent | 只能申請 |

每次改動寫一行 `changes.jsonl`（誰、何時、哪張單、改前改後、`rev`），可回退。寫檔權限靠檔案擁有者，同現況「實際限制依檔案與信箱權限」。

## 4. 嵌套

- **層數不限**：`plan.json` 的 `children` 可以一直往下；放行判準沿祖先鏈逐層檢查。
- **對上全景的部門樹**：節點 `id` 用跟全景**同一套 id**，報表才能直接貼到全景節點上；報表也分 `self`（本人）與 `rollup`（含所有後代），跟全景同形。
- **部門樹的來源**：建議配額表自己寫 `match`（自成一體、可單獨驗），不去吃全景推出來的父子關係。全景的父子是四段推論（`config.parents` → subagent 紀錄 → 前綴 → `parent_rules`），拿推論結果當扣帳依據不穩。兩邊不一致時，報表列 `unmatched`，由人修表。
- **對上 kernel 樹（什麼時候才真的串站）**：只有需要**實體隔離**時才用 `llm_forward` 多一站：另一台機器、另一個 daemon、不信任的外包部門、或部門要自己管 slots。這時：
  - 下游站看到的 sender 是「上游站」——在配額表裡就把這個 sender 掛在該部門節點上，下游只管「這個部門總共多少」；
  - 部門內部怎麼分，由上游站旁邊自己的 `plan.json` 管（它的根 cap ≤ 上層給它的 cap）；
  - 也就是**同一棵樹可以在某個節點「切出去」交給另一站執行**。帳靠 ledger 的 `child` 串，分配器加總時按 `child` 去重，不重算。
- **不建議**為了「看起來像公司」而每部門一站。記帳的樹免費，路由的樹每層都有成本。

## 5. 董事長怎麼看、怎麼調

### 5.1 看：正式讀取介面

分配器每輪寫 `report.json`，並提供指令 `aos-llm-quota report [--node ID] [--json]`（全景只叫這支，不翻 stack）：

```json
{
  "schema": "llm-quota-report/1",
  "as_of": "2026-11-14T12:00:05+08:00",
  "plan_rev": 12,
  "stale": false,
  "pools": {"gpt": {"metering": "metered", "window": "day", "used_pct": 37},
            "claude": {"metering": "not recorded"}},
  "nodes": {
    "ok-release": {
      "parent": "company", "priority": "high",
      "pools": {"gpt": {
        "self":   {"calls": 12,  "tokens": 310000,  "points": 310},
        "rollup": {"calls": 371, "tokens": 9400000, "points": 11200,
                   "refused": 3, "waiting": 1, "elapsed_ms": 5400000},
        "guarantee": {"calls": 400}, "cap": {"calls": 900},
        "used_pct": 41, "state": "ok",
        "by_model": {"sol-high": {"calls": 350}, "astra-high": {"calls": 21}}
      }}
    }
  },
  "unmatched": ["procs/gpt-lead2"]
}
```

- `state`：`ok`／`soft`（過 soft_pct）／`hard`（被擋中）。
- `metering`：`metered`（站 ledger，準）／`estimated`（事後估）／`not recorded`。**沒量到就老實寫 not recorded**，跟全景現在的約定一致。
- 「電力」卡顯示：各池這一窗用了幾成、各部門 `rollup` 用量條（對 cap）、被擋次數、紅黃綠。

### 5.2 調：`power` 單

全景現有欄位夠用，只要約定讀法。信體 `order`：

```json
{"kind": "power", "target": "ok-release", "priority": "高",
 "quota": "gpt cap 1200 calls/day", "what": "release 這兩天要衝"}
```

- `priority`：認「高／中／低／high／normal／low」，空＝不變，其他字＝回信問。
- `quota` 的寫法（一行，可多項用分號）：`[池] cap|保底 數字 calls|tokens|點 [/day|/week]`、`+20%`／`-20%`（對 cap）。空＝不變。
- 看得懂 → 固定程序直接改 `plan.json`、回一封信帶 `applied: {before, after, plan_rev}`。看不懂或驗表不過（例如保底加總超過父）→ 轉給接單 agent（沒設就 `repo-aos`）解讀後**回信列出打算怎麼改**，董事長回一句才生效。
- 董事長的單就是授權，不再走 gate；但改完一定回信講改了什麼，可用 `rev` 回退。

### 5.3 需要全景補的

1. 「電力」卡與部門卡改讀 `aos-llm-quota report --json`（或全景後端包一個 `GET /api/power`）；節點多一格 `power`。
2. `power` 單的 `priority` 改成下拉（高／中／低／不變）；`quota` 拆成結構欄：池、種類（上限／保底）、數字、單位、窗。自由文字留在 `what`。
3. `power` 接單者設定指到電力部門信箱。
4. 報表 `stale: true`（分配器超過幾輪沒更新）時卡片要標「資料舊了」。

## 6. 成本與觀測

- **原生單位：次數、token（in／out／cached 分開記）、秒**。這三個是 ledger 真的有的。
- **換算單位：點**。`點 ＝ total_tokens ÷ 1000 × rates[pack]`，`rates` 先照已知的相對說法填（sol＝1、astra＝3），用來讓「不同模型」可以放在同一條額度裡比。它不是錢。
- **錢：只當參考欄**。訂閱是月費吃到飽，沒有每 token 單價；LiteLLM 也沒有這些模型的價目。要的話之後加一欄「若按公開 API 價約多少」，只供感覺，不拿來扣帳。
- **Claude 池的真單位是「週額度的百分比」**。這個數沒有換算公式（01b），只能靠校正：有人看到 `/usage` 的百分比時記一筆 `calibrations.jsonl`（時間、百分比），分配器用它反推「這一週每 1% 約等於多少點」。
- **每日結算**：`daily/<日期>.json`＝當天各部門、各模型的 calls／tokens／點／秒／被拒次數，**寫當時的部門歸屬**（改組後歷史不漂）。「一天燒多少、誰燒的」就讀這個。
- **讀 ledger 的紀律**：按 `id` 去重、壞行跳過並計數（寫進報表 `ledger_bad_lines`）、記讀到哪個位移，不每輪從頭掃。ledger 不輪替是既有問題，分配器只讀不動。

## 7. 盲區：Claude（eca）不經 llm kernel

**判斷：這是本題最重要的一塊。不面對它，這一層管的是不缺的資源、看不到缺的資源。**但也不該為了管它就改掉 eca 的走法。分四個選項：

| 選項 | 做法 | 好處 | 代價／風險 |
|---|---|---|---|
| a 不管 | Claude 池永遠 `not recorded` | 零工作 | 這一層對最緊的資源沒用 |
| b 只量不管 | 寫一支「外部電表」：從 Claude Code 本機的對話紀錄（每則回覆帶 usage）事後抄成跟 ledger 同形的行，按工作目錄／session 對到 agent 與部門；`metering: estimated` | 馬上看得到「哪條線吃掉本週幾成」；不改任何 agent 的走法 | 來源格式不是正式介面、會變（**需核**：紀錄位置、欄位、能否對到 agent；`.claude-alt` 是另一個池）；對不準真實百分比，要靠校正 |
| c 量＋軟管 | b 之上加兩道閘：**派工閘**（開新 Claude agent／`hire` 單時先查該部門 Claude 池，超了就拒或改派 gpt）；**回合閘**（eca 身的 hook 在每回合開始查 `gate.json`，超了就要它寫 HANDOFF 停手） | 把現在「99% 時各線暫停寫 HANDOFF」的人工規矩自動化，而且**分部門**停，不是全公司一起停 | 粒度是回合不是每次呼叫，會超一點；要動 eca 的設定（需使用者點頭） |
| d 改道 | Claude 也經 LiteLLM → llm kernel（agent-fsm 身接 claude-*） | 跟 gpt 完全同一套 | 失去 Claude Code 的整套身體；訂閱憑證這樣用穩不穩、合不合用法未知；工程最大 |

**建議：先 b，再 c，d 不做。**b 能立刻回答使用者「誰燒的」；c 的派工閘很便宜（在開 agent 那一刻擋，一次擋掉幾百次呼叫），而且對 Claude 這種「一開就燒很多」的身體，**在派工時管比在每次呼叫時管更有效**。順帶：fable 最貴，`rates` 裡給它高倍率、部門預設 cap 為 0（要董事長或主管明給），就把「fable 少用」變成表上的一格。

Argon（Gemini）、Codex CLI 同理：先 `not recorded`，有來源再接電表。

## 8. 第一版切在哪

**第一版＝「看得到＋靜態上限」，不動 kernel 程式、不動活樹。**

範圍（全在 repo 外暫存樹，fake 端點）：

1. `plan.json` 格式與驗表（`aos-llm-quota check`）：樹、`match`、保底加總、priority 夾值。
2. `aos-llm-quota report`：讀一到多個站的 `ledger.jsonl`（去重、位移）→ `report.json`（self／rollup、by_model、refused 先留空欄）＋`daily/`。
3. `aos-llm-quota compile`：把表編成一段可貼進站 `kernel.json` 的 `budget.senders`（每個 sender 取「自己到根的最小 cap」）＋一份「沒列名 sender」清單。**只產出檔，不自己寫進站**。
4. 驗收劇本：暫存樹起一站＋兩個部門、三隻 fake agent；部門 A 設小 cap，看到 A 被 BudgetMissing 擋、B 照跑；`report` 的 rollup 與 ledger 手算對得上；把活樹 llm-gpt 的 ledger **複製一份**餵進去，出一張真的「昨天誰燒多少」。

第一版**明講做不到**：父格圈子孫（靜態 sender 上限只能近似）、保底、蓋優先級、降級、Claude。

之後幾步（每步獨立可停）：

| 步 | 內容 | 需要 |
|---|---|---|
| 2 | 站上 hook＋`gate.json`：父格、保底、蓋部門優先級、`default` 額度 | 核 `before_verdict` 能力；agent-fsm 不必改（優先級由站蓋） |
| 3 | 接 `power` 單（固定程序＋agent 兜底）、全景讀報表 | 全景補 5.3 |
| 4 | Claude 外部電表（選項 b）＋校正 | 先派蒐集核來源 |
| 5 | 派工閘／回合閘（選項 c）、降級 `fallback` | 動 gate 與 eca 設定，使用者點頭 |
| 6 | 切出去給子站（forward）與跨機 | 有第二台機器的需求時 |

換上活樹（改 llm-gpt 的 `senders` 舊名、掛 hook）是另一張單，要使用者放行。

## 9. 要使用者拍板的方向題

| # | 題目 | 選項與後果 | 我的建議 |
|---|---|---|---|
| 1 | 比喻與名字 | (a) 機制用配給制、頁面仍叫「電力」；(b) 連名字一起改（例「配給處」）；(c) 堅持純電力模型（按量、無保底） | a。判準：全景已有 power 單，改名只有成本 |
| 2 | 實體 | (a) 一份表＋固定程序＋站上 hook；(b) 每部門一個 llm kernel 站串起來；(c) 一隻 agent 管 | a。b 每層多一個常駐 proc 與一次轉信，只在要隔離時用 |
| 3 | Claude 盲區 | 第 7 節 a／b／c／d | 先 b 再 c。判準：如果「Claude 來源抄不到、對不到 agent」，退回 a 並在卡片寫 not recorded |
| 4 | 單位 | (a) 次數＋token 為準、另算「點」；(b) 只用次數；(c) 換算成錢 | a。c 沒有價目可依 |
| 5 | 超賣 | (a) 子部門上限加總可超過父、保底不可；(b) 一律不可超過（嚴格切塊） | a。b 會讓沒用完的額度閒置 |
| 6 | 自動降級 | (a) 預設關、部門自己寫 `fallback` 才開；(b) 預設開；(c) 永不做 | a。換模型會改品質，不該偷換 |
| 7 | 誰能調 | (a) 只有董事長；(b) 主管可在自己額度內往下分；(c) 電力部門 agent 可自動調 | b，c 只提議。判準：部門超過三層時 a 會讓董事長每天批單 |
| 8 | 部門歸屬來源 | (a) 配額表自己寫 `match`；(b) 直接吃全景的樹 | a。b 省一份表，但推論錯就扣錯帳 |
| 9 | 分配器掛掉時 | (a) 照最後一份放行表繼續、報表標 stale；(b) 全部擋 | a。基礎設施壞了不該讓全公司停工；站總量與 pack 上限還在 |
| 10 | 沒列名的 sender | (a) 給小額度 `default`；(b) 直接拒；(c) 不限（現況） | a（例如每天 50 次），並列在報表 `unmatched` |

## 10. 最大風險與邊緣狀況

1. **管錯對象**：只做完 gpt 那半就停，等於替不缺的資源蓋了一套制度。對策：第 4 步（Claude 電表）排在降級、切站這些之前。
2. **sender 不驗真**：agent 可以冒別人的 stack 路徑寄信，吃別部門額度。配額層不解這題（屬權限系統）；先靠信箱與檔案權限，報表列「同一 sender 來自多個來源」的異常（需核能否看出）。
3. **分配器有時差**：放行表每 N 秒才更新，token 又不預扣，部門會超一點。上界＝一輪內 slots 能跑完的量；用站總量與 pack 上限當最後防線。額度不要設到剛剛好。
4. **優先級通膨**：人人都想當 high。對策：級是部門的不是 agent 的、子不能高過父、`reserved.high` 的格數小於 slots；報表列出 high 部門佔比。注意 aging 升上去的不算 reserved（既有行為）。
5. **卡死鏈**：主管在等子 agent，子 agent 被額度擋，主管自己也沒額度去處理 BLOCKED 信。對策：主管本人（`self`）建議一律給小保底；通報信另寄電力部門。
6. **換窗瞬間一擁而上**：一堆冷卻中的 agent 同時醒來搶 3 個 slot。冷卻序列已經錯開一部分；排隊照部門級，可接受。
7. **forward 鏈上原寄件人不見**：下游只看到上游站。第 4 節用「切子樹」繞過；若將來要在下游看原寄件人，得在轉信時帶 `origin`（且只信上游站帶的），那是站的改動，先不做。
8. **改組與歷史**：部門中途改名／搬家，舊帳算誰的。每日結算寫當時歸屬；當窗內的用量跟著 sender 走到新部門（可能讓新部門一搬來就超），報表註記。
9. **Claude 估計不準**：估的點數與真實週百分比對不上，會誤擋或漏擋。對策：`estimated` 的池**預設只亮燈不擋**，校正幾次、誤差看得下去才開閘。
10. **ledger 越長越大、有壞行**：分配器記位移、去重、計壞行；輪替是站的事，另案。
11. **站不熱讀設定／hook 不能判拒**：兩個「需核」任何一個不成立，第 2 步要加一個小的站改動，工期會多。第一版不受影響。
12. **使用者沒回答的邊緣狀況**：照他的通則，視為比喻的天然差異或實作時自然可解，不追問。
