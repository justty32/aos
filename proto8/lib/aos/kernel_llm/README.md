# 問腦總機：通用 kernel 的骨架加問腦專屬那一包，每跑一次做一輪。

`_entry` 把 `llm_rules` 交給 `round.run(pack, cfg_path, name="kernel_llm")`（骨架在 [`../kernel/`](../kernel/README.md)）。一輪做的事：收上一輪掛出去、已經跑完的問腦結果寄回信；再看 `$AOS_STACK/requests/new/` 裡排隊的請求信，照急不急排好，在格數與額度內請 daemon 把每封掛成一個問腦 proc（`llm_<信名>`），然後結束，不等它跑完。由那台 llm daemon 當身體一次次叫。

對外的樣子跟 C++ 的 [`impls/aos-llm-kernel`](../../../impls/aos-llm-kernel/README.md) 相同：`kernel.json` 的寫法、stack 裡每個檔的格式、信與回信的形狀、錯誤代號都不變，那邊的用法文件照樣適用。不同的只有三件：stderr 開頭是 `kernel_llm:`、多了三個 hook 時機、下面「跟 C++ 那支的差別」列的幾處。現在兩支並存，範本還是掛 C++ 那支。

```json
{"exec": {"argv": ["aos-exec", {"$env": "AOS_HOME", "$path": "/lib/aos/kernel_llm"}, {"$env": "AOS_CD", "$path": "kernel.json"}]},
 "interval_ms": 300}
```

用法：`aos-exec <這夾> [--enable-counters] <kernel.json>`。需要 `AOS_STACK` 與 `AOS_DAEMON`。掛問腦 proc 的信寄到 `AOS_KERNEL`（有設的話），沒設才寄 `AOS_DAEMON` 那台的 ctl 信箱；看 proc 跑完沒一律讀 `AOS_DAEMON` 的表。`kernel.json` 沒有 `next`、`count_daemon` 這兩個鍵。起 llm daemon 的殼如果有給一般 proc 用的 `AOS_KERNEL`，要先 `unset`，不然問腦 proc 會被寄到那一站。

## 零件

| 檔案 | 工作 |
|---|---|
| `_entry` | 英文 help、參數、找共用模組、讀設定，呼叫骨架 |
| `llm_rules.py` | 五個口（收成品、收拾與看信、排序、放不放、掛去跑）、回信、撤回、記帳的順序 |
| `packs.py` | 讀 `kernel.json`、能力包（查代號、釘死的參數、交給端點函數的那組）、窗 `endpoints.json` |
| `order.py` | `priority` 與期限、aging、排序與後端黏著、窗 `queue.json` |
| `slots.py` | 總格、high 保留格、包格、後端格與同時幾種包 |
| `budget.py` | 總額、每包、每寄件人的額度，用量帳 `used.json` |
| `ledger.py` | 逐封帳 `ledger.jsonl` |
| `../kernel/runner.py` | 掛 proc、看表收成品、逾時、重掛一次、拔列（通用零件，不是問腦專用） |

## 一輪的順序

1. 讀 `kernel.json`：頂層的格（`slots`、`reserved`、`aging_cycles`、`budget`、`exec`、`endpoint`、`timeout_ms`、`backends`、`hooks`）先解指示詞；`endpoints` 每一組到用的時候才解，解不開只有用那組的信回 `DirectiveBad`，別的信照跑。找 daemon 與掛信信箱。
2. 骨架建信箱、鎖 `requests/.flock`。
3. 收成品：讀 `queue.json`、`used.json`、daemon 的表，寫窗 `endpoints.json`。`cur/` 裡掛出去的每封交給 `runner.settle`：跑完的解讀成回信（成功、合格的錯誤物件原樣、`EndpointFailed`、`ReplyBad`），被收掉或死在半路的重掛一次，第二次還是沒結果回 `EndpointFailed`。有結果的先記 `ledger.jsonl` 與 `used.json`，再跑 `before_reply`，然後寄回信、整封刪。
4. 收拾：`new/`、`tmp/` 裡有 `sender.flock` 而沒人鎖著的信刪掉（寄件人走了）。不算判決，不跑 hook。
5. 看 `new/`：信封讀不懂的直接回 `LetterBad`。其餘交給骨架，信留在 `new/` 不認領。
6. 排序：級數（含 aging）→ 期限 → 同後端黏著 → 包的速度 → 等得久 → 先寄。
7. 逐封：新信先跑 `before_verdict`；驗信；期限已過回 `DeadlineBad`；總額到頂回 `BudgetMissing`（`spent: "wait"` 就整列停下等下一窗）；總格、保留格、包與寄件人的額度、包格、後端格都有空才放行，沒空留在 `new/`。判完跑 `after_verdict`（新信一次；排著的信離開隊時再一次）。
8. 放行的：認領進 `cur/`、寫 `request.json`、寄掛信、寫 `proc.json`；寄不進回 `LaunchFailed`。拒的：認領、回 `{"error": {"code", "msg"}}`、整封刪。
9. 寫 `queue.json`，退 0。

## hooks

寫在 `kernel.json` 的 `hooks`，格的鍵與規則同[框架站](../kernel/README.md#hooks)。問腦這包的差別：

| 事件 | 在問腦上 |
|---|---|
| `before_verdict` | 每封新信一次，在驗信之前。`body` 就是問腦信的 body（`endpoint`、`request`、`priority`）；改過的 body 之後驗信、額度、掛載都照它。退 10 回 `{"error": {"code": "HookRejected", ...}}` |
| `after_verdict` | `verdict` 是 `pass`／`refuse`／`queue`。把沒格的改成 `pass` 就照掛（會超過格數）；把驗不過的信改成 `pass` 沒有包可跑，照原本的錯回信 |
| `before_reply` | 只有掛出去跑過、有結果的信（成功或失敗）在寄回信前跑一次；不用開 `reply_via_me`。`body` 是要寄回去的那份（已拿掉 `child`）；`reply_sender` 是 null。總機自己拒掉的信（`LetterBad`、`BudgetMissing`…）不跑。退 10 改回 `{"error": {"code": "HookRejected", "msg": "reply blocked by hook <名>: <stdout>"}}` |

- 帳在 `before_reply` 之前記，記的是端點函數原本的回話；hook 只改寄出去的那一份。
- `before_reply` 自己失敗（`on_error: stop`）：這輪退 1，信留在 `cur/`、`proc.json` 多一個 `"counted": true`，下一輪從 hook 重來，帳不記第二次。
- 重掛不重跑判決的 hook。
- `before_verdict` 改過、還在排的 body 存 `$AOS_STACK/bodies/<信名>.json`；信離開隊（掛上、拒掉、被撤、寄件人走了）就刪。
- 骨架先排序才跑 `before_verdict`，所以新信第一輪的位置照改之前的 body 排；還在排的下一輪起照改過的 body 排。

## 錯誤代號

自己的錯印 `kernel_llm: error: CODE reason`、退 1：`ArgumentsBad`、`FlagUnknown`、`StackMissing`、`CfgMissing`、`CfgBad`、`DirectiveBad`、`DaemonMissing`、`MailboxMissing`、`CommandMissing`、`PostFailed`、`LockFailed`、`QueueBad`、`UsedBad`、`CounterBad`、`ClockBad`、`StateBad`、`WriteFailed`、`HookFailed`。

回信裡的代號（一封信的錯不是總機的錯，一輪照樣退 0）：`LetterBad`、`RequestBad`、`EndpointMissing`、`EndpointUnknown`、`DirectiveBad`、`CfgBad`、`DeadlineBad`、`BudgetMissing`、`LaunchFailed`、`EndpointFailed`、`ReplyBad`、`HookRejected`，以及端點函數自己回的錯誤物件。

## 跟 C++ 那支的差別

- stderr 開頭 `kernel_llm:`；`--help` 的文字不同。
- 收到 TERM：C++ 做完這一輪才退 128＋N；這支當場結束。在途的狀態都在 stack 裡，下一輪接手。
- 先後：C++ 先找 daemon 才建信箱與上鎖；這支的鎖與建信箱在骨架，`LockFailed` 的訊息是骨架的。`StackMissing`、`CfgBad`、`DaemonMissing` 同時成立時先報哪個不變。
- `kernel.json` 的 `hooks` 壞了是 `CfgBad`（C++ 不認這個鍵）。
- `deadline` 的 ISO 8601 驗得比較嚴：年月日時分秒要寫滿位數。
- daemon 的窗（`procs_state.json`、`state_flux.json`）讀不懂時不印提醒，直接當沒有。
- 每輪多起幾個子行程（`aos-post`、設定裡有指示詞時的 `aos-directive`），一輪比 C++ 慢。

## 測試

`tests/` 的 `test_ledger`、`test_backends`、`test_nesting`、`test_stopped_slot`、`test_two_machines` 是從 C++ 那支搬來的黑箱測試；`test_hooks` 是三個 hook 時機與 `AOS_KERNEL` 的掛信去處。真端點的兩支（`*_live`）還在 `impls/aos-llm-kernel/tests`。

```sh
cd proto8/lib/aos/kernel_llm/tests && python3 -m unittest test_ledger
```
