結論：現有 llm kernel 已有「總額、每個 endpoint pack、每個 sender」三種額度，以及單封信的優先序；也已有多層 llm kernel 轉交機制。**但沒有在本次讀到的實作中找到「部門樹自動繼承額度／優先級」的欄位或連動**。`kernel_gate` 的 proc 管理與 llm kernel 的問腦排程是兩條不同路徑，不能把組織上下層直接當成問腦額度上下層。來源：`proto8/lib/aos/kernel_llm/budget.py:50`、`proto8/lib/aos/kernel_llm/order.py:48`、`proto8/lib/aos/llm_forward/_entry:29`、`/home/lorkhan/aos-home/knowledge/aos/kernel.json#/where_to_send`。

以下 repo 相對路徑皆以 `/home/lorkhan/repo/aos/` 為根；分開標明「repo 實作」與「活樹設定」，不把待換樹的程式視為已部署。

## (a) 行程、收信、挑信與 Pack

**行程與收信**
- repo 現行入口是 Python `lib/aos/kernel_llm/_entry`，把 `llm_rules` 交給通用 `round.run()`；每次只做一輪，不自己常駐等待模型。每封放行的問腦另掛成 daemon 的 `llm_<信名>` proc，下一輪收結果。來源：`proto8/lib/aos/kernel_llm/_entry:76`、`proto8/lib/aos/kernel_llm/README.md:3`。
- 活樹 `llm-gpt` 的 README 說它是 ws daemon 底下的 looping proc；`loop.json` 每 300 ms 呼叫 `$AOS_HOME/lib/aos/kernel_llm`。因此它不必是「獨立一台 daemon」；知識庫所寫「daemon of its own」沒有完整反映這個部署。來源：`/home/lorkhan/aos-home/kernels/llm-gpt/README.md:1`、`/home/lorkhan/aos-home/kernels/llm-gpt/loop.json`、`/home/lorkhan/aos-home/knowledge/aos/kernel.json#/templates`。
- agent 以 `AOS_LLM_KERNEL=<kernel stack>` 指向問腦站，信寄到 `<kernel stack>/requests/`；`aos-llm ask` 同步，或 `send`＋`recv` 非同步。信體為 `{"endpoint":"pack-name","request":{"messages":[...]},"priority":...}`；agent 的 `llm.json.model` 是 pack 名，不是直接傳給供應商的模型名。來源：`/home/lorkhan/aos-home/knowledge/aos/brain.json#/_description`。

**實際欄位與預設**
- 頂層 `slots`：正整數，預設 `1`，計算已掛出去尚未收尾的請求。pack 的 `slots`：選填正整數，沒寫只受總格限制。另可用 `backends.<name>.slots`、`max_packs` 限同後端並行數與同時使用的包數。來源：`proto8/lib/aos/kernel_llm/packs.py:106`、`proto8/lib/aos/kernel_llm/packs.py:173`、`proto8/lib/aos/kernel_llm/slots.py:48`。
- `reserved: {"high": N}`：預設 `0`，必須小於總 `slots`；只按**宣告的 high** 保留，aging 升上去的不算。`aging_cycles`：正整數，預設 `3`。來源：`proto8/lib/aos/kernel_llm/packs.py:182`、`proto8/lib/aos/kernel_llm/llm_rules.py:453`。
- `priority`：省略為 normal；接受 `"low"`、`"normal"`、`"high"`、數字，或 `{"level":"high","deadline":"2026-11-14T10:00:00Z"}`。數字只取正負，映射成 `-1/0/1`，不是任意多級數值；deadline 也可用 epoch 秒。來源：`proto8/lib/aos/kernel_llm/order.py:22`、`proto8/lib/aos/kernel_llm/order.py:48`。
- 排序為：`宣告級數 + waited_cycles // aging_cycles` → deadline 近 → 同後端黏著最後掛的 pack → pack `speed` → 等得久 → 信名先後。`speed` 接受 `fast/normal/slow`，預設 normal；不搶掉已在飛的請求。來源：`proto8/lib/aos/kernel_llm/order.py:128`、`proto8/lib/aos/kernel_llm/order.py:133`、`proto8/lib/aos/kernel_llm/docs/01-用法.md:66`。
- budget 實際結構如下；各上限省略即不限，`window` 預設 day，`spent` 預設 refuse。pack 與 sender 的上限共用頂層 window／spent，不能各自設定。來源：`proto8/lib/aos/kernel_llm/budget.py:50`、`proto8/lib/aos/kernel_llm/packs.py:106`。

```json
{
  "budget": {
    "max_calls": 3000,
    "max_tokens": 2000000,
    "window": "day",
    "spent": "refuse",
    "senders": {
      "/absolute/agent/stack": {
        "max_calls": 100,
        "max_tokens": 200000
      }
    }
  },
  "endpoints": {
    "pack-name": {
      "budget": {
        "max_calls": 500,
        "max_tokens": 1000000
      }
    }
  }
}
```

**活樹目前值**
- 總 `slots=3`、`timeout_ms=600000`、預設 `endpoint="fake"`；沒設總 `max_calls/max_tokens`、`reserved`、`aging_cycles` 或 `backends`。
- day／refuse；sender 上限為 `gpt-lead2=160`、`sol-T03=120`、`sol-T04=120` 次；astra-high 包上限 500 次、sol-high 包上限 1000 次，皆未設 token 上限。來源：`/home/lorkhan/aos-home/kernels/llm-gpt/kernel.json#/slots`、`/home/lorkhan/aos-home/kernels/llm-gpt/kernel.json#/budget`、`/home/lorkhan/aos-home/kernels/llm-gpt/kernel.json#/endpoints`。

一個實際 pack 的全部欄位：

```json
{
  "sol-high": {
    "url": "http://127.0.0.1:4000/v1",
    "model": "chatgpt-gpt-6.1-sol-high",
    "slots": 2,
    "cost": "high",
    "summary": "LiteLLM gpt-6.1 sol, high effort: gpt team worker",
    "budget": {"max_calls": 1000}
  }
}
```

來源：`/home/lorkhan/aos-home/kernels/llm-gpt/kernel.json#/endpoints/sol-high`。其他可選欄位有 `exec`、`fixed`、`speed`、`backend`、`context`；其中 `fixed` 與 pack 的 `model` 不允許請求覆寫。來源：`proto8/lib/aos/kernel_llm/docs/01-用法.md:17`。

## (b) Budget 記帳與超額後行為

- **不是 sender 或 pack 二選一，而是同時記三份**：kernel 總量、`packs.<代號>`、`senders.<寄件人>`。sender 是信封身分；正常 agent 為 `$AOS_STACK`，不是 workspace。用量帳把 sender 轉成相對 kernel stack 的路徑；設定中的相對 sender key 則從 `kernel.json` 所在夾解。來源：`proto8/lib/aos/kernel_llm/budget.py:26`、`proto8/lib/aos/kernel_llm/budget.py:50`、`proto8/lib/aos/kernel_llm/budget.py:208`。
- **單位同時支持次數與 token，不是金額**。token 優先取 `usage.total_tokens`；沒有 total 時取 `prompt_tokens + completion_tokens`。usage 缺漏或不合型別，token 增量為 0，但已執行的呼叫仍算一次。來源：`proto8/lib/aos/kernel_llm/budget.py:246`、`proto8/lib/aos/kernel_llm/budget.py:208`。
- 收尾時才正式記帳；有掛過的 `EndpointFailed/ReplyBad` 也算。未執行即拒的 `BudgetMissing/RequestBad/DeadlineBad` 等不算，第一次掛信就失敗也不算。記帳在 `before_reply` hook 之前。來源：`proto8/lib/aos/kernel_llm/llm_rules.py:238`、`proto8/lib/aos/kernel_llm/docs/02-token-回報與額度.md:46`。
- **BudgetMissing 判準**：下一封啟動前，已完成次數＋在飛數達 `max_calls`，或已完成 token 達 `max_tokens`。先判總額；有總格／保留格可用後再判 pack、sender。token 不預扣，因此可超過在飛請求所花的量。來源：`proto8/lib/aos/kernel_llm/budget.py:229`、`proto8/lib/aos/kernel_llm/llm_rules.py:429`、`proto8/lib/aos/kernel_llm/llm_rules.py:453`。
- `spent="refuse"` 回 `{"error":{"code":"BudgetMissing","msg":"..."}}`；`spent="wait"` 留隊，總額耗盡會停整列，pack／sender 耗盡則其他包／人仍可跑。kernel 不自動降級換包。window 支持 hour/day/all，依本地時間換窗；all 不歸零。來源：`proto8/lib/aos/kernel_llm/llm_rules.py:453`、`proto8/lib/aos/kernel_llm/budget.py:144`。
- **sender 限制不是驗證邊界**：未列名的 sender 沒有專屬上限，仍受總額與 pack 上限；sender 不驗真，沒有「未列名一律 N 次」兜底，也不看 `class`。來源：`proto8/lib/aos/kernel_llm/docs/04-已知限制.md:19`。

**AK17 後的 repo 行為**
- 收到 BudgetMissing，agent-fsm 觸發 `brain_failed(name="BudgetMissing")`，寫 `cooldown.json`，退 10 留在 wait，不停機、不增加 history／observed，之後重寄同一份請求。其他 kernel 錯仍走 BrainFailed。來源：`proto8/templates/agent-fsm/wait.py:428`。
- 冷卻實際序列為 **30 秒、1、2、4、8、15、30 分鐘，之後每 30 分鐘**；不是每一階都嚴格翻倍。成功清冷卻；模型或調整鍵改變導致重組時，也會先清 BudgetMissing 冷卻。來源：`proto8/lib/agent/cooldown.py:21`、`proto8/templates/agent-fsm/wait.py:334`、`proto8/templates/agent-fsm/wait.py:460`。
- `brain_notify` 只負責通知，不加額度、不換 pack、不執行重試：寄 BLOCKED 信到 `AOS_NOTIFY_BOX`，以 `{code, history_lines}` 去重，寄成後記在 hook cell 的 `notified.json`。未設 box 或通知失敗只 warning、退 0。`subagent add` 未明給 box 時，預設父 agent mailbox。來源：`proto8/lib/agent/brain_notify/_entry:60`、`proto8/lib/agent/brain_notify/_entry:75`、`proto8/lib/agent/subagent/_entry:182`。
- 舊定義要另補 hook；紀錄明列 AK17 的 template/lib/knowledge 是換樹項目，**本次沒有核對所有活 agent 是否已套用**。來源：`proto8/thinking/2026-11/14/astra-kernel-1114.md:267`。

## (c) 每次呼叫的 Token／花費紀錄

有兩種逐次觀測與一份累計帳，但未找到內建的金額結算欄位。

| 位置 | 格式與內容 | 來源 |
|---|---|---|
| `<llm kernel stack>/ledger.jsonl` | 每個掛過的請求收尾追加一行 JSON，成功／失敗都記 | `proto8/lib/aos/kernel_llm/ledger.py:9` |
| `<llm kernel stack>/used.json` | 當窗與累計 calls/tokens，另分 packs、senders | `proto8/lib/aos/kernel_llm/budget.py:208` |
| `<agent stack>/observed.jsonl` | think 列包含 letter、endpoint、model、usage、elapsed_ms；BudgetMissing 不寫列 | `proto8/templates/agent-fsm/wait.py:420`、`proto8/lib/observed.py:13` |

ledger 欄位為：

```text
id, endpoint, sender, model, seen_at, mounted_at, finished_at,
elapsed_ms, usage, code, child, switched
```

來源：`proto8/lib/aos/kernel_llm/ledger.py:18`。

- `usage` 保留端點回覆原值，因此可含供應商提供的細分 token；kernel 自己只抽總 token 記額度。`cost="high"` 是 pack 屬性，不是價格或已付金額；HTTP endpoint 輸出只挑 `message/usage/model`。來源：`proto8/lib/aos/kernel_llm/ledger.py:18`、`proto8/lib/aos/kernel_llm/budget.py:246`、`proto8/lib/base/llm_http/_entry:123`。
- ledger 不輪替；可能因中斷有壞行、缺行或重複，讀者要跳過壞行並按 `id` 去重。多層各記 usage，不能直接全加；全鏈加總取沒有 child 的葉子列。來源：`proto8/lib/aos/kernel_llm/docs/02-token-回報與額度.md:28`。
- 完成後請求資料夾會刪除，kernel 不留請求原文；原文應看 agent history。來源：`proto8/lib/aos/kernel_llm/docs/04-已知限制.md:12`。

以上是實作定義的位置；本次未讀取活樹 runtime stack 的 ledger／used，沒有冒稱確認其現有內容。

## (d) Kernel Gate、組織樹與 Llm Kernel

- **gate 管 proc 控制請求**：`AOS_KERNEL` 指 gate mailbox；通用站可做 allowed、max_running、排隊、hold/pass/refuse，以及 limits/users 等處理。gate 是掛在 agent 的 on_clock hook，不是 agent 自己逐封轉寄。來源：`/home/lorkhan/aos-home/knowledge/aos/kernel.json#/gate`、`proto8/lib/aos/kernel/README.md:36`。
- **llm kernel 管問腦**：另一個變數 `AOS_LLM_KERNEL`，管理 endpoint packs、問腦 slots、priority、calls/tokens budget，以及模型回信。兩者共用框架零件，但使用不同規則包。來源：`/home/lorkhan/aos-home/knowledge/aos/kernel.json#/where_to_send`、`proto8/lib/aos/kernel/README.md:5`。
- workflow 記錄的「頂層 → ok-* → sol」是派工／掛載關係：頂層 repo-aos 開 gate，opus eca 掛其下，eca 可再開 gate 掛 sol。**沒有因此自動替 sol 的問腦加上部門額度或 priority**。來源：`wf/workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md:48`、`proto8/templates/agent-fsm/brain.py:194`。
- 兩條路有一個**可配置的交會點**：llm kernel 啟動每次 endpoint proc 時，也會把掛信寄到自己的 `AOS_KERNEL`；未設才直寄 `AOS_DAEMON`。這是 gate 可攔 endpoint proc 的啟動，不是 gate 額度自動轉成 llm budget。來源：`proto8/lib/aos/kernel_llm/llm_rules.py:118`。
- 既有 llm 多層鏈是另外透過 `llm_forward`：pack 指定 `{"kernel":"<下一層 stack>","to":"<下一層 pack>"}`。它傳遞 request／priority，下層把上層 kernel 的 `$AOS_WS` 視為 sender，不冒用原 agent；成功記 child 串帳。來源：`proto8/lib/aos/llm_forward/_entry:29`、`proto8/lib/aos/llm_forward/_entry:67`。
- 11-14 紀錄已有 sol → llm-t1 → llm-gpt 的暫存樹實驗，各 sol 在第一層按 stack 分額度成立；框架線也記錄 Python 版兩層測試通過。這是實驗證據，不代表目前所有 ok-* 都已走這條鏈。來源：`proto8/thinking/2026-11/14/astra-kernel-1114.md:5`、`proto8/thinking/2026-11/14/kernel-framework-1114.md:123`。

## (e) Priority 怎麼定、誰能改、能否嵌套

- **宣告值由寄件信決定**，不是按 sender、部門或父 agent 自動算；數值再大也只映射 high。沒有找到內建的部門權重表或 priority 權限檢查。來源：`proto8/lib/aos/kernel_llm/order.py:22`、`proto8/lib/aos/kernel_llm/llm_rules.py:356`。
- stock agent-fsm 的 `brain.py` 只組 request 與 endpoint，沒有寫 priority；`llm_settings.py` 只接受 model 與取樣鍵，故正常 stock 請求會落到預設 normal，不能只在 `llm.json` 加 priority 就生效。來源：`proto8/templates/agent-fsm/brain.py:194`、`proto8/templates/agent-fsm/llm_settings.py:12`。
- 就程式能力而言，能寄請求者可填 priority；有設定檔／hook 寫入權者可調 aging、reserved、speed，或以 `before_verdict` 改 body。沒有額外角色授權層；實際限制依檔案與信箱權限。來源：`proto8/lib/aos/kernel_llm/README.md:41`、`proto8/lib/aos/kernel_llm/docs/04-已知限制.md:17`。
- **可嵌套 llm kernel，但不是嵌套 priority 結構**：各站自行排序，forward 傳下去的是宣告 level 與有效 deadline，不傳本層 aging 後的級數；沒有父子級權重合成。來源：`proto8/lib/aos/kernel_llm/llm_rules.py:491`、`proto8/lib/aos/llm_forward/_entry:67`。

## 沒找到／不確定

- **部署版本未全面核實**：活樹指定的 loop 已指 Python kernel_llm，但未讀活樹 lib／agent 定義，不能確認 AK17 與所有最新規則已部署。知識庫仍有舊內容，例如 brain 頁未提 AK17、CLI 頁把它描述為 daemon 身體。來源：`/home/lorkhan/aos-home/knowledge/aos/brain.json#/priority`、`/home/lorkhan/aos-home/knowledge/aos/cli/parts/llm_kernel.json`。
- **未確認實際路由與 runtime 帳**：本次只讀指定的三份 llm-gpt 定義檔，未讀各 ok-* 的 gate 設定、環境或 runtime stack；無法證明當前每封請求經過哪些 gate／llm 站。
- **未找到部門額度繼承、未列名 sender 預設配額、分層 priority 或數值金額預算**；現有邊界是單站總量、pack、sender，及額外串接的 llm 站。來源：`proto8/lib/aos/kernel_llm/budget.py:50`、`proto8/lib/aos/kernel_llm/order.py:48`。
- **外部金額帳未知**：未查 LiteLLM 自己的資料庫／log；只能確認 aos 這層的 ledger 與 used 格式，不能斷言外部沒有成本帳。來源：`proto8/lib/aos/kernel_llm/ledger.py:18`。
- **文件有一處矛盾**：token 文件仍寫「不保留格」，但程式已有 `reserved.high`；本報告以實作為準。來源：`proto8/lib/aos/kernel_llm/docs/02-token-回報與額度.md:64`、`proto8/lib/aos/kernel_llm/packs.py:195`。

必讀實際已讀：`_description.json`（最先）、`AGENTS.md`、`common/user.md`、`dispatch/aos-teams.md`、aos-teams 的 06 與 07；全程唯讀，未寫檔、未發 daemon／agent 指令或寄信。