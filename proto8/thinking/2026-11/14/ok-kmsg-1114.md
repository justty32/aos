# ok-kmsg 11-14：hook 能回「晚點再試」的拒絕；llm kernel 沒在跑時 listen／say 印一行提示（設計稿與紀錄）

> 線 ok-kmsg（fable eca，部長 head-comm）。來源：使用者 11-14 專區回信 `kernel:now*`；意見出處 `wf/advices/kernel與額度.md` 的兩條。
> 狀態：**已交件**（d6a564191 程式與測試、e6c1d8c0e 意見改已解）；第一、二節是 v1，與第五節不同處以第五節（v2 定稿）為準。

## 〇、已對好的介面（ok-astra，commit 313ce20ec）

- BudgetMissing 的 error 帶 `code`、`msg`、`scope`、`window`、`since`、`resets_at`、`limit`、`max`（另有 `endpoint`／`key`）。
- 程式真的會讀的只有：`wait.py` 讀 `code`、`msg`、`window`（只看是不是 `all`）、`resets_at`（ISO 8601 帶時區才算數）；`brain_notify` 讀 `window`、`resets_at`。其餘只給人看。
- `resets_at` 在未來＝冷卻到 `resets_at+5 s`（至少 30 s）；剛過 60 s 內＝30 s；沒有或解不開＝AK17 間隔表（30 s 起加倍、30 分鐘封頂）；`window: "all"`＝agent 停下（退 1）。
- C++ 的 `impls/aos-llm-kernel` 沒有這些欄位（ok-astra 沒碰）。

## 一、第 1 題：hook 回「晚點再試」

### 現況（讀碼）

- `after_verdict` hook 已經做得到：stdout 回 `{"verdict":"refuse","error":{"code":"BudgetMissing","msg":"…","resets_at":"…"}}`，`code`、`msg` 以外的鍵原樣帶進回信（`lib/aos/kernel/hooks.py` after_verdict 尾段）。kernel、`wait.py` 都不用改。
- `before_verdict` 退 10 做不到：`hooks.rejected()` 寫死回 `("HookRejected", stdout 文字)`；`round.py` 用 `pack.refuse(ctx, 名, 信, *hooks.rejected(result))` 回信。三個包的 `refuse()` 都已收第三個參數 `extra`。
- 被擋時 `result["text"]`＝那個 hook 的 stdout（`lib/hook_run.py:221`）。

### 設計

1. **代號沿用 `BudgetMissing`**（ok-astra 建議、head-comm 同意）：意思放寬成「額度或 hook 叫你晚點再試」。好處是 `wait.py`、`cooldown.py`、`brain_notify` 一行都不用改。
2. **只改 `hooks.rejected()`**（`round.py` 那一行靠 `*` 展開，不必動）：
   - hook 退 10 而 stdout 去空白後是一個 JSON 物件、裡面 `error` 是物件、`error.code` 和 `error.msg` 都是字串、`code` 在白名單 `{"BudgetMissing", "HookRejected"}` → 回 `(code, msg, extra)`。`extra`＝`error` 裡其餘的鍵，再補 `scope`（hook 沒給才補 `"hook"`）與 `hook`（一律寫成攔下的 hook 名）。
   - `code` 不在白名單 → 仍回 `HookRejected`，`msg` 用 `error.msg`，其餘鍵照帶，並 `ctx.warn` 一行（英文）說代號不被接受。
   - 其他情形（不是 JSON、不是物件、沒有合格的 `error`）→ 跟現在完全一樣：`("HookRejected", 文字或 "blocked by hook <名>")`。
   - `code` 是 `BudgetMissing` 時只驗型別：`resets_at` 要是字串或 null、`window` 要是字串；型別不對就丟掉那個鍵並 warn（時間格式不在 kernel 驗，`wait.py` 本來就容錯）。
3. **hook 作者的三種寫法**（寫進文件）：
   - 給 `resets_at`（ISO 8601 帶時區）＝agent 冷卻到那時再寄同一封。
   - 不給 `resets_at`、不給 `window`＝agent 照 AK17 間隔表自己重試。
   - 給 `"window": "all"`＝agent 停下等人。
4. **`before_reply` 被擋**不變（仍是 HookRejected）。
5. **`hooks.py` 是掛 proc 的 kernel 和問腦的 kernel 共用的**，所以兩種站都得到這個能力；掛 proc 那邊的寄信人（`subagent`、`agents_ctl`）目前只把 error 印出來，不會自動重試——不在這條線範圍，文件註明。
6. **C++ 版不動**：待蒐集確認 C++ 版沒有 hook 這條路（有的話再議）。
7. **範例 hook**：在 `lib/aos/kernel_llm/docs` 加一段十行以內的 sh／python 範例（部門配額用完→退 10、印 BudgetMissing＋resets_at）。

### 測試（新檔，不改既有測試）

- `lib/aos/kernel/tests/test_hook_retry_later.py`：(a) JSON＋BudgetMissing＋resets_at → 回信 error 有 code、msg、resets_at、scope=hook、hook=名；(b) 純文字 → 跟舊行為逐字相同；(c) 白名單外的 code → HookRejected＋warning；(d) 壞 JSON、JSON 陣列、缺 msg → 舊行為；(e) resets_at 型別不對 → 鍵被丟。
- `lib/aos/kernel_llm/tests/test_hook_retry_later.py`：問腦的站 before_verdict 與 after_verdict 兩條路各一例，看回信。
- `templates/tests/agent-fsm/`：加一例「error 只有 code、msg、resets_at、scope=hook、hook」→ 記冷卻到 resets_at、退 10（證明 wait.py 不用改）。

## 二、第 2 題：kernel 沒在跑時要看得到一行提示

### 現況（讀碼）

- agent-fsm 等腦時，stack 裡有 `think/pending.txt`（內容＝寄給 kernel 的信名）。
- 「kernel 有沒有在跑」`aos-llm` 已經會判：看 kernel stack 的 `state.json`——沒有＝那裡沒有 daemon；`phase` 不是 running／waiting／stopping 或 `pid` 不在＝停了（`impls/aos-llm/src/send/send.cpp` idle_reason）。但 `wait.py` 用 `aos-llm recv --quiet`，這行被關掉；寄信時那行 warning 只進 agent 自己的 `stderr.txt`。
- `wait.py` 每滿 10 分鐘的警告也只進 `stderr.txt`。
- `aos-agent listen` 是外人：只看得到 agent 的 stack，不知道 agent 的 `AOS_LLM_KERNEL` 指到哪。逾時只回 `AnswerMissing waited N s; … not answered yet`。
- kernel 的 `.flock` 只在一輪之內拿著，不能當「在跑」的依據。

### 設計

1. **agent 把「我在等哪個 kernel」留在 stack 裡**：`wait.py` 寄出請求、寫 `think/pending.txt` 的同一步，另寫 `think/brain_wait.json`：`{"letter": "<信名>", "kernel": "<kernel stack 絕對路徑>", "sent_at": "<ISO>"}`；刪 `pending.txt` 的每一處一併刪它。兩種寄不出去的情形也寫（`letter` 是 null、多一個 `problem`）：`AOS_LLM_KERNEL` 沒設（LlmKernelMissing）、解不到資料夾（SendFailed＋KERNEL_GONE 冷卻）。寫不成只 warning，不改原本結果。
2. **`aos_agent/hints.py` 新函式 `brain_hint(a)`**（獨立、只讀、任何讀檔錯誤都回 None、不丟例外）：
   - 沒有 `think/brain_wait.json` → None（舊 agent、eca 身、沒在等腦：安靜）。
   - 有 `problem` → 回那句。
   - 否則照 `aos-llm` 同一套規則看 `<kernel>/state.json`；kernel 在跑 → None；沒在跑 → 回一句英文：
     `NAME is waiting for its brain, but the llm kernel at KERNEL is not running (WHY); start it (see the daemon-root README: the llms project next to this one), or set AOS_LLM_KERNEL to the right stack and add NAME again`
3. **`listen.py` 的 `wait_latest()`**：每秒那次檢查裡多呼叫一次 `brain_hint(a)`，有話且還沒印過就 `note(話 + ". Still waiting, Ctrl-C to leave")`（每次等待只印一次）；逾時的 `AnswerMissing` 原因後面接 `; ` 加同一句。不碰 `latest()`、`print_answer()`、`handed_unanswered()`（跟 ok-pilot 約好的）。`ask`、`chat` 走同一個 `wait_latest`，自動涵蓋。
4. **`say.py`**：寄完後呼叫一次 `brain_hint(a)`，有話就 `note`（agent 早就卡在等腦時，寄話的人當下就看得到）。
5. **工具層**（`subagent` 的 ask／listen、`mailbox_send`）：待蒐集確認它們是不是經 `aos-agent`；是就自動涵蓋，不是就在設計 v2 補。`mailbox_send` 不加（信箱不經腦，收信人可能是 eca）。
6. **不做**：`aos-daemon-ctl ls` 的 REASON 欄標「等腦」（意見的第 2 案）——要動 daemon 寫 state 的路，留給別線。kernel 在跑但信排很久（slot 滿、額度 wait）不提示，那是正常排隊，10 分鐘警告照舊。
7. **生效時點**：`listen.py`／`hints.py`／`say.py` 在 `proto8/cmd`，存檔即活樹生效——照「先寫暫存檔、改名、立刻 import＋定向測試」做，新函式對沒有 `brain_wait.json` 的 agent 完全安靜。`wait.py` 是範本，活樹用的是複本，等換樹（寄 ok-kf 排進步驟表）才生效；換樹前活樹的 listen 行為不變。

### 測試（新檔）

- `cmd/aos-agent/tests/test_brain_hint.py`：假 stack＋假 kernel stack——沒檔安靜；kernel 沒 state.json／phase stopped／pid 不在各印對應一句；kernel 在跑安靜；`problem` 原樣；壞 JSON 安靜；listen 逾時訊息帶提示；say 之後印提示。
- `templates/tests/agent-fsm/test_brain_wait_file.py`：寄出時寫檔、收到回信／拒絕／信不見重寄時刪檔、兩種寄不出去的情形寫 `problem`。

## 三、會動的檔

| 檔 | 題 | 活樹即時生效？ |
|---|---|---|
| `proto8/lib/aos/kernel/hooks.py` | 1 | 否（lib 是複本） |
| `proto8/lib/aos/kernel/tests/test_hook_retry_later.py`、`kernel_llm/tests/test_hook_retry_later.py`（新） | 1 | — |
| `proto8/templates/agent-fsm/wait.py` | 2 | 否（範本複本） |
| `proto8/cmd/aos-agent/aos_agent/hints.py`、`listen.py`、`say.py` | 2 | **是** |
| `proto8/cmd/aos-agent/tests/test_brain_hint.py`、`templates/tests/agent-fsm/` 兩支（新） | 1、2 | — |
| 文件：`lib/aos/kernel/README.md`、`kernel_llm/README.md` 與 docs/01（hooks 表）、`templates/agent-fsm/README.md`、`cmd/aos-agent/README.md`、`templates/daemon-root/README.md`、`knowledge/aos` 相關條 | 1、2 | — |

不碰：`kernel_llm/docs/02-token-回報與額度.md`（別線排隊）、`llm_rules.py`、`cooldown.py`、`aos-llm`（線雜 T20）、C++。

## 四、紀錄

- 13:15 開工核對；寄 ok-astra 對介面。13:17 ok-astra 回：欄位定稿、313ce20ec。
- 13:13 掛 ok-kmsg-sol-1／-2（kits/gather）做唯讀蒐集；13:40 尚未交稿，設計稿 v1 先依自己讀碼寫。
- 13:25 分層：部長 head-comm。13:36 回 head-tools：listen.py 只加提示、不碰取回答邏輯，目標 16:30 前交件。

## 五、Argon 審 v1 的採納表（原文 [01-Argon審v1](ok-kmsg-1114/01-Argon審v1.md)）＝v2 定稿

| # | Argon 說 | 採不採 | v2 怎麼做 |
|---|---|---|---|
| A1 | `rejected()` 拿不到 `ctx.warn` | 採（換做法） | v2 完全不 warn：認不得的 stdout 一律走舊行為，所以 `rejected(result)` 簽名不變、`round.py` 不動 |
| A2 | after_verdict 兩條路沒講清 | 採 | 退 10（before_verdict、after_verdict 都經 `rejected()`）＝新規則、自動補 `scope`／`hook`；after_verdict 退 0 改判＝照 313ce20ec 原樣，欄位 hook 自己給，不補不驗。測試照這個分 |
| A3、A4、B1 | `brain_wait.json` 會殘留、要原子寫、要跟 pending 對 | 採 B1 | 只在寄出成功時原子寫 `{"letter","kernel"}`；不寫 `problem`；**不必刪**——`brain_hint` 要 `think/pending.txt` 的信名等於 `letter` 才採信 |
| A5 | 會誤報、刷屏、pid 判法、read_window 會吵、回信已到 | 全採 | 見下「第 2 題 v2」 |
| A6、B2 | 舊 hook 的 stdout 恰是 JSON 會變樣 | 採 | 只認 `error.code == "BudgetMissing"`；其他任何 stdout（含別的 JSON）跟現在逐字相同 |
| A7.1 | hook 可偽造 scope 等 | 採 | `scope`、`hook` 強制覆寫；額外鍵只放行 `resets_at` |
| A7.2 | `window: "all"` 會讓 agent 不帶冷卻退 1，auto_restart 下連續重試 | 採 | hook 給的 `window` 一律不帶進回信；要 agent 停下＝照舊印純文字（HookRejected） |
| A7.3 | `kernel_dir()` 沒 strip | 不採 | 既有行為、不在本線範圍；記一條意見稿 |
| A8 | 上線順序 | 採 | 先 `hints.py`（暫存檔→`os.replace`→import 測）→ 再 `listen.py`、`say.py` |
| A9 | 測試缺口 | 採 | 併入下列測試 |

### 第 1 題 v2（`lib/aos/kernel/hooks.py` 的 `rejected(result)`，約 15 行）

```
text = result["text"].strip()
若 text 解成 JSON 物件 d，且 d["error"] 是物件 e，且 e["code"] == "BudgetMissing"，且 e["msg"] 是非空字串，
  且（"resets_at" 不在 e，或 e["resets_at"] 是 None 或字串）：
    extra = {"scope": "hook", "hook": result["hook"]}
    "resets_at" 在 e → extra["resets_at"] = e["resets_at"]
    回 ("BudgetMissing", e["msg"], extra)
其他：回 ("HookRejected", text or "blocked by hook %s" % result["hook"])      ← 跟現在一樣
```

- hook 作者兩種寫法：給 `resets_at`（ISO 8601 帶時區）＝agent 冷卻到那時；不給或給 null＝agent 照間隔表（30 秒起加倍、30 分鐘封頂）重試。要 agent 停＝純文字。
- 測試 `lib/aos/kernel/tests/test_hook_retry_later.py`：帶 resets_at／不帶／null；`scope`、`hook`、`window`、`limit` 被 hook 偽造→覆寫或丟掉；純文字、空 stdout、別的 code 的 JSON、JSON 陣列、缺 msg、resets_at 是數字 → 逐字舊行為；after_verdict 退 10 同規則；after_verdict 退 0 改判帶 BudgetMissing＋resets_at 原樣進回信。`kernel_llm/tests/test_hook_retry_later.py`：問腦的站 before_verdict 一例、after_verdict 退 0 一例。agent-fsm 一例：error 只有 code、msg、resets_at、scope、hook → 冷卻到 resets_at。

### 第 2 題 v2

- `wait.py`：`write_atomic(pending, …)` 成功後，原子寫 `think/brain_wait.json`＝`{"letter": 信名, "kernel": kernel stack 絕對路徑}`（`kernel_dir()` 是 None 就不寫；寫不成只 warning）。其他地方不動、不刪。
- `hints.py` 新函式 `brain_hint(a)`，回一句話或 None；全程只讀、任何例外回 None：
  1. `a.phase == "running"` 且 `label(a) == "running"`，否則 None（停、睡、暫停已有別的提示）。
  2. 讀 `think/pending.txt` 得信名；讀 `think/brain_wait.json`（直接 open＋json.load）；`letter` 不等於信名 → None。
  3. `think/reply/new/<信名>` 或 `think/reply/cur/<信名>` 在（回信到了）→ None。… 回信的信名不同於請求信名時這條無效，施工時照 `aos-llm recv` 的找法對；找不到簡單判法就略過這條。
  4. 看 `<kernel>/state.json`：檔不在（FileNotFoundError）＝`no llm daemon there (no state.json)`；讀到物件而 `phase` 不在 running／waiting／stopping，或 `pid` 不是正整數（bool 不算），或 `os.kill(pid, 0)` 丟 ProcessLookupError ＝`the llm daemon is not running (phase X[, pid gone])`；PermissionError＝活著；壞 JSON、其他錯＝None。
  5. 句子：`NAME is waiting for its brain, but the llm kernel at KERNEL is not running (WHY); start that llm kernel, or if AOS_LLM_KERNEL points to the wrong place, add NAME again with the right one`
- 另一種情形（kernel 資料夾根本不在）：agent 的 `cooldown.json`（用 `cooldown.read`）code 是 `SendFailed` 且 reason 含 `(llm kernel folder not found)`，且 agent 在跑 → 句子 `NAME cannot reach its brain: REASON; it retries by itself when the folder appears`。`AOS_LLM_KERNEL` 沒設＝agent 已停、表上有 reason，現有 `run_hint` 會說，不另做。
- `listen.py`：獨立旗標 `brain_warned`（不共用 `warned`），在兩處每秒檢查點各呼叫一次、只印一次；逾時的 AnswerMissing 尾巴接 `; ` 加同一句（當下 `brain_hint` 有話才接）。
- `say.py`：寄完、現有兩句提示都沒印時，呼叫一次 `brain_hint`。
- 測試：v1 列的加上 phase waiting／stopping 不報、EPERM 不報（mock `os.kill`）、pid 是 True／0／負數、agent 暫停或停著不報、pending 信名對不上不報、cooldown 那一型。

## 六、施工與驗收（11-14 下午）

- 暫存樹 `~/code/ok-kmsg-1114/src`（git archive accea11a3）：ok-kmsg-sol-3 做第 1 題、ok-kmsg-sol-4 做第 2 題（定義 `wf/temp/ok-kmsg/defs/build`＝gather 包加 shell）。蒐集員 sol-1、sol-2 因 sol 名額緊（全體 3）中途停掉，設計靠隊長自己讀碼。
- 驗收：隊長讀 diff、重跑新測試；補一處（`json.loads` 另接 `RecursionError`）。查到 `subagent` 工具的 ask／listen 是呼叫 `aos-agent listen`（`lib/agent/subagent/_entry:234-239`），自動涵蓋，不用改。
- 整合複本 `~/code/ok-kmsg-1114/rel2`（git archive c2eced25c，含 ok-fsm 的 wait.py 改動 3b02a41c4；三方合併無衝突）整夾：kernel 122 OK、kernel_llm 61 OK、aos-agent 145 OK（expected failures=2，原有）、agent-fsm 152 OK。
- 紅綠：`rejected()` 改回舊版 → `test_hook_retry_later` 8 例 FAIL；拿掉 listen 兩個呼叫 → `test_brain_hint` 2 例 FAIL。
- 生效：`hints.py`、`listen.py`、`say.py` 存檔即活樹生效（沒有 `brain_wait.json` 的 agent 完全安靜）；`hooks.py`、`wait.py` 等換樹。
- 還欠：`cmd/aos-agent/README.md`、`templates/agent-fsm/README.md` 各一兩句（別線 claim 中，之後補）。

## 七、交件與收尾（11-14 14:20～14:40）

- 接上活樹（head-comm 放行）：`cmd/aos-agent/aos_agent` 的 `hints.py` → `listen.py`、`say.py`，寫暫存檔再改名，備份在 `~/code/ok-kmsg-1114/backup-live/`；repo 工作樹定向測試 42 OK；暫存樹 `~/code/ok-kmsg-1114/e2e2` 起自己的 daemon＋假 agent 實跑 say／listen／ask，stderr 全空。
- commit：d6a564191（程式、5 支新測試、三份 README、本紀錄）；e6c1d8c0e（`wf/advices/kernel與額度.md` 兩條改已解、README 計數 20／4／14）。d6a564191 的 git archive 複本四夾：kernel 122、kernel_llm 61、aos-agent 145（expected failures=2，既有）、agent-fsm 152，全 OK。
- 換樹：ok-kf 把 d6a564191 排進 11-14 晚換樹第 3 步（`hooks.py`、`wait.py` 隨 lib、templates 整夾換）；換後驗＝第一隻 agent-fsm 問過腦後 stack 出現 `think/brain_wait.json`。
- 對口：ok-astra（欄位介面）、ok-fsm（`wait.py` 先後，它的 3b02a41c4 先進）、ok-sec（Q10 也動 `wait.py`，不重疊）、ok-pilot（`listen.py` 之後改取回答的邏輯，保留 `say_brain()`／`timeout_reason()`）、ok-release（範本改了）。另審了 ok-fsm 的 `session_key` 補丁：不打架。
- 收隊：四隻 sol 都 `subagent rm`（stack 留著）；自己起的兩台暫存 daemon 用記下的 pid 收掉；沒刪檔。`pgrep -af aos-daemon` 裡 cmdline 是活樹 daemon.json、pid 會換的那些是活樹 daemon 替每隻 agent-fsm fork 的看顧行程（看 PPID 分辨），不是異常。
- 後補：`cmd/aos-agent/README.md` 兩句（ok-limits 放 claim 後補）；`templates/agent-fsm/README.md` 一列（ok-astra claim 中，等回音）。
- 沒做、留給別線：`aos-daemon-ctl ls` 的 REASON 標「等腦」；掛 proc 的寄信人收到 BudgetMissing 自動重試；`wait.py` 的 `kernel_dir()` 沒對 `AOS_LLM_KERNEL` 去空白（Argon A7.3）。
