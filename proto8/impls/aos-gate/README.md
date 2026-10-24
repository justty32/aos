# aos-gate

`aos-gate - 把一張單子寄進 kernel 的信箱，等回信，結果原樣交回`（NAME，C-54 R1）

**一句話：`aos-gate [旗標] 單子.json`——不直接跑那張單子，而是寫成一封信丟進 `$AOS_KERNEL` 信箱的 `new/`，等 kernel（[aos-kernel-llm](../aos-kernel-llm/README.md)）輪到它、跑完回信，再把 stdout、stderr 原樣吐出來、以單子的碼結束。**
叫它的那一格看到的跟直接跑那張單子一樣，不知道有 kernel（C-20）。一個 lib（`lib/libaos-gate.a`，沒有公開標頭）加一支薄命令列（`bin/aos-gate`）。連 aos-kernel-llm 的公開標頭（信箱與信的格式）。全家慣例見 [impls/README.md](../README.md)。

像寄掛號信：你不自己跑一趟，把要辦的事寫好丟進郵筒、站在旁邊等回條；回條來了就照著上面的結果交差。等太久被叫走（收到訊號）就把信從郵筒抽回來；已經在辦的就讓他辦完，回條沒人拿、由郵局清掉。

```sh
cat fsm.json   # think 格不直接跑腦，跑閘門；腦那張單子放在同一格的 brain，加 priority
# "think": {"exec": {"argv": ["aos-gate", {"$env": "AOS_CF", "$path": "#/states/think/brain"}],
#                    "stdout": {"$env": "AOS_STACK", "$path": "plan.txt"}, "timeout_ms": 120000},
#           "brain": {"argv": ["python3", "brain.py"], "priority": "high"}, "next": "act"}
AOS_KERNEL=/path/to/mailbox aos-exec --ws ws agent    # 信箱位置由叫它的人綁（像 AOS_BRAIN_*，P-39）
```

完整例子是 [demo/kernel-llm](../../demo/README.md)；設計與決定見 [thinking 2026-10-24 LLM kernel](../../thinking/2026-10-24-llm-kernel.md)。

## 用法

```
aos-gate [旗標] 單子.json
```

- **命令列**：唯一的位置參數＝單子檔（可寫 `檔#/指標`）；目前沒有旗標。不讀 stdin（單子要 stdin 就自己寫 `stdin` key；沒寫＝kernel 那邊給 `/dev/null`）。
- **`AOS_KERNEL`**：信箱資料夾。沒設、空的、不是資料夾＝`MailboxMissing`（馬上退、不寄）；在的話缺 `tmp/`、`new/` 自己建。
- **寄信**：
  1. `AOS_CF`／`AOS_CD`／`AOS_CO` 設成單子的位置（單子檔的實際路徑、它的資料夾、指標）——同 aos-exec 跑 `檔#/指標` 的單子。
  2. 讀單子、**在閘門的環境解整份指示詞**（＝叫它那一刻的值；`$ref` 從單子檔的資料夾算）。不是物件＝`CfgBad`；解不開＝`DirectiveBad`。
  3. `priority` 先驗（形狀見 aos-kernel-llm），壞＝`PriorityBad`、不寄。
  4. `cwd` 轉絕對：沒寫＝單子檔的資料夾（同 aos-exec），相對的接在它後面。
  5. 信＝`{"inst": 單子, "env": 閘門這一刻的整份環境, "priority": 原樣}`，寫進 `tmp/.<信號>/letter.json`（先建 `sender.lock`、flock 住，拿到行程結束：kernel 靠它認寄信的人還在，10-24 晚改、不看 pid，所以關在沙箱裡也行）再改名進 `new/<信號>/`。
- **等**：每 20 毫秒看一次 `done/<信號>/`（中間收到訊號馬上醒）。**等多久不歸閘門管**：由包它那格的 `timeout_ms` 守（10-15 KISS 1.8）；kernel 不在＝信堆在 `new/`、一直等，kernel 起來就接著做。
  信在 `new/`、`cur/`、`done/` 都找不到（照信走的方向依序看，不會看漏）＝`LetterMissing`。
- **交回**：`stdout.txt` 原樣寫到自己的 stdout、`stderr.txt` 寫到 stderr（單子自己導到別處的就沒有這兩個檔），刪掉 `done/<信號>/`；
  回信 `{"code", "signal"}`＝以那個碼結束（被訊號停掉的單子是 128＋N）；回信 `{"error": {"code", "msg"}}`（kernel 沒跑或跑不起來）＝印一行 `aos-gate: 代號 原因`、退 1；回信讀不懂＝`ReplyBad`。
- **訊號**（SIGINT／SIGTERM／SIGHUP，例如包它那格逾時）：撤信——`new/<信號>` 改名回 `tmp/` 再刪（改得成＝還沒被認領）；已經在 `cur/`（正在跑）就讓它跑完、回信由 kernel 之後清掉；已經在 `done/` 就刪。以 128＋N 結束。

## 元素

```
 main ──▶ block_signals ──▶ parse_cli ──▶ mailbox（$AOS_KERNEL）──▶ post（讀、解、驗 priority、cwd、寄）──▶ wait_reply（輪詢、撤信、relay）
```

| 檔 | 做什麼 |
|---|---|
| `src/send/send.hpp`、`send.cpp` | `mailbox`、`post` |
| `src/wait/wait.hpp`、`wait.cpp` | `wait_reply`（輪詢、`withdraw`、`relay`） |
| `src/common/common.hpp` | `using`；代號沿用 aos-kernel-llm 的 |
| `src/main.cpp` | 命令列：串上面；出錯印「aos-gate: 代號 原因」 |

## 為什麼這樣做

- **指示詞在閘門這邊解、環境整份帶過去**：單子的意思由叫它的那一刻決定，kernel 在哪個資料夾、哪個環境跑都一樣（透明，C-20）。
- **不另設等待上限**：10-15 KISS 1.8 刪了閘門的 `wait_ms`／`QueueTimeout`，排隊算在呼叫者的 `timeout_ms` 裡。
- **信箱不在就馬上錯、在了就一直等**：寫錯 `AOS_KERNEL` 當場看得出來；kernel 暫時不在（重起中）則不算錯。

## 錯誤代號

stderr 一行 **`aos-gate: 代號 原因`**、退 1。

| 代號 | 什麼時候 |
|---|---|
| `ArgumentsBad`、`FlagUnknown`（共用） | 沒給／多給單子檔、不認得的旗標 |
| `MailboxMissing` | 沒設 `AOS_KERNEL`、空的、不是資料夾 |
| `CfgMissing`、`CfgBad`、`DirectiveBad`（共用） | 單子檔不在、指不到；不是 JSON、不是物件；指示詞解不開 |
| `PriorityBad` | priority 寫壞（沒寄） |
| `MkdirFailed`、`WriteFailed`（共用） | 信寫不了、改名不了 |
| `LetterMissing` | 信在信箱裡不見了 |
| `ReplyBad` | 回信讀不懂 |
| kernel 回的：`DeadlineMissed`、`BudgetMissing`（額度用完，10-24 下午）、`LetterBad`、`RunFailed`、`EntryBad`、`DirectiveBad`、`LaunchFailed`、`Internal` | 見 [aos-kernel-llm](../aos-kernel-llm/README.md) |

## 建置與測試

```sh
cmake -B build && cmake --build build && ctest --test-dir build
```

- `test_cli`（`tests/test_cli.py`，unittest 16 案，約 1 秒）：測試自己當 kernel（搬信、寫回信），只測閘門這一半——A 命令列、信箱不在、單子檔的錯、priority 壞不寄；B 信的內容（指示詞在閘門的環境解、`AOS_CF`／`AOS_CD`／`AOS_CO`、cwd 轉絕對、整份環境、priority 原樣、信號照寄的先後）；
  C 交回（stdout／stderr／碼、128＋N、kernel 回的錯、回信讀不懂四種）；D 訊號撤信（在 `new/` 撤掉、在 `cur/` 留著）、信不見了、沒有 kernel 時一直等、等的時候一直鎖著 `sender.lock`（被 SIGKILL 就放掉；改成建了不鎖會紅，10-24 晚實測）。拿掉撤信、拿掉轉 stdout 都會紅（10-24 實測）。
- 跟真 kernel 一起跑的在 `proto8/tests/test_kernel_llm.py`。

## 已知限制

- 輪詢 20 毫秒（N-14「輪詢保底、inotify 加速」，這版只有輪詢）。
- 不轉自己的 stdin。
- 被 SIGKILL 來不及撤信：信留在 `new/`，鎖跟著行程放掉，kernel 下一次看寄信的人不在了會丟掉、不跑。
